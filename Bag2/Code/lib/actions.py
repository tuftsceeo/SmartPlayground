"""
Actions — Definitions, resource mapping, and chain execution
==============================================================
Animal sounds are remote-only (Splat). Silently skipped on wand.

Usage:
    from actions import ActionRunner, ACTIONS, ANIMAL_SOUNDS
    runner = ActionRunner(leds, buzzer)
    runner.run_chain([["turnred", "notea"], ["playnote"]])
"""

import sys
import time
import _thread

from buzzer import NOTE_FREQ

ACTIONS = {
    "playnote", "turnpurple",
    "turnred", "turnblue", "turngreen", "turnwhite", "turnyellow", "turnoff",
    "notea", "noteb", "notec", "noted", "notee", "notef", "noteg",
}

ANIMAL_SOUNDS = {
    "cat", "chicken", "cow", "dog", "pig",
    "duck", "elephant", "horse", "goat",
}

ALL_ACTIONS = ACTIONS | ANIMAL_SOUNDS

ACTION_RESOURCE = {
    "playnote":   "buzzer",
    "notea":      "buzzer", "noteb": "buzzer", "notec": "buzzer",
    "noted":      "buzzer", "notee": "buzzer", "notef": "buzzer",
    "noteg":      "buzzer",
    "turnpurple": "led", "turnred": "led", "turnblue": "led",
    "turngreen":  "led", "turnwhite": "led", "turnyellow": "led",
    "turnoff":    "led",
    "cat": "splat_sound", "chicken": "splat_sound", "cow": "splat_sound",
    "dog": "splat_sound", "pig": "splat_sound", "duck": "splat_sound",
    "elephant": "splat_sound", "horse": "splat_sound", "goat": "splat_sound",
}


def resolve_and_group(group):
    by_res = {}
    for action in group:
        res = ACTION_RESOURCE.get(action, action)
        by_res[res] = action
    return list(by_res.values())


def chain_to_str(chain):
    parts = []
    for group in chain:
        if len(group) > 1:
            parts.append(" & ".join(group))
        else:
            parts.append(group[0])
    return " -> ".join(parts)


class ActionRunner:
    def __init__(self, leds, buzzer):
        self.leds = leds
        self.buzzer = buzzer
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
        fn = self._fns.get(name)
        if fn:
            fn()
        elif name in ANIMAL_SOUNDS:
            pass  # remote only
        else:
            print("  [WARN] Unknown action: %s" % name)

    def run_and_group(self, group):
        local = [a for a in group if a in self._fns]
        if len(local) == 0:
            return
        if len(local) == 1:
            self.run_action(local[0]); return

        done = [0]
        def _thread_fn(name):
            try:
                self.run_action(name)
            except Exception as e:
                print("  [ERR] %s:" % name); sys.print_exception(e)
            done[0] += 1

        for a in local[:-1]:
            _thread.start_new_thread(_thread_fn, (a,))
        self.run_action(local[-1])

        t = time.ticks_ms() + 3000
        while done[0] < len(local) - 1:
            if time.ticks_diff(time.ticks_ms(), t) > 0:
                break
            time.sleep_ms(10)

    def run_chain(self, chain):
        for group in chain:
            self.run_and_group(group)