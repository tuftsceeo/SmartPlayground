---
title: CrowPanel5 Display touch bus and RGB stability
date: 2026-10-28
status: open (workarounds in place)
devices: [CrowPanel5 Display (Elecrow CrowPanel HMI 5.0in V3, ESP32-S3 N4R8)]
components: [RGB panel 800x480, GT911, PCA9557, lvgl_micropython]
code:
  - Bag3/Code/Experiments/CrowPanel5 Display/board.py
  - Bag3/Code/Experiments/CrowPanel5 Display/display_lvgl.py
  - Bag3/Code/Experiments/CrowPanel5 Display/firmware/CROWPANEL_S3_5/
open:
  - Touch bus dead after a software reset; root cause unknown
keywords: [CrowPanel, Elecrow, GT911, PCA9557, I2C, GPIO19, GPIO20, USB-Serial-JTAG, RGB, drift, PCLK, soft reset, backlight, PWM, flicker, shimmer]
---

# CrowPanel5 Display

## Native USB holds the touch I2C pins

GPIO19/20 are the ESP32-S3's native USB pins and the board's touch I2C bus. On
`ESP32_GENERIC_S3` firmware the pins cannot be driven: a pin set to output low reads high, and
both hardware and software I2C scans are empty. Clearing the USB pad-enable bits and the IO_MUX
sleep-select bit from Python had no effect.

**Fix:** the `CROWPANEL_S3_5` board turns off the USB-Serial-JTAG console and TinyUSB CDC (see
`firmware/BUILD.md`). With it, the scan finds 0x18 and 0x5D.

## Touch bus dead after a software reset

After `machine.reset()` or `mpremote reset` (reset cause 2) on the `CROWPANEL_S3_5` firmware,
GPIO19/20 again cannot be driven low and the scan is empty. After an EN reset (RTS pulse,
RST button, power) they work (reset cause 1). IO_MUX for GPIO19 reads `0x1f02` in the broken
state and `0xc02` after an EN reset; clearing bit 1 alone does not restore it.

**Workaround:** reset through EN only.

## Image drifts sideways under redraw load

Without a bounce buffer the image creeps sideways while LVGL redraws, and a frame shows a
slant. The RGB DMA reads the frame buffer from PSRAM, and lvgl_micropython's RGB bus copies the
whole 768 KB frame PSRAM-to-PSRAM after every update. Lowering the pixel clock from 15 to
12 MHz slows the drift but does not stop it.

**Fix:** `firmware/rgb_bus_bounce_buffer.patch` (SRAM bounce buffers, 10 lines each) and
`CONFIG_LCD_RGB_RESTART_IN_VSYNC=y`, at 12 MHz. Stable under continuous touch.

## Quick taps missed

With LVGL's default 33 ms touch read period, quick taps on a button register no event; held
presses do. `display_lvgl.init()` sets the read period to 10 ms; 10 quick taps gave 10 clicks.

## Colour shimmer from backlight PWM

With the backlight on `STATE_PWM` (lvgl_micropython drives it at 38 kHz; `set_backlight(100)`
is not fully on), coloured areas oscillate smoothly in brightness with no touch.

**Fix:** `display_lvgl.init()` uses `STATE_HIGH`, so the backlight is on without PWM and cannot
be dimmed. The shimmer stopped.
