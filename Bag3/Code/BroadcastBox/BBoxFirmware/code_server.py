"""
code_server.py — SoftAP + TCP file server (non-blocking arm/poll).

Split from BBoxPrototype/s3_sender.py so the UI loop can coexist with
accept(). Wire protocol unchanged.
"""

import gc
import os
import socket
import network
from time import sleep_ms

try:
    import hashlib
except ImportError:
    import uhashlib as hashlib

SSID = 'SP-FILEPUSH'
PWD = 'playground1'
PORT = 8266
AP_CHANNEL = 1
CHUNK = 512
YIELD_MS = 20
SOCK_REPLY_TIMEOUT_S = 30
AP_SETTLE_MS = 300  # same value the wand uses post-cycle

FS_ROOT = '/flash'
DEFAULT_SRC = FS_ROOT + '/payload.py'
DEFAULT_DEST = 'jumpin.py'


def _emit(cb, event):
    """Fire a caller callback without letting it break the server.

    Mirrors how the wand guards its own on_progress hook: a UI paint that
    throws must not abort a transfer or take down the main loop.
    """
    if cb is None:
        return
    try:
        cb(event)
    except Exception as e:
        print("# code_server on_event(%s) err: %s" % (event, str(e)))


def _asked_to_abort(cb):
    """True only if the caller's should_abort() clearly said so.

    A callback that raises is treated as "keep going": dropping a transfer
    because a button read glitched would be worse than finishing it.
    """
    if cb is None:
        return False
    try:
        return bool(cb())
    except Exception as e:
        print("# code_server should_abort err: %s" % str(e))
        return False


def _hash_file(path):
    h = hashlib.sha256()
    buf = bytearray(CHUNK)
    mv = memoryview(buf)
    with open(path, 'rb') as f:
        while True:
            n = f.readinto(buf)
            if not n:
                break
            h.update(mv[:n])
    return h.digest()


def _start_ap(ssid=SSID, pwd=PWD):
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap.config(essid=ssid, password=pwd, authmode=network.AUTH_WPA_WPA2_PSK)
    except (ValueError, OSError):
        ap.config(essid=ssid, password=pwd, security=3)
    # Pin the channel rather than taking the port default. A radio has one
    # channel, so the wand can only associate here after tearing ESP-NOW
    # down, and an idle ESP-NOW radio sits on channel 1 -- landing on the
    # same channel means the wand never has to change channel to join.
    # Staying in 1-11 also keeps this reachable regardless of the wand's
    # regulatory domain: 12-14 are restricted in some regions, and a station
    # that is restricted can still see the AP in a scan while being unable
    # to associate with it.
    try:
        ap.config(channel=AP_CHANNEL)
    except (ValueError, OSError):
        pass
    try:
        ap.config(pm=0)
    except (ValueError, OSError, AttributeError):
        pass
    while not ap.active():
        sleep_ms(100)
    return ap


class CodeServer:
    def __init__(self, src_path=DEFAULT_SRC, dest_name=DEFAULT_DEST,
                 port=PORT, ssid=SSID, pwd=PWD):
        self.src_path = src_path
        self.dest_name = dest_name
        self.port = port
        self.ssid = ssid
        self.pwd = pwd
        self._ap = None
        self._srv = None
        self._client = None
        self._armed = False
        self._serving = False
        self._last_ok = None
        self._pickups = 0

    @property
    def armed(self):
        return self._armed

    @property
    def serving(self):
        return self._serving

    @property
    def last_ok(self):
        return self._last_ok

    @property
    def pickups(self):
        """Completed successful serves this session."""
        return self._pickups

    def arm(self):
        if self._armed:
            return True
        if not self._file_ready():
            return False
        self._ap = _start_ap(self.ssid, self.pwd)
        self._srv = socket.socket()
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(('0.0.0.0', self.port))
        self._srv.listen(1)
        self._srv.settimeout(0)
        self._armed = True
        self._last_ok = None
        return True

    def disarm(self):
        self._close_client()
        if self._srv is not None:
            try:
                self._srv.close()
            except OSError:
                pass
            self._srv = None
        if self._ap is not None:
            try:
                self._ap.active(False)
            except OSError:
                pass
            self._ap = None
            sleep_ms(AP_SETTLE_MS)
        self._armed = False
        self._serving = False
        gc.collect()

    def poll(self, on_event=None, should_abort=None):
        """Non-blocking: accept one client and serve one file. Returns state str or None.

        on_event('serving') fires before the blocking serve, so a caller can
        paint a "serving" screen before the transfer starts. It replaces the
        old 'serving' return value, which was unreachable: _client is always
        cleared before poll() returns, so the branch testing it never ran. should_abort() is
        sampled between chunks during the transfer; a True return closes the
        client and returns 'abort' without promoting or acking. An aborted
        transfer is safe on the wand side -- it sees a short read or hash
        mismatch, removes its .part file, does not promote, and retries within
        its own budget.
        """
        if not self._armed or self._srv is None:
            return None
        try:
            cs, _ = self._srv.accept()
        except OSError:
            return None
        self._client = cs
        self._serving = True
        _emit(on_event, 'serving')
        result = self._serve_client(cs, should_abort=should_abort)
        self._close_client()
        self._serving = False
        if result == 'abort':
            # Not a completed transfer -- leave no stale success behind.
            self._last_ok = None
            return 'abort'
        ok = result
        self._last_ok = ok
        if ok:
            self._pickups += 1
        return 'ok' if ok else 'fail'

    def _file_ready(self):
        try:
            return os.stat(self.src_path)[6] > 0
        except OSError:
            return False

    def _close_client(self):
        if self._client is not None:
            try:
                self._client.close()
            except OSError:
                pass
            self._client = None

    def _serve_client(self, cs, should_abort=None):
        name_bytes = self.dest_name.encode('utf-8')
        if len(name_bytes) > 255:
            return False
        size = os.stat(self.src_path)[6]
        digest = _hash_file(self.src_path)
        ok = False
        try:
            cs.settimeout(SOCK_REPLY_TIMEOUT_S)
            cs.write(size.to_bytes(4, 'big'))
            cs.write(digest)
            cs.write(bytes([len(name_bytes)]))
            cs.write(name_bytes)
            buf = bytearray(CHUNK)
            mv = memoryview(buf)
            with open(self.src_path, 'rb') as f:
                while True:
                    n = f.readinto(buf)
                    if not n:
                        break
                    cs.write(mv[:n])
                    sleep_ms(YIELD_MS)
                    if _asked_to_abort(should_abort):
                        return 'abort'
            reply = cs.read(2)
            ok = (reply == b'OK')
            sleep_ms(100)
        except OSError:
            ok = False
        return ok
