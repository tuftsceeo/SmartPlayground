# CrowPanel5 Display (bench)

Bench evaluation of the Elecrow CrowPanel HMI 5.0" V3 (ESP32-S3) on lvgl_micropython. It is not
used by teachers.

- **SoC:** ESP32-S3-WROOM-1-N4R8: 4 MB flash, 8 MB octal PSRAM (read with `esptool flash_id`).
- **Display:** 800x480, 16-bit parallel RGB565, driven by the ESP32-S3 RGB peripheral.
- **Touch:** GT911 at 0x5D. Its reset and interrupt lines are on a PCA9557 expander at 0x18,
  not on ESP32 GPIOs.
- **USB:** CH340 USB-serial on UART0 (`/dev/cu.usbserial-*`). The ESP32-S3's native USB pins
  (GPIO19/20) carry the touch I2C bus.

## Status

Display and touch work. Colours are correct, the image is stable under touch load, touch
coordinates follow the finger, and quick taps register.

## Files

Teacher tool (boot order in `main.py`: radio first, then display, then everything else):

- `main.py`: brings the radio up, then the display, then `panel.Panel` and the home screen, then `panel.run()`.
- `panel.py`: controller and main loop. Radio and NFC exclusivity, roster, targets, chat logs, roll call, start/stop, send code, cards, groups, nicknames. `panel.run()` also resumes the loop from the REPL.
- `host.py`: ChatBroadcast commands over `json_link` (identity `crowpanel`): the Dial's table plus `card.write`, `games.rescan`, `unlink`. Read-only commands are answered before Link; after Just charge only `identify` is.
- `ui_kit.py`: widget helpers, scrolling fixed-width labels, screen cache, back navigation, toast. Text, colour and HIDDEN changes are applied only when the value differs, since each one invalidates the object.
- `home.py` (1), `scr_recipients.py` (2), `scr_games.py` (3, sheet on the top layer), `scr_send.py` (4), `scr_cards.py` (5), `scr_device.py` (6), `scr_link_prompt.py` (7), `scr_linked.py` (8), `scr_linked_card.py` (9).
- `nfc_target.py`: the shared NFC tap target, fixed at x 528, y 150, 240x180.
- `kbd.py`: on-screen keyboard on its own screen, so a key press redraws only the key and the text field (group names, nicknames, card text up to 54 bytes). Screen refreshes are skipped while it is open.
- `perf_probe.py`: bench timing from the REPL (`screen_cost`, `kbd_cost`, `loop`). Not imported by the app.
- `make_icons.py`: host tool; converts `icons/*.png` to `icons/*.a8`.
- `roster.py`: devices by MAC (last heard, battery, signal), filled by roll call and any message heard.
- `store.py`: groups and nicknames in `/flash/panel.json`.
- `library.py`: built-in wand games plus `/flash/games/*.py` with `.tags.json`; card text per game.
- `fleet.py`: roll call, find, staggered `code_push` with pause and retry (adapted from the Dial's).
- `nfc.py`: PN532 on the touch bus behind the reader methods `card_writer.py` uses. Without a reader the card screens show the error.
- Copies from `BDialFirmware/`: `code_link.py`, `code_sender.py`, `json_link.py`, `stats_log.py`, `card_writer.py` (WS1850S class removed).
- `pn532.py` (copy of `Wand Module/lib/pn532.py`), `pn532_bus.py` (field control, bounded detect).
- `m0_main.py`, `m0_stress.py`, `m0_diag.py`: M0 coexistence test.

Bench:

- `board.py`: pin and timing constants (no allocation, safe to import first).
- `display_lvgl.py`: RGB bus, display, PCA9557 touch reset, GT911, task handler, test pattern. `BUS` holds the touch I2C bus.
- `icons/`: PNG icons exported from the design, white on transparent, at the exact size used (`<name>_<size>.png`). The board loads the `.a8` copies (width byte, height byte, one alpha byte per pixel) once into RAM and tints them with `image_recolor`. This firmware has no image cache, so drawing from PNG decoded the file on every redraw: about 2.8 s for a full home screen, against 0.24 s from A8. Run `make_icons.py` after changing a PNG.
- `ds_tokens.py`: design-system colours and radii (copy of the IPS096 file, full-size radii).
- `gallery.py`: design-system pages; Prev / Next buttons switch pages.
- `firmware/BUILD.md`: build and flash steps, with a version record.
- `firmware/CROWPANEL_S3_5/`: MicroPython board definition used for the build.
- `firmware/rgb_bus_bounce_buffer.patch`: lvgl_micropython RGB bus change (bounce buffer).

Running `import main` again from the REPL initialises the display twice and the board panics; restart with EN.

## Pins

From Elecrow's LovyanGFX config for this board, matched by the ESPHome device page.

| Function | GPIO |
|---|---|
| RGB data0-15 (B0-B4, G0-G5, R0-R4) | 8, 3, 46, 9, 1, 5, 6, 7, 15, 16, 4, 45, 48, 47, 21, 14 |
| DE / VSYNC / HSYNC / PCLK | 40 / 41 / 39 / 0 |
| Backlight | 2 |
| I2C SDA / SCL (GT911, PCA9557) | 19 / 20 |
| HMI port GPIO_D | 38 |
| UART TX / RX | 43 / 44 |
| I2S LRCLK / BCLK / SDIN | 18 / 42 / 17 |
| SD MOSI / MISO / CLK / CS | 11 / 13 / 12 / 10 |

Timings: hsync front/pulse/back 8/4/43, vsync 8/4/12, PCLK sampled on the falling edge.

Touch reset (Elecrow's V3 sequence, in `display_lvgl.touch_reset()`): all PCA9557 pins to
output and low, wait 20 ms, IO0 (GT911 RST) high, wait 100 ms, IO1 (GT911 INT) to input.

## Running

`fs_driver.fs_register` must run after `display_lvgl.init()`. Registering a file driver before
LVGL is initialised panics in `lv_fs_drv_register` (LoadProhibited) and the board reboots in a loop.
To break the loop, pulse RTS and send Ctrl-C repeatedly for a few seconds; the REPL prompt appears.

While `main.py` runs, mpremote can fail with "could not enter raw repl" or "could not exec
command". Re-run the command and check file sizes with `os.stat` afterwards.

Only a hardware reset (EN, power, or esptool's RTS reset) leaves GPIO19/20 usable. After
`machine.reset()` or `mpremote reset` the touch bus is dead; see
`Bag3/Code/known_issues/2026-10-28-crowpanel5-display.md`.

```sh
P=/dev/cu.usbserial-310
python3 -m mpremote connect $P resume fs cp board.py :board.py + fs cp display_lvgl.py :display_lvgl.py + fs cp ds_tokens.py :ds_tokens.py + fs cp gallery.py :gallery.py + fs cp home.py :home.py + fs cp main.py :main.py
python3 -m mpremote connect $P resume fs mkdir :icons + fs cp -r icons :
```

Then reset the board with its RST button, or pulse RTS from the host.

## Results

| Check | Result | Notes |
|---|---|---|
| Firmware | Pass | `mem_free` 8,320,528, LVGL 9.4; board name `Elecrow CrowPanel 5.0 V3` |
| I2C scan | Pass | 0x18 (PCA9557), 0x5D (GT911) |
| GT911 | Pass | Product 911, firmware 0x1060, 800x480 |
| Colours | Pass | R, G, B bars in order; border white |
| Stability | Pass | 12 MHz, bounce buffer, restart in VSYNC. Without the bounce buffer the image drifts under touch load, at 12 MHz as well as 15 |
| Touch tracking | Pass | Label coordinates follow the finger |
| Button | Pass | 10 quick taps, 10 counts, with a 10 ms touch read period (33 ms missed quick taps) |
| Shimmer | Pass | Backlight on without PWM (`STATE_HIGH`); with 38 kHz PWM, coloured areas oscillated in brightness |
| Gallery | Pass | Design-system pages look right by eye; gradients on the Header page |
| Home screen | Pass | Design 1 home layout and copy, 30 PNG icons tinted with image_recolor; checked by eye |
