"""
code_puller.py — join a Broadcast Box/Dial SoftAP and pull one game file.

Icon Display copy; same code as MockWand/code_puller.py except the antenna
fallback. main.py passes hubtype="icon_display" and an icon_dir.
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

# BENCH: heap probes (lib/memprobe.py). Optional; a no-op stand-in is used
# when the module is absent.
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

# PEER: SSID/PWD/PORT/CHUNK/YIELD_MS and the wire protocol are mirrored by
# hand in BBoxFirmware/ and BDialFirmware/code_server.py and in the MockWand
# and SplatCompanion pullers. Change them together.
HOST = '192.168.4.1'
PORT = 8266
# Host SSIDs are "SP-FILEPUSH-<id>" (code_server.HOST_ID). SSID is an alias
# of SSID_PREFIX, kept for log call sites and as pull()'s `ssid` default.
SSID_PREFIX = 'SP-FILEPUSH'
SSID = SSID_PREFIX
PWD = 'playground1'

CHUNK = 512
YIELD_MS = 20

# Diagnostic switch. This module is imported before sta.active(True) claims
# the radio's memory, so diagnostic strings live in pull_probe.py, imported
# only when this is True and only after the join. Nothing added to this
# module may allocate ahead of the radio (AGENTS.md).
DEBUG_PULL = False

# Wire protocol. Request (requester speaks first):
#   v1:  len(1) | slug
#   v2:  0xFF | len(1) | slug | len(1) | hubtype
# Slugs are at most 16 bytes, so a first byte of 0xFF marks v2.
# Response, per file: size(4B BE) | sha256(32B) | name_len(1B) | name, the
# body in CHUNK-byte pieces, then a 2-byte b'OK'/b'NO' ack from this side.
# size 0 is a refusal and carries nothing else. With icon_dir set, a 1-byte
# icon count follows the game's ack, then that many files in the same shape.
REQ_V2 = 0xFF
MAX_ICONS = 64

# Per-join-attempt association timeout. connect() is only called after a
# scan has found the AP.
CONNECT_TIMEOUT_S = 6
# Socket idle timeout, per recv. Must stay above code_server.py's
# SOCK_REPLY_TIMEOUT_S (8 s) so the host reaps a stalled transfer first.
SOCK_TIMEOUT_S = 12

# Scans on the first join attempt before reporting NoAP.
SCAN_ATTEMPTS = 3

# Wait after each STA active(False)/active(True) before the next call.
RADIO_SETTLE_MS = 300
# Join attempts per pull boot; each re-cycles the STA interface.
JOIN_ATTEMPTS = 2


class NoAP(OSError):
    """The host's SSID was not seen in any scan on the first attempt."""


class JoinFailed(OSError):
    """The SSID was visible but the join did not complete."""

# espnow_manager owns the antenna setting (it drives the same pins). The
# fallback applies only on a board without /lib; this device has no
# external antenna.
try:
    from espnow_manager import EXTERNAL_ANTENNA
except ImportError:
    EXTERNAL_ANTENNA = False


def _configure_antenna(external, verbose=False):
    """Drive the XIAO ESP32-C6 RF switch to the onboard or u.FL antenna.

    GPIO3 = switch enable (active low), GPIO14 = select (0 onboard,
    1 external). Both pins are driven for either selection.
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
    """True if `path` compiles. Runs no module code.

    Reads the whole file, so it needs a free block about the file's size;
    a MemoryError is reported like a syntax error.
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
    """Send the v1 or v2 request frame (see REQ_V2)."""
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
    """Read one file header. Returns (size, digest, name); size 0 = refusal."""
    size = int.from_bytes(_read_exact(cs, 4), 'big')
    if size == 0:
        return 0, b'', ''
    head = _read_exact(cs, 32 + 1)
    name = _read_exact(cs, head[32]).decode('utf-8')
    return size, head[0:32], name


def _recv_body(cs, tmp_path, expected_size, expected_digest, on_progress=None,
               probe=None):
    """Write one file body to tmp_path. True if length and sha256 match.

    Does not promote, delete or ack. Sleeps YIELD_MS after each chunk.
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
            if probe is not None:
                probe.step(received, expected_size)
            sleep_ms(YIELD_MS)
    if probe is not None:
        probe.done(received, expected_size)
    return (received == expected_size) and (h.digest() == expected_digest)


def _pull_icons(cs, icon_dir, verbose=False):
    """Receive the icon leg into icon_dir. Returns the number promoted.

    Icons are hash-checked only, not compiled. A failed icon is acked NO and
    the leg continues.
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


def _wanted_ssid(prefix, host_id):
    """The exact SSID for host_id, or None for any "<prefix>*" host."""
    return (prefix + '-' + host_id) if host_id else None


