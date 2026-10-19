"""
splat_scan.py -- list advertising Splats by BLE MAC (serial scan_splats)
=======================================================================
Scan logic from docs_and_design/2026-10-07-splat-pairing/scan_splats.py.
Imported lazily by pair_idle on the first scan_splats command, on an
unpaired wand only. BLE is left active afterwards: turning it off and on
again mid-session risks the memory failure in AGENTS.md.

UNVERIFIED on hardware: BLE activation this late in a session.
"""

import time

SCAN_MS = 5000


def _name(adv):
    i = 0
    while i + 1 < len(adv):
        n = adv[i]
        if n == 0:
            break
        if adv[i + 1] in (0x08, 0x09):
            return bytes(adv[i + 2:i + 1 + n]).decode()
        i += n + 1
    return ''


def scan(ms=SCAN_MS):
    """Returns [{"mac": "AB:42:...", "rssi": -60}, ...], strongest first."""
    import ubluetooth
    found = {}
    done = [False]

    def irq(event, data):
        if event == 5:
            addr_type, addr, adv_type, rssi, adv = data
            if _name(adv).startswith('Splat'):
                found[':'.join(['%02X' % b for b in addr])] = rssi
        elif event == 6:
            done[0] = True

    ble = ubluetooth.BLE()
    ble.active(True)
    ble.irq(irq)
    ble.gap_scan(ms, 30000, 30000)
    t0 = time.ticks_ms()
    while not done[0] and time.ticks_diff(time.ticks_ms(), t0) < ms + 1000:
        time.sleep_ms(20)
    ble.gap_scan(None)
    out = [{"mac": m, "rssi": r} for m, r in found.items()]
    out.sort(key=lambda d: -d["rssi"])
    return out
