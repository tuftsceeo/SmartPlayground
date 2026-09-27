"""
companion.py -- Splat Companion idle station (no game running)
===============================================================
Hardware-free. Companion takes an ESP-NOW manager, the shared
splat_api.SplatAPI and a status-LED object, so the same code runs on the
device and in the CPython simulation (test_splat_companion.py).

This station is games-only, like the icon display. Between games it does
nothing on its own: it keeps the Splat's BLE link up so the next game
starts on a ready link, and waits for a game to be requested. Splat
presses while idle are drained and discarded -- nothing plays and nothing
is sent.

One step() call services, in order:
1. the BLE link (splat.poll(): reconnect, keepalive, switch polling);
   idle button events are discarded
2. up to ESPNOW_BATCH ESP-NOW messages (mgr.poll)
3. the status LEDs

Messages handled while idle:
    {"type": "start_game", "name": "<game>"}
        a game this station has -> pending_start_game, read by main.py;
        any other name is printed and ignored
    {"type": "stop"} or ["stop"]
        silence the Splat (splat.off())
Everything else is counted as ignored. This station adds no ESP-NOW peers
and sends nothing while idle; a game that wants others to hear about a
press broadcasts its own message.
"""

import time


# ─── Tunables ─────────────────────────────────

ESPNOW_POLL_MS = 5           # idle interval between modem FETCHes
ESPNOW_BATCH = 8             # max messages handled per step

# Companion status LED colors: (r, g, b), breathe
LED_MODEM_DOWN = ((15, 0, 0), False)
LED_BLE_WAIT = ((0, 0, 15), False)
LED_READY = ((0, 12, 12), True)


class Companion:
    def __init__(self, mgr, splat, leds=None, is_game_fn=None):
        """is_game_fn(name) -> bool, checked before honouring an ESP-NOW
        start_game (same check main.py's own NFC dispatch uses). None means
        this station never accepts start_game -- used in the CPython
        simulation, which has no game table.
        """
        self.mgr = mgr
        self.splat = splat
        self.link = splat.link
        self.leds = leds
        self.is_game_fn = is_game_fn
        self.pending_start_game = None  # set by on_message, read by main.py
        self._was_ready = False
        self._next_poll = time.ticks_ms()
        self._events_dropped_seen = 0
        self.counters = {
            "rx": 0, "stops": 0, "ignored": 0, "idle_presses": 0,
            "ble_up": 0, "ble_down": 0,
            "start_games": 0, "start_games_unknown": 0,
        }

    # ─── Loop ─────────────────────────────────

    def step(self):
        ev = self.splat.poll()
        if ev == "press":
            self.counters["idle_presses"] += 1
        ready = self.link.ready
        if ready and not self._was_ready:
            self.counters["ble_up"] += 1
            print("  Companion: Splat %s ready" % self.link.mac_address)
        elif self._was_ready and not ready:
            self.counters["ble_down"] += 1
            print("  Companion: Splat link down")
        self._was_ready = ready

        dropped = self.link.events_dropped
        if dropped != self._events_dropped_seen:
            print("  [ERR] splat button queue overflow: %d events dropped"
                  % (dropped - self._events_dropped_seen))
            self._events_dropped_seen = dropped

        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_poll) >= 0:
            n = 0
            while n < ESPNOW_BATCH:
                msg_type, data, mac = self.mgr.poll()
                if msg_type is None:
                    break
                n += 1
                self.on_message(msg_type, data, mac)
            now = time.ticks_ms()
            self._next_poll = now if n == ESPNOW_BATCH else time.ticks_add(
                now, ESPNOW_POLL_MS)

        if self.leds is not None:
            color, breathe = self._led_state()
            self.leds.show(color, breathe, now)

    def _led_state(self):
        lk = getattr(self.mgr, "_link", None)
        if lk is not None and getattr(lk, "down", False):
            return LED_MODEM_DOWN
        if not self.link.ready:
            return LED_BLE_WAIT
        return LED_READY

    # ─── ESP-NOW side ─────────────────────────

    def on_message(self, msg_type, data, mac):
        self.counters["rx"] += 1
        if msg_type == "stop":
            self.counters["stops"] += 1
            self.splat.off()
            print("  Companion: stop from %s" % mac)
        elif msg_type == "start_game":
            self._on_start_game(data, mac)
        else:
            self.counters["ignored"] += 1

    def _on_start_game(self, data, mac):
        # Bubbled up rather than launched here: only main.py's idle loop
        # knows the game table (is_game_fn) and runs games.
        name = data.get("name") if isinstance(data, dict) else None
        if self.is_game_fn is not None and name and self.is_game_fn(name):
            self.counters["start_games"] += 1
            self.pending_start_game = name
        else:
            self.counters["start_games_unknown"] += 1
            print("  Companion: ignoring unknown start_game name %r from %s"
                  % (name, mac))
