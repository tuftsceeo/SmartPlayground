"""
Exercise the Box's pull wire contract host-side, both ends, plus concurrency.

The cases live in wire_contract.py, which wire_test_dial.py runs against the
Dial's copy of code_server.py. The two servers are the same file bar their
heap comments, so both are held to the same contract from one place.

Run:  python3 Bag3/Code/BroadcastCode/BroadcastBox/tools/devtests/wire_test.py
Exits non-zero on any mismatch. It does NOT touch hardware.
"""
import sys

import wire_contract

sys.exit(1 if wire_contract.run("BBoxFirmware", "Box") else 0)
