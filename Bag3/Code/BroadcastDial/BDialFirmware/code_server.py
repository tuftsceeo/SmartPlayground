# PEER: Bag3/Code/BroadcastBox/BBoxFirmware/code_server.py — keep in sync
#
# DIVERGED 2026-09-15: this file now serves up to MAX_CLIENTS wands at once
# (see the CodeServer docstring below); the Box's copy is still the
# single-client version this file used to be. The wire protocol itself did
# NOT change -- MockWand/code_puller.py needs no update, and a single wand
# talking to this server sees exactly the same bytes as before. Porting the
# same rewrite to the Box is tracked as follow-on work.
"""
code_server.py — SoftAP + TCP file server (non-blocking arm/poll, multi-client).

Split from BBoxPrototype/s3_sender.py so the UI loop can coexist with
accept(). Wire protocol unchanged.

Each connected wand is driven through a small per-client state machine
(_Client / _step_req / _step_hdr / _step_body / _step_ack) so poll() can
advance several transfers a little bit per call instead of blocking on one
at a time. select.select() (0 timeout) is used each tick to find which
client sockets are actually ready, so idle clients cost nothing.
"""

import gc
import os
import socket
import network
from time import sleep_ms, ticks_ms, ticks_diff, ticks_add

try:
    import hashlib
except ImportError:
    import uhashlib as hashlib

try:
    import select
except ImportError:
    import uselect as select

SSID = 'SP-FILEPUSH'
PWD = 'playground1'
PORT = 8266
AP_CHANNEL = 1
CHUNK = 512
YIELD_MS = 20
SOCK_REPLY_TIMEOUT_S = 30
SOCK_REQUEST_TIMEOUT_S = 5   # how long to wait for the wand's request frame
AP_SETTLE_MS = 300  # same value the wand uses post-cycle

# How many wands CodeServer will serve at once. The ESP32 SoftAP itself
# associates several stations fine -- this cap exists for RAM, not radio,
# reasons (see MIN_FREE_ACCEPT below). Bench-verified starting point; lower
# it here if gc.mem_free() gets uncomfortably low during a multi-wand burst.
MAX_CLIENTS = 4

# Below this much free heap, poll() defers accepting any *additional*
# client rather than risk an OOM mid-transfer -- a queued wand just waits
# one more poll() tick and retries within its own budget. The Dial's SoftAP
# bring-up is the documented OOM-fragile spot (see dial_board.py H5 and
# arm()'s gc.collect() below); 30 KB is a starting guess, not a measured
# floor -- tune after a real multi-wand bench run.
MIN_FREE_ACCEPT = 30000

# PEER: MockWand/code_puller.py holds a hand-kept copy of SSID/PWD/PORT/CHUNK/
# YIELD_MS and of the wire protocol (now spread across _step_req/_step_hdr/
# _step_body/_step_ack below, framing unchanged from the old _serve_client).
# There is no shared module (the two run on different devices), so any wire
# protocol change here must be mirrored there in the same commit.

FS_ROOT = '/flash'
DEFAULT_SRC = FS_ROOT + '/payload.py'
DEFAULT_DEST = 'jumpin.py'
GAMES_DIR = FS_ROOT + '/games'
ACTIVE_PATH = FS_ROOT + '/active.txt'

# Per-client state machine states.
_S_REQ = 'req'    # reading the wand's request frame
_S_HDR = 'hdr'     # writing size+digest+name (or the 4-byte refusal)
_S_BODY = 'body'   # streaming the file
_S_ACK = 'ack'     # reading the 2-byte OK/NO


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


def prewarm_ap():
    """Cycle the AP radio on/off once, as early in boot as possible.

    Diagnostic/experimental (Dial-only, 2026-09-09 SERVE-mode OOM chase):
    ap.active(True) is where the ESP32 WiFi driver grabs its internal
    buffer pools, which wants a sizeable contiguous heap block. The theory
    is that ap.active(False) stops the radio without fully releasing that
    driver-owned allocation back to the general heap -- so doing this once
    while the heap is still close to pristine (before LVGL screens/NFC
    objects fragment it) means the real arm() later only has to reuse an
    already-reserved block instead of finding a fresh one in a fragmented
    heap. Unverified: whether MicroPython actually behaves this way on
    this board is exactly what the mem_free() prints here (and the
    surrounding _log_mem calls in bdial_server.py:run()) are meant to
    confirm on a real retry. If free memory bounces back up after
    active(False) below, this function isn't buying anything.
    """
    print("# AP prewarm: mem_free before=%d" % gc.mem_free())
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    print("# AP prewarm: mem_free after active(True)=%d" % gc.mem_free())
    ap.active(False)
    gc.collect()
    print("# AP prewarm: mem_free after active(False)+gc=%d" % gc.mem_free())


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
    try:
        ap.config(max_clients=MAX_CLIENTS)
    except (ValueError, OSError, AttributeError):
        print("# CodeServer: ap.config(max_clients=...) unsupported on this port")
    while not ap.active():
        sleep_ms(100)
    return ap


