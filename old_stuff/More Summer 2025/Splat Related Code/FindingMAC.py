#use to find the MAC address of the splat
import time
import bluetooth
from micropython import const
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)

_ADV_TYPE_NAME = const(0x09)
def decode_field(payload, adv_type):
    i = 0
    result = []
    while i + 1 < len(payload):
        if payload[i + 1] == adv_type:
            result.append(payload[i + 2 : i + payload[i] + 1])
        i += 1 + payload[i]
    return result


def decode_name(payload):
    n = decode_field(payload, _ADV_TYPE_NAME)
    return str(n[0], "utf-8") if n else ""



def bt_irq(event, data):
  if event == _IRQ_SCAN_RESULT:
    # A single scan result.
    addr_type, addr, adv_type, rssi, adv_data = data
    if decode_name(adv_data) == 'Splat':
        
        print(':'.join(['%02X' % i for i in addr]))
  elif event == _IRQ_SCAN_DONE:
    # Scan duration finished or manually stopped.
    print('scan complete')

# Scan for 10s (at 100% duty cycle)
ms_scan = 10000
bt = bluetooth.BLE()
bt.irq(bt_irq)
bt.active(True)
bt.gap_scan(ms_scan, 30000, 30000)
time.sleep_ms(ms_scan)