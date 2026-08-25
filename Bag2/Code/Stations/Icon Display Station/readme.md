# Icon Display Station

A planned 16×16 WS2812B icon matrix, sharing the ESP32-C6 + LED Driver Board hardware pattern used by [Slide Score Station](../Slide%20Score%20Station/readme.md). This document currently tracks hardware bring-up and power budgeting -- the station's `main.py` hasn't been written yet.

## Status

Bring-up in progress. No `main.py` / `hubtype.py` entry yet -- just the diagnostic scripts below and the findings from running them.

## Hardware

- **Board:** Seeed XIAO ESP32-C6
- **Driver board:** [Seeed LED Driver Board](https://wiki.seeedstudio.com/led_driver_board/) -- rated 5V/3A or 12V/2A output. Has two independent data pins; confirm which one is actually wired before assuming a `DATA_PIN` value:
  - A0 screw terminal → **GPIO0** (same pin Slide Score Station uses)
  - D5 Grove connector → **GPIO23**
- **Matrix:** BTF-LIGHTING WS2812B 5050 SMD, 16×16, 256 pixels
- **Reference comparison:** Slide Score Station drives a BTF-LIGHTING WS2812B "Pebble Pixel" seed string, only 40 pixels -- roughly 6x smaller load. Code that works there doesn't guarantee this board/matrix combo behaves the same under load.

## Known hardware issue

One driver board tested produced no output at all -- not a pin, wiring, or power problem, just a bad unit. Swapping to a second board fixed it. If a new Icon Display unit doesn't respond even to `single_pixel_test.py`, a board swap is a real possibility, not just a wiring bug to keep chasing.

## Bring-up scripts

- **`single_pixel_test.py`** -- minimal one-pixel sanity check, color-cycling a single pixel. Run this first on any new board/strip pairing, before the power test -- it isolates pin/wiring/board issues from power budget entirely, at ~30mA of load.
- **`voltage_test.py`** -- ramps the lit pixel count up one row (16px) at a time at a fixed test intensity, holding each step for a multimeter read or just watching the far end of the matrix for dimming/color shift/flicker. Rows cycle through a 6-color rainbow (same palette as Slide Score Station's `RAINBOW_ROWS`) instead of solid white, since real icon content mostly lights 1-2 channels per pixel, not all three -- white is the worst case, not the typical one.

## Findings so far (2026-08-25)

| Supply | Pattern | Intensity | Result |
|---|---|---|---|
| 5V wall adapter | solid white | 50% | Safe through 7 rows (112px, ~3.36A). Fails at 8 rows (128px, ~3.84A) -- brackets the driver board's rated 5V/3A output almost exactly. |
| 12V battery | solid white | 50% | Safe through 12 rows (192px) -- notably more headroom than the 5V path, likely because the board's 12V input runs through a buck regulator with more current capacity than the direct 5V terminal. |
| 12V battery | ROYGBIV rows (rainbow) | 50% | Ran the full ramp to all 256px / 16 rows with no failure. |

**Takeaway:** solid-white-at-50%-everywhere is a deliberately pessimistic worst case, not representative of real icon content -- that's why it fails well before the rainbow test does. The rainbow result is the one closer to how the display will actually be used, and it clears the full matrix comfortably at 50% on the 12V supply.

## Design guidance going forward

- **Electrical ceiling ≠ sustainable ceiling.** Every measurement above is an instantaneous read after a few seconds of hold. It says nothing about running for minutes or hours -- heat builds in both the WS2812 dies and the driver board's regulator well after the rail has already stabilized. "Didn't sag during the test" is not the same as "safe to leave on."
- **Static/idle content should run measurably dimmer than the tested ceiling**, not at it. Reserve higher brightness for short animations or highlight moments rather than a display that sits lit continuously at the same level -- both for headroom margin and because sustained heat is its own failure mode, separate from voltage sag.
- Use the existing `lib/brightness.py` convention (already used by `Leds` elsewhere in this codebase) for a global intensity multiplier in the eventual `main.py`, rather than hardcoding brightness -- gives one knob to dial down for sustained/idle states vs. brief full-brightness moments.
- If the full matrix ever needs to run bright and fully lit for extended periods, revisit power injection (a second 5V feed partway down the matrix) rather than leaning on brightness alone -- see the header of `voltage_test.py` for the injection note.

## Bring-up scripts (cont'd)

- **`icon_test.py`** -- tests the serpentine wiring hypothesis and previews real content. Lights each row in a rotating color first (clean bands confirm the row-major serpentine guess in its `pixel_index()`; diagonal streaks mean it's wired by column instead, like Slide Score Station's bar graph), then draws three shapes scaled 3x from the 5x5 grids in `lib/leds.py` (`HEART`, `STAR`, `ARROW_R` -- the arrow is asymmetric on purpose, so a wiring mistake is obvious). Runs dim (`ICON_INTENSITY = 0.2`) since these are static holds, not a load test. Also exposes `draw_pixels(pixels)`, which takes any flat 256-entry `(r,g,b)` tuple (row-major, top-left) and draws it through the same `pixel_index()`/intensity path -- the intended target for `image_to_icon.py`'s output.
- **`image_to_icon.py`** -- PC-side tool (not a device script; needs `pip install pillow`) that converts a PNG/JPEG into a 16x16 icon: `python image_to_icon.py cat.png -o cat_icon.py`. Prints an ANSI terminal preview either way. `--palette` snaps every pixel to the nearest color in `lib/leds.py`'s named palette (via the same OKLab distance metric as `Utilities/color_selection.py`) so icons match the rest of the project's outdoor-tuned colors instead of raw image brightness; `--max-channel N` caps peak brightness per pixel to stay inside the power budget from the Findings table above. Output is a droppable `.py` file (`NAME = (...)`, same style as `leds.py`'s `SHAPE_*` constants) -- copy it to the device and `icon_test.draw_pixels(cat_icon.ICON)`.
  - Considered [WLED-PixelArtConverter](https://github.com/werkstrom/WLED-PixelArtConverter) instead of writing this: it targets WLED's own JSON segment/preset format, and these devices run plain MicroPython, not WLED, so its output has nowhere to plug in. Native tool was less work than adapting its output.

## Confirmed (2026-08-25)

Physical pixel wiring is **serpentine, row-major, starting top-left** -- `icon_test.py`'s `pixel_index()` rainbow-rows check came back clean, and the scaled HEART/STAR/ARROW_R shapes rendered correctly (arrow pointed the right way, nothing mirrored/rotated). This mapping can now be relied on for real icon content instead of treated as a guess.

## Open questions / next steps

- Pick a concrete sustained-brightness ceiling (see Design guidance above) before writing station logic.
- No `hubtype.py` entry / `main.py` yet -- `icon_test.py`'s `pixel_index()` is the reference implementation to carry over once that starts.
