# Broadcast icon display

A 16×16 WS2812B panel (256 px) on a XIAO ESP32-C6 that loads, runs, switches
and unloads single-file game modules with the same `main.py` structure and game contract as
the wand (`Wand Module/main.py`).

It gets those files from the Broadcast Box: tap a `getcode:<slug>` card, the
display pulls over ESP-NOW: it
broadcasts a `code_req` with `hub:"icon_display"` (pinned to the card's `@<id>`
host when present) and `lib/espnow_code.py` `receive(..., icon_dir=)` fetches
`<slug>_icon.py` and then each icon the offer names (the offer's `icons` plus
`list_from` pages; see `BroadcastDial/README.md`, "Serving over ESP-NOW").
On success the display resets into the new game; on failure the old copy
stays and it returns to idle. Icons are checked by size and SHA-256 only, and
a failed icon does not fail the game.

This display's `lib/espnow_manager.py` does not set `ESPNOW_RXBUF`, so the
ESP-NOW driver keeps its default receive buffer (526 B, about 2 frames).
`lib/espnow_code.py` is a hand-kept copy of `MockWand/lib/espnow_code.py`.

It also answers the icon editor web app over USB while idle, so icons can be
drawn and saved straight to it. That link is live whenever the device is not
in a game — there is nothing to switch on. A game owns the loop while it runs,
so authoring pauses for its duration.

## History: the old `Icon Display Station`

This tree descends from `Stations/Icon Display Station/`, a USB-serial-only version with no
radio, deleted on 2026-11-15 (it is in git history). Its icon tools and web editor are in
`Bag3/Code/IconEditor/`; its hardware notes are under "Hardware bring-up notes" below.
`icon_server.py` here is now the only copy.

## Layout

```
boot.py            does not light the panel -- see its docstring
main.py            boot order, idle loop, game dispatch
hubtype.txt        "icon_display"
icon_matrix.py     Matrix: serpentine addressing, intensity LUT, bulk draw
icon_store.py      read/write icons/<name>.py as text
icon_server.py     USB command set for the icon editor; PEER of the station's
json_link.py       one JSON object per line, printable ASCII only
espnow_code.py    ESP-NOW pull of the game and icons; copy of MockWand/lib/
goalrace.py        built-in game (the display half of the two-device pair)
scoreboard.py      built-in game (running tally, the draw16/chart16 demo)
icons/             named icons, referenced from a game by name
lib/               espnow_manager, game_store, game_slots, hubtype, display_tags,
                   nfc_reader, ws1850s, nfc_ws1850s, memprobe, shapes,
                   draw16, chart16, display_station
games/             picturemoves.py, codebreakers.py: copied to /games/<slug>.py
                   (found at runtime like a pulled game; no main.py entry)
```

### Station mode (`lib/display_station.py`)

With no game running, the display obeys any wand. Nothing filters by sender.

| Message | Effect |
|---|---|
| `{"type": "show", "icon": "<name>"}` | that icon, held 60 s; an unknown name prints `[ERR]` and is ignored |
| `{"type": "show", "px": [[row, col, [r, g, b]], ...]}` | up to 64 pixels on a dark panel |
| `{"type": "show", "text": "12:3"}` | up to 4 characters of draw16's font (`0-9 -:.`) |
| `{"type": "dance", "s": ["jump", "spin", "wave", "freeze"]}` | Move Mixer: loops the dance, one step every 2 s, beat bar and step dots; each dance plays at least 2 loops, the newest waiting dance replaces older waiting ones; ends after 10 min with no new dance |

Any of these may carry `"to": "<mac>"`: then only that display obeys. Without `to`, every
display obeys (the M3 rule; see `known_issues/2026-11-13-game-system-gaps.md`).

`main.py` imports the module on the first `"raw"` ESP-NOW message while idle, after the
radio is up, and drops it on a stop, a card tap, a pull or a game start.

A built-in game is looked up by `main.py`'s `_module_on_flash()`, which
checks the **flash root** -- the `games/` directory in this repo is where the
sources live, not where the device wants them.

### Adding an icon has a second step

`icons/` here is the source of truth for a generated list the chat app sends
to the model: `ChatBroadcast/js/ledicons/defaultIcons.js`. A display game may
only name icons in that list -- `app.js` refuses a game naming anything else
at send time -- so an icon that is only on the device is invisible to
ChatBroadcast and unusable in a generated game. After adding or removing one
here:

    python3 ChatBroadcast/tools/sync_icons.py          # regenerate
    python3 ChatBroadcast/tools/sync_icons.py --check  # exit 1 on drift

