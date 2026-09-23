# PEER: Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/code_server.py — keep in sync.
# The two are the same server on different boards; only the comments about
# each board's heap, and the Dial-only prewarm_ap() it carries, differ. Fix
# one copy and say which (Bag3/AGENTS.md).
"""
code_server.py — SoftAP + TCP file server (non-blocking arm/poll, multi-client).

Split from BBoxPrototype/s3_sender.py so the UI loop can coexist with
accept().

Each connected device is driven through a small per-client state machine
(_Client / _step_req / _step_hdr / _step_body / _step_ack / _step_icount) so
poll() can advance several transfers a little bit per call instead of blocking
on one at a time. select.select() (0 timeout) is used each tick to find which
client sockets are actually ready, so idle clients cost nothing.

A client that takes the icon leg walks HDR->BODY->ACK once for the game file
and then once more per icon; _step_ack() is what routes between the two.
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
# Four lowercase hex chars from the tail of this ESP32's base MAC. Readable
# with no network call (unlike a station MAC, which needs STA_IF active),
# which matters because arm()/_start_ap() run with the AP still down -- see
# the module-level invariant note in bdial_server.py/bbox_server.py. Gives
# each host a distinct SSID so several hosts in one room can be told apart
# by a scanning client (see code_puller.py's _find_ap()) and by a getcode
# card's "@<id>" suffix (see card_writer callers in bdial_server.py /
# bbox_server.py).
HOST_ID = hexlify(machine.unique_id()[-2:]).decode()
SSID = SSID_PREFIX + '-' + HOST_ID
PWD = 'playground1'
PORT = 8266
AP_CHANNEL = 1
CHUNK = 512
YIELD_MS = 20
SOCK_REPLY_TIMEOUT_S = 30
SOCK_REQUEST_TIMEOUT_S = 5   # how long to wait for the requester's frame
AP_SETTLE_MS = 300  # same value the wand uses post-cycle

# Diagnostic switch, default off. Every string in this module is allocated
# when bdial_server.py imports it -- before prewarm_ap(), long before arm()
# -- and the AP needs a large contiguous block it can only get early. So the
# probe's strings live in serve_probe.py, which is imported only when this is
# True and only after _start_ap() has returned. Keep it that way: nothing
# added here may allocate before the radio has its memory.
DEBUG_SERVE = False

# How many devices CodeServer will serve at once. The ESP32 SoftAP itself
# associates several stations fine -- this cap exists for RAM, not radio,
# reasons (see MIN_FREE_ACCEPT below). Bench-verified starting point; lower
# it here if gc.mem_free() gets uncomfortably low during a multi-wand burst.
MAX_CLIENTS = 4

# Below this much free heap, poll() defers accepting any *additional*
# client rather than risk an OOM mid-transfer -- a queued wand just waits
# one more poll() tick and retries within its own budget. SoftAP bring-up is
# the OOM-fragile spot on both boards (see arm()'s gc.collect() below); 30 KB
# is a starting guess, not a measured floor -- tune after a real multi-wand
# bench run.
MIN_FREE_ACCEPT = 30000

# PEER: MockWand/code_puller.py and BroadcastBox/IconDisplay/code_puller.py
# each hold a hand-kept copy of SSID/PWD/PORT/CHUNK/YIELD_MS and of the wire
# protocol (spread across _parse_request/_step_hdr/_step_body/_step_ack below;
# the framing is unchanged from the single-client version these files were
# written against). There is no shared module (they run on different devices),
# so any wire protocol change here must be mirrored in all of them in the same
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

# Per-client state machine states.
_S_REQ = 'req'        # reading the requester's opening frame
_S_HDR = 'hdr'        # writing size+digest+name (or the 4-byte refusal)
_S_BODY = 'body'      # streaming the current file
_S_ACK = 'ack'        # reading the 2-byte OK/NO
_S_ICOUNT = 'icount'  # writing the icon leg's 1-byte count

# Which states are waiting to write rather than to read. poll() hands these
# to select()'s write list; everything else goes in the read list.
_WRITE_STATES = (_S_HDR, _S_BODY, _S_ICOUNT)


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


def _parse_request(buf):
    """Parse an opening frame out of whatever bytes have arrived so far.

    Returns one of three things, because the frame arrives a piece at a time
    and the caller has to know which:
      (slug, role)  the frame is complete; slug '' means "whatever is active"
      an int        that many more bytes are needed before it can be parsed
      None          the frame is unusable and the client should be dropped

    Pure, and the only place either device reads this frame, so the two
    shapes cannot drift apart. See REQ_V2 for both; a v1 frame names no
    hubtype and gets DEFAULT_ROLE, which is what keeps an un-updated wand
    working.
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
    print("# CodeServer: AP up, ssid=%s" % ssid)
    return ap


