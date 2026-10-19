"""
bench_g1_scan.py -- gate G1 (and 3.2): board identity, antenna pins, ~10 s Splat scan
Run on a wand right after a power cycle (`run` stops main.py if it is running):
    python3 -m mpremote connect $WAND resume run bench_g1_scan.py
Prints ID lines, one SPLAT line per Splat seen, then one `G1 {json}` line.
GPIO3/GPIO14 are read without reconfiguring them (Pin(n) with no mode), so
they show what boot code left set: GPIO3=0 RF switch on, GPIO14 1=external.
"""
import time
import os
import json
import machine
import ubluetooth

SCAN_S = 10


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _hex(b, sep=":"):
    return sep.join("%02X" % x for x in b)


def _name(adv):
    i = 0
    while i + 1 < len(adv):
        n = adv[i]
        if n == 0:
            break
        if adv[i + 1] in (0x08, 0x09):
            return bytes(adv[i + 2:i + 1 + n]).decode()
        i += n + 1
    return ""


u = os.uname()
ident = {
    "hubtype": _read("/hubtype.txt"),
    "unique_id": _hex(machine.unique_id(), ""),
    "machine": u.machine,
    "release": u.release,
    "version": u.version,
    "gpio3": machine.Pin(3).value(),
    "gpio14": machine.Pin(14).value(),
}
try:
    import network
    ident["sta_mac"] = _hex(network.WLAN(network.STA_IF).config("mac"))
except Exception as ex:
    ident["sta_mac"] = "err %r" % ex

found = {}


def irq(event, data):
    if event == 5:
        addr_type, addr, adv_type, rssi, adv = data
        name = _name(adv)
        if name.startswith("Splat"):
            m = _hex(addr)
            prev = found.get(m)
            if prev is None:
                found[m] = [addr_type, name, rssi, 1]
            else:
                prev[3] += 1
                if rssi > prev[2]:
                    prev[2] = rssi


ble = ubluetooth.BLE()
ble.active(True)
ident["ble_mac"] = _hex(ble.config("mac")[1])
for k in ("hubtype", "unique_id", "machine", "release", "version",
          "sta_mac", "ble_mac", "gpio3", "gpio14"):
    print("ID %s=%s" % (k, ident[k]))
ble.irq(irq)
ble.gap_scan(SCAN_S * 1000, 30000, 30000)
time.sleep(SCAN_S + 1)
ble.gap_scan(None)
ble.active(False)

splats = []
for m, v in found.items():
    print("SPLAT %s addr_type=%d name=%s rssi_max=%d hits=%d" % (m, v[0], v[1], v[2], v[3]))
    splats.append({"mac": m, "name": v[1], "rssi": v[2], "hits": v[3]})
ident["scan_s"] = SCAN_S
ident["splats"] = splats
print("G1 " + json.dumps(ident))