Nothing runs that check automatically.

### draw16 and chart16 are firmware-resident

`lib/espnow_code.py` pulls a game its own file and its icons; the sender's
`ROLE_FILES` has no `lib` leg and the staging tree carries no `lib/`. A game that imports
`draw16` or `chart16` therefore raises ImportError on a display flashed
before they were added. Flash the display before handing out games that use
them.

## Writing a game

`main.py` is laid out like the wand's (`Wand Module/main.py`): radio prewarm at the top,
the same section names, `_load_play` / `_run_games` / `_start_play` / `check_broadcast` /
`show_idle` / `_espnow_pull_and_launch`, and the wand's game contract:

```python
def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
```

- `nfc` — the raw reader (`Ws1850sReader`, PN532-compatible), or `None` when no reader
  answered. Build `NfcReader(nfc, COMMANDS)` as a wand game does.
- `leds` — the panel (`Matrix`): `set_pixels`, `draw_bytes`, `clear`, `set_intensity`,
  `redraw`, and `.src` as a scratch frame.
- `buz`, `accel`, `batt` — `None`: no buzzer, accelerometer or battery here.
- `i2c` — the reader's bus. `net` — `None`.
- `enow` — `ESPNowManager`, already initialized. Poll it every loop iteration and return
  when `msg_type` is `"stop"` or `"start_game"`.

A game takes as many leading parameters as it needs. The older `play(nfc, panel, enow)`
(exactly three parameters, `nfc` a ready-built `NfcReader`) is still called that way, so
existing display games and generated ones keep working.

Declare the cards a game reads as string literals in a module-level
`COMMANDS` set, unioned with `exit_tags_excluding("<yourgame>")` from
`lib/display_tags.py`. Four separate consumers read that set statically,
without running the game.

Load a named icon with `icon_store.read_icon(name, into=panel.src)` then
`panel.draw_bytes(panel.src)`.

To add a built-in: add its tag to `GAME_TAGS` in `lib/display_tags.py` and to
`GAME_MODULES` in `main.py`. The two are checked against each other at boot.

A game starts on a card tap, on an ESP-NOW `start_game`, or straight after a
pull. A bench game can also be started over USB without a card:
`{"cmd":"start_game","name":"<slug>"}` through `icon_server.py`. It refuses an
unknown or uninstalled slug loudly rather than falling back -- see
`icon_server.py`'s `do_start_game()` docstring.

## Card reader

A WS1850S at I2C `0x28` -- the same chip as the Broadcast Box, on the same
pins as the wand (SDA 22 / SCL 23, 100 kHz). It is **not** a PN532, and that
driver is not in this tree.

`lib/nfc_reader.py` was written against a PN532 and calls four methods on its
reader object; `lib/nfc_ws1850s.py` presents those four on top of the
WS1850S, so the card-reading logic stays one shared file rather than two that
drift. The shim also clears Crypto1 before every detection, which the PN532
never needed: on this chip any MIFARE auth latches encrypted mode and blocks
every later read until it is cleared.

`main.py` scans the bus before constructing the reader and prints every
address it found if `nfc_addr` is not among them. A missing reader costs card
taps and nothing else -- the rest of the device still boots and runs.

## Glyph vocabulary

The display speaks the wand's visual language, scaled 3x onto the 16x16
panel: a **boot screen** whose left column is one cell per stage (dim white
started, green ok, amber degraded, red fatal) with data cells beside it, and
a **static green square** while it waits -- the wand's `idle_default()`, which
colours that square by battery charge. This device has no battery, so it is
plain green: powered, idle, nothing wrong.

`lib/shapes.py` is a PEER copy of `MockWand/lib/leds.py`'s 5x5 `SHAPE_*`
tuples (data only, no LED driver), plus `draw_shape()` and `wifi_animate()`,
which scale a 5x5 frame onto this 16x16 panel via `icon_store.scale_into()`.
`main.py`'s pull mode and load-failure paths use these so the two devices
show the same meaning for the same event -- a child should read it the same
way off either, not byte-for-byte identical pixels. `show_idle()`'s breath
and the transfer progress bar stay whole-panel colour; neither has a wand
equivalent to mirror.