def _log_visible_aps(nets, prefix, host_id):
    """Print the caller's scan results, marking the wanted SSID(s)."""
    wanted = _wanted_ssid(prefix, host_id)
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
        if wanted is not None:
            mark = "  <-- wanted" if name.lower() == wanted.lower() else ""
        else:
            mark = "  <-- candidate" if name.startswith(prefix) else ""
        # scan() tuple: (ssid, bssid, channel, rssi, security, hidden).
        print("    %-24s ch=%s rssi=%s sec=%s%s"
              % (name, net[2], net[3], net[4], mark))


def _find_ap(sta, prefix, host_id, verbose):
    """Scan once. Returns (ssid, bssid, channel, nets) or (None, None, None, nets).

    With host_id: exact, case-insensitive match on "<prefix>-<host_id>".
    Without: the strongest-RSSI "<prefix>*" SSID. nets is the raw scan
    result, or None if scan() raised.
    """
    try:
        nets = sta.scan()
    except Exception as e:
        if verbose:
            print("  pre-join scan failed: %s" % (e,))
        return None, None, None, None
    wanted = _wanted_ssid(prefix, host_id)
    best = None  # (rssi, ssid, bssid, channel)
    for net in nets:
        try:
            name = net[0].decode('utf-8')
        except Exception:
            continue
        if wanted is not None:
            if name.lower() != wanted.lower():
                continue
        elif not name.startswith(prefix):
            continue
        rssi = net[3]
        if best is None or rssi > best[0]:
            best = (rssi, name, net[1], net[2])
    if best is None:
        if verbose:
            print("  %s not in pre-join scan" % (wanted or (prefix + '*'),))
        return None, None, None, nets
    if verbose:
        print("  found %s on ch=%s rssi=%s" % (best[1], best[3], best[0]))
    return best[1], best[2], best[3], nets


def _status_name(sta):
    """sta.status() as "NAME (value)"; STAT_* constants vary by port."""
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


def _reset_sta(external_antenna, verbose):
    """Cycle the STA interface off and on and return it.

    The antenna is selected before every active(True): GPIO3 is also the
    driver's WIFI_ENABLE line and is not assumed to survive active(False).
    """
    sta = network.WLAN(network.STA_IF)
    try:
        if sta.active():
            sta.disconnect()
            sta.active(False)
            sleep_ms(RADIO_SETTLE_MS)
    except OSError:
        pass
    _configure_antenna(external_antenna, verbose)
    sta.active(True)
    sleep_ms(RADIO_SETTLE_MS)
    if verbose:
        print("  radio reset, status=%s" % _status_name(sta))
    return sta


