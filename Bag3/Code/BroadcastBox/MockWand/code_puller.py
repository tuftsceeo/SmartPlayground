"""
code_puller.py — join Broadcast Box SoftAP and pull jumpin.py (Mock Wand).

Adapted from BBoxPrototype/c6_receiver.py. Calls enow.shutdown() before
WiFi connect; external_antenna=True for Wand Module PCB (GPIO 3/14).
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
    if Pin is None:
        return
    wifi_en = Pin(3, Pin.OUT)
    ant_cfg = Pin(14, Pin.OUT)
    wifi_en.value(0)
    sleep_ms(100)
    ant_cfg.value(1)


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


def _connect_wifi(ssid, pwd, external_antenna, verbose, enow=None):
    if enow is not None:
        try:
            enow.shutdown()
        except Exception:
            pass
    if external_antenna:
        _configure_external_antenna()
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
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
    try:
        sta.config(pm=0)
    except (ValueError, OSError, AttributeError) as e:
        if verbose:
            print("[XFER] WARNING: could not disable power-save: %s" % (e,))
    if verbose:
        print("  joined %s, ip=%s" % (ssid, sta.ifconfig()[0]))
    return sta, prev_pm


def pull(host=HOST, port=PORT, ssid=SSID, pwd=PWD,
         external_antenna=True, verbose=False, enow=None):
    """Pull one file from the Box. Returns True on verified promote."""
    sta, prev_pm = _connect_wifi(ssid, pwd, external_antenna, verbose, enow=enow)

    ok = False
    cs = None
    try:
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
