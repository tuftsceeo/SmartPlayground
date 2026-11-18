"""
serial_monitor.py — watch a board's serial output WITHOUT interrupting it.

Host-side tool. Not firmware; never upload this to a device.

Why this exists: `mpremote ... exec` enters the raw REPL, which sends Ctrl-C
and stops whatever the board is running. The program does not come back until
the next reset. So `mpremote` cannot be used to observe a running box -- the
act of looking kills the thing you wanted to look at.

This just opens the port and reads. It sends nothing and does not touch
DTR/RTS (native USB CDC on the ESP32-S3 has no auto-reset circuit on those
lines, and there is no reason to poke them anyway).

It also survives the port disappearing. A board reset drops and re-enumerates
the USB CDC device, so the /dev entry vanishes for several seconds; without
the retry loop the monitor dies exactly when a reset is the thing you were
trying to capture.

Usage:
    python3 serial_monitor.py /dev/cu.usbmodemXXXX [seconds] > run.log

Pick `seconds` generously. If a person has to perform the test, they are not
watching your terminal -- a window that expires while they read your
instructions captures nothing. 900 is a reasonable default for a hands-on test.
"""

import sys
import time

import serial

BAUD = 115200

port = sys.argv[1]
duration_s = float(sys.argv[2]) if len(sys.argv) > 2 else 900

start = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - start, msg), flush=True)


ser = None
while time.time() - start < duration_s:
    try:
        if ser is None:
            ser = serial.Serial(port, BAUD, timeout=0.5,
                                dsrdtr=False, rtscts=False)
            log("# monitor: port opened")
        line = ser.readline()
        if line:
            log(line.decode('utf-8', 'replace').rstrip())
    except serial.SerialException as e:
        # Expected on every board reset: the CDC device goes away entirely.
        log("# monitor: port dropped (%s) -- retrying" % str(e))
        try:
            if ser:
                ser.close()
        except Exception:
            pass
        ser = None
        time.sleep(1.0)

if ser:
    try:
        ser.close()
    except Exception:
        pass
log("# monitor: done")
