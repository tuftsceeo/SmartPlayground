# Broadcast icon display

A 16×16 WS2812B panel (256 px) on a XIAO ESP32-C6 that loads, runs, switches
and unloads single-file game modules, the way MockWand does.

It gets those files from the Broadcast Box: tap a `getcode:<slug>` card, the
device queues a pull and reboots, and the next boot fetches its game file and
that game's named icons over the Box's SoftAP. The Box is the only device on
USB; this one has no serial protocol of its own.

## Relationship to `Bag3/Code/Stations/Icon Display Station/`

That tree is the original station: a USB icon authoring server
(`icon_server.py` over `json_link.py`) plus the host-side conversion pipeline
and the browser editor. It is unchanged and still the place to author icons.

This tree is a copy of the parts a game-playing device needs —
`icon_matrix.py`, `icon_store.py`, `icons/` — with the USB server, the
bring-up scripts and the host-side tooling left behind, and the wand's boot,
radio, card-reading and code-pull machinery added.

## Layout

```
boot.py            does not light the panel -- see its docstring
main.py            boot order, idle loop, game dispatch
hubtype.txt        "icon_display"
icon_matrix.py     Matrix: serpentine addressing, intensity LUT, bulk draw
icon_store.py      read/write icons/<name>.py as text
code_puller.py     SoftAP pull; PEER of BBoxFirmware/code_server.py
pull_flag.py       what a getcode tap leaves behind across the reboot
goalrace.py        built-in game (the display half of the two-device pair)
icons/             named icons, referenced from a game by name
lib/               espnow_manager, game_store, hubtype, display_tags,
                   nfc_reader, pn532, memprobe
```

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

## Unverified

The `icon_display` entry in `lib/hubtype.py` carries a pin map that has not
been checked against a board: the driver board has two data outputs (A0 →
GPIO0, D5 → GPIO23) and which is wired differs per unit, and the card reader
is not fitted at all, so `has_nfc` is `False` and the I2C pins are the wand's
carried over as a starting point. Nothing in this tree has run on hardware.
