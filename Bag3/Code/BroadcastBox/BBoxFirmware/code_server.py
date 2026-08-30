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
CHUNK = 512
YIELD_MS = 20
SOCK_REPLY_TIMEOUT_S = 30

FS_ROOT = '/flash'
DEFAULT_SRC = FS_ROOT + '/payload.py'
DEFAULT_DEST = 'jumpin.py'


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

    @property
    def armed(self):
        return self._armed

    @property
    def serving(self):
        return self._serving

    @property
    def last_ok(self):
        return self._last_ok

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
        self._armed = False
        self._serving = False
        gc.collect()

    def poll(self):
        """Non-blocking: accept one client and serve one file. Returns state str or None."""
        if not self._armed or self._srv is None:
            return None
        if self._client is not None:
            return 'serving'
        try:
            cs, _ = self._srv.accept()
        except OSError:
            return None
        self._client = cs
        self._serving = True
        ok = self._serve_client(cs)
        self._last_ok = ok
        self._close_client()
        self._serving = False
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

    def _serve_client(self, cs):
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
            reply = cs.read(2)
            ok = (reply == b'OK')
            sleep_ms(100)
        except OSError:
            ok = False
        return ok
