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

- `board.py`: pin and timing constants (no allocation, safe to import first).
- `display_lvgl.py`: RGB bus, display, PCA9557 touch reset, GT911, task handler, test pattern.
- `main.py`: starts the gallery.
- `ds_tokens.py`: design-system colours and radii (copy of the IPS096 file, full-size radii).
- `gallery.py`: design-system pages (Levels, Button, Chip, Toast, Status, Field, Header, Palette); Prev / Next buttons switch pages. Built-in Montserrat 12/14/16 only.
- `firmware/BUILD.md`: build and flash steps, with a version record.
- `firmware/CROWPANEL_S3_5/`: MicroPython board definition used for the build.
- `firmware/rgb_bus_bounce_buffer.patch`: lvgl_micropython RGB bus change (bounce buffer).

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

Only a hardware reset (EN, power, or esptool's RTS reset) leaves GPIO19/20 usable. After
`machine.reset()` or `mpremote reset` the touch bus is dead; see
`Bag3/Code/known_issues/2026-10-28-crowpanel5-display.md`.

```sh
P=/dev/cu.usbserial-310
python3 -m mpremote connect $P resume fs cp board.py :board.py + fs cp display_lvgl.py :display_lvgl.py + fs cp ds_tokens.py :ds_tokens.py + fs cp gallery.py :gallery.py + fs cp main.py :main.py
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
