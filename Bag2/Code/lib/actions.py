"""
Actions — Definitions, resource mapping, and chain execution
==============================================================
Defines all available actions, maps them to hardware resources,
and handles AND/THEN chain building and execution.

Usage:
    from actions import ActionRunner

    runner = ActionRunner(leds, buzzer)
    runner.run_chain([["turnred", "notea"], ["playnote"]])
    #  = (turnred AND notea) THEN playnote
"""

import sys
import time
import _thread

from buzzer import NOTE_FREQ


# ─────────────────────────────────────────────
# ACTION NAMES
# ─────────────────────────────────────────────
ACTIONS = {
    "playnote", "turnpurple",
    "turnred", "turnblue", "turngreen", "turnwhite", "turnyellow", "turnoff",
    "notea", "noteb", "notec", "noted", "notee", "notef", "noteg",
}

# ─────────────────────────────────────────────
# RESOURCE MAP
# Actions sharing a resource cannot run simultaneously.
# In an AND group, last one wins for that resource.
# ─────────────────────────────────────────────
ACTION_RESOURCE = {
    "playnote":   "buzzer",
    "notea":      "buzzer",
    "noteb":      "buzzer",
    "notec":      "buzzer",
    "noted":      "buzzer",
    "notee":      "buzzer",
    "notef":      "buzzer",
    "noteg":      "buzzer",
    "turnpurple": "led",
    "turnred":    "led",
    "turnblue":   "led",
    "turngreen":  "led",
    "turnwhite":  "led",
    "turnyellow": "led",
    "turnoff":    "led",
}


# ─────────────────────────────────────────────
# CHAIN HELPERS
# ─────────────────────────────────────────────

def resolve_and_group(group):
    """Deduplicate by resource — last one wins."""
    by_resource = {}
    for action in group:
        res = ACTION_RESOURCE.get(action, action)
        by_resource[res] = action
    return list(by_resource.values())


def chain_to_str(chain):
    """Pretty-print a chain for display."""
    parts = []
    for group in chain:
        if len(group) > 1:
            parts.append(" & ".join(group))
        else:
            parts.append(group[0])
    return " -> ".join(parts)


# ─────────────────────────────────────────────
# ACTION RUNNER
# ─────────────────────────────────────────────

class ActionRunner:
    def __init__(self, leds, buzzer):
        """
        Args:
            leds: Leds instance
            buzzer: Buzzer instance
        """
        self.leds = leds
        self.buzzer = buzzer

        # Build action function table
        self._fns = {
            "playnote":   buzzer.melody,
            "notea":      lambda: buzzer.play_note(NOTE_FREQ["notea"]),
            "noteb":      lambda: buzzer.play_note(NOTE_FREQ["noteb"]),
            "notec":      lambda: buzzer.play_note(NOTE_FREQ["notec"]),
            "noted":      lambda: buzzer.play_note(NOTE_FREQ["noted"]),
            "notee":      lambda: buzzer.play_note(NOTE_FREQ["notee"]),
            "notef":      lambda: buzzer.play_note(NOTE_FREQ["notef"]),
            "noteg":      lambda: buzzer.play_note(NOTE_FREQ["noteg"]),
            "turnpurple": lambda: leds.solid(127, 0, 127),
            "turnred":    lambda: leds.solid(127, 0, 0),
            "turnblue":   lambda: leds.solid(0, 0, 127),
            "turngreen":  lambda: leds.solid(0, 127, 0),
            "turnwhite":  lambda: leds.solid(80, 80, 80),
            "turnyellow": lambda: leds.solid(127, 80, 0),
            "turnoff":    leds.off,
        }

    def run_action(self, name):
        """Run a single action by name."""
        fn = self._fns.get(name)
        if fn:
            fn()
        else:
            print("  [WARN] Unknown action: %s" % name)

    def run_and_group(self, group):
        """Run all actions in a group simultaneously using threads."""
        if len(group) == 1:
            self.run_action(group[0])
            return

        done = [0]

        def thread_action(name):
            try:
                self.run_action(name)
            except Exception as e:
                print("  [ERR] %s:" % name); sys.print_exception(e)
            done[0] += 1

        for action in group[:-1]:
            _thread.start_new_thread(thread_action, (action,))

        self.run_action(group[-1])

        timeout = time.ticks_ms() + 3000
        while done[0] < len(group) - 1:
            if time.ticks_diff(time.ticks_ms(), timeout) > 0:
                break
            time.sleep_ms(10)

    def run_chain(self, chain):
        """Execute a full action chain: AND groups together, THEN groups sequential."""
        for group in chain:
            self.run_and_group(group)