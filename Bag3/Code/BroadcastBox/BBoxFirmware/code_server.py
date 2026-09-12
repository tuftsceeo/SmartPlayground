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
SOCK_REQUEST_TIMEOUT_S = 5   # how long to wait for the requester's frame
AP_SETTLE_MS = 300  # same value the wand uses post-cycle

# PEER: MockWand/code_puller.py and BroadcastBox/IconDisplay/code_puller.py
# each hold a hand-kept copy of SSID/PWD/PORT/CHUNK/YIELD_MS and of the wire
# protocol in _serve_client() below. There is no shared module (they run on
# different devices), so any change here must be mirrored in both in the same
# commit.

# Request-frame version sentinel. A v1 request opens with the slug's length,
# capped at 16 by the slug rule, so a first byte of 0xFF cannot be one. That
# is what lets this serve an un-updated wand and a hubtype-aware device from
# the same socket.
#
#   v1:  len(1) | slug                          -> always the wand file
#   v2:  0xFF | len(1) | slug | len(1) | hubtype
REQ_V2 = 0xFF

# Which file each kind of device gets for a slug, and whether it also takes
# the icon leg. A hubtype absent from here is refused rather than guessed at:
# handing a device a file written for different hardware is worse than
# telling it plainly that there is nothing for it.
#   suffix  -- appended to the slug for this role's source file
#   icons   -- send the named-icon leg after the game file
ROLE_FILES = {
    'wand':         {'suffix': '',      'icons': False},
    'icon_display': {'suffix': '_icon', 'icons': True},
}
DEFAULT_ROLE = 'wand'   # what a v1 request, which names no hubtype, gets

MAX_ICONS = 64

FS_ROOT = '/flash'
DEFAULT_SRC = FS_ROOT + '/payload.py'
DEFAULT_DEST = 'jumpin.py'
GAMES_DIR = FS_ROOT + '/games'
ACTIVE_PATH = FS_ROOT + '/active.txt'


