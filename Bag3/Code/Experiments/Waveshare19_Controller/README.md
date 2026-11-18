# Waveshare19_Controller

Early mockup of the Waveshare ESP32-S3-Touch-LCD-1.9 as a larger Broadcast Box
(170x320 portrait, touch, LVGL). Software only: **nothing here has run on the board.**
Plan: `Bag3/STRESS_TEST_PREP_PLAN.md`, S13. Not part of the stress-test firmware.

## Files
- `mockup.html`, `screenshots/`: the 170x320 HTML mockup and its PNGs.
- `main.py` starts `mockup.py`: seven LVGL screens with made-up data (`fake_data.py`).
  No radio, NFC or file transfer. `display_test.py`, `probe.py`, `bl_test.py` and
  `color_test.py` are the bench probes and still run on their own.
- Copied: `tokens.py` (subset of `CrowPanel5_Display/ds_tokens.py`); `hw_display.py`
  (display and touch setup from `display_test.py`); `ui.py` (cut down from
  `CrowPanel5_Display/ui_kit.py`).

## Screens
| # | Screen | Box / Dial today | Added by the touch screen |
|---|---|---|---|
| 1 | Home | Box idle; Dial ring Read / Tags / Text | Status strip (link, serving, battery); Games, Read card, Serving buttons |
| 2 | Games | Box tier-1 list; Dial game list | Full names with pull counts; Utility tags row |
| 3 | Game's tags | Box tier-2 list; Dial tag list | Colour dots (code purple, play blue), written mark, Write all, Back |
| 4 | Write: hold card | Box armed/scanning; Dial scan | Large tag name, "Tag n of N", progress bar, Cancel |
| 5 | Write result | Box Written / Already / Failed / Done; Dial result | One screen with a coloured band; Next or Done |
| 6 | Read card | Box Read Card; Dial reader | Waits with "Tap a card"; Exit |
| 7 | Serving | Box "Sharing <id>" + pickups | Host id, game, pull count, recent pulls, Stop |

Cut for now: Text card entry (Dial keyboard) and Booting/error.

## NFC reader pins (`board.py`)
The reader gets its own I2C bus so it cannot stall touch or the IMU on bus 0.
Checked against every pin constant in `board.py`; no clash. Not checked: which pins
Waveshare brings out to a header. The WS1850S is assumed, as on the Box.

| Constant | GPIO | Reason |
|---|---|---|
| `NFC_SDA` | 1 | Plain GPIO (ADC1 ch0); no strapping, USB, PSRAM or display role |
| `NFC_SCL` | 2 | Plain GPIO (ADC1 ch1); next to GPIO 1 for easy wiring |
| `NFC_RST` | 5 | Plain GPIO for reader reset or power-down |
| `NFC_IRQ` | 6 | Plain GPIO; optional, polling works without it |

Avoided: 3, 45, 46 (strapping), 19/20 (USB), 42 (JTAG pad), 15/16 (32 kHz crystal pads),
38 (kept spare), 33-37 (PSRAM).

## What the board lacks compared with the Box and Dial
- **NFC reader:** none fitted; the pins above are a proposal.
- **ESP-NOW:** unknown. The S3 has the radio; whether this lvgl_micropython build includes
  `espnow` is a one-line REPL check. The radio must claim its memory before LVGL or `ui`
  is imported, so `mockup.py` would need reordering (see
  `Bag3/Code/docs_and_design/2026-09-23-ap-memory-order.md`).
- **Game files and serving:** nothing stores, serves or pulls games. The SD card is SDMMC
  1-bit, so it needs a different driver from the SPI-style one.
- **Laptop link:** no `json_link` / `bdial_server` / `code_link` equivalent. Native USB is
  on GPIO 19/20.
- **Controls:** touch only; no hold-to-exit or knob. No speaker or buzzer pin, so no beeps.
- **Battery:** ADC through a divider; no percentage curve or charge state like the Box's.

## Fonts
The board has only Montserrat 14, 16 and 24 (per the user). Headings and big text will be
smaller than in `mockup.html`, which uses a larger Nunito, until a larger font is built in.
`ui.py` falls back to Montserrat 16 if 24 is missing.

## Never run on the board
All LVGL code; `lv.SYMBOL.*` availability; the `lv.timer_create` call; touch reaching LVGL
as clicks (`display_test.py` reads the touch chip itself); the NFC pin choice.
