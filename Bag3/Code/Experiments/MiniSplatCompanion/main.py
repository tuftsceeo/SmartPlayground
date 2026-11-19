"""
Mini Splat Companion: one Splat <-> the playground. XIAO ESP32-C6, 3 NeoPixels.
Forked from Wand Module/main.py (see README.md); hubtype.txt = splat_mini.
"""

# Radio prewarm, before any other import (AGENTS.md: nothing may allocate
# before the radio claims its memory). ESP-NOW first, then BLE: BLE first
# fails with "WiFi Out of Memory". ONBOARD antenna: GPIO14 = 0 (the Wand
# prewarm uses 1 = external). Same rxbuf as lib/espnow_manager.py.
try:
    import network, espnow
    from machine import Pin
    Pin(3, Pin.OUT).value(0)
    import time
    time.sleep_ms(100)
    Pin(14, Pin.OUT).value(0)
    network.WLAN(network.STA_IF).active(True)
    _e = espnow.ESPNow()
    _e.config(rxbuf=4096)
    _e.active(True)
    del _e
except Exception as _err:
    print("  [WARN] radio prewarm failed; ESPNowManager.init() will retry:", _err)
try:
    import ubluetooth
    ubluetooth.BLE().active(True)
except Exception as _err:
    print("  [WARN] BLE prewarm failed:", _err)

import machine
import time
import sys
import json
import gc
import os

from hubtype import HUB_TYPE, HUB_CONFIG
from max17048 import MAX17048
from leds import Leds, battery_color, OFF, RED, GREEN_DIM, AMBER, AMBER_DIM, BLUE, BLUE_DIM, CYAN, GREEN, WHITE
from espnow_manager import ESPNowManager
from stubs import NullBuzzer, NullNfc, NullAccel
import game_store

game_store.ensure_dir()
if game_store.GAMES_DIR not in sys.path:
    sys.path.append(game_store.GAMES_DIR)

MINI_VERSION = "0.1.0"
# Pulls are keyed by hub type. The Box/Dial (code_sender.py ROLE_FILES) only
# serve "wand"; asking as "splat_mini" is refused. So the pull request and
# the status_poll kind both say "wand" (README "Pull hub and status kind").
PULL_HUB = "wand"
STATUS_KIND = "wand"
HEARTBEAT_MS = 5000
SOC_REFRESH_MS = 60_000

BUILTIN_GAMES = ("jumpin",)


def _emit(obj):
    print(json.dumps(obj))


def _on_flash(mod):
    for ext in (".py", ".mpy"):
        try:
            os.stat(mod + ext)
            return True
        except OSError:
            pass
    return False


def game_module(name):
    """Module name for a game tag this mini can run, else None."""
    if not name:
        return None
    if name in BUILTIN_GAMES and _on_flash(name):
        return name
    if game_store.exists(name):
        return name
    return None


def is_game(name):
    return game_module(name) is not None


# ── Hardware ──
leds = Leds()
i2c = machine.SoftI2C(sda=machine.Pin(HUB_CONFIG["i2c_sda"]),
                      scl=machine.Pin(HUB_CONFIG["i2c_scl"]),
                      freq=HUB_CONFIG["i2c_freq"])
nfc_stub = NullNfc()
buz_stub = NullBuzzer()
accel_stub = NullAccel()
splat = None            # mini_splat.MiniSplat, built in _boot() after the radio
_pending_push = None    # (slug, host, replace) from a Dial/Box code_push


_last_status = None     # cache for _show_status; cleared by anything that draws


def _invalidate():
    global _last_status
    _last_status = None


def _flash(color, times=3):
    _invalidate()
    leds.flash_color(color, times=times, on_ms=150, off_ms=100)


def _queue_push(data):
    global _pending_push
    _pending_push = (data.get("slug") or "", data.get("host") or "",
                     data.get("replace") or "")


