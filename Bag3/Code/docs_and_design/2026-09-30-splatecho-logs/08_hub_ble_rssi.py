# Splat advertisement RSSI at the hub: board default, then forced onboard, then external.
import ubluetooth, time
from machine import Pin
ble = ubluetooth.BLE()
if not ble.active():
    ble.active(True)
res = {}
def irq(ev, data):
    if ev == 5:
        at, addr, adv, rssi, ad = data
        a = bytes(addr)
        if a[0] == 0xAB and a[1] == 0x42:
            res.setdefault(a.hex(), []).append(rssi)
ble.irq(irq)
def scan(label):
    res.clear()
    ble.gap_scan(3000, 30000, 30000)
    time.sleep_ms(3400)
    print("SCAN", label, {k[-4:]: (len(v), sum(v) // len(v), min(v)) for k, v in res.items()})
print("PINS before: gpio3", Pin(3).value(), "gpio14", Pin(14).value())
scan("default")
Pin(3, Pin.OUT).value(0)
time.sleep_ms(100)
Pin(14, Pin.OUT).value(0)
scan("onboard")
Pin(14, Pin.OUT).value(1)
scan("external")
Pin(14, Pin.OUT).value(0)
