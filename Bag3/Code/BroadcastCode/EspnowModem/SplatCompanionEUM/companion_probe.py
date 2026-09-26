"""
companion_probe.py -- periodic diagnostics for the Splat Companion
==================================================================
Imported lazily by splat_companion.py when DEBUG_PROBE is True, after BLE
and the modem link are up, so its strings are allocated after BLE's
memory (AGENTS.md, memory order).

Each report prints the companion counters, the BLE link state and write
counts, and the EUM link and memory figures. host_idf_largest is the
largest free contiguous internal block on the companion.
"""

import gc
import time


class Probe:
    def __init__(self, comp, every_ms):
        self.comp = comp
        self.every_ms = every_ms
        self._next = time.ticks_add(time.ticks_ms(), every_ms)
        self._max_step_gap = 0
        self._last = time.ticks_ms()

    def maybe_print(self):
        now = time.ticks_ms()
        gap = time.ticks_diff(now, self._last)
        self._last = now
        if gap > self._max_step_gap:
            self._max_step_gap = gap
        if time.ticks_diff(now, self._next) < 0:
            return
        self._next = time.ticks_add(now, self.every_ms)
        c = self.comp
        lk = c.link
        print("[probe] t=%d comp=%s" % (now, c.counters))
        print("[probe] ble state=%s splat=%s attempts=%d connects=%d drops=%d "
              "failed=%d btn_dropped=%d %s player_fail=%d"
              % (lk.state_name(), lk.mac_address, lk.attempts, lk.connects,
                 lk.drops, lk.failed_attempts, lk.events_dropped,
                 lk.write_stats(), c.player.write_failures))
        print("[probe] link=%s" % c.mgr.link_stats())
        print("[probe] mem=%s" % c.mgr.mem_stats())
        print("[probe] gc_free=%d max_step_gap_ms=%d"
              % (gc.mem_free(), self._max_step_gap))
        self._max_step_gap = 0
        self._last = time.ticks_ms()      # exclude this report's print time
