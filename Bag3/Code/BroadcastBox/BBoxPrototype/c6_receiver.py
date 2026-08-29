"""
c6_receiver.py - joins the S3's SoftAP and pulls one file (runs on the C6)
===========================================================================

Half of a prototype for pushing a .py file from the Mac to a Xiao ESP32-C6
without a cable on the C6 end. Pairs with s3_sender.py.

This is NOT esp32.Partition firmware OTA - no .bin, no A/B partition swap.
It is a plain write into this board's MicroPython filesystem.

Usage (from the Mac, once the S3 has printed that its AP is up):

    mpremote connect <c6-port> exec "import c6_receiver; c6_receiver.pull()"

Wire protocol - see s3_sender.py / README.md for the byte layout.
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

HOST = '192.168.4.1'
PORT = 8266
SSID = 'SP-FILEPUSH'
PWD = 'playground1'

CHUNK = 512
YIELD_MS = 20

CONNECT_TIMEOUT_S = 15
SOCK_TIMEOUT_S = 30


def _configure_external_antenna():
    """External-antenna GPIO switch for the Wand Module's C6 PCB.

    Mirrors _configure_external_antenna() in Bag3/Code/lib/espnow_manager.py.
    Inlined rather than imported so this script has no /lib dependency and
    runs standalone on a bare board.

    This is specific to the Wand Module's PCB wiring (GPIO3/14), not a
    generic C6 property. Confirmed against real hardware: on a bare Xiao
    ESP32-C6 dev board (no Wand PCB) this raises "OSError: Wifi Internal
    Error" on the following sta.connect() - toggling these pins put the
    radio in a bad state on that board. Leave external_antenna=False unless
    you are actually on Wand Module hardware.
    """
    if Pin is None:
        return
    wifi_en = Pin(3, Pin.OUT)
    ant_cfg = Pin(14, Pin.OUT)
    wifi_en.value(0)
    sleep_ms(100)
    ant_cfg.value(1)  # external antenna


def _read_exact(sock, n):
    """Read exactly n bytes or raise. A bare recv(n)/read(n) can legitimately
    return short on a TCP socket - looping here is required, not defensive
    paranoia."""
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


def _connect_wifi(ssid, pwd, external_antenna, verbose):
    if external_antenna:
        _configure_external_antenna()
    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    # Remember the board's power-save posture so it can be restored after the
    # transfer window - this runs once a day, no reason to hold the radio
    # awake continuously.
    try:
        prev_pm = sta.config('pm')
    except (ValueError, OSError, AttributeError):
        prev_pm = None

    sta.connect(ssid, pwd)
    waited = 0
    while not sta.isconnected():
        sleep_ms(200)
        waited += 200
        if waited >= CONNECT_TIMEOUT_S * 1000:
            raise OSError("could not join %s within %ds" % (ssid, CONNECT_TIMEOUT_S))

    # Required, not optional: disables 802.11 power-save so the radio doesn't
    # doze between beacons (DTIM interval, ~100-300ms). This is a MAC-layer
    # sleep state - no amount of sleep_ms() yielding between chunks can reach
    # it, which is why this is a separate fix from YIELD_MS below.
    try:
        sta.config(pm=0)
    except (ValueError, OSError, AttributeError) as e:
        print("[XFER] WARNING: could not disable power-save (pm=0): %s" % (e,))

    if verbose:
        print("  joined %s, ip=%s" % (ssid, sta.ifconfig()[0]))
    return sta, prev_pm


def pull(host=HOST, port=PORT, ssid=SSID, pwd=PWD,
         external_antenna=False, verbose=False):
    """Connect to the S3, pull one file, verify it, and atomically promote
    it into place. Returns True on a verified, promoted file.

    external_antenna is off by default - it is Wand Module PCB-specific
    (GPIO3/14), not a generic C6 property, and breaks plain WiFi connect on
    a bare Xiao C6 dev board (confirmed against hardware). Only set it True
    when actually running on Wand Module hardware.
    """
    sta, prev_pm = _connect_wifi(ssid, pwd, external_antenna, verbose)

    ok = False
    cs = None
    try:
        cs = socket.socket()
        cs.settimeout(SOCK_TIMEOUT_S)
        cs.connect((host, port))
        print("[XFER] connected to %s:%d" % (host, port))

        header = _read_exact(cs, 4 + 32 + 1)
        expected_size = int.from_bytes(header[0:4], 'big')
        expected_digest = header[4:36]
        name_len = header[36]
        dest = _read_exact(cs, name_len).decode('utf-8')
        tmp_path = dest + '.part'

        print("[XFER] receiving %s, %d bytes expected" % (dest, expected_size))
        if verbose:
            print("  mem_free before body: %d" % gc.mem_free())

        buf = bytearray(CHUNK)
        mv = memoryview(buf)
        received = 0
        h = hashlib.sha256()

        with open(tmp_path, 'wb') as f:
            while received < expected_size:
                want = min(CHUNK, expected_size - received)
                n = cs.readinto(buf, want)
                if not n:
                    break
                f.write(mv[:n])
                h.update(mv[:n])
                received += n
                sleep_ms(YIELD_MS)

        if verbose:
            print("  mem_free after body:  %d" % gc.mem_free())

        good = (received == expected_size) and (h.digest() == expected_digest)

        if not good:
            print("[XFER] FAILED: got %d/%d bytes, digest_ok=%s" %
                  (received, expected_size, h.digest() == expected_digest))
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            cs.write(b'NO')
            # Give TCP a moment to actually flush before the finally block
            # closes the socket - an immediate close after write can drop
            # the last write on this stack (confirmed against real hardware:
            # the sender hung in its reply read without this).
            sleep_ms(100)
        else:
            try:
                os.rename(dest, dest + '.bak')
            except OSError:
                pass  # no previous file - normal on a first push
            os.rename(tmp_path, dest)
            cs.write(b'OK')
            sleep_ms(100)  # let TCP flush before close - see comment above
            print("[XFER] OK: %s promoted, %d bytes, sha256 verified" % (dest, received))
            ok = True

    except OSError as e:
        print("[XFER] failed: %s" % (e,))
    finally:
        if cs is not None:
            cs.close()
        # Restore power posture before releasing the radio.
        try:
            if prev_pm is not None:
                sta.config(pm=prev_pm)
        except (ValueError, OSError, AttributeError):
            pass
        sta.disconnect()
        sta.active(False)
        gc.collect()  # clean heap before whatever imports the new file next

    return ok
