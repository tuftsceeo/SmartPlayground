"""
s3_sender.py - SoftAP + TCP file server (runs on the ESP32-S3)
==============================================================

Half of a prototype for pushing a .py file from the Mac to a Xiao ESP32-C6
without a cable on the C6 end. The Mac stages the file onto this board over
USB with mpremote; this script puts up a SoftAP and serves the file to one
C6 running c6_receiver.py.

This is NOT esp32.Partition firmware OTA - no .bin, no A/B partition swap.
It is a plain write into the C6's MicroPython filesystem.

Usage (from the Mac, two terminals - see README.md):

    mpremote connect <s3-port> cp ./payload.py :payload.py
    mpremote connect <s3-port> exec "import s3_sender; s3_sender.serve('payload.py', 'pushed.py')"

Wire protocol (see README.md):
      4 bytes  size, big-endian
     32 bytes  sha256 of the file
      1 byte   length of the destination filename
      N bytes  destination filename, utf-8
   size bytes  raw file contents
    <- 2 bytes  b'OK' or b'NO' from the receiver
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
PWD = 'playground1'          # WPA needs >= 8 characters
PORT = 8266

# 512 is the validated default from the working examples in the reference
# report. There is no reason to go bigger for an 8-30KB file, and the C6 on
# the other end has less RAM headroom than this board does.
CHUNK = 512

# Yields the CPU so the lwIP/WiFi driver's background task gets scheduled to
# drain its buffers. This is a *different* bottleneck from radio power-save,
# and fixing only one of the two produces stalls that are hell to reproduce.
YIELD_MS = 20

ACCEPT_TIMEOUT_S = 120
SOCK_REPLY_TIMEOUT_S = 30


def _hash_file(path):
    """sha256 of a file, computed incrementally through one reused buffer.

    Never reads the whole file - the hashing pass has to obey the same memory
    discipline as the transfer itself.
    """
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


def _start_ap(ssid, pwd, verbose):
    ap = network.WLAN(network.AP_IF)
    # config() must follow active(True) on this port - calling it first raises
    # OSError: Wifi Invalid Mode (confirmed against real ESP32-S3 hardware).
    ap.active(True)
    try:
        ap.config(essid=ssid, password=pwd, authmode=network.AUTH_WPA_WPA2_PSK)
    except (ValueError, OSError):
        # Newer MicroPython renamed authmode -> security.
        ap.config(essid=ssid, password=pwd, security=3)

    # Power-save is a station-side behaviour; on AP_IF this is usually a no-op
    # and may not be supported at all. Unlike on the receiver, failure here is
    # not interesting.
    try:
        ap.config(pm=0)
    except (ValueError, OSError, AttributeError):
        pass

    while not ap.active():
        sleep_ms(100)
    if verbose:
        print("  AP up: %s at %s" % (ssid, ap.ifconfig()[0]))
    return ap


def serve(src_path='payload.py', dest_name=None, port=PORT,
          ssid=SSID, pwd=PWD, verbose=False):
    """Serve src_path to the first C6 that connects. Blocks until done.

    dest_name is the filename the receiver writes; defaults to src_path.
    Returns True if the receiver reported a good transfer.
    """
    if dest_name is None:
        dest_name = src_path
    name_bytes = dest_name.encode('utf-8')
    if len(name_bytes) > 255:
        raise ValueError("destination name too long")

    size = os.stat(src_path)[6]
    digest = _hash_file(src_path)
    print("[SEND] %s -> %s, %d bytes" % (src_path, dest_name, size))

    ap = _start_ap(ssid, pwd, verbose)

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', port))
    srv.listen(1)
    srv.settimeout(ACCEPT_TIMEOUT_S)      # don't hang forever unattended
    print("[SEND] waiting for a receiver on 192.168.4.1:%d ..." % port)

    ok = False
    cs = None
    try:
        cs = srv.accept()[0]
        # Without this, a lost/slow reply hangs the sender in cs.read(2)
        # forever - confirmed against real hardware, not a hypothetical.
        cs.settimeout(SOCK_REPLY_TIMEOUT_S)
        print("[SEND] receiver connected")

        cs.write(size.to_bytes(4, 'big'))
        cs.write(digest)
        cs.write(bytes([len(name_bytes)]))
        cs.write(name_bytes)

        if verbose:
            print("  mem_free before body: %d" % gc.mem_free())

        buf = bytearray(CHUNK)
        mv = memoryview(buf)
        sent = 0
        with open(src_path, 'rb') as f:
            while True:
                n = f.readinto(buf)
                if not n:
                    break
                cs.write(mv[:n])
                sent += n
                sleep_ms(YIELD_MS)

        if verbose:
            print("  mem_free after body:  %d" % gc.mem_free())
        print("[SEND] %d bytes out, waiting for verdict" % sent)

        reply = cs.read(2)
        ok = (reply == b'OK')
        print("[SEND] receiver said: %s" % (reply,))
    except OSError as e:
        print("[SEND] failed: %s" % (e,))
    finally:
        if cs is not None:
            cs.close()
        srv.close()
        ap.active(False)
        gc.collect()

    return ok
