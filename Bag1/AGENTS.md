# Bag1/AGENTS.md

Factual description of Bag1 only. Bag1 went to classrooms and is not under active development —
treat it as **read-only by default; ask before editing.** This file does not compare Bag1 to Bag2 or
Bag3, and does not propose porting anything forward — see the root [`AGENTS.md`](../AGENTS.md) for
the vocabulary (hub / module / station) and the "ask which Bag" rule that governs the whole repo.

## Naming

The component called the **Plushie module** here (`Bag1/Plushie_Module/`) is what later Bags call the
**Wand module** — a direct design descendant, same component renamed. The rigid-case hardware was
already being called "wand" in conversation before the file/config names caught up; `config.py`'s
`box` variant (`Box_settings`, `hw_version = 2`, rigid rectilinear case rather than plush) is a brief
internal/file-naming label from that transition, not a distinct generation of its own — "wand" is
what stuck, formalized in the file and folder names starting in Bag2.

## Components in this Bag

Bag1 has no `hubtype.txt`. Device identity comes from `Config` subclasses in
`Bag1/Plushie_Module/config.py`, selected by editing `Bag1/Plushie_Module/hardware.py`, which
currently reads `tool = config.Box_settings` (hardcoded, not auto-detected):

| `Config` subclass | `module_type` | LEDs | Notes |
|---|---|---|---|
| `Plushie_settings` | `plushie` | 12 | |
| `Box_settings` | `box` | 25 | `hw_version = 2`; rigid-case variant — see Naming below; `hardware.py` currently points here |
| `Splats_settings` | `splats` | 3 | only variant with `Splat_Notes` in its game list |
| `Button_settings` | `button` | 12 (inherited) | `first_game = 7` |
| `Controller_settings` | `controller` | 0 | `antenna = False`; used by the teacher-side controller, not a student module |

Base `Config`: `hw_version = 3`, `sw_version = 3.2`, `intensity = 0.1`, `volume = 1.0`,
`antenna = True`. Device name is read from a `hubname` file at boot.

## Architecture

Games are Python classes registered statically in `Config.games` as `(GameClass, response_interval)`
tuples — not looked up by tag name. Base class `games/game.py::Game` defines the lifecycle:
`start()` (sync), `async loop()` (called repeatedly), `close()`. `Tool.start_game(number)` in
`main.py` creates an `asyncio` task running `game.run(response_time)`. Entry point is `main.py`
(constructs a `Tool` instance, calls `asyncio.run(me.main())`); `hardware.py` selects which `Config`
to use.

## Game catalog

12 games registered in `Config.games` (base `Config`, inherited by `Plushie_settings` / `Box_settings`
/ `Button_settings`):

| Class | File | What it does |
|---|---|---|
| `Notes` | `sound.py` | On button press, plays a random note (C4–C5) and shows its assigned color |
| `Shake` | `shake.py` | Shake harder → more LEDs light up (accelerometer magnitude); one-way ratchet, button resets |
| `Shake_Rainbow` | `shake_rainbow.py` | Shake harder → color climbs `WHITE→RED→ORANGE→YELLOW→GREEN→BLUE→INDIGO→VIOLET` |
| `Hot_cold` | `hotcold.py` | Hide-and-seek: LED count reflects ESP-NOW RSSI to a "hidden gem" target module |
| `Jump` | `jump.py` | Counts jumps via free-fall detection (accel magnitude drop); one LED per jump |
| `Clap` | `clap.py` | Visualizes ESP-NOW antenna range: modules in range light up and buzz on a `/notify` broadcast |
| `Rainbow` | `rainbow.py` | Shows a battery-level bar in green, then publishes the reading over ESP-NOW |
| `Hibernate` | `hibernate.py` | Blinks red 5×, then calls a deep-sleep routine unless the button is held |
| `Pattern_btn` | `pattern_rainbow_btn.py` | Button module: broadcasts one LED color per press, paired with `Pattern_plush` |
| `Pattern_plush` | `pattern_rainbow_plushie.py` | Plushie module: displays a running color pattern received from `Pattern_btn` (FIFO of 12) |
| `Color_Press` | `color_press.py` | Flip upright/upside-down to commit button-press counts as an ice-cream-scoop color |
| `Color_Press_Mult` | `color_press_mult.py` | Same mechanic, 3 scoops (`NUM_SCOOPS = 3`, `SCOOP_SIZE = 4`) |
| `Splat_Notes` | `splat_notes.py` | Registered only under `Splats_settings`; plays notes via BLE on a connected splat (`utilities/ble_splat.py`) |