def _shutdown_espnow(enow, verbose):
    """Shut ESP-NOW down and drop its object before a WiFi join.

    A live espnow.ESPNow object makes sta.connect() stay at STAT_IDLE. The
    direct active(False) is a fallback for manager copies that keep it.
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
    """Call on_status(phase, tick); exceptions from it are ignored."""
    if on_status is None:
        return
    try:
        on_status(phase, tick)
    except Exception:
        pass


def _scan_for_ap(sta, prefix, host_id, verbose, on_status, tick, tries):
    """Scan up to `tries` times. Returns (ssid, bssid, channel, tick, nets).

    ssid and bssid are None if no match was seen; nets is the last scan.
    """
    nets = None
    wanted = _wanted_ssid(prefix, host_id) or (prefix + '*')
    for attempt in range(tries):
        _notify(on_status, 'scan', tick)
        tick += 1
        ssid, bssid, ch, nets = _find_ap(sta, prefix, host_id, verbose)
        if bssid is not None:
            return ssid, bssid, ch, tick, nets
        if verbose:
            print("[XFER] scan %d/%d: %s not visible" % (attempt + 1, tries, wanted))
    return None, None, None, tick, nets


def _connect_wifi(ssid_prefix, pwd, host_id, external_antenna, verbose,
                  enow=None, on_status=None):
    if enow is not None:
        _shutdown_espnow(enow, verbose)
    wanted = _wanted_ssid(ssid_prefix, host_id) or (ssid_prefix + '*')
    tick = 0
    last_status = "unknown"
    for attempt in range(JOIN_ATTEMPTS):
        sta = _reset_sta(external_antenna, verbose)
        try:
            prev_pm = sta.config('pm')
        except (ValueError, OSError, AttributeError):
            prev_pm = None

        # Full scan budget on the first attempt, one scan on the second.
        tries = SCAN_ATTEMPTS if attempt == 0 else 1
        found_ssid, bssid, found_ch, tick, nets = _scan_for_ap(
            sta, ssid_prefix, host_id, verbose, on_status, tick, tries)
        if bssid is None:
            if verbose:
                _log_visible_aps(nets, ssid_prefix, host_id)
            if attempt == 0:
                raise NoAP("%s not visible in %d scans" % (wanted, SCAN_ATTEMPTS))
            raise JoinFailed("%s vanished between join attempts" % (wanted,))

        try:
            sta.connect(found_ssid, pwd, bssid=bssid)
        except TypeError:
            # Older builds have no bssid kwarg.
            sta.connect(found_ssid, pwd)
        # Record every status seen during the wait: STAT_IDLE throughout
        # means connect() did not start; STAT_CONNECTING then a fall back
        # means the association or handshake failed.
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
            if DEBUG_PULL:
                import pull_probe
                pull_probe.joined(sta, found_ssid, bssid, found_ch, nets,
                                  ssid_prefix, tick)
            try:
                sta.config(pm=0)
            except (ValueError, OSError, AttributeError) as e:
                if verbose:
                    print("[XFER] WARNING: could not disable power-save: %s" % (e,))
            if verbose:
                print("  joined %s, ip=%s" % (found_ssid, sta.ifconfig()[0]))
            return sta, prev_pm

        last_status = _status_name(sta)
        if verbose:
            print("[XFER] join attempt %d/%d failed, status=%s"
                  % (attempt + 1, JOIN_ATTEMPTS, last_status))

    if verbose:
        _log_visible_aps(nets, ssid_prefix, host_id)
    raise JoinFailed("could not join %s within %ds (status=%s)"
                     % (wanted, CONNECT_TIMEOUT_S, last_status))


def pull(host=HOST, port=PORT, ssid=SSID, pwd=PWD,
         external_antenna=EXTERNAL_ANTENNA, verbose=False, enow=None,
         on_progress=None, on_status=None, slug="", hubtype="",
         icon_dir=None, host_id=""):
    """Join a Box/Dial SoftAP and pull one game file.

    ssid: SSID prefix. host_id: pin the pull to "<ssid>-<host_id>"; empty
    takes the strongest "<ssid>*" host. slug: game to request; empty asks
    for the host's active game. hubtype: sent in a v2 request; empty sends
    v1, which the host answers with the wand file. icon_dir: request the
    icon leg and write it there. on_progress(received, total) runs after
    each chunk; on_status(phase, tick) runs during scan and join. Exceptions
    from either callback are ignored.

    Returns:
      True         file verified, compiled and promoted
      'noap'       no matching SSID seen
      'nojoin'     join failed, or socket/request/header failed before the body
      'norequest'  host refused (size 0)
      False        body failed, hash mismatch, or compile() rejected the file
    """
    ok = False
    # An OSError before the first body byte returns 'nojoin', after it False.
    body_started = False
    cs = None
    sta = None
    prev_pm = None
    memprobe.probe("pull:entry")  # BENCH
    try:
        # BENCH: frag() records the heap just before sta.active(True), the
        # pull boot's radio memory claim.
        memprobe.frag("pull:pre-wifi-join")  # BENCH
        sta, prev_pm = _connect_wifi(ssid, pwd, host_id, external_antenna,
                                     verbose, enow=enow, on_status=on_status)
        memprobe.probe("pull:post-wifi-join")  # BENCH

        cs = socket.socket()
        cs.settimeout(SOCK_TIMEOUT_S)
        cs.connect((host, port))
        if verbose:
            print("[XFER] connected to %s:%d" % (host, port))
        memprobe.probe("pull:post-sock-connect")  # BENCH

        _write_request(cs, slug, hubtype, verbose)

        expected_size, expected_digest, name = _read_file_header(cs)
        if expected_size == 0:
            if verbose:
                print("[XFER] Box has no game %r for %r"
                      % (slug or "<active>", hubtype or "<v1>"))
            return 'norequest'

        # Pulled games go in /games so they cannot shadow flash-root modules.
        game_store.ensure_dir()
        dest = game_store.GAMES_DIR + '/' + name
        tmp_path = dest + '.part'

        if verbose:
            print("[XFER] receiving %s, %d bytes expected" % (dest, expected_size))
        memprobe.probe("pull:pre-body")  # BENCH

        body_started = True
        _probe = None
        if DEBUG_PULL:
            import pull_probe
            _probe = pull_probe.BodyProbe(sta)
        good = _recv_body(cs, tmp_path, expected_size, expected_digest,
                          on_progress, probe=_probe)

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
            # Intact but does not compile: keep the previous game.
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
            # The next boot launches the last pulled game.
            if name.endswith('.py'):
                game_store.set_last_pulled(name[:-3])
            ok = True
        memprobe.probe("pull:post-promote")  # BENCH

        # Icon leg. An icon failure does not change the game's result.
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
        if not body_started:
            ok = 'nojoin'
    finally:
        if cs is not None:
            cs.close()
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
        memprobe.probe("pull:cleanup")  # BENCH

    return ok
