"""
json_drive.py — send one JSON command over the CDC serial link to a running
Box/Dial/Wand and print replies for a short window.

Host-side tool, pyserial only. Opens the port directly and writes a single
newline-delimited JSON line -- does NOT use `mpremote exec` for this, which
would stop the running program (see HARDWARE_PROTOCOL.md, "Driving the
boards without a person"). This is what lets identify/info/games.*/arm/
disarm be driven from the host instead of the touch/encoder UI, for whatever
a JSON command can reach.

Only one process may hold a port at a time (HARDWARE_PROTOCOL.md) -- check
nothing else (a monitor, another mpremote call) is using it first.

Usage:
    python3 tools/json_drive.py PORT '{"cmd":"games.list","id":1}' [read_seconds]
"""
import json
import sys
import time

import serial


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    port = sys.argv[1]
    cmd = sys.argv[2]
    read_s = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0

    s = serial.Serial(port, baudrate=115200, timeout=0.2)
    time.sleep(0.3)
    s.reset_input_buffer()
    s.write((cmd + "\n").encode("utf-8"))
    s.flush()

    end = time.time() + read_s
    buf = b""
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
    for line in buf.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            print("<-", json.dumps(obj))
        except ValueError:
            print("## non-json:", line)
    s.close()


if __name__ == "__main__":
    main()