`games/nfc_sound.py` (note-on-NFC-tap variant of `Notes`) and `games/Now_sniffer.py` (a standalone
ESP-NOW traffic monitor with its own `Controller` class, not a `Game`) exist in the tree but are
**not registered in any `Config.games` list.**

## Communication

`Bag1/Plushie_Module/utilities/now.py::Now` wraps ESP-NOW with a **`{'topic': ..., 'value': ...}`
JSON pub-sub scheme**, broadcasting to `\xff\xff\xff\xff\xff\xff`. Topics seen in `main.py`:
`/game` (start/switch game, value is `(game_number, base64_controller_mac)`), `/ping` (RSSI sample),
`/notify`, `/color`, `/battery`, `/nfc`, `/slide`. `Tool.publish(msg)` wraps outbound messages;
inbound messages are queued (`collections.deque`) and drained by `Tool.pop_queue()` /
`execute_queue()`. This is Bag1's own protocol, unrelated to later Bags' `espnow_manager.py`.

## Controllers

`Bag1/Plushie_Module/controllers/` holds four variants of the teacher-side controller, all built on
`utilities/now.py`:

| File | What it is |
|---|---|
| `controller.py` | Base `Control` class; `tool = config.Controller_settings`; builds a numbered game list from `tool.games` |
| `controller_sm.py` | Minimal variant — no `config` import, just connects and logs incoming ESP-NOW traffic |
| `controller_sophie.py` | Variant of `controller.py` (`sophie = True` flag; otherwise near-identical) |
| `controller_ws.py` | Variant with a touchscreen AMOLED display (`Display` class; `FT3168_ADDR` touch controller, `TCA9554_ADDR` GPIO expander) |

Plus `ssd1306.py`, an OLED driver shared by the display-based controllers.

## Utilities / drivers (`Bag1/Plushie_Module/utilities/`)

| File | Purpose |
|---|---|
| `now.py` | ESP-NOW pub-sub wrapper (see Communication above) |
| `nfc.py` | NFC detect/remove callback wrapper around `pn532_i2c.py` |
| `pn532_i2c.py` | PN532 NFC reader driver over I2C |
| `i2c_bus.py` | Shared I2C bus setup; `LIS2DW12` accelerometer and `Battery` wrapper (selects `lc709203f` or `max17048`) |
| `lights.py` | NeoPixel driver (`Lights` class, `LED_PIN = 20`) |
| `colors.py` | Named RGB color constants |
| `lc709203f.py` | LC709203F battery fuel gauge driver |
| `max17048.py` | MAX17048 battery fuel gauge driver |
| `ble_splat.py` | BLE central driver for third-party splat toys (`ubluetooth`, UUIDs `0xfff0`/`0xfff3`/`0xfff4`) — the ancestor of later Bags' `ble_splat.py` |
| `utilities.py` | `Button`, `Buzzer`, `Hibernate` (deep-sleep) helpers; pins `BUTTON_PIN=0`, `BUZZER_PIN=19`, `MOTOR_PIN=21` |

## Not part of the working system

- `not_used/` — `NFC_code/` (an earlier NFC subsystem: `main.py`, `old_main.py`, `icons.py`,
  `pn532_i2c.py`, `sensors.py`, `servo.py`, `ssd1306.py`), plus `ledmatrix.py`, `sound-block.py`,
  `websocket.py`, `websocket-example.py`, `E1001.html`.
- `unit_tests/` — `NFC_test.py`, `games-test.py`, `now_test.py`, `utilities_test.py`,
  `wifi_test.py`: interactive bring-up scripts, not an automated suite.

## Design files

`Bag1/Design Files/CAD Files/Splat Companion/` — STLs and a reference image for "Splat Companion V1"
(full assembly, battery case, LED box, LED cover, USB cover).

## Documentation

`Bag1/Plushie_Module/README.md` is the original module README: a Mermaid architecture diagram, a
workshop-era game-ideas brainstorm list, and a link to an external PyScript front-end app. Treat the
brainstorm list and the external link as historical rather than current; the diagram's accuracy has
not been re-checked against the code above. Not rewritten here.

`Bag1/Plushie_Module/LICENSE` — an MIT license (Copyright 2025, Chris). This is the only license file
present in any Bag.