# ── Game launch ──
class _StartGameCapture:
    """Wrap enow so an in-game start_game poll captures the next game name and
    a code_push ends the game (the idle loop then pulls)."""

    def __init__(self, enow):
        self._enow = enow
        self.pending_name = None

    def poll(self, timeout_ms=0):
        mt, data, mac = self._enow.poll(timeout_ms)
        if mt == "start_game":
            self.pending_name = data.get("name") if isinstance(data, dict) else None
        elif mt == "code_push":
            _queue_push(data)
            return "stop", data, mac
        return mt, data, mac

    def __getattr__(self, attr):
        return getattr(self._enow, attr)


def _unload_game(name):
    mod = game_module(name)
    if mod and mod in sys.modules:
        del sys.modules[mod]
    gc.collect()


def _game_fail(name, exc, why="game_load"):
    print("  [FAIL] %s: %s" % (why, name))
    if exc is not None:
        sys.print_exception(exc)
    _emit({"type": "error", "where": why, "slug": name, "err": str(exc)})
    _flash(RED)
    _unload_game(name)


def _is_arity_error(e):
    msg = str(e)
    return "positional argument" in msg or ("argument" in msg and "given" in msg)


def _start_play(play_func, name, enow, batt, net):
    """Call play(nfc, leds, buz, accel, i2c, enow, batt, net), tolerating the
    older six- and seven-parameter games (same rule as the Wand's)."""
    args = (nfc_stub, leds, buz_stub, accel_stub, i2c, enow, batt, net)
    code = getattr(play_func, "__code__", None)
    n = getattr(code, "co_argcount", None) if code is not None else None
    if n is not None:
        return play_func(*args[:n]) if n < len(args) else play_func(*args)
    for k in (8, 7, 6):
        try:
            return play_func(*args[:k])
        except TypeError as e:
            if not _is_arity_error(e) or k == 6:
                raise


def _splat_decls(mod):
    """(local, lobby): SPLATS_LOCAL or None; True for a lobby/host game.
    Raises ValueError for an invalid SPLATS_LOCAL."""
    lobby = (getattr(mod, "SPLAT_HOST", False) is True
             or getattr(mod, "SPLATS_MIN", None) is not None
             or getattr(mod, "PLAYERS_MIN", None) is not None)
    n = getattr(mod, "SPLATS_LOCAL", None)
    if n is not None and (not isinstance(n, int) or isinstance(n, bool)
                          or n < 1 or n > 2 or lobby):
        raise ValueError("%s: SPLATS_LOCAL=%r (int 1..2, alone)" % (mod.__name__, n))
    return n, lobby


def _run_games(name, enow, batt):
    """Run a game and chain start_game force-switches without going idle."""
    while is_game(name):
        try:
            mod = __import__(game_module(name))
            play_func = getattr(mod, "play")
            local, lobby = _splat_decls(mod)
        except Exception as e:
            _game_fail(name, e)
            return
        if lobby:
            # Lobby and host games need pairing/lobby machinery the mini lacks.
            print("  [REFUSED] %s is a lobby/host game; the mini has no lobby" % name)
            _emit({"type": "error", "where": "game_load", "slug": name,
                   "err": "lobby/host game unsupported on splat_mini"})
            _flash(AMBER)
            _unload_game(name)
            return
        wrapper = _StartGameCapture(enow)
        net = None
        if local is not None:
            if local > 1 or not splat.connected:
                have = 1 if splat.connected else 0
                print("  [FAIL] %s needs %d Splat(s), %d connected" % (name, local, have))
                _emit({"type": "error", "where": "game_load", "slug": name,
                       "err": "needs %d Splat(s), %d connected" % (local, have)})
                _flash(AMBER)
                _unload_game(name)
                return
            net = splat.game_handle()
        _emit({"type": "game_start", "slug": name})
        try:
            try:
                _start_play(play_func, name, wrapper, batt, net)
            except TypeError as e:
                if not _is_arity_error(e):
                    raise
                _game_fail(name, e)
                return
        finally:
            if net is not None:
                net.close()
        _emit({"type": "game_end", "slug": name})
        next_name = wrapper.pending_name
        play_func = None
        wrapper = None
        _unload_game(name)
        if not next_name or not is_game(next_name):
            break
        name = next_name


