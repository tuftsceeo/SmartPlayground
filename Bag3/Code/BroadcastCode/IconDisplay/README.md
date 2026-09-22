# Broadcast icon display

A 16×16 WS2812B panel (256 px) on a XIAO ESP32-C6 that loads, runs, switches
and unloads single-file game modules, the way MockWand does.

It gets those files from the Broadcast Box: tap a `getcode:<slug>` card, the
device queues a pull and reboots, and the next boot fetches its game file and
that game's named icons over the Box's SoftAP.

It also answers the icon editor web app over USB while idle, so icons can be
drawn and saved straight to it. That link is live whenever the device is not
in a game — there is nothing to switch on. A game owns the loop while it runs,
so authoring pauses for its duration.

## Relationship to `Bag3/Code/Stations/Icon Display Station/`

That tree is the original station: the USB icon authoring server plus the
host-side conversion pipeline and the browser editor. It is unchanged.

This tree copies the parts a game-playing device needs — `icon_matrix.py`,
`icon_store.py`, `icons/`, and the USB server — leaving behind the bring-up
scripts and the host-side tooling, and adds the wand's boot, radio,
card-reading and code-pull machinery.

`icon_server.py` differs from the station's copy in two ways: it is handed
the `Matrix` rather than building one (this device's `main.py` already made
the real one), and it carries `do_start_game`/`is_game`, a bench-only way to
launch a game over USB (see Writing a game, below) that the station has
nothing to launch for. The panel-ownership latch and the `start()` /
`step()` / `finish()` split are ported to both copies, not a divergence.
Both copies carry a `PEER:` note.

## Layout

```
boot.py            does not light the panel -- see its docstring
main.py            boot order, idle loop, game dispatch
hubtype.txt        "icon_display"
icon_matrix.py     Matrix: serpentine addressing, intensity LUT, bulk draw
icon_store.py      read/write icons/<name>.py as text
icon_server.py     USB command set for the icon editor; PEER of the station's
json_link.py       one JSON object per line, printable ASCII only
code_puller.py     SoftAP pull; PEER of BBoxFirmware/code_server.py
pull_flag.py       what a getcode tap leaves behind across the reboot
goalrace.py        built-in game (the display half of the two-device pair)
scoreboard.py      built-in game (running tally, the draw16/chart16 demo)
icons/             named icons, referenced from a game by name
lib/               espnow_manager, game_store, hubtype, display_tags,
                   nfc_reader, ws1850s, nfc_ws1850s, memprobe, shapes,
                   draw16, chart16
```

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

`code_server.py` sends a pulled game its own file and its icons; `ROLE_FILES`
has no `lib` leg and the staging tree carries no `lib/`. A game that imports
`draw16` or `chart16` therefore raises ImportError on a display flashed
before they were added. Flash the display before handing out games that use
them.

## Writing a game

```python
def play(nfc, panel, enow):
```

- `nfc` — an `NfcReader`, already built, or `None` while no reader is fitted.
  A wand game is handed the raw PN532 instead and builds its own; this one is
  not.
- `panel` — the `Matrix` itself: `set_pixels`, `draw_bytes`, `clear`,
  `set_intensity`, `redraw`, and `.src` as a scratch frame.
- `enow` — `ESPNowManager`, already initialized. Poll it every loop iteration
  and return when `msg_type` is `"stop"` or `"start_game"`, or the game cannot
  be switched out of.

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

## Two constraints that are not preferences

- **Radio before the panel.** `main.py` calls `enow.init()` before
  `icon_matrix` is imported. `esp_wifi_init()`/`esp_wifi_start()` need tens of
  KB of contiguous internal IDF heap, MicroPython's GC heap is carved out of
  that same heap in splits that are never returned, and `Matrix()` takes a
  768-byte NeoPixel buffer, a 512-byte offset table, a 256-byte LUT and a
  768-byte frame. Building the panel first is what produced
  `OSError: WiFi Out of Memory` on the wand.
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