class _Client:
    """One device's in-flight connection: a tiny resumable state machine.

    Nothing here is shared between clients -- role/slug/src_path/dest_name are
    captured per client at request time (see CodeServer._lookup) instead of
    living on CodeServer itself, so two devices requesting different games, or
    the same game in different roles, cannot cross-contaminate each other's
    transfer.
    """

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
        # Reused for every chunk this client ever sends -- allocated on the
        # first body step, released by _drop(). See _step_body().
        self.chunkbuf = None

        # serve_probe counters. sel = times select() named this socket ready;
        # blocked = times a body write then moved no bytes.
        self.started_ms = ticks_ms()
        self.sel = 0
        self.blocked = 0

        # Icon leg. game_ok is this client's real outcome: an icon that fails
        # costs a picture, not the game, so it never changes game_ok.
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
        # Set for the duration of one poll() call so the per-client step
        # functions (which run several layers below poll()) can report
        # 'ok'/'fail' without threading the callback through every method.
        self._on_event = None
        # One-entry digest cache: several devices pulling the same game in
        # the same burst should not each re-hash the whole file. One entry is
        # enough for that case; an icon leg evicts it as it walks its files,
        # which is why the cache is keyed by path rather than assumed to hold
        # the game.
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
        """Completed successful serves this session."""
        return self._pickups

    def set_game(self, slug, src_path=None, role=DEFAULT_ROLE):
        """Point the server at a slug's source file for one device role.

        The file on the Box carries the role's suffix (<slug>_icon.py for an
        icon display); the name it lands under on the device does not. Every
        device holds at most one module per slug, so the role lives here and
        in ChatBroadcast, never on the device's flash.

        This is the shared, mutating view of "what is loaded", used by
        bdial_server.py for the menu and mode entry. It is NOT what an
        in-flight transfer reads -- see _lookup().
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
        """Resolve slug (or /flash/active.txt) into (slug, src_path, dest_name).

        Pure -- never touches self. Used per-client during a transfer so one
        device's request can never redirect another's in-flight file. An
        unknown role resolves to nothing at all, so the requester gets the
        explicit zero-size refusal rather than a file it cannot run.
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
        """Resolve slug (or /flash/active.txt) and update self in place.

        Returns the slug used, or None if nothing is serveable for this role.
        """
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
        # Prefer active game; fall back to whatever src_path already is.
        if not self._file_ready():
            if self.resolve() is None or not self._file_ready():
                return False
        # Bringing up the WiFi stack needs a chunk of contiguous heap.
        # Collect right before the one call that needs it, and treat a
        # failure here the same as "no game to serve" -- every other
        # failure path in this method returns False rather than raising,
        # and this one should too.
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
        # Only now: the AP has its memory, so parsing a module cannot cost it.
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
        """Non-blocking: accept up to MAX_CLIENTS devices and advance each a
        step. Returns 'abort' if should_abort() fired, else None.

        on_event('serving') fires once per accepted client, before that
        client's transfer starts, so a caller can paint a "serving" screen.
        on_event('ok') / on_event('fail') fires once per client as it
        finishes. should_abort() is sampled once per poll() call (not once
        per client or per chunk -- poll() no longer blocks, so the caller's
        own main loop keeps sampling input on every tick); a True return
        drops every in-flight client without acking or promoting any of
        them. An aborted transfer is safe on the device side -- it sees a
        short read or hash mismatch, removes its .part file, does not
        promote, and retries within its own budget.
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
            # Same pacing as the old single-client loop: give the AP's
            # WiFi driver a breather between chunk writes rather than
            # spinning the poll() loop as fast as possible.
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
        # Hand the chunk buffer back now rather than waiting for the client
        # object itself to be collected -- this is the one choke point both
        # _finish() and abort/disarm go through.
        c.chunkbuf = None
        c.outbuf = None

    def _drop_all(self):
        for c in self._clients:
            self._drop(c)
        self._clients = []

    def _finish(self, c, ok):
        """One client's transfer is over (success, failure, or timeout).

        `ok` is the GAME file's outcome. A client that took the icon leg has
        already been counted as a pickup's worth of work by then; a failed
        icon inside that leg is printed, not reported here.
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
            # Expected: the device closed, reset, or walked out of range
            # mid-transfer. Its own retry budget covers this.
            self._finish(c, False)
        except Exception as e:
            # Anything else is a fault in this server -- a MemoryError on a
            # tight heap is the one seen in the field -- not a device going
            # away. It has to be caught here: escaping _advance() leaves the
            # client parked in its current state, sending nothing, until its
            # deadline expires, while the device sits on a socket nothing
            # will ever write to again. Reap it, and print, because this
            # path is never normal.
            print("# CodeServer: %s in %s for %r: %s"
                  % (type(e).__name__, c.state, c.slug or '?', e))
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
        """Accumulate the opening frame until _parse_request() can read it.

        Reads only the bytes the parser says are still missing, so this can
        never swallow the ack that comes later on the same socket.
        """
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
        """requested == '' means "serve whatever is active" (see _step_req).

        This is where a client's own file is chosen, per client: the result
        goes onto the _Client record, never onto self, so a second device
        asking for a different game (or the same game as a different role)
        cannot redirect this one's in-flight transfer.
        """
        c.role = role
        result = self._lookup(requested or None, role)
        c.deadline = ticks_add(ticks_ms(), SOCK_REPLY_TIMEOUT_S * 1000)
        if result is None:
            # Unknown slug, nothing active, or a role this device has no file
            # for. Say so plainly with a zero size rather than dropping the
            # connection, so the requester can show a real error instead of
            # waiting out its socket timeout.
            c.outbuf = (0).to_bytes(4, 'big')
            c.outpos = 0
            c.refusing = True
            c.state = _S_HDR
            return
        slug_used, src_path, dest_name = result
        c.slug = slug_used
        self._begin_file(c, src_path, dest_name)

    def _begin_file(self, c, src_path, dest_name):
        """Queue one file's header and move the client into _S_HDR.

        Shared by the game file and every icon, so the two legs cannot drift
        apart on framing.

        A file that cannot be sized or named ends the client, because the
        requester has already been told how many icons to expect and would
        otherwise wait out its timeout for a header that is never coming.
        The outcome reported is c.game_ok: if the game file itself already
        landed, a vanished icon costs a picture, not the game.
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
                # One buffer per client, reused for every chunk of every
                # file it takes (game, then each icon). Allocating a fresh
                # bytearray per chunk put a 512-byte request on the hottest
                # path of a device that already defers accepts below
                # MIN_FREE_ACCEPT; a slow client spans far more of that
                # churn than a fast one.
                c.chunkbuf = bytearray(CHUNK)
            n = c.fh.readinto(memoryview(c.chunkbuf)[:want])
            if not n:
                # File shrank/vanished under us mid-serve -- treat like any
                # other mid-transfer failure.
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
        """Read one file's 2-byte ack, then decide what this client gets next.

        The game file's ack either ends the client or opens the icon leg; an
        icon's ack moves to the next icon. A failed icon is printed and the
        leg carries on -- the game is already on the device by then.
        """
        remaining = 2 - len(c.inbuf)
        part = c.sock.read(remaining)
        if part is None:
            return
        if not part:
            # Peer closed mid-ack. game_ok is still False unless the game
            # file was already acked, so this reports the game's outcome
            # whichever leg we were in.
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
