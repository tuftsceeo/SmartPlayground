"""
bench_host_pairs.py -- bench check for the Splat host's color pairs (not deployed)
=================================================================================
Run with the wand's main.py not running (mpremote's raw REPL soft reset does this):
    python -m mpremote connect COM7 run "utilities/bench_host_pairs.py"
Uses the wand's own lib/ (splat_hub, splat_link, ble_splat, leds). Switch every
Splat on first. No pairing file or role is written.

Steps; press any Splat's button to go to the next one (or wait STEP_MS):
  1. connect: up to 4 Splats by name; prints each unit's MAC and connect time
  2. identify: unit 0 red, 1 green, 2 blue, 3 yellow (whole Splat)
  3. halves: LEDs 0-6 red, 7-13 blue (the "left"/"right" parts)
  4. pairs: every ordered pair of the 6 identity colors, 4 Splats at a time,
     at the idle-glow brightness; the wand shows each unit's pair in its
     2x2 corner block (left column A, right column B)
"""

import time
import ubluetooth

from splat_hub import SplatHub
from splat_api import SplatGroup
from leds import Leds, OFF, RED, GREEN, BLUE, MAGENTA, AMBER, WHITE

COUNT = 4
CONNECT_MS = 45000
SCAN_IDLE_MS = 60000
STEP_MS = 60000
GLOW_SCALE = 0.5
LEFT = (0, 1, 2, 3, 4, 5, 6)
RIGHT = (7, 8, 9, 10, 11, 12, 13)
CORNERS = ((0, 1, 5, 6), (3, 4, 8, 9), (15, 16, 20, 21), (18, 19, 23, 24))
# splat_api.COLOR_RGB and splatpair.WAND_RGB for splatpair.PALETTE
PALETTE = ("turnred", "turngreen", "turnblue", "turnpurple", "turnyellow", "turnwhite")
SPLAT_RGB = {"turnred": (255, 0, 0), "turngreen": (0, 255, 0), "turnblue": (0, 0, 255),
             "turnpurple": (160, 0, 200), "turnyellow": (255, 180, 0),
             "turnwhite": (200, 200, 200)}
WAND_RGB = {"turnred": RED, "turngreen": GREEN, "turnblue": BLUE,
            "turnpurple": MAGENTA, "turnyellow": AMBER, "turnwhite": WHITE}


def scaled(rgb):
    return (int(rgb[0] * GLOW_SCALE), int(rgb[1] * GLOW_SCALE), int(rgb[2] * GLOW_SCALE))


def wait_press(group, ms):
    end = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        if group.poll() == "press":
            print("  (press on unit %d)" % group.last_index)
            return
        time.sleep_ms(1)
    print("  (no press; timed out)")


def write(link, leds, rgb):
    ok = link.setLEDs(leds, rgb[0], rgb[1], rgb[2])
    time.sleep_ms(40)
    return ok


def _adv_name(adv):
    i = 0
    while i + 1 < len(adv):
        n = adv[i]
        if n == 0:
            break
        if adv[i + 1] in (0x08, 0x09):
            return bytes(adv[i + 2:i + n + 1]).decode()
        i += n + 1
    return None


def scan_splats(leds):
    """STEP 1a: scan while the Splats are switched on one at a time. Ends at
    COUNT Splats or SCAN_IDLE_MS after the last new one."""
    ble = ubluetooth.BLE()
    ble.active(True)
    found = []

    def irq(event, data):
        if event == 5:
            addr_type, addr, adv_type, rssi, adv = data
            mac = ":".join(["%02X" % b for b in bytes(addr)])
            if mac not in found and len(found) < COUNT and _adv_name(adv) == "Splat":
                found.append(mac)

    ble.irq(irq)
    ble.gap_scan(0, 30000, 30000)
    print("STEP 1a scan: switch the Splats on one at a time")
    last = time.ticks_ms()
    shown = 0
    while len(found) < COUNT and time.ticks_diff(time.ticks_ms(), last) < SCAN_IDLE_MS:
        if len(found) > shown:
            shown = len(found)
            last = time.ticks_ms()
            print("RESULT found %d: %s" % (shown, found[-1]))
            leds.np[CORNERS[shown - 1][0]] = WHITE
            leds.np.write()
        time.sleep_ms(1)
    ble.gap_scan(None)
    time.sleep_ms(200)
    if len(found) > shown:
        print("RESULT found %d: %s" % (len(found), found[-1]))
    return list(found)


def main():
    leds = Leds()
    leds.off()
    macs = scan_splats(leds)
    if not macs:
        print("RESULT no Splats found")
        return
    hub = SplatHub(count=len(macs), macs=macs)
    group = SplatGroup(hub)
    try:
        COUNT = len(macs)
        print("STEP 1b connect: %d Splats, %d ms" % (COUNT, CONNECT_MS))
        t0 = time.ticks_ms()
        seen = [False] * COUNT
        while time.ticks_diff(time.ticks_ms(), t0) < CONNECT_MS:
            group.poll()
            for i, link in enumerate(hub.links):
                if link.ready and not seen[i]:
                    seen[i] = True
                    print("RESULT unit %d ready %s at %d ms"
                          % (i, link.mac_address, time.ticks_diff(time.ticks_ms(), t0)))
            if all(seen):
                break
            time.sleep_ms(1)
        units = [i for i in range(COUNT) if seen[i]]
        print("RESULT connected %d of %d" % (len(units), COUNT))
        if not units:
            return

        print("STEP 2 identify: unit 0 red, 1 green, 2 blue, 3 yellow")
        ident = ("turnred", "turngreen", "turnblue", "turnyellow")
        leds.off()
        for i in units:
            hub.links[i].setLEDsON(SPLAT_RGB[ident[i]])
            time.sleep_ms(40)
            for p in CORNERS[i]:
                leds.np[p] = WAND_RGB[ident[i]]
            print("  unit %d %s = %s" % (i, hub.links[i].mac_address, ident[i]))
        leds.np.write()
        wait_press(group, STEP_MS)

        print("STEP 3 halves: LEDs 0-6 red (left?), 7-13 blue (right?)")
        for i in units:
            write(hub.links[i], LEFT, SPLAT_RGB["turnred"])
            write(hub.links[i], RIGHT, SPLAT_RGB["turnblue"])
        wait_press(group, STEP_MS)

        pairs = [(a, b) for a in PALETTE for b in PALETTE if a != b]
        n = len(units)
        print("STEP 4 pairs: %d ordered pairs, %d per screen" % (len(pairs), n))
        for s in range(0, len(pairs), n):
            leds.off()
            print("  screen %d:" % (s // n + 1))
            for k, i in enumerate(units):
                if s + k >= len(pairs):
                    hub.links[i].setLEDsON((0, 0, 0))
                    continue
                a, b = pairs[s + k]
                write(hub.links[i], LEFT, scaled(SPLAT_RGB[a]))
                write(hub.links[i], RIGHT, scaled(SPLAT_RGB[b]))
                c = CORNERS[i]
                leds.np[c[0]] = leds.np[c[2]] = WAND_RGB[a]
                leds.np[c[1]] = leds.np[c[3]] = WAND_RGB[b]
                print("    unit %d: %s / %s" % (i, a, b))
            leds.np.write()
            wait_press(group, STEP_MS)
        print("RESULT done")
    finally:
        leds.off()
        hub.close_all()


main()
