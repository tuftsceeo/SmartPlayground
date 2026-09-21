"""
code_puller.py — join Broadcast Box SoftAP and pull jumpin.py (Mock Wand).

Adapted from BBoxPrototype/c6_receiver.py. Calls enow.shutdown() before
WiFi connect. See EXTERNAL_ANTENNA below for the GPIO 3/14 antenna switch --
it is off by default, matching the prototype.
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

try:
    from machine import Pin
except ImportError:
    Pin = None

# BENCH: heap/IDF-heap instrumentation for the memory-stabilization work.
# Not part of the pull protocol itself -- see lib/memprobe.py's docstring.
# Optional import, matching this file's existing style (hashlib/Pin above):
# code_puller.py predates memprobe.py and should still run without it.
try:
    import memprobe
except ImportError:
    class _NoProbe:
        def probe(self, *a, **k): return None
        def mark(self): return (0, 0)
        def span(self, *a, **k): return None
        def frag(self, *a, **k): return None
    memprobe = _NoProbe()

import game_store

REV = "phase0-2026-09-04"
print("# code_puller rev", REV)

# PEER: BBoxFirmware/code_server.py holds a hand-kept copy of SSID/PWD/PORT/
# CHUNK/YIELD_MS and of the wire protocol in pull() below. There is no shared
# module (the two run on different devices), so any change here must be
# mirrored there in the same commit.
HOST = '192.168.4.1'
PORT = 8266
SSID = 'SP-FILEPUSH'
PWD = 'playground1'

CHUNK = 512
YIELD_MS = 20

# Request-frame version sentinel. A v1 request opens with the slug's length,
# which is capped at 16 by game_store's slug rule, so a first byte of 0xFF
# cannot be mistaken for one. That is what lets a Box serve both an
# un-updated wand (v1) and a device that names its hubtype (v2).
#
#   v1:  len(1) | slug
#   v2:  0xFF | len(1) | slug | len(1) | hubtype
#
# The response is unchanged for both: size(4B BE) | sha256(32B) |
# name_len(1B) | name, then the body in CHUNK-byte pieces, then a 2-byte
# b'OK'/b'NO' ack from this side.
#
# A device that asked for icons (pull(icon_dir=...)) reads one more leg after
# that ack: a 1-byte icon count, then that many files in the same
# header+body+ack shape. A count of 0 ends the session, which is what a wand
# would get if it ever asked.
REQ_V2 = 0xFF
MAX_ICONS = 64

# Timeouts are deliberately short. A failed pull is cheap to recover from --
# the teacher just taps the card again -- so waiting a long time to be told
# "no" is worse than failing fast and letting them retap. Everything here is
# sized so a total failure costs a few seconds, not most of a minute.
#
# The join timeout is short because we never call connect() blind: the AP was
# in a scan moments earlier, so an association that has not completed in this
# long is not going to.
CONNECT_TIMEOUT_S = 6
SOCK_TIMEOUT_S = 10

# How many full scans to spend looking for the Box's SSID before deciding the
# AP simply is not up. A scan is ~1.5-2s, so three is ~6s worst case -- enough
# to ride out one scan landing between beacons without making "the Box is off"
# an expensive answer.
SCAN_ATTEMPTS = 3

# Settle time after toggling the STA interface off/on. The driver needs a
# moment before connect() will take; without it the reset is cosmetic.
RADIO_SETTLE_MS = 300
# One retry: the first join after ESP-NOW teardown is the flaky one.
JOIN_ATTEMPTS = 2


class NoAP(OSError):
    """The Box's SSID was never seen in any scan -- the AP is not up.

    Distinct from JoinFailed because the two mean different things to the
    person holding the wand: no AP means "the Box isn't broadcasting",
    which no amount of retrying on this wand can fix.
    """


class JoinFailed(OSError):
    """The SSID was visible but the association or auth never completed."""

# There is one radio and one pair of antenna-select pins, and espnow_manager
# drives them too, so it owns the setting -- a disagreement would mean
# whichever module ran last silently won. Falls back to internal so this
# still runs on a board with no /lib.
try:
    from espnow_manager import EXTERNAL_ANTENNA
except ImportError:
    EXTERNAL_ANTENNA = False


def _configure_antenna(external, verbose=False):
    """Select internal (onboard) or external (u.FL) antenna on the C6.

    Selects explicitly in BOTH directions rather than only switching to
    external, so the state does not depend on what last touched these pins:
    espnow_manager._configure_antenna() drives them too, on every
    ESPNowManager.init(). Leaving them alone could mean transmitting into a
    u.FL connector with no antenna attached.

    GPIO3 = RF switch enable (active low), GPIO14 = select (0 = onboard,
    1 = external).
    """
    if Pin is None:
        return
    wifi_en = Pin(3, Pin.OUT)
    ant_cfg = Pin(14, Pin.OUT)
    wifi_en.value(0)
    sleep_ms(100)
    ant_cfg.value(1 if external else 0)
    if verbose:
        print("  antenna: %s" % ("external (u.FL)" if external else "internal (onboard)"))


def _compiles(path, verbose=False):
    """True if `path` parses as MicroPython source.

    compile() runs the parser only -- no imports, no side effects from the
    game's module body -- so this is safe to run on untrusted-ish code that
    the teacher's LLM just wrote. It catches the common failure (a syntax
    error in generated code) without pretending to catch runtime errors.
    """
    try:
        with open(path, 'r') as f:
            src = f.read()
        compile(src, path, 'exec')
        return True
    except Exception as e:
        if verbose:
            print("[XFER] rejected: %s does not compile: %s" % (path, e))
        return False


def _read_exact(sock, n):
    out = bytearray(n)
    mv = memoryview(out)
    got = 0
    while got < n:
        chunk = sock.recv(n - got)
        if not chunk:
            raise OSError("connection closed early (got %d/%d bytes)" % (got, n))
        mv[got:got + len(chunk)] = chunk
        got += len(chunk)
    return bytes(out)


def _write_request(cs, slug, hubtype, verbose=False):
    """Send the opening frame. The requester speaks first; the Box writes
    nothing until it has read this. See BBoxFirmware/code_server.py
    _read_request()."""
    req = (slug or "").encode('utf-8')
    if hubtype:
        hub = hubtype.encode('utf-8')
        cs.write(bytes([REQ_V2, len(req)]))
        if req:
            cs.write(req)
        cs.write(bytes([len(hub)]))
        cs.write(hub)
    else:
        cs.write(bytes([len(req)]))
        if req:
            cs.write(req)
    if verbose:
        print("[XFER] requested %r as %r" % (slug or "<active>", hubtype or "<v1>"))


def _read_file_header(cs):
    """Read one file header. Returns (size, digest, name).

    A size of 0 is the Box's explicit refusal and carries no digest or name,
    so the caller must check it before reading further.
    """
    size = int.from_bytes(_read_exact(cs, 4), 'big')
    if size == 0:
        return 0, b'', ''
    head = _read_exact(cs, 32 + 1)
    name = _read_exact(cs, head[32]).decode('utf-8')
    return size, head[0:32], name


def _recv_body(cs, tmp_path, expected_size, expected_digest, on_progress=None):
    """Stream one file body to tmp_path and verify length and hash.

    Returns True only when every byte arrived and the sha256 matches. The
    caller decides what to do with tmp_path either way -- this does not
    promote, delete, or ack.
    """
    buf = bytearray(CHUNK)
    mv = memoryview(buf)
    received = 0
    h = hashlib.sha256()
    if on_progress:
        try:
            on_progress(0, expected_size)
        except Exception:
            pass
    with open(tmp_path, 'wb') as f:
        while received < expected_size:
            want = min(CHUNK, expected_size - received)
            n = cs.readinto(buf, want)
            if not n:
                break
            f.write(mv[:n])
            h.update(mv[:n])
            received += n
            if on_progress:
                try:
                    on_progress(received, expected_size)
                except Exception:
                    pass
            sleep_ms(YIELD_MS)
    return (received == expected_size) and (h.digest() == expected_digest)


def _pull_icons(cs, icon_dir, verbose=False):
    """Receive the icon leg into icon_dir. Returns the number promoted.

    Only reached by a device that passed icon_dir to pull(); the Box sends a
    count of 0 to anything else. Icons are data, not modules -- icon_store
    parses them as text -- so there is no compile check here, only the hash.
    A bad icon is dropped and the rest of the leg still runs: a missing
    picture is a better outcome than abandoning a game file that arrived
    intact.
    """
    try:
        os.mkdir(icon_dir)
    except OSError:
        pass
    head = cs.read(1)
    if not head:
        if verbose:
            print("[XFER] no icon leg (connection closed)")
        return 0
    count = head[0]
    if count > MAX_ICONS:
        raise OSError("icon count %d over limit %d" % (count, MAX_ICONS))
    if verbose:
        print("[XFER] icon leg: %d file(s)" % count)
    promoted = 0
    for i in range(count):
        size, digest, name = _read_file_header(cs)
        if size == 0:
            if verbose:
                print("[XFER] icon %d/%d: Box sent no file" % (i + 1, count))
            continue
        dest = icon_dir + '/' + name
        tmp_path = dest + '.part'
        good = _recv_body(cs, tmp_path, size, digest)
        if good:
            os.rename(tmp_path, dest)
            cs.write(b'OK')
            promoted += 1
            if verbose:
                print("[XFER] icon %s, %d bytes" % (dest, size))
        else:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            cs.write(b'NO')
            print("[XFER] icon FAILED: %s" % dest)
        sleep_ms(100)
    return promoted


def _log_visible_aps(nets, wanted):
    """Print every SSID the radio can see, flagging the one we wanted.

    Takes the nets from a scan the caller already did rather than scanning
    again. On the failure path we have just spent three scans; a fourth one
    only to print it added ~2.5s to the answer the user is waiting for.
    """
    if nets is None:
        print("[XFER] scan failed, nothing to report")
        return
    if not nets:
        print("[XFER] scan saw NO access points at all -- check the antenna")
        return
    print("[XFER] scan saw %d AP(s):" % len(nets))
    for net in nets:
        try:
            name = net[0].decode('utf-8')
        except Exception:
            name = str(net[0])
        mark = "  <-- wanted" if name == wanted else ""
        # scan() tuple: (ssid, bssid, channel, rssi, security, hidden).
        # Channel and security matter here: the Box's AP inherits the
        # channel of whatever else its radio is doing, and a security mode
        # the C6 won't accept looks the same from isconnected() alone.
        print("    %-24s ch=%s rssi=%s sec=%s%s"
              % (name, net[2], net[3], net[4], mark))


def _find_ap(sta, wanted, verbose):
    """Return (bssid, channel, nets) for wanted, or (None, None, nets).

    Hands back the raw scan results too, so a caller that ends up failing can
    log what was audible without paying for another scan.

    Reports the channel because that is the one radio property the wand and
    the Box must agree on, and because a channel outside the wand's
    regulatory domain is visible to a scan yet impossible to associate with.
    """
    try:
        nets = sta.scan()
    except Exception as e:
        if verbose:
            print("  pre-join scan failed: %s" % (e,))
        return None, None, None
    for net in nets:
        try:
            name = net[0].decode('utf-8')
        except Exception:
            continue
        if name == wanted:
            if verbose:
                print("  found %s on ch=%s rssi=%s sec=%s"
                      % (wanted, net[2], net[3], net[4]))
            return net[1], net[2], nets
    if verbose:
        print("  %s not in pre-join scan" % (wanted,))
    return None, None, nets


def _status_name(sta):
    """Decode sta.status() into a name, for join diagnostics.

    Distinguishes a wrong password from an AP that never answered, which
    isconnected() alone cannot. Built by lookup because which STAT_*
    constants exist varies by port and MicroPython version.
    """
    try:
        raw = sta.status()
    except (OSError, AttributeError):
        return "unavailable"
    for name in ('STAT_IDLE', 'STAT_CONNECTING', 'STAT_GOT_IP',
                 'STAT_WRONG_PASSWORD', 'STAT_NO_AP_FOUND',
                 'STAT_ASSOC_FAIL', 'STAT_BEACON_TIMEOUT',
                 'STAT_HANDSHAKE_TIMEOUT', 'STAT_CONNECT_FAIL'):
        if getattr(network, name, None) == raw:
            return "%s (%s)" % (name, raw)
    return str(raw)


def _reset_sta(verbose):
    """Return a STA interface clean enough to associate with an AP.

    ESPNowManager.shutdown() only calls enow.active(False) -- it leaves the
    STA active in whatever state ESP-NOW's init() put it in (active,
    disconnected, and channel-locked by the ESP-NOW driver). Calling
    connect() from there can scan and see the AP while never associating,
    which is exactly the "AP visible at good rssi but join times out" case.
    BBoxPrototype/c6_receiver.py never hit this because it ran standalone
    with no ESP-NOW; fully cycling the interface is what puts the radio back
    into that same known-good starting state.
    """
    sta = network.WLAN(network.STA_IF)
    try:
        if sta.active():
            sta.disconnect()
            sta.active(False)
            sleep_ms(RADIO_SETTLE_MS)
    except OSError:
        pass
    sta.active(True)
    sleep_ms(RADIO_SETTLE_MS)
    if verbose:
        print("  radio reset, status=%s" % _status_name(sta))
    return sta


def _shutdown_espnow(enow, verbose):
    """Release the radio from ESP-NOW before trying to join an AP.

    ESPNowManager.shutdown() now drops its espnow object itself, so the
    reach-through below is normally a no-op. It stays as a fallback for an
    older manager copy that only called active(False) and kept the object
    alive: while an espnow.ESPNow object holds the interface, sta.connect()
    is refused silently, leaving status at STAT_IDLE for the whole timeout
    instead of advancing to STAT_CONNECTING or reporting a failure.
    """
    try:
        enow.shutdown()
    except Exception as e:
        if verbose:
            print("  espnow manager shutdown raised: %s" % (e,))
    raw = getattr(enow, 'enow', None)
    if raw is None:
        return
    try:
        raw.active(False)
    except Exception as e:
        if verbose:
            print("  espnow active(False) raised: %s" % (e,))
    if verbose:
        try:
            print("  espnow active now: %s" % (raw.active(),))
        except Exception:
            pass
    try:
        enow.enow = None
    except Exception:
        pass
    gc.collect()
    sleep_ms(RADIO_SETTLE_MS)


def _notify(on_status, phase, tick):
    """Call the caller's status hook, ignoring anything it raises.

    Same contract as on_progress in pull(): the display is never allowed to
    break the transfer.
    """
    if on_status is None:
        return
    try:
        on_status(phase, tick)
    except Exception:
        pass


def _scan_for_ap(sta, ssid, verbose, on_status, tick, tries):
    """Look for `ssid` in up to `tries` scans.

    Returns (bssid, channel, tick, nets), where nets is the last scan's raw
    results so a failing caller can log them. bssid is None when it never showed
    up, which the caller turns into NoAP -- we scan before ever calling
    connect() precisely so that "the Box is off" is answered in seconds by a
    scan rather than in tens of seconds by a connect timeout.
    """
    nets = None
    for attempt in range(tries):
        _notify(on_status, 'scan', tick)
        tick += 1
        bssid, ch, nets = _find_ap(sta, ssid, verbose)
        if bssid is not None:
            return bssid, ch, tick, nets
        if verbose:
            print("[XFER] scan %d/%d: %s not visible" % (attempt + 1, tries, ssid))
    return None, None, tick, nets


def _connect_wifi(ssid, pwd, external_antenna, verbose, enow=None,
                  on_status=None):
    if enow is not None:
        _shutdown_espnow(enow, verbose)
    # Always select, either way -- see _configure_antenna() docstring for why
    # "leave the pins alone" isn't a safe default here.
    _configure_antenna(external_antenna, verbose)

    tick = 0
    last_status = "unknown"
    for attempt in range(JOIN_ATTEMPTS):
        sta = _reset_sta(verbose)
        try:
            prev_pm = sta.config('pm')
        except (ValueError, OSError, AttributeError):
            prev_pm = None

        # Point the driver at one specific AP rather than trusting whatever
        # channel it thinks it is on. ESP-NOW pins the radio to a channel
        # while it runs, and that pin can outlive the teardown -- connecting
        # by BSSID makes the driver resolve the AP from a fresh scan, which
        # is the same reason an ESP-NOW-only peer has to be handed the
        # channel of the AP the other side is associated with.
        # Only the first pass spends the full scan budget. By the second we
        # have already seen the AP once, so one confirming scan is enough --
        # re-spending three would double the cost of the slowest failure.
        tries = SCAN_ATTEMPTS if attempt == 0 else 1
        bssid, found_ch, tick, nets = _scan_for_ap(sta, ssid, verbose,
                                                   on_status, tick, tries)
        if bssid is None:
            # Not visible on the first pass: the AP is not up. Say so now
            # instead of spending a join timeout (and then a second attempt)
            # proving it the slow way. If it vanished only on the retry it was
            # up a moment ago, so that is a flaky join, not a missing Box.
            if verbose:
                _log_visible_aps(nets, ssid)
            if attempt == 0:
                raise NoAP("%s not visible in %d scans" % (ssid, SCAN_ATTEMPTS))
            raise JoinFailed("%s vanished between join attempts" % (ssid,))

        try:
            sta.connect(ssid, pwd, bssid=bssid)
        except TypeError:
            # Older builds have no bssid kwarg.
            sta.connect(ssid, pwd)
        # Sample status through the wait, not just at the end. A run that
        # never leaves STAT_IDLE means connect() was refused and no attempt
        # was ever made (driver still held elsewhere); one that reaches
        # STAT_CONNECTING and falls back means the association itself failed.
        waited = 0
        seen = []
        while not sta.isconnected() and waited < CONNECT_TIMEOUT_S * 1000:
            st = _status_name(sta)
            if st not in seen:
                seen.append(st)
            _notify(on_status, 'join', tick)
            tick += 1
            sleep_ms(200)
            waited += 200
        if verbose:
            print("  status seen while joining: %s" % (', '.join(seen) or 'none',))

        if sta.isconnected():
            try:
                sta.config(pm=0)
            except (ValueError, OSError, AttributeError) as e:
                if verbose:
                    print("[XFER] WARNING: could not disable power-save: %s" % (e,))
            if verbose:
                print("  joined %s, ip=%s" % (ssid, sta.ifconfig()[0]))
            return sta, prev_pm

        last_status = _status_name(sta)
        if verbose:
            print("[XFER] join attempt %d/%d failed, status=%s"
                  % (attempt + 1, JOIN_ATTEMPTS, last_status))

    # The AP was visible every time, so this is association/auth, not radio
    # or range -- still worth logging what we could hear before giving up.
    if verbose:
        _log_visible_aps(nets, ssid)
    raise JoinFailed("could not join %s within %ds (status=%s)"
                     % (ssid, CONNECT_TIMEOUT_S, last_status))


def pull(host=HOST, port=PORT, ssid=SSID, pwd=PWD,
         external_antenna=EXTERNAL_ANTENNA, verbose=False, enow=None,
         on_progress=None, on_status=None, slug="", hubtype="",
         icon_dir=None):
    """Pull one game file from the Box. Returns True on verified promote.

    slug names the game to ask for; "" means "whatever the Box has active".
    It comes from the tapped card ("getcode:<slug>") by way of pull_flag,
    since the tap and the pull happen in different boots.

    hubtype says what kind of device is asking, so the Box can hand a wand
    and an icon display different files for the same slug. Pass HUB_TYPE
    from lib/hubtype.py. Leaving it "" sends the older request frame, which
    a Box always answers with the wand file.

    icon_dir, when set, asks for the icon leg after the game file and writes
    what arrives into that directory. A device with no panel leaves it None.

    on_progress(received, expected_size), if given, is called after each
    chunk is written to flash -- lets the caller drive an LED progress
    indicator without this module knowing anything about LEDs. Wrapped in
    try/except so a bad callback can't break the transfer.

    on_status(phase, tick), if given, is called repeatedly while the radio is
    working -- phase is 'scan' or 'join' and tick is a free-running counter,
    which is exactly what an LED animation needs. Also wrapped in try/except.

    Returns, in order of how the caller should treat them:

      True          the file arrived, verified and was promoted.
      'noap'        the Box's SSID was never seen. Do not retry: nothing on
                    this wand can make an AP that is not up appear.
      'nojoin'      the AP was there but the join or the connection to the
                    server failed before any of the file arrived. Do not
                    retry -- a second boot joins the same AP the same way.
      'norequest'   the Box answered that it has no such game. Do not retry;
                    a retry cannot change the answer.
      False         the transfer itself failed partway through. This one IS
                    worth retrying: the pieces are all present and it is the
                    kind of failure a fresh radio often gets past.
    """
    ok = False
    # Everything up to the first body byte is "setup": a failure there is a
    # pairing problem, not a transfer problem, and the two get different
    # treatment by the caller (give up vs. reboot and retry).
    body_started = False
    cs = None
    sta = None
    prev_pm = None
    memprobe.probe("pull:entry")  # BENCH
    try:
        # Inside the try: _connect_wifi() raises OSError if the Box's AP
        # never shows up, and it has already called enow.shutdown() by
        # then. Letting that escape left ESP-NOW dead, the STA still
        # active, and the caller unable to tell a failure from a crash --
        # it skipped the caller's own failure handling entirely.
        #
        # BENCH: this sta.active(True) is structurally the same allocation
        # as enow.init()'s -- esp_wifi_init()/esp_wifi_start() on a radio
        # that has never run WiFi this boot. It is the pull's own OOM risk
        # point, distinct from (and in addition to) the *next* boot's
        # enow.init(). frag() brackets it the same way main.py's pre-enow
        # probe does.
        memprobe.frag("pull:pre-wifi-join")  # BENCH
        sta, prev_pm = _connect_wifi(ssid, pwd, external_antenna, verbose,
                                     enow=enow, on_status=on_status)
        memprobe.probe("pull:post-wifi-join")  # BENCH

        cs = socket.socket()
        cs.settimeout(SOCK_TIMEOUT_S)
        cs.connect((host, port))
        if verbose:
            print("[XFER] connected to %s:%d" % (host, port))
        memprobe.probe("pull:post-sock-connect")  # BENCH

        # ── Request frame: the requester speaks first ── see REQ_V2.
        _write_request(cs, slug, hubtype, verbose)

        expected_size, expected_digest, name = _read_file_header(cs)
        if expected_size == 0:
            # Explicit refusal: the Box has no such game for this kind of
            # device. Distinct from a transfer failure -- retrying cannot
            # change the answer, so say so.
            if verbose:
                print("[XFER] Box has no game %r for %r"
                      % (slug or "<active>", hubtype or "<v1>"))
            return 'norequest'

        # Pulled games live in /games, never the flash root -- they must not
        # be able to shadow a built-in game or main.py. See lib/game_store.py.
        game_store.ensure_dir()
        dest = game_store.GAMES_DIR + '/' + name
        tmp_path = dest + '.part'

        if verbose:
            print("[XFER] receiving %s, %d bytes expected" % (dest, expected_size))
        # BENCH: the transfer body is the peak-memory window of the whole
        # pull -- socket buffers, the sha256 hasher, and the chunk buffer
        # are all live at once. This is the state that matters most for
        # "how fragile is a pull", not just before/after the whole call.
        memprobe.probe("pull:pre-body")  # BENCH

        body_started = True
        good = _recv_body(cs, tmp_path, expected_size, expected_digest, on_progress)

        memprobe.probe("pull:post-body")  # BENCH

        if not good:
            if verbose:
                print("[XFER] FAILED: %s did not arrive intact" % dest)
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            cs.write(b'NO')
            sleep_ms(100)
        elif not _compiles(tmp_path, verbose):
            # Bytes arrived intact but the file is not importable. Promoting
            # it would replace a working game with one that can only fail at
            # _load_play() time, on a device with no way to show a traceback.
            # Keep the old game, discard this one, and report failure.
            good = False
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            cs.write(b'NO')
            sleep_ms(100)
        else:
            try:
                os.rename(dest, dest + '.bak')
            except OSError:
                pass
            os.rename(tmp_path, dest)
            cs.write(b'OK')
            sleep_ms(100)
            if verbose:
                print("[XFER] OK: %s promoted, %d bytes" % (dest, expected_size))
            # Remember what we just pulled so the boot after the imminent
            # reset can launch it instead of dropping into the idle loop.
            if name.endswith('.py'):
                game_store.set_last_pulled(name[:-3])
            ok = True
        memprobe.probe("pull:post-promote")  # BENCH

        # ── Icon leg ── only a device that asked for one reads this. The
        # game file is already promoted and acked by here, so an icon that
        # fails costs a picture, not the game.
        if ok and icon_dir:
            try:
                n_icons = _pull_icons(cs, icon_dir, verbose)
                if verbose:
                    print("[XFER] %d icon(s) promoted" % n_icons)
            except OSError as e:
                print("[XFER] icon leg failed: %s" % (e,))
            memprobe.probe("pull:post-icons")  # BENCH

    except NoAP as e:
        if verbose:
            print("[XFER] no AP: %s" % (e,))
        memprobe.probe("pull:exception")  # BENCH
        ok = 'noap'
    except JoinFailed as e:
        if verbose:
            print("[XFER] join failed: %s" % (e,))
        memprobe.probe("pull:exception")  # BENCH
        ok = 'nojoin'
    except OSError as e:
        if verbose:
            print("[XFER] failed: %s" % (e,))
        memprobe.probe("pull:exception")  # BENCH
        # Before the body started this is still the setup phase (socket
        # connect, request, header) -- same "give up" class as a bad join.
        if not body_started:
            ok = 'nojoin'
    finally:
        if cs is not None:
            cs.close()
        # sta stays None if _connect_wifi() itself failed early.
        if sta is not None:
            try:
                if prev_pm is not None:
                    sta.config(pm=prev_pm)
            except (ValueError, OSError, AttributeError):
                pass
            try:
                sta.disconnect()
                sta.active(False)
            except OSError:
                pass
        gc.collect()
        memprobe.probe("pull:cleanup")  # BENCH -- what the NEXT reset inherits

    return ok
