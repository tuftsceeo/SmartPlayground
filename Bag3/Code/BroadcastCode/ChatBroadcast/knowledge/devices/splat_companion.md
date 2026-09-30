# Device: Splat Companion  (`[DEVICE: splat]`)

## What it is and who sees it

A small station that controls one or more **Splat** toys — pads children press, which light up and
play sounds. The station (XIAO ESP32-C6) talks to the Splats over Bluetooth and
to wands and the display over ESP-NOW. It has a 12-light ring for its own status and a card reader
the station uses to switch games.

It has **no buzzer, no motion sensor, and no 5×5 grid**. Its `leds` is the 12-light status ring,
not a wand's grid.

Between games the station does nothing: pressing a Splat plays nothing. Everything a Splat does
comes from a game file for this device.

## The `play()` contract

```python
def play(splat, leds, enow, batt=None):
```

| Argument | What it is | Notes |
|---|---|---|
| `splat` | the Splat(s), over Bluetooth (`splat_api.SplatAPI`) | Already connected or connecting; never build Bluetooth yourself |
| `leds` | the station's 12-light ring | Only `leds.fill((r, g, b))` and `leds.off()`; do not import the wand's `leds` |
| `enow` | ESP-NOW manager, already started | Poll every loop |
| `batt` | battery gauge, or `None` | Guard with `if batt is not None:` |

**No card reader in a game.** The station reads cards itself: a stop card or another game's card
tapped during play arrives through `enow` as `"stop"` or `"start_game"`. Returning on those two is
all a game needs to do.

Never create `ubluetooth.BLE()`, `ESPNowManager()` or `splat_link.SplatLink` in a game. Never keep
`splat`, `leds` or `enow` in a module-level variable or register a callback on `enow`.

## Canonical template

```python
"""
<Game title> — <one line on what happens on the Splat>
"""
import time


def play(splat, leds, enow, batt=None):
    try:
        leds.fill((10, 10, 10))
        while True:
            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if msg_type == "raw" and isinstance(data, dict):
                if data.get("type") == "yourmsg":
                    splat.color("turnblue")

            ev = splat.poll()
            if ev == "press":
                splat.play(["turngreen", "cat"])
                enow.broadcast({"type": "score", "hit": True})
            elif ev == "release":
                splat.off()

            time.sleep_ms(1)
    finally:
        splat.off()
        leds.off()
```

## API

Every `splat` call is safe when a Splat is not connected: it returns `False` and does nothing, so a
dropped Bluetooth link never crashes a game.

| Call | What it does |
|---|---|
| `splat.poll()` | **Call every loop.** Keeps Bluetooth alive; returns `"press"`, `"release"` or `None` |
| `splat.connected` | `True` once a Splat is linked |
| `splat.color("turnred")` | Solid color |
| `splat.sound("cat")` | Animal sound |
| `splat.note("note_c")` | One note (replaces a held note) |
| `splat.play(["turngreen", "cat", "note_c"])` | Several at once |
| `splat.off()` | Stop sound, note and lights |

Use **only** the names in "SPLAT ACTION NAMES ON THE SPLAT COMPANION" sent with the request. The app
refuses a game that names anything else.

**Several Splats (up to 4).** The calls above act on every connected Splat, and `poll()` reports a
press from any of them.

- `splat.count` — how many Splats this station is set up for
- `splat.connected_count` — how many are connected now
- `splat.last_index` — which Splat (0, 1, …) the last `poll()` event came from
- `splat.unit(i)` — one Splat, with the same calls: `splat.unit(splat.last_index).color("turngreen")`

A game must still work when `splat.count == 1`. Check `splat.count` before using `unit(1)`.

## Everyday words → code

| The teacher says | Use |
|---|---|
| "when a child jumps on the Splat" | `splat.poll() == "press"` |
| "the Splat turns green and barks" | `splat.play(["turngreen", "dog"])` |
| "play a note" | `splat.note("note_c")` |
| "tell the wands / display" | `enow.broadcast({"type": "hit"})` |
| "each Splat a different color" | `splat.unit(i).color(...)` for `i` below `splat.count` |

## Limits and why

- **`splat.poll()` and `enow.poll()` every loop, with `time.sleep_ms(1)`.** Bluetooth needs
  frequent service; skipping it drops presses and the link.
- **No card reading in the game.** Cards arrive as `"stop"` / `"start_game"`.
- **Nothing forwards Splat presses automatically.** Broadcast a message if another device must know.
- **`splat.off()` in `finally`** so a game that exits mid-sound does not leave the Splat lit.

## Checklist

- [ ] `[DEVICE: splat]` before the block
- [ ] `def play(splat, leds, enow, batt=None):`
- [ ] `splat.poll()` and `enow.poll()` every loop; `time.sleep_ms(1)`
- [ ] Return on `"stop"` / `"start_game"`
- [ ] Only action names from the list sent with the request
- [ ] `batt` guarded with `if batt is not None:`
- [ ] `splat.off()` and `leds.off()` in `finally`