## Measured white

The datasheet white in `IconEditor/webapp/js/pipeline/ledGamut.js`,
duty (255,171,93), reads pale pink on this panel behind its dark diffuser.
Measured 2026-10-31 by eye: calibration grids of red/green/blue duty steps,
photographed beside a laptop showing a white page, narrowed over three rounds
(red 255 was pink at every green/blue; green 255 with red 185-200 was close).

| | Duty |
|---|---|
| white | (185, 255, 150) |
| light grey (x0.706) | (131, 180, 106) |
| grey (x0.431) | (80, 110, 65) |
| near black (x0.118) | (22, 30, 18) |

Applied 2026-11-01 to `icons/` and `IconEditor/icons/` (72 files)
with `drafts/remap_white.py`, which rewrites any colour on the old neutral
ratio to WHITE at the same brightness, then `sync_icons.py` for
ChatBroadcast. `games/halloween_frames.bin` gets the same swap from
`drafts/export_halloween.py`. The web editor's palette and its image-import
white use the measured white since 2026-11-15 (`ledGamut.js` `WHITE_DIR`,
`palette.js` `WHITE`). Not yet changed: the Python tools
(`hand_author_icons.py`, `tools/iconlib/`) and the simulator, so a newly authored or regenerated icon
comes out pink again -- run `remap_white.py` on it. One photo against one
laptop is a rough reading; recheck it on another panel.

## Two constraints that are not preferences

- **Radio before the panel.** `main.py` calls `enow.init()` before
  `icon_matrix` is imported. `esp_wifi_init()`/`esp_wifi_start()` need tens of
  KB of contiguous internal IDF heap, MicroPython's GC heap is carved out of
  that same heap in splits that are never returned, and `Matrix()` takes a
  768-byte NeoPixel buffer, a 512-byte offset table, a 256-byte LUT and a
  768-byte frame. Building the panel first is what produced
  `OSError: WiFi Out of Memory` on the wand. See
  [`docs_and_design/2026-09-23-ap-memory-order.md`](../docs_and_design/2026-09-23-ap-memory-order.md).
- **`MAX_INTENSITY = 0.50`** is a measured supply ceiling, not a preference.
  See the station tree's `readme.md` for the voltage ramp behind it.
  `IDLE_INTENSITY`/`ALERT_INTENSITY` (`main.py`) and `READY_INTENSITY`/
  `WINNER_INTENSITY` (`goalrace.py`) are all `0.15` for now -- a single
  conservative value while sparse-glyph current draw at higher brightness is
  uncharacterized on the bench, not a requirement the measured ceiling
  itself demands.

## Unverified

The LED data pin in `lib/hubtype.py` is per-unit: the driver board has two
data outputs (A0 → GPIO0, D5 → GPIO23) and which one is wired differs, so
`led_pin` is 0 for the bench unit and may be wrong for another.

Boot, the USB editor link, the pull (game and icons) and a two-device game
have all run on hardware. The card reader has not: it is fitted and
configured, but no tap has been read on a device yet, so the `0x28` address
and the shim in `lib/nfc_ws1850s.py` are unproven outside the host tests in
`tools/devtests/nfc_display.py`.

## Hardware bring-up notes

From the old `Icon Display Station` readme. The scripts it names (`single_pixel_test.py`,
`voltage_test.py`) were deleted with that tree and are in git history.

### Status (as of the old station)

Hardware bring-up complete (serpentine row-major wiring confirmed, power ceilings measured). `main.py` cycles the `icons/` folder. The image-to-icon conversion pipeline (below) is the current focus -- the six fruit icons in `assets/`/`icons/` are conversion-pipeline test fixtures, not vetted device content.

### Hardware

