"""
splat_companion.py -- Splat Companion (EUM) entry point
=======================================================
Board: Seeed XIAO ESP32-C6 (hubtype.txt: splat_companion), with an
M5StickS3 running EspnowModem/modem/main.py on UART1.

main.py brings BLE up first, then imports this module and calls main().
The companion's own radio does BLE only; ESP-NOW goes through the modem.
"""

import sys
import time
import machine

from hubtype import HUB_TYPE, HUB_CONFIG
import espnow_manager
from splat_link import SplatLink
from companion import Companion
from status_leds import StatusLeds


# UART to the modem. XIAO ESP32-C6: D0 = GPIO0 (TX), D1 = GPIO1 (RX).
MODEM_UART_TX = 0
MODEM_UART_RX = 1

SPLAT_MAC = None             # e.g. "AB:42:00:00:7E:B6"; None = first "Splat" seen
DEBUG_PROBE = False          # periodic stats from companion_probe.py
PROBE_EVERY_MS = 10000

FAULT_LIMIT = 5              # step() exceptions within FAULT_WINDOW_MS -> reset
FAULT_WINDOW_MS = 10000


def main():
    print("\n  Splat Companion (EUM), hub type %s" % HUB_TYPE)
    if HUB_TYPE != "splat_companion":
        raise RuntimeError("hubtype.txt says %r, expected splat_companion" % HUB_TYPE)

    link = SplatLink(mac_address=SPLAT_MAC)
    leds = StatusLeds(HUB_CONFIG["led_pin"], HUB_CONFIG["num_leds"])
    leds.show((0, 0, 15), False, 0)

    espnow_manager.UART_TX = MODEM_UART_TX
    espnow_manager.UART_RX = MODEM_UART_RX
    mgr = espnow_manager.ESPNowManager()
    try:
        mgr.init()
    except OSError:
        leds.show((15, 0, 0), False, 0)
        print("  [FATAL] no EUM modem on UART%d tx=%d rx=%d"
              % (espnow_manager.UART_ID, MODEM_UART_TX, MODEM_UART_RX))
        raise

    comp = Companion(mgr, link, leds)
    probe = None
    if DEBUG_PROBE:
        import companion_probe
        probe = companion_probe.Probe(comp, PROBE_EVERY_MS)

    faults = []
    try:
        while True:
            try:
                comp.step()
                if probe is not None:
                    probe.maybe_print()
            except Exception as e:
                sys.print_exception(e)
                now = time.ticks_ms()
                faults = [t for t in faults
                          if time.ticks_diff(now, t) < FAULT_WINDOW_MS]
                faults.append(now)
                if len(faults) > FAULT_LIMIT:
                    print("  [FATAL] %d faults in %d ms, resetting"
                          % (len(faults), FAULT_WINDOW_MS))
                    time.sleep_ms(200)
                    machine.reset()
            time.sleep_ms(1)
    finally:
        # Ctrl-C (KeyboardInterrupt) or a non-Exception error
        print("  Splat Companion: shutting down")
        comp.shutdown()
        leds.off()