def icons_dir_for(slug):
    """Where a game's named icons live on the Box.

    ChatBroadcast writes them here in the same raw-REPL session as the game
    files, so a pull can serve a game and its pictures without a second trip.
    """
    return GAMES_DIR + '/' + slug + '_icons'


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
        self.active_slug = None
        self.role = DEFAULT_ROLE
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

    def set_game(self, slug, src_path=None, role=DEFAULT_ROLE):
        """Point the server at a slug's source file for one device role.

        The file on the Box carries the role's suffix (<slug>_icon.py for an
        icon display); the name it lands under on the device does not. Every
        device holds at most one module per slug, so the role lives here and
        in ChatBroadcast, never on the device's flash.
        """
        if not slug:
            self.active_slug = None
            self.role = DEFAULT_ROLE
            self.src_path = DEFAULT_SRC
            self.dest_name = DEFAULT_DEST
            return
        suffix = ROLE_FILES.get(role, ROLE_FILES[DEFAULT_ROLE])['suffix']
        self.active_slug = slug
        self.role = role
        self.src_path = src_path if src_path else (GAMES_DIR + '/' + slug + suffix + '.py')
        self.dest_name = slug + '.py'

    def resolve(self, slug=None, role=DEFAULT_ROLE):
        """Resolve slug (or /flash/active.txt) into src_path/dest_name.

        Returns the slug used, or None if nothing is serveable for this role.
        An unknown role resolves to nothing at all, so the requester gets the
        explicit zero-size refusal rather than a wand file it cannot run.
        """
        if role not in ROLE_FILES:
            return None
        if slug:
            suffix = ROLE_FILES[role]['suffix']
            path = GAMES_DIR + '/' + slug + suffix + '.py'
            try:
                if os.stat(path)[6] > 0:
                    self.set_game(slug, path, role)
                    return slug
            except OSError:
                return None
            return None
        try:
            with open(ACTIVE_PATH, 'r') as f:
                active = f.read().strip()
        except OSError:
            active = ''
        if active:
            return self.resolve(active, role)
        return None

    def arm(self):
        if self._armed:
            return True
        # Prefer active game; fall back to whatever src_path already is.
        if not self._file_ready():
            if self.resolve() is None or not self._file_ready():
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
        try:
            import stats_log
            stats_log.record_pull(self.active_slug or '?', ok)
        except Exception as e:
            print("# stats pull failed: %s" % str(e))
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

    def _read_str(self, cs):
        """Read one length-prefixed UTF-8 field: 1 byte length + that many bytes.

        Returns the string ('' for a zero length), or None if the socket ran
        out. read() may come back short on a stream socket, so this loops.
        """
        head = cs.read(1)
        if not head:
            return None
        n = head[0]
        if n == 0:
            return ''
        body = bytearray()
        while len(body) < n:
            part = cs.read(n - len(body))
            if not part:
                return None
            body.extend(part)
        return bytes(body).decode('utf-8')

    def _read_request(self, cs):
        """Read the requester's opening frame. See REQ_V2 for both shapes.

        Returns (slug, role) -- slug '' means "serve whatever is active" --
        or None if nothing usable arrived. A v1 frame names no hubtype and
        gets DEFAULT_ROLE, which is what keeps an un-updated wand working.
        The requester speaks first, so this must happen before any of the
        response bytes are written.
        """
        try:
            cs.settimeout(SOCK_REQUEST_TIMEOUT_S)
            head = cs.read(1)
            if not head:
                return None
            if head[0] != REQ_V2:
                # v1: the byte just read is the slug length.
                n = head[0]
                if n == 0:
                    return '', DEFAULT_ROLE
                body = bytearray()
                while len(body) < n:
                    part = cs.read(n - len(body))
                    if not part:
                        return None
                    body.extend(part)
                return bytes(body).decode('utf-8'), DEFAULT_ROLE
            slug = self._read_str(cs)
            if slug is None:
                return None
            role = self._read_str(cs)
            if role is None:
                return None
            return slug, (role or DEFAULT_ROLE)
        except (OSError, UnicodeError, ValueError):
            return None

    def _refuse(self, cs):
        """Answer a zero size: "nothing here for you".

        Said plainly rather than by dropping the connection, so the requester
        can show a real error instead of waiting out its socket timeout.
        """
        try:
            cs.settimeout(SOCK_REPLY_TIMEOUT_S)
            cs.write((0).to_bytes(4, 'big'))
        except OSError:
            pass

    def _send_file(self, cs, src_path, dest_name, should_abort=None):
        """Send one file: header, body, then read the 2-byte ack.

        Returns True on b'OK', 'abort' if should_abort() fired mid-body, and
        False otherwise. Shared by the game file and every icon so the two
        legs cannot drift apart.
        """
        name_bytes = dest_name.encode('utf-8')
        if len(name_bytes) > 255:
            return False
        size = os.stat(src_path)[6]
        digest = _hash_file(src_path)
        cs.settimeout(SOCK_REPLY_TIMEOUT_S)
        cs.write(size.to_bytes(4, 'big'))
        cs.write(digest)
        cs.write(bytes([len(name_bytes)]))
        cs.write(name_bytes)
        buf = bytearray(CHUNK)
        mv = memoryview(buf)
        with open(src_path, 'rb') as f:
            while True:
                n = f.readinto(buf)
                if not n:
                    break
                cs.write(mv[:n])
                sleep_ms(YIELD_MS)
                if _asked_to_abort(should_abort):
                    return 'abort'
        reply = cs.read(2)
        sleep_ms(100)
        return reply == b'OK'

    def _icon_files(self, slug):
        """The .py files in this game's icon directory, sorted, capped.

        Empty when the game has no icons or the directory was never written,
        which is the normal case -- the leg then costs one zero byte.
        """
        try:
            names = sorted(n for n in os.listdir(icons_dir_for(slug))
                           if n.endswith('.py'))
        except OSError:
            return []
        return names[:MAX_ICONS]

    def _serve_icons(self, cs, slug, should_abort=None):
        """Send the icon leg: a 1-byte count, then that many files.

        Reached only by a role whose ROLE_FILES entry takes icons; everything
        else is sent a count of 0. The game file is already acked by here, so
        an icon that fails costs a picture, not the game.
        """
        names = self._icon_files(slug)
        cs.write(bytes([len(names)]))
        if not names:
            return 0
        base = icons_dir_for(slug)
        sent = 0
        for name in names:
            result = self._send_file(cs, base + '/' + name, name, should_abort)
            if result == 'abort':
                return sent
            if result:
                sent += 1
            else:
                print("# icon %s/%s not acked" % (slug, name))
        return sent

    def _serve_client(self, cs, should_abort=None):
        request = self._read_request(cs)
        if request is None:
            # No intelligible request -- nothing to serve, and writing a
            # response into a socket we cannot read from just wastes the
            # 30s reply timeout.
            return False
        requested, role = request
        if self.resolve(requested or None, role) is None:
            # Unknown slug, nothing active, or a role this Box has no file
            # for.
            self._refuse(cs)
            return False
        ok = False
        try:
            result = self._send_file(cs, self.src_path, self.dest_name, should_abort)
            if result == 'abort':
                return 'abort'
            ok = bool(result)
            if ok and ROLE_FILES[role]['icons']:
                n = self._serve_icons(cs, self.active_slug, should_abort)
                if n:
                    print("# served %d icon(s) for %s" % (n, self.active_slug))
        except OSError:
            ok = False
        return ok
