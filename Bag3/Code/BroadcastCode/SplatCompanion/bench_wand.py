"""
bench_wand.py -- stand-in wand for the Splat Companion bench test
================================================================
Runs on any board with an espnow_manager.py (a stock MockWand, or an EUM
host). Nothing in the wand firmware sends splat_config or splat_cmd yet,
so this script plays that role.

    python3 -m mpremote connect $WAND_PORT resume run bench_wand.py

Set COMPANION_MAC to the MAC the companion prints at boot
("ESPNow(EUM): active (MAC: ...)"): the modem's MAC, not the XIAO's.

Phases (each prints "[bench] PHASE <name>" when it starts):
1. config   send splat_config CONFIG_CHAIN; press the splat during LISTEN_S
2. cmd      send splat_cmd CMD_CHAIN, then splat_cmd off after CMD_OFF_AFTER_S
3. stop     send stop; press the splat once more during LISTEN_S
Every splat_event received is printed with its arrival time.
"""

import time

from espnow_manager import ESPNowManager

COMPANION_MAC = "AA:BB:CC:DD:EE:FF"
CONFIG_CHAIN = [["turnred", "cat"], ["turnblue", "note_c"], ["turngreen"]]
CMD_CHAIN = [["turnyellow", "dog"], ["turnpurple", "note_e"]]
LISTEN_S = 20
CMD_OFF_AFTER_S = 3


def listen(mgr, seconds, log):
    end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        msg_type, data, mac = mgr.poll()
        if msg_type is not None:
            if isinstance(data, dict) and data.get("type") == "splat_event":
                log.append((time.ticks_ms(), data.get("event")))
                print("[bench] t=%d splat_event %s from %s splat=%s"
                      % (time.ticks_ms(), data.get("event"), mac, data.get("splat")))
            else:
                print("[bench] t=%d other %s from %s" % (time.ticks_ms(), msg_type, mac))
        time.sleep_ms(1)


def send(what, ok):
    print("[bench] t=%d sent %s ok=%s" % (time.ticks_ms(), what, ok))
    if not ok:
        raise RuntimeError("send %s failed" % what)


def main():
    mgr = ESPNowManager()
    mgr.init()
    mgr.add_peer(COMPANION_MAC)
    log = []

    print("[bench] PHASE config: press and release the splat a few times")
    send("splat_config", mgr.send_splat_config(COMPANION_MAC, CONFIG_CHAIN))
    listen(mgr, LISTEN_S, log)

    print("[bench] PHASE cmd: watch the splat")
    send("splat_cmd", mgr.send_to(COMPANION_MAC,
                                  {"type": "splat_cmd", "actions": CMD_CHAIN}))
    listen(mgr, CMD_OFF_AFTER_S, log)
    send("splat_cmd off", mgr.send_to(COMPANION_MAC,
                                      {"type": "splat_cmd", "off": True}))
    listen(mgr, 2, log)

    print("[bench] PHASE stop: press the splat once; expect events, no light/sound")
    send("stop", mgr.send_stop_to(COMPANION_MAC))
    listen(mgr, LISTEN_S, log)

    print("[bench] DONE splat_events=%d presses=%d releases=%d"
          % (len(log), sum(1 for _, e in log if e == "press"),
             sum(1 for _, e in log if e == "release")))
    mgr.remove_peer(COMPANION_MAC)


main()