def _launch_game(name, enow, batt):
    _invalidate()
    leds.off()
    try:
        _run_games(name, enow, batt)
    except Exception as e:
        _game_fail(name, e, "game_run")
    finally:
        splat.after_game()


# ── Code pull (ESP-NOW, radio already up) ──
def _pull_progress(received, total):
    lit = max(1, int((received / total) * leds.num)) if total else 1
    for i in range(leds.num):
        leds.np[i] = CYAN if i < lit else BLUE_DIM
    leds.np.write()


def _pull_and_launch(enow, slug, host_id, batt, replace=""):
    import espnow_code
    print("# getcode (slug=%r host=%r) via espnow" % (slug, host_id))
    if slug:
        _unload_game(slug)
    gc.collect()
    leds.fill(BLUE_DIM)
    ok = espnow_code.receive(enow, slug=slug, hubtype=PULL_HUB,
                             on_progress=_pull_progress, verbose=True,
                             host_id=host_id)
    stats = espnow_code.LAST_STATS or {}
    _emit({"type": "pull", "slug": slug or "", "host": host_id or "",
           "result": str(ok), "why": stats.get("why"),
           "bytes": stats.get("bytes"), "total_ms": stats.get("total_ms")})
    if ok is not True:
        # no host / no such game / busy / broken transfer: red flashes
        _flash(RED)
        leds.off()
        return
    _flash(GREEN, 2)
    name = stats.get("name") or slug
    import game_slots
    for old in game_slots.record(name, replace):
        _unload_game(old)
    _unload_game(name)
    _launch_game(name, enow, batt)


# ── Broadcast check (idle loop) ──
def _check_broadcast(enow, batt):
    """Returns "stop", ("start_game", name), "battery" or None."""
    mt, data, mac = enow.poll()
    if mt == "stop":
        return "stop"
    if mt == "battery":
        _show_battery(batt)
        return "battery"
    if mt == "start_game":
        name = data.get("name") if isinstance(data, dict) else None
        if is_game(name):
            return ("start_game", name)
        print("  ESP-NOW: ignoring unknown start_game name: %r" % name)
    if mt == "code_push" and isinstance(data, dict):
        _queue_push(data)
        return "stop"
    return None


def _read_soc(batt, last_soc):
    if batt is not None:
        try:
            _, s = batt.read_all()
            return max(0, min(100, int(s)))
        except Exception:
            pass
    return last_soc


def _show_battery(batt):
    if batt is None:
        print("  [WARN] Battery sensor not available")
        _flash(AMBER, 2)
        return
    _invalidate()
    from battery import show_battery
    show_battery(batt, leds, None)


# ── Idle status on the 3 pixels ──
# 0: ESP-NOW (dim green up, amber down). 1: Splat link (blue linked, amber
# blinking while searching). 2: battery.


