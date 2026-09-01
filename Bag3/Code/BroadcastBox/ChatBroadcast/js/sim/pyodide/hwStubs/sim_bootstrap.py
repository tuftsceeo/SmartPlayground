"""
Simulation harness — patches time.sleep*, runs generated game code in bounded bursts.
"""

import sys
import time as _time
import inspect

from neopixel import reset_pixels, flush_pixels


class SimYield(Exception):
    """Raised at sleep checkpoints to yield control back to the browser."""


class SimError(Exception):
    """Unrecoverable simulation failure."""


_sim_yielding = False
_checkpoint_count = 0
CHECKPOINT_BUDGET = 300

# Mutable dict updated from JS before each tick (see inputBridge.js).
input_state = {
    "button": 1,       # 1 = released, 0 = pressed (active LOW)
    "accel": (0, 0, 1),
    "nfc_pending": None,   # (command, uid_hex) or None
    "espnow_queue": [],    # list of (msg_type, data, mac_str)
}


def _sleep_ms(ms):
    global _checkpoint_count, _sim_yielding
    flush_pixels()
    _checkpoint_count += 1
    if _checkpoint_count >= CHECKPOINT_BUDGET:
        _sim_yielding = True
        raise SimYield()
    return None


def _sleep(s):
    return _sleep_ms(int(float(s) * 1000))


def _ticks_ms():
    return int(_time.time() * 1000)


def _ticks_diff(a, b):
    return a - b


def _ticks_add(t, delta):
    return t + delta


def patch_time():
    _time.sleep_ms = _sleep_ms
    _time.sleep = _sleep
    _time.ticks_ms = _ticks_ms
    _time.ticks_diff = _ticks_diff
    _time.ticks_add = _ticks_add


def patch_leds_off():
    """Skip leds.off() during SimYield teardown (play() finally blocks)."""
    import leds
    _orig = leds.Leds.off

    def _off(self):
        if _sim_yielding:
            return None
        return _orig(self)

    leds.Leds.off = _off


def sync_machine_input():
    import machine
    machine.set_input_state(input_state)


def find_game_class(ns):
    skip = {"Leds", "Buzzer", "Pin", "NfcReader", "PN532", "LIS2DW12", "ESPNowManager"}
    candidates = []
    for name, obj in ns.items():
        if not isinstance(obj, type) or name in skip:
            continue
        if hasattr(obj, "run") and callable(getattr(obj, "run")):
            candidates.append(obj)
    if not candidates:
        return None
    # Prefer *Game suffix (JumpInGame, MelodyGame, …)
    for cls in candidates:
        if cls.__name__.endswith("Game"):
            return cls
    return candidates[0]


def build_game_args(game_cls, nfc, leds, buz, accel, enow):
    sig = inspect.signature(game_cls.__init__)
    params = list(sig.parameters.keys())[1:]
    mapping = {
        "nfc": nfc,
        "leds": leds,
        "buz": buz,
        "buzzer": buz,
        "accel": accel,
        "enow": enow,
        "i2c": None,
    }
    args = []
    for p in params:
        if p in mapping:
            args.append(mapping[p])
        else:
            args.append(None)
    return args


def run_sim_tick(user_code, nfc, leds, buz, accel, i2c, enow):
    """Execute one bounded simulation burst. Returns pixel CSS strings."""
    global _sim_yielding, _checkpoint_count
    _sim_yielding = False
    _checkpoint_count = 0
    reset_pixels()
    sync_machine_input()
    patch_time()
    patch_leds_off()

    ns = {"__name__": "__game__"}
    try:
        exec(compile(user_code, "<game>", "exec"), ns)
    except SyntaxError as e:
        raise SimError("Syntax error: {}".format(e)) from e

    game_cls = find_game_class(ns)
    try:
        if game_cls:
            args = build_game_args(game_cls, nfc, leds, buz, accel, enow)
            game = game_cls(*args)
            game.run()
        elif "play" in ns and callable(ns["play"]):
            ns["play"](nfc, leds, buz, accel, i2c, enow)
        else:
            raise SimError("No Game class with run() or play() found in generated code.")
    except SimYield:
        pass
    finally:
        _sim_yielding = False

    flush_pixels()
    from neopixel import get_pixels
    pixels = get_pixels()
    return ["rgb({},{},{})".format(p[0], p[1], p[2]) for p in pixels]
