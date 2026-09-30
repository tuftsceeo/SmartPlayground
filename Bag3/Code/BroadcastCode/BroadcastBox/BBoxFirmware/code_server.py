# PEER: Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/code_server.py — keep in sync.
# The Dial copy adds prewarm_ap() and an ungated per-client DEBUG print.
"""
code_server.py — SoftAP + TCP game-file server, non-blocking, multi-client.

arm() brings up the AP and listening socket; the caller's main loop calls
poll(). Each client is a _Client state machine (REQ -> HDR -> BODY -> ACK,
then ICOUNT and one HDR -> BODY -> ACK per icon for the icon leg). poll()
uses select() with a 0 timeout and advances each ready client one step.
"""

import gc
import os
import socket
import network
import machine
from time import sleep_ms, ticks_ms, ticks_diff, ticks_add

try:
    import hashlib
except ImportError:
    import uhashlib as hashlib

try:
    import select
except ImportError:
    import uselect as select

try:
    from ubinascii import hexlify
except ImportError:
    from binascii import hexlify

SSID_PREFIX = 'SP-FILEPUSH'
# Last four hex digits of the base MAC (machine.unique_id(), no radio
# needed). Names this host's SSID and the "@<id>" suffix on its getcode cards.
HOST_ID = hexlify(machine.unique_id()[-2:]).decode()
SSID = SSID_PREFIX + '-' + HOST_ID
PWD = 'playground1'
PORT = 8266
AP_CHANNEL = 1
CHUNK = 512
YIELD_MS = 20
# Client deadline after each unit of progress. Must stay below the
# requester's SOCK_TIMEOUT_S (code_puller.py, 12 s), so a stalled client is
# reaped before the requester retries. Also bounds the ack wait, which
# covers the requester's hash and compile check.
SOCK_REPLY_TIMEOUT_S = 8
SOCK_REQUEST_TIMEOUT_S = 5   # wait for the request frame after accept
AP_SETTLE_MS = 300           # after ap.active(False) in disarm()

# Diagnostic switch. This module is imported before the AP claims its
# memory, so diagnostic strings live in serve_probe.py, imported only when
# this is True and only after _start_ap(). Nothing added to this module may
# allocate ahead of the radio (AGENTS.md).
DEBUG_SERVE = False

# Maximum concurrent clients; also the AP's max_clients and the listen
# backlog.
MAX_CLIENTS = 4

# With at least one client connected, a further accept waits while
# gc.mem_free() is below this. Unmeasured starting value.
MIN_FREE_ACCEPT = 30000

# PEER: SSID/PWD/PORT/CHUNK/YIELD_MS and the wire protocol are mirrored by
# hand in the MockWand, IconDisplay and SplatCompanion code_puller.py.
# Change them together.

# Request frame (see code_puller.py for the full protocol):
#   v1:  len(1) | slug                          -> DEFAULT_ROLE's file
#   v2:  0xFF | len(1) | slug | len(1) | hubtype
REQ_V2 = 0xFF

# Per-hubtype source file and icon leg. An unlisted hubtype is refused.
#   suffix  -- appended to the slug for this role's source file
#   icons   -- send the named-icon leg after the game file
ROLE_FILES = {
    'wand':            {'suffix': '',       'icons': False},
    'icon_display':    {'suffix': '_icon',  'icons': True},
    'splat_companion': {'suffix': '_splat', 'icons': False},
}
DEFAULT_ROLE = 'wand'   # role for a v1 request

MAX_ICONS = 64

FS_ROOT = '/flash'
DEFAULT_SRC = FS_ROOT + '/payload.py'
DEFAULT_DEST = 'jumpin.py'
GAMES_DIR = FS_ROOT + '/games'
ACTIVE_PATH = FS_ROOT + '/active.txt'

# Per-client state machine states.
_S_REQ = 'req'        # reading the requester's opening frame
_S_HDR = 'hdr'        # writing size+digest+name (or the 4-byte refusal)
_S_BODY = 'body'      # streaming the current file
_S_ACK = 'ack'        # reading the 2-byte OK/NO
_S_ICOUNT = 'icount'  # writing the icon leg's 1-byte count

# States that go on select()'s write list; all others on the read list.
_WRITE_STATES = (_S_HDR, _S_BODY, _S_ICOUNT)


def icons_dir_for(slug):
    """Directory holding a game's named icons (written by ChatBroadcast)."""
    return GAMES_DIR + '/' + slug + '_icons'


def _emit(cb, event):
    """Call cb(event); an exception from it is printed and ignored."""
    if cb is None:
        return
    try:
        cb(event)
    except Exception as e:
        print("# code_server on_event(%s) err: %s" % (event, str(e)))


def _asked_to_abort(cb):
    """True if should_abort() returns true. An exception counts as False."""
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


def _parse_request(buf):
    """Parse a v1 or v2 request frame from the bytes received so far.

    Returns (slug, role) when complete (slug '' = active game), an int count
    of bytes still needed, or None if the frame is unusable.
    """
    if not buf:
        return 1
    if buf[0] != REQ_V2:
        n = buf[0]
        need = 1 + n - len(buf)
        if need > 0:
            return need
        try:
            return bytes(buf[1:1 + n]).decode('utf-8'), DEFAULT_ROLE
        except (UnicodeError, ValueError):
            return None
    if len(buf) < 2:
        return 2 - len(buf)
    n = buf[1]
    if len(buf) < 3 + n:        # slug bytes, then the hubtype's length byte
        return 3 + n - len(buf)
    m = buf[2 + n]
    need = 3 + n + m - len(buf)
    if need > 0:
        return need
    try:
        slug = bytes(buf[2:2 + n]).decode('utf-8')
        role = bytes(buf[3 + n:3 + n + m]).decode('utf-8')
    except (UnicodeError, ValueError):
        return None
    return slug, (role or DEFAULT_ROLE)


def _start_ap(ssid=SSID, pwd=PWD):
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap.config(essid=ssid, password=pwd, authmode=network.AUTH_WPA_WPA2_PSK)
    except (ValueError, OSError):
        ap.config(essid=ssid, password=pwd, security=3)
    # Channel 1: the ESP-NOW default channel, and inside 1-11.
    try:
        ap.config(channel=AP_CHANNEL)
    except (ValueError, OSError):
        pass
    try:
        ap.config(pm=0)
    except (ValueError, OSError, AttributeError):
        pass
    try:
        ap.config(max_clients=MAX_CLIENTS)
    except (ValueError, OSError, AttributeError):
        print("# CodeServer: ap.config(max_clients=...) unsupported on this port")
    while not ap.active():
        sleep_ms(100)
    print("# CodeServer: AP up, ssid=%s" % ssid)
    return ap