- **Board:** Seeed XIAO ESP32-C6
- **Driver board:** [Seeed LED Driver Board](https://wiki.seeedstudio.com/led_driver_board/) -- rated 5V/3A or 12V/2A output. Has two independent data pins; confirm which one is actually wired before assuming a `DATA_PIN` value:
  - A0 screw terminal → **GPIO0** (same pin Slide Score Station uses)
  - D5 Grove connector → **GPIO23**
- **Matrix:** BTF-LIGHTING WS2812B 5050 SMD, 16×16, 256 pixels
- **Reference comparison:** Slide Score Station drives a BTF-LIGHTING WS2812B "Pebble Pixel" seed string, only 40 pixels -- roughly 6x smaller load. Code that works there doesn't guarantee this board/matrix combo behaves the same under load.

### Known hardware issue

One driver board tested produced no output at all -- not a pin, wiring, or power problem, just a bad unit. Swapping to a second board fixed it. If a new Icon Display unit doesn't respond even to `single_pixel_test.py`, a board swap is a real possibility, not just a wiring bug to keep chasing.

### Bring-up scripts

- **`single_pixel_test.py`** -- minimal one-pixel sanity check, color-cycling a single pixel. Run this first on any new board/strip pairing, before the power test -- it isolates pin/wiring/board issues from power budget entirely, at ~30mA of load.
- **`voltage_test.py`** -- ramps the lit pixel count up one row (16px) at a time at a fixed test intensity, holding each step for a multimeter read or just watching the far end of the matrix for dimming/color shift/flicker. Rows cycle through a 6-color rainbow (same palette as Slide Score Station's `RAINBOW_ROWS`) instead of solid white, since real icon content mostly lights 1-2 channels per pixel, not all three -- white is the worst case, not the typical one.

### Findings so far (2026-08-25)

| Supply | Pattern | Intensity | Result |
|---|---|---|---|
| 5V wall adapter | solid white | 50% | Safe through 7 rows (112px, ~3.36A). Fails at 8 rows (128px, ~3.84A) -- brackets the driver board's rated 5V/3A output almost exactly. |
| 12V battery | solid white | 50% | Safe through 12 rows (192px) -- notably more headroom than the 5V path, likely because the board's 12V input runs through a buck regulator with more current capacity than the direct 5V terminal. |
| 12V battery | ROYGBIV rows (rainbow) | 50% | Ran the full ramp to all 256px / 16 rows with no failure. |

**Takeaway:** solid-white-at-50%-everywhere is a deliberately pessimistic worst case, not representative of real icon content -- that's why it fails well before the rainbow test does. The rainbow result is the one closer to how the display will actually be used, and it clears the full matrix comfortably at 50% on the 12V supply.

### Design guidance going forward

- **Electrical ceiling ≠ sustainable ceiling.** Every measurement above is an instantaneous read after a few seconds of hold. It says nothing about running for minutes or hours -- heat builds in both the WS2812 dies and the driver board's regulator well after the rail has already stabilized. "Didn't sag during the test" is not the same as "safe to leave on."
- **Static/idle content should run measurably dimmer than the tested ceiling**, not at it. Reserve higher brightness for short animations or highlight moments rather than a display that sits lit continuously at the same level -- both for headroom margin and because sustained heat is its own failure mode, separate from voltage sag.
- Use the existing `lib/brightness.py` convention (already used by `Leds` elsewhere in this codebase) for a global intensity multiplier in the eventual `main.py`, rather than hardcoding brightness -- gives one knob to dial down for sustained/idle states vs. brief full-brightness moments.
- If the full matrix ever needs to run bright and fully lit for extended periods, revisit power injection (a second 5V feed partway down the matrix) rather than leaning on brightness alone -- see the header of `voltage_test.py` for the injection note.

### Bring-up scripts (cont'd)

- **`icon_test.py`** -- tests the serpentine wiring hypothesis and previews real content. Lights each row in a rotating color first (clean bands confirm the row-major serpentine guess in its `pixel_index()`; diagonal streaks mean it's wired by column instead, like Slide Score Station's bar graph), then draws three shapes scaled 3x from the 5x5 grids in `lib/leds.py` (`HEART`, `STAR`, `ARROW_R` -- the arrow is asymmetric on purpose, so a wiring mistake is obvious). Runs dim (`ICON_INTENSITY = 0.2`) since these are static holds, not a load test. Also exposes `draw_pixels(pixels)`, which takes any flat 256-entry `(r,g,b)` tuple (row-major, top-left) and draws it through the same `pixel_index()`/intensity path -- the intended target for `image_to_icon.py`'s output.

### Confirmed (2026-08-25)

Physical pixel wiring is **serpentine, row-major, starting top-left** -- `icon_test.py`'s `pixel_index()` rainbow-rows check came back clean, and the scaled HEART/STAR/ARROW_R shapes rendered correctly (arrow pointed the right way, nothing mirrored/rotated). This mapping can now be relied on for real icon content instead of treated as a guess.
