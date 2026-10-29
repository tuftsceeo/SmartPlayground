"""
scan_splats.py -- list advertising BLE devices named 'Splat' with their MAC
Run on a wand: python3 -m mpremote connect $WAND resume run scan_splats.py
"""
import time
import ubluetooth

SCAN_S = 10
found = {}


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


def irq(event, data):
    if event == 5:
        addr_type, addr, adv_type, rssi, adv = data
        name = _name(adv)
        if name.startswith('Splat'):
            found[':'.join('%02X' % b for b in addr)] = (addr_type, name, rssi)


ble = ubluetooth.BLE()
ble.active(True)
ble.irq(irq)
ble.gap_scan(SCAN_S * 1000, 30000, 30000)
time.sleep(SCAN_S + 1)
for m, v in found.items():
    print("SPLAT %s addr_type=%d name=%s rssi=%d" % (m, v[0], v[1], v[2]))
print("SCAN-DONE %d found" % len(found))
ble.active(False)
