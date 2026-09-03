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

REV = "phase0-2026-09-01"
print("# code_puller rev", REV)

HOST = '192.168.4.1'
PORT = 8266
SSID = 'SP-FILEPUSH'
PWD = 'playground1'

CHUNK = 512
YIELD_MS = 20

CONNECT_TIMEOUT_S = 15
SOCK_TIMEOUT_S = 30

# Settle time after toggling the STA interface off/on. The driver needs a
# moment before connect() will take; without it the reset is cosmetic.
RADIO_SETTLE_MS = 300
# One retry: the first join after ESP-NOW teardown is the flaky one.
JOIN_ATTEMPTS = 2

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


def _log_visible_aps(sta, wanted):
    """Print every SSID the radio can see, flagging the one we wanted."""
    try:
        nets = sta.scan()
    except Exception as e:
        print("[XFER] scan failed: %s" % (e,))
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
    """Return (bssid, channel) for wanted from a fresh scan, or (None, None).

    Reports the channel because that is the one radio property the wand and
    the Box must agree on, and because a channel outside the wand's
    regulatory domain is visible to a scan yet impossible to associate with.
    """
    try:
        nets = sta.scan()
    except Exception as e:
        if verbose:
            print("  pre-join scan failed: %s" % (e,))
        return None, None
    for net in nets:
        try:
            name = net[0].decode('utf-8')
        except Exception:
            continue
        if name == wanted:
            if verbose:
                print("  found %s on ch=%s rssi=%s sec=%s"
                      % (wanted, net[2], net[3], net[4]))
            return net[1], net[2]
    if verbose:
        print("  %s not in pre-join scan" % (wanted,))
    return None, None


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


def _connect_wifi(ssid, pwd, external_antenna, verbose, enow=None):
    if enow is not None:
        _shutdown_espnow(enow, verbose)
    # Always select, either way -- see _configure_antenna() docstring for why
    # "leave the pins alone" isn't a safe default here.
    _configure_antenna(external_antenna, verbose)

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
        bssid, found_ch = _find_ap(sta, ssid, verbose)
        try:
            if bssid is not None:
                sta.connect(ssid, pwd, bssid=bssid)
            else:
                sta.connect(ssid, pwd)
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

    # Log what the radio can actually hear before giving up: an empty scan
    # points at the antenna (external selects the u.FL connector -- nothing
    # attached means almost no range), other SSIDs but not this one points at
    # the Box's AP not being up, and this one present at a usable rssi points
    # at association/auth rather than radio or range.
    if verbose:
        _log_visible_aps(sta, ssid)
    raise OSError("could not join %s within %ds (status=%s)"
                  % (ssid, CONNECT_TIMEOUT_S, last_status))


def pull(host=HOST, port=PORT, ssid=SSID, pwd=PWD,
         external_antenna=EXTERNAL_ANTENNA, verbose=False, enow=None,
         on_progress=None):
    """Pull one file from the Box. Returns True on verified promote.

    on_progress(received, expected_size), if given, is called after each
    chunk is written to flash -- lets the caller drive an LED progress
    indicator without this module knowing anything about LEDs. Wrapped in
    try/except so a bad callback can't break the transfer.
    """
    ok = False
    cs = None
    sta = None
    prev_pm = None
    try:
        # Inside the try: _connect_wifi() raises OSError if the Box's AP
        # never shows up, and it has already called enow.shutdown() by
        # then. Letting that escape left ESP-NOW dead, the STA still
        # active, and the caller unable to tell a failure from a crash --
        # it skipped the caller's own failure handling entirely.
        sta, prev_pm = _connect_wifi(ssid, pwd, external_antenna, verbose, enow=enow)

        cs = socket.socket()
        cs.settimeout(SOCK_TIMEOUT_S)
        cs.connect((host, port))
        if verbose:
            print("[XFER] connected to %s:%d" % (host, port))

        header = _read_exact(cs, 4 + 32 + 1)
        expected_size = int.from_bytes(header[0:4], 'big')
        expected_digest = header[4:36]
        name_len = header[36]
        dest = _read_exact(cs, name_len).decode('utf-8')
        tmp_path = dest + '.part'

        if verbose:
            print("[XFER] receiving %s, %d bytes expected" % (dest, expected_size))
            print("  mem_free before body: %d" % gc.mem_free())

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

        if verbose:
            print("  mem_free after body:  %d" % gc.mem_free())

        good = (received == expected_size) and (h.digest() == expected_digest)

        if not good:
            if verbose:
                print("[XFER] FAILED: got %d/%d bytes" % (received, expected_size))
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
                print("[XFER] OK: %s promoted, %d bytes" % (dest, received))
            ok = True

    except OSError as e:
        if verbose:
            print("[XFER] failed: %s" % (e,))
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

    return ok
