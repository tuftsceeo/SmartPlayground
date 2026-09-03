"""import_bench.py -- BENCH-TEST CODE. NOT in the fielded wand baseline.

Deviation from Bag3/Code/Wand Module/. Measures per-game import (compile)
time and heap cost in isolation, to answer two questions before designing
a loading indicator:

  1. Is a static icon (leds.show_shape, already in main.py's _load_play())
     enough, or does the worst-case game need an animated spinner because
     the compile is long enough for a static icon to read as "frozen"?
  2. Does unloading a finished game (del sys.modules[...] + gc.collect())
     actually reclaim its bytecode, or does MicroPython's qstr pool make
     the reclaim partial/illusory over a session that cycles many games?

Run from the Thonny/REPL prompt on the wand itself, NOT imported by
main.py or boot.py (that would defeat the point -- this script's job is
to measure imports main.py has NOT yet made):

    import import_bench
    import_bench.bench_sequential()      # mode A -- one boot, no unload
    import_bench.bench_isolated()        # mode B -- one game per reboot
    import_bench.bench_unload_cycle("gestures")   # mode C

Output lines are prefixed MEMSPAN (via memprobe) and BENCHROW (this
module's own summary rows), so a serial capture can be grepped directly.
"""

import gc
import sys
import time

import memprobe

# Kept in sync BY HAND with main.py's GAME_MODULES -- this script
# deliberately does not `import main` (that would eagerly compile every
# game itself and defeat the measurement). If you add a game to
# main.py's GAME_MODULES, add it here too.
GAME_MODULES = {
    "colorquest":     "color_quest",
    "freezedance":    "freeze_dance",
    "jumpin":         "jumpin",
    "cooking":        "cooking",
    "melody":         "melody",
    "shake":          "shake",
    "shakerainbow":   "shake_rainbow",
    "rainbow":        "rainbow",
    "jump":           "jump",
    "sound":          "sound",
    "nfcsound":       "nfc_sound",
    "simpleicecream": "simpleicecream",
    "multiicecream":  "multiicecream",
    "gestures":       "gestures",
    "finddevice":     "finddevice",
}

# Every game's top-level imports (pn532, nfc_reader, game_tags, leds,
# buzzer, espnow_manager, brightness) are already in main.py's own import
# set, so preloading them here makes each game's measured span its own
# marginal compile cost -- the same cost main.py would actually pay,
# not inflated by shared-dependency compilation. target.py (561 B) is
# the one game-specific shared dep (color_quest only) and is left out
# deliberately so color_quest's number still reflects that real cost.
_PRELOAD = ("pn532", "nfc_reader", "game_tags", "leds", "buzzer",
            "espnow_manager", "brightness", "lis2dw12", "max17048")

_COUNTER_PATH = "/importbenchidx"


def _preload():
    for mod in _PRELOAD:
        __import__(mod)
    gc.collect()
    memprobe.probe("preloaded")


# ─────────────────────────────────────────────
# Mode A -- sequential, one boot, cumulative
# ─────────────────────────────────────────────
def bench_sequential(unload=False):
    """Import all games in table order in one boot. No reset between them.

    Gives the cumulative heap growth main.py's old eager-import block paid
    every boot -- useful as a sanity total, but NOT the number that should
    drive the loading-indicator decision (see bench_isolated() for that).
    """
    _preload()
    rows = []
    for tag in GAME_MODULES:
        mod_name = GAME_MODULES[tag]
        tok = memprobe.mark()
        try:
            __import__(mod_name)
            ok = True
        except Exception as e:
            ok = False
            print("  [BENCH] %s failed to import: %s" % (mod_name, e))
        memprobe.span("import:%s" % tag, tok)
        if unload and ok and mod_name in sys.modules:
            del sys.modules[mod_name]
            gc.collect()
        rows.append((tag, ok))
    memprobe.frag("sequential-done")
    print("BENCHROW mode=sequential unload=%s n=%d" % (unload, len(rows)))
    return rows


# ─────────────────────────────────────────────
# Mode B -- isolated, one game per reboot
# ─────────────────────────────────────────────
# Reuses the pull_flag.py file-as-counter idiom verbatim (already proven
# on this hardware) rather than inventing a second one.
def _read_index():
    try:
        with open(_COUNTER_PATH, "r") as f:
            raw = f.read().strip()
        return int(raw) if raw else 0
    except (OSError, ValueError):
        return 0


def _write_index(n):
    with open(_COUNTER_PATH, "w") as f:
        f.write("%d" % n)


def _clear_index():
    try:
        import os
        os.remove(_COUNTER_PATH)
    except OSError:
        pass


def bench_isolated():
    """Import exactly one game from a cold, freshly-booted heap, print its
    span, then reset and move to the next game. 15 reboots total.

    This is the number that should drive the loading-indicator decision:
    the user-visible case is a cold wand, first game of the session -- not
    a heap already warmed by 14 prior imports (that is bench_sequential).

    Call once per boot (e.g. from the REPL after each auto-reset) or
    invoke it from boot.py temporarily while running the sweep; either
    way, do not leave the boot.py hook in place afterward.
    """
    tags = list(GAME_MODULES.keys())
    idx = _read_index()
    if idx >= len(tags):
        print("BENCHROW mode=isolated done n=%d" % len(tags))
        _clear_index()
        return
    tag = tags[idx]
    mod_name = GAME_MODULES[tag]
    _preload()
    tok = memprobe.mark()
    try:
        __import__(mod_name)
    except Exception as e:
        print("  [BENCH] %s failed to import: %s" % (mod_name, e))
    memprobe.span("isolated:%s" % tag, tok)
    print("BENCHROW mode=isolated idx=%d/%d tag=%s" % (idx, len(tags), tag))
    _write_index(idx + 1)
    time.sleep_ms(200)  # let the print flush over the serial link
    import machine
    machine.reset()


# ─────────────────────────────────────────────
# Mode C -- unload/reload cycle, same game, one boot
# ─────────────────────────────────────────────
def bench_unload_cycle(tag, cycles=3):
    """Import -> unload -> gc.collect() -> repeat, same game, one boot.

    The delta between cycle 1's post-unload heap and cycle N's is the
    qstr/pool residual _unload_game() cannot reclaim -- the direct,
    empirical answer to "does unloading actually reclaim anything".
    """
    if tag not in GAME_MODULES:
        print("  [BENCH] unknown tag: %s" % tag)
        return
    mod_name = GAME_MODULES[tag]
    _preload()
    memprobe.probe("cycle:%s:baseline" % tag)
    for i in range(cycles):
        tok = memprobe.mark()
        __import__(mod_name)
        memprobe.span("cycle:%s:import:%d" % (tag, i), tok)
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        gc.collect()
        memprobe.probe("cycle:%s:post-unload:%d" % (tag, i))
    print("BENCHROW mode=unload_cycle tag=%s cycles=%d" % (tag, cycles))