class _Client:
    """One wand's in-flight connection: a tiny resumable state machine.

    Nothing here is shared between clients -- src_path/dest_name/slug are
    captured per client at request time (see CodeServer._lookup) instead of
    living on CodeServer itself, so two wands requesting different games at
    once cannot cross-contaminate each other's transfer.
    """

    def __init__(self, sock, deadline):
        self.sock = sock
        self.state = _S_REQ
        self.deadline = deadline

        # Inbound framing (request bytes, then the 2-byte ack).
        self.inbuf = bytearray()
        self.req_len = None

        # Outbound framing (header bytes, or the current file chunk).
        self.outbuf = None
        self.outpos = 0
        self.refusing = False

        # Resolved per this client's own request.
        self.slug = None
        self.src_path = None
        self.dest_name = None
        self.size = 0

        # Body streaming state.
        self.fh = None
        self.sent = 0
        self._chunk_len = 0


class CodeServer:
    def __init__(self, src_path=DEFAULT_SRC, dest_name=DEFAULT_DEST,
                 port=PORT, ssid=SSID, pwd=PWD):
        self.src_path = src_path
        self.dest_name = dest_name
        self.active_slug = None
        self.port = port
        self.ssid = ssid
        self.pwd = pwd
        self._ap = None
        self._srv = None
        self._clients = []
        self._armed = False
        self._last_ok = None
        self._pickups = 0
        # Set for the duration of one poll() call so the per-client step
        # functions (which run several layers below poll()) can report
        # 'ok'/'fail' without threading the callback through every method.
        self._on_event = None
        # One-entry digest cache: several wands pulling the same game in
        # the same burst should not each re-hash the whole file.
        self._digest_cache = (None, None, None)  # (path, size, digest)

    @property
    def armed(self):
        return self._armed

    @property
    def serving(self):
        return len(self._clients) > 0

    @property
    def serving_count(self):
        """Number of wands currently mid-transfer."""
        return len(self._clients)

    @property
    def last_ok(self):
        return self._last_ok

    @property
    def pickups(self):
        """Completed successful serves this session."""
        return self._pickups

    def set_game(self, slug, src_path=None):
        """Point the server at /flash/games/<slug>.py serving as <slug>.py."""
        if not slug:
            self.active_slug = None
            self.src_path = DEFAULT_SRC
            self.dest_name = DEFAULT_DEST
            return
        self.active_slug = slug
        self.src_path = src_path if src_path else (GAMES_DIR + '/' + slug + '.py')
        self.dest_name = slug + '.py'

    def _lookup(self, slug):
        """Resolve slug (or /flash/active.txt) into (slug, src_path, dest_name).

        Pure -- never touches self. Used per-client during a transfer so one
        wand's request can never redirect another's in-flight file. resolve()
        below is the same lookup, kept for callers (bdial_server.py) that
        want it to also update self.src_path/self.dest_name/self.active_slug.
        """
        if slug:
            path = GAMES_DIR + '/' + slug + '.py'
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
            return self._lookup(active)
        return None

    def resolve(self, slug=None):
        """Resolve slug (or /flash/active.txt) and update self in place.

        Returns the slug used, or None if nothing is serveable.
        """
        result = self._lookup(slug)
        if result is None:
            return None
        slug_used, src_path, _dest_name = result
        self.set_game(slug_used, src_path)
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
        # Prefer active game; fall back to whatever src_path already is.
        if not self._file_ready():
            if self.resolve() is None or not self._file_ready():
                return False
        # Bringing up the WiFi stack needs a chunk of contiguous heap (see
        # dial_board.py H5: it OOM'd in Phase 0 probing with ~40 kB free,
        # and has since OOM'd for real with dial_ui.py's full set of LVGL
        # screens resident). Collect right before the one call that needs
        # it, and treat a failure here the same as "no game to serve" --
        # every other failure path in this method returns False rather
        # than raising, and this one should too.
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
        gc.collect()

    def poll(self, on_event=None, should_abort=None):
        """Non-blocking: accept up to MAX_CLIENTS wands and advance each a
        step. Returns 'abort' if should_abort() fired, else None.

        on_event('serving') fires once per accepted client, before that
        client's transfer starts, so a caller can paint a "serving" screen.
        on_event('ok') / on_event('fail') fires once per client as it
        finishes. should_abort() is sampled once per poll() call (not once
        per client or per chunk -- poll() no longer blocks, so the caller's
        own main loop keeps sampling input on every tick); a True return
        drops every in-flight client without acking or promoting any of
        them. An aborted transfer is safe on the wand side -- it sees a
        short read or hash mismatch, removes its .part file, does not
        promote, and retries within its own budget.
        """
        if not self._armed or self._srv is None:
            return None
        self._on_event = on_event

        self._accept_new()

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
            if c.state in (_S_REQ, _S_ACK):
                rlist.append(c.sock)
            else:
                wlist.append(c.sock)
        try:
            rr, ww, _xx = select.select(rlist, wlist, [], 0)
        except OSError:
            rr, ww = [], []
        ready = list(rr) + list(ww)
        for c in list(self._clients):
            if c.sock in ready:
                self._advance(c)

        if any(c.state == _S_BODY for c in self._clients):
            # Same pacing as the old single-client loop: give the AP's
            # WiFi driver a breather between chunk writes rather than
            # spinning the poll() loop as fast as possible.
            sleep_ms(YIELD_MS)

        return None

    def _accept_new(self):
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
            _emit(self._on_event, 'serving')

    def _file_ready(self):
        try:
            return os.stat(self.src_path)[6] > 0
        except OSError:
            return False

    def _drop(self, c):
        """Close a client without treating it as a completed transfer.

        Used for disarm() and abort -- neither is a pass/fail outcome, so
        no on_event('ok'/'fail') fires and stats_log is not touched.
        """
        try:
            if c.fh is not None:
                c.fh.close()
        except OSError:
            pass
        try:
            c.sock.close()
        except OSError:
            pass

    def _drop_all(self):
        for c in self._clients:
            self._drop(c)
        self._clients = []

    def _finish(self, c, ok):
        """One client's transfer is over (success, failure, or timeout)."""
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
        try:
            if c.state == _S_REQ:
                self._step_req(c)
            elif c.state == _S_HDR:
                self._step_hdr(c)
            elif c.state == _S_BODY:
                self._step_body(c)
            elif c.state == _S_ACK:
                self._step_ack(c)
        except OSError:
            self._finish(c, False)

    # ── per-state steps ──────────────────────────────────────────
    #
    # Each of these does at most one read or one write per call -- poll()
    # calls _advance() once per ready client per tick, which is what makes
    # several transfers progress "a little bit at a time" instead of one
    # running to completion while the rest wait. c.deadline is refreshed on
    # every unit of progress rather than being a single upfront budget for
    # the whole transfer, mirroring the old blocking code's per-call
    # settimeout() (each read/write got its own SOCK_*_TIMEOUT_S, not the
    # transfer as a whole) -- a client that is still moving bytes, however
    # slowly, is never dropped just for taking a while.

    def _step_req(self, c):
        """Read the wand's opening frame: 1 byte length + that many UTF-8
        bytes. A length of 0 means "serve whatever is active"."""
        progressed = False
        if c.req_len is None:
            b = c.sock.read(1)
            if b is None:
                return
            if not b:
                self._finish(c, False)
                return
            progressed = True
            c.req_len = b[0]
            if c.req_len == 0:
                self._resolve_request(c, '')
                return
        remaining = c.req_len - len(c.inbuf)
        if remaining > 0:
            part = c.sock.read(remaining)
            if part is None:
                if progressed:
                    c.deadline = ticks_add(ticks_ms(), SOCK_REQUEST_TIMEOUT_S * 1000)
                return
            if not part:
                self._finish(c, False)
                return
            c.inbuf.extend(part)
            progressed = True
        if len(c.inbuf) >= c.req_len:
            try:
                slug = bytes(c.inbuf).decode('utf-8')
            except (UnicodeError, ValueError):
                self._finish(c, False)
                return
            self._resolve_request(c, slug)
            return
        if progressed:
            c.deadline = ticks_add(ticks_ms(), SOCK_REQUEST_TIMEOUT_S * 1000)

    def _resolve_request(self, c, requested):
        """requested == '' means "serve whatever is active" (see _step_req)."""
        result = self._lookup(requested or None)
        c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
        if result is None:
            # Unknown slug, or nothing active. Tell the wand plainly with a
            # zero size rather than dropping the connection, so it can show
            # a real error instead of timing out.
            c.outbuf = (0).to_bytes(4, 'big')
            c.outpos = 0
            c.refusing = True
            c.state = _S_HDR
            return
        slug_used, src_path, dest_name = result
        name_bytes = dest_name.encode('utf-8')
        if len(name_bytes) > 255:
            self._finish(c, False)
            return
        try:
            size = os.stat(src_path)[6]
        except OSError:
            self._finish(c, False)
            return
        digest = self._hash_file_cached(src_path, size)
        c.slug, c.src_path, c.dest_name, c.size = slug_used, src_path, dest_name, size
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
        except OSError:
            self._finish(c, False)
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
            buf = bytearray(want)
            n = c.fh.readinto(buf)
            if not n:
                # File shrank/vanished under us mid-serve -- treat like any
                # other mid-transfer failure.
                self._finish(c, False)
                return
            c.outbuf = buf
            c._chunk_len = n
            c.outpos = 0
        n = c.sock.write(memoryview(c.outbuf)[c.outpos:c._chunk_len])
        if not n:
            return
        c.outpos += n
        c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
        if c.outpos >= c._chunk_len:
            c.sent += c._chunk_len
            c.outbuf = None

    def _step_ack(self, c):
        remaining = 2 - len(c.inbuf)
        part = c.sock.read(remaining)
        if part is None:
            return
        if not part:
            self._finish(c, False)
            return
        c.inbuf.extend(part)
        if len(c.inbuf) >= 2:
            self._finish(c, bytes(c.inbuf) == b'OK')
        else:
            c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
