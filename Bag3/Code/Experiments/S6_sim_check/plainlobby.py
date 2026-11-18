# S6 check: a plain wand lobby (PLAYERS_MIN alone). Leader red, joiner blue.
import time

PLAYERS_MIN = 2


def play(nfc, leds, buz, accel, i2c, enow, batt, net):
    print("plainlobby: in game, leader=%s wands=%d" % (net.is_leader, len(net.wands)))
    color = (40, 0, 0) if net.is_leader else (0, 0, 40)
    try:
        while True:
            ev = net.poll()
            if ev is not None and ev[0] == "ended":
                return
            leds.fill(color)
            time.sleep_ms(50)
    finally:
        leds.off()