def _show_status(enow, soc, now_ms):
    global _last_status
    linked = splat.connected
    blink = (now_ms // 500) % 2 == 0
    p0 = GREEN_DIM if enow.is_active else AMBER_DIM
    p1 = BLUE_DIM if linked else (AMBER_DIM if blink else OFF)
    p2 = battery_color(soc) if soc > 10 or blink else OFF
    state = (p0, p1, p2)
    if state == _last_status:
        return
    _last_status = state
    leds.np[0] = p0
    leds.np[1] = p1
    leds.np[2] = p2
    leds.np.write()


# ── Boot ──
def _boot():
    print("\n" + "=" * 50)
    print("  Mini Splat Companion %s  (hub type %s)" % (MINI_VERSION, HUB_TYPE))
    print("=" * 50)
    leds.fill(WHITE)
    # Radio first (the prewarm above already claimed it; init() keeps it).
    enow = ESPNowManager()
    try:
        enow.init()
    except Exception as e:
        print("  [WARN] ESP-NOW:")
        sys.print_exception(e)
    import game_slots    # after the radio claim
    enow.status_extra = lambda: game_slots.report("")

    batt = None
    last_soc = 100
    try:
        batt = MAX17048(i2c)
        v, s = batt.read_all()
        last_soc = max(0, min(100, int(s)))
        print("  Battery: %.2fV, %.1f%%" % (v, s))
    except Exception as e:
        print("  [WARN] Battery (no MAX17048 answered at 0x36):")
        sys.print_exception(e)
        batt = None
    if batt is not None:
        enow.set_status_provider(lambda b=batt: int(b.soc), kind=STATUS_KIND)
    else:
        enow.set_status_provider(lambda: None, kind=STATUS_KIND)

    global splat
    import mini_splat
    splat = mini_splat.MiniSplat()
    print("  Splat: %s" % ("pinned " + mini_splat._read_mac() if mini_splat._read_mac()
                           else "first Splat found by name"))
    _emit({"type": "identity", "device": "splat_mini", "version": MINI_VERSION,
           "hub": HUB_TYPE, "games": sorted(list(BUILTIN_GAMES) + game_store.slugs())})
    leds.off()
    return enow, batt, last_soc


GRACE_S = 2     # as the Wand: a Ctrl-C window before main() takes the board


def _boot_grace(drain):
    print("# booting -- Ctrl-C within %ds to stay at the REPL" % GRACE_S)
    for _s in range(GRACE_S * 4):
        drain.drain()
        time.sleep_ms(250)


def main():
    global _pending_push
    import stdin_drain
    drain = stdin_drain.Drainer()
    _boot_grace(drain)
    enow, batt, last_soc = _boot()
    last_hb = time.ticks_ms()
    last_soc_ms = last_hb

    # A game pushed over USB (ChatBroadcast) soft-resets and is named here.
    just = game_store.take_last_pulled()
    if just:
        print("  Launching just-pulled game: %s" % just)
        _launch_game(just, enow, batt)

    print("\n  Waiting: Splat link, start_game / code_push over ESP-NOW\n")
    try:
        while True:
            now = time.ticks_ms()
            if time.ticks_diff(now, last_hb) >= HEARTBEAT_MS:
                last_hb = now
                _emit({"type": "heartbeat", "up": now})
            drain.tick()
            time.sleep_ms(1)    # every iteration, ahead of the `continue` below

            if _pending_push is not None:
                slug, host, replace = _pending_push
                _pending_push = None
                if enow.is_active:
                    _pull_and_launch(enow, slug, host, batt, replace)
                else:
                    _flash(RED)
                continue

            if splat.take_connect():
                print("  Splat connected")
                splat.glow()
                _flash(BLUE, 2)
            for i, ev in splat.poll():
                if ev == "press":
                    _invalidate()
                    leds.fill(WHITE)
                    time.sleep_ms(120)
                    leds.off()

            result = _check_broadcast(enow, batt)
            if result == "stop":
                if enow.is_active:
                    enow.send_stop_all_peers()
                    enow.clear_peers()
                print("  Reset via broadcast")
            elif isinstance(result, tuple) and result[0] == "start_game":
                if enow.is_active:
                    enow.send_stop_all_peers()
                    enow.clear_peers()
                _launch_game(result[1], enow, batt)

            if time.ticks_diff(now, last_soc_ms) > SOC_REFRESH_MS:
                last_soc_ms = now
                last_soc = _read_soc(batt, last_soc)
            _show_status(enow, last_soc, now)
    finally:
        splat.close()
        leds.off()


main()