class _Client:
    """One connection's transfer state. Request fields are per client."""

    def __init__(self, sock, deadline):
        self.sock = sock
        self.state = _S_REQ
        self.deadline = deadline

        # Inbound framing (request bytes, then the 2-byte ack).
        self.inbuf = bytearray()

        # Outbound framing (header bytes, or the current file chunk).
        self.outbuf = None
        self.outpos = 0
        self.refusing = False

        # Resolved per this client's own request.
        self.slug = None
        self.role = DEFAULT_ROLE
        self.src_path = None
        self.dest_name = None
        self.size = 0

        # Body streaming state, reset per file (game file, then each icon).
        self.fh = None
        self.sent = 0
        self._chunk_len = 0
        # One chunk buffer per client: allocated on the first body step,
        # released by _drop().
        self.chunkbuf = None

        # serve_probe counters. sel = times select() named this socket ready;
        # blocked = times a body write then moved no bytes.
        self.started_ms = ticks_ms()
        self.sel = 0
        self.blocked = 0

        # Icon leg. game_ok is the game file's result; icons do not change it.
        self.game_ok = False
        self.icon_names = None
        self.icon_idx = 0
        self.icons_ok = 0


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
        self._clients = []
        self._armed = False
        self._last_ok = None
        self._pickups = 0
        # poll()'s on_event, held for the step functions during one call.
        self._on_event = None
        # One-entry sha256 cache keyed by (path, size).
        self._digest_cache = (None, None, None)  # (path, size, digest)
        self._probe = None      # serve_probe.Probe, set in arm() if DEBUG_SERVE

    @property
    def armed(self):
        return self._armed

    @property
    def serving(self):
        return len(self._clients) > 0

    @property
    def serving_count(self):
        """Number of devices currently mid-transfer."""
        return len(self._clients)

    @property
    def last_ok(self):
        return self._last_ok

    @property
    def pickups(self):
        """Successful transfers since boot."""
        return self._pickups

    def set_game(self, slug, src_path=None, role=DEFAULT_ROLE):
        """Set the active slug and its source file for `role`.

        The source carries the role suffix (<slug>_icon.py); the device-side
        name does not. Transfers resolve their own file via _lookup().
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

    def _lookup(self, slug, role=DEFAULT_ROLE):
        """Resolve slug (or /flash/active.txt) to (slug, src_path, dest_name).

        Does not modify self. None for an unknown role or a missing/empty file.
        """
        if role not in ROLE_FILES:
            return None
        if slug:
            suffix = ROLE_FILES[role]['suffix']
            path = GAMES_DIR + '/' + slug + suffix + '.py'
            try:
                if os.stat(path)[6] > 0:
                    return (slug, path, slug + '.py')
            except OSError:
                return None
            return None
        try:
            with open(ACTIVE_PATH, 'r') as f:
                active = f.read().strip()
        except OSError:
            active = ''
        if active:
            return self._lookup(active, role)
        return None

    def resolve(self, slug=None, role=DEFAULT_ROLE):
        """_lookup() then set_game(). Returns the slug, or None."""
        result = self._lookup(slug, role)
        if result is None:
            return None
        slug_used, src_path, _dest_name = result
        self.set_game(slug_used, src_path, role)
        return slug_used

    def _hash_file_cached(self, path, size):
        c_path, c_size, c_digest = self._digest_cache
        if c_path == path and c_size == size:
            return c_digest
        digest = _hash_file(path)
        self._digest_cache = (path, size, digest)
        return digest

    def arm(self):
        if self._armed:
            return True
        if not self._file_ready():
            if self.resolve() is None or not self._file_ready():
                return False
        # Nothing may run between this collect and _start_ap(). An AP start
        # failure returns False like the other failure paths.
        gc.collect()
        try:
            self._ap = _start_ap(self.ssid, self.pwd)
        except OSError as e:
            print("# CodeServer.arm: AP start failed: %s" % str(e))
            self._ap = None
            return False
        try:
            self._srv = socket.socket()
            self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._srv.bind(('0.0.0.0', self.port))
            self._srv.listen(MAX_CLIENTS)
            self._srv.settimeout(0)
        except OSError as e:
            print("# CodeServer.arm: socket setup failed: %s" % str(e))
            try:
                self._ap.active(False)
            except OSError:
                pass
            self._ap = None
            self._srv = None
            return False
        self._armed = True
        self._last_ok = None
        # serve_probe is imported only after _start_ap().
        if DEBUG_SERVE:
            import serve_probe
            self._probe = serve_probe.Probe(self)
        return True

    def disarm(self):
        self._drop_all()
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
        self._probe = None
        gc.collect()

    def poll(self, on_event=None, should_abort=None):
        """Accept new clients and advance each ready one a step. Non-blocking.

        on_event('serving') fires per accepted client; 'ok' or 'fail' per
        finished client. should_abort() is sampled once per call; true drops
        every client and returns 'abort'. Otherwise returns None.
        """
        if not self._armed or self._srv is None:
            return None
        self._on_event = on_event

        self._accept_new()
        if self._probe is not None:
            self._probe.tick()

        if _asked_to_abort(should_abort):
            self._drop_all()
            self._last_ok = None
            return 'abort'

        if not self._clients:
            return None

        now = ticks_ms()
        for c in list(self._clients):
            if ticks_diff(now, c.deadline) > 0:
                self._finish(c, False)

        if not self._clients:
            return None

        rlist = []
        wlist = []
        for c in self._clients:
            if c.state in _WRITE_STATES:
                wlist.append(c.sock)
            else:
                rlist.append(c.sock)
        try:
            rr, ww, _xx = select.select(rlist, wlist, [], 0)
        except OSError:
            rr, ww = [], []
        ready = list(rr) + list(ww)
        for c in list(self._clients):
            if c.sock in ready:
                self._advance(c)

        if any(c.state == _S_BODY for c in self._clients):
            # Pacing between chunk writes.
            sleep_ms(YIELD_MS)

        return None

    def _accept_new(self):
        if self._probe is not None and len(self._clients) >= MAX_CLIENTS:
            self._probe.at_cap(MAX_CLIENTS)
        while len(self._clients) < MAX_CLIENTS:
            if self._clients and gc.mem_free() < MIN_FREE_ACCEPT:
                print("# CodeServer.poll: low mem (%d free), deferring accept"
                      % gc.mem_free())
                break
            try:
                cs, _addr = self._srv.accept()
            except OSError:
                break
            try:
                cs.setblocking(False)
            except AttributeError:
                cs.settimeout(0)
            deadline = ticks_add(ticks_ms(), SOCK_REQUEST_TIMEOUT_S * 1000)
            self._clients.append(_Client(cs, deadline))
            if self._probe is not None:
                self._probe.accepted()
            _emit(self._on_event, 'serving')

    def _file_ready(self):
        try:
            return os.stat(self.src_path)[6] > 0
        except OSError:
            return False

    def _drop(self, c):
        """Close a client's file and socket. No event, no stats record."""
        try:
            if c.fh is not None:
                c.fh.close()
        except OSError:
            pass
        try:
            c.sock.close()
        except OSError:
            pass
        c.chunkbuf = None
        c.outbuf = None

    def _drop_all(self):
        for c in self._clients:
            self._drop(c)
        self._clients = []

    def _finish(self, c, ok):
        """End a client: drop it, emit 'ok'/'fail', record to stats_log.

        `ok` is the game file's result.
        """
        if self._probe is not None:
            self._probe.finished(c, ok)
        self._drop(c)
        try:
            self._clients.remove(c)
        except ValueError:
            pass
        self._last_ok = ok
        if ok:
            self._pickups += 1
        _emit(self._on_event, 'ok' if ok else 'fail')
        try:
            import stats_log
            stats_log.record_pull(c.slug or '?', ok)
        except Exception as e:
            print("# stats pull failed: %s" % str(e))

    def _advance(self, c):
        c.sel += 1
        try:
            if c.state == _S_REQ:
                self._step_req(c)
            elif c.state == _S_HDR:
                self._step_hdr(c)
            elif c.state == _S_BODY:
                self._step_body(c)
            elif c.state == _S_ACK:
                self._step_ack(c)
            elif c.state == _S_ICOUNT:
                self._step_icount(c)
        except OSError:
            # Peer closed, reset or dropped.
            self._finish(c, False)
        except Exception as e:
            # Any other error (e.g. MemoryError) is printed and the client
            # reaped, so it does not sit until its deadline.
            print("# CodeServer: %s in %s for %r: %s"
                  % (type(e).__name__, c.state, c.slug or '?', e))
            self._finish(c, False)

    # ── per-state steps ──────────────────────────────────────────
    #
    # Each step does at most one read or write. c.deadline is refreshed on
    # every unit of progress, so a slow client that is still moving bytes
    # is not dropped.

    def _step_req(self, c):
        """Read the request frame, only as many bytes as the parser needs."""
        result = _parse_request(c.inbuf)
        if isinstance(result, int):
            part = c.sock.read(result)
            if part is None:
                return      # nothing available yet; the deadline still runs
            if not part:
                self._finish(c, False)   # peer closed mid-frame
                return
            c.inbuf.extend(part)
            c.deadline = ticks_add(ticks_ms(), SOCK_REQUEST_TIMEOUT_S * 1000)
            result = _parse_request(c.inbuf)
        if isinstance(result, int):
            return          # still short; come back next tick
        if result is None:
            self._finish(c, False)   # unusable frame
            return
        slug, role = result
        self._resolve_request(c, slug, role)

    def _resolve_request(self, c, requested, role):
        """Choose this client's file; requested '' = active game."""
        c.role = role
        result = self._lookup(requested or None, role)
        c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
        if result is None:
            # Nothing to serve: send the 4-byte zero-size refusal.
            c.outbuf = (0).to_bytes(4, 'big')
            c.outpos = 0
            c.refusing = True
            c.state = _S_HDR
            return
        slug_used, src_path, dest_name = result
        c.slug = slug_used
        self._begin_file(c, src_path, dest_name)

    def _begin_file(self, c, src_path, dest_name):
        """Queue a file header (game or icon) and enter _S_HDR.

        A file that cannot be sized or named finishes the client with
        c.game_ok.
        """
        name_bytes = dest_name.encode('utf-8')
        if len(name_bytes) > 255:
            print("# %s: dest name too long (%d bytes)"
                  % (src_path, len(name_bytes)))
            self._finish(c, c.game_ok)
            return
        try:
            size = os.stat(src_path)[6]
        except OSError as e:
            print("# %s: cannot stat mid-serve: %s" % (src_path, str(e)))
            self._finish(c, c.game_ok)
            return
        digest = self._hash_file_cached(src_path, size)
        c.src_path = src_path
        c.dest_name = dest_name
        c.size = size
        c.outbuf = (size.to_bytes(4, 'big') + digest
                    + bytes([len(name_bytes)]) + name_bytes)
        c.outpos = 0
        c.refusing = False
        c.state = _S_HDR

    def _step_hdr(self, c):
        n = c.sock.write(memoryview(c.outbuf)[c.outpos:])
        if not n:
            return
        c.outpos += n
        c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
        if c.outpos < len(c.outbuf):
            return
        if c.refusing:
            self._finish(c, False)
            return
        try:
            c.fh = open(c.src_path, 'rb')
        except OSError as e:
            print("# %s: cannot open mid-serve: %s" % (c.src_path, str(e)))
            self._finish(c, c.game_ok)
            return
        c.outbuf = None
        c.sent = 0
        c.state = _S_BODY

    def _step_body(self, c):
        if c.outbuf is None:
            if c.sent >= c.size:
                try:
                    c.fh.close()
                except OSError:
                    pass
                c.fh = None
                c.state = _S_ACK
                c.inbuf = bytearray()
                c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
                return
            want = min(CHUNK, c.size - c.sent)
            if c.chunkbuf is None:
                # One buffer per client, reused for every chunk and file.
                c.chunkbuf = bytearray(CHUNK)
            n = c.fh.readinto(memoryview(c.chunkbuf)[:want])
            if not n:
                # File shrank or vanished mid-serve.
                self._finish(c, False)
                return
            c.outbuf = c.chunkbuf
            c._chunk_len = n
            c.outpos = 0
        n = c.sock.write(memoryview(c.outbuf)[c.outpos:c._chunk_len])
        if not n:
            c.blocked += 1
            return
        c.outpos += n
        c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
        if c.outpos >= c._chunk_len:
            c.sent += c._chunk_len
            c.outbuf = None

    def _step_ack(self, c):
        """Read a 2-byte ack. After the game file: finish, or start the icon
        leg. After an icon: next icon. A NO on an icon is printed only.
        """
        remaining = 2 - len(c.inbuf)
        part = c.sock.read(remaining)
        if part is None:
            return
        if not part:
            # Peer closed mid-ack: report the game's result.
            self._finish(c, c.game_ok)
            return
        c.inbuf.extend(part)
        if len(c.inbuf) < 2:
            c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
            return
        ok = bytes(c.inbuf) == b'OK'
        c.inbuf = bytearray()
        if c.icon_names is None:
            # That was the game file.
            c.game_ok = ok
            if not ok or not ROLE_FILES.get(c.role, {}).get('icons'):
                self._finish(c, ok)
                return
            c.icon_names = self._icon_files(c.slug)
            c.icon_idx = 0
            c.outbuf = bytes([len(c.icon_names)])
            c.outpos = 0
            c.state = _S_ICOUNT
            c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
            return
        if ok:
            c.icons_ok += 1
        else:
            print("# icon %s/%s not acked"
                  % (c.slug, c.icon_names[c.icon_idx]))
        c.icon_idx += 1
        self._next_icon(c)

    def _step_icount(self, c):
        """Write the icon leg's 1-byte count, then send the first icon."""
        n = c.sock.write(memoryview(c.outbuf)[c.outpos:])
        if not n:
            return
        c.outpos += n
        c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
        if c.outpos < len(c.outbuf):
            return
        c.outbuf = None
        self._next_icon(c)

    def _next_icon(self, c):
        """Start the next icon, or finish the client when the leg is done."""
        if c.icon_idx >= len(c.icon_names):
            if c.icons_ok:
                print("# served %d icon(s) for %s" % (c.icons_ok, c.slug))
            self._finish(c, c.game_ok)
            return
        name = c.icon_names[c.icon_idx]
        self._begin_file(c, icons_dir_for(c.slug) + '/' + name, name)

    def _icon_files(self, slug):
        """Sorted .py names in the game's icon directory, up to MAX_ICONS."""
        try:
            names = sorted(n for n in os.listdir(icons_dir_for(slug))
                           if n.endswith('.py'))
        except OSError:
            return []
        return names[:MAX_ICONS]
