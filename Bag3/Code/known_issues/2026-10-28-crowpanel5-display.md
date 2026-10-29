---
title: CrowPanel5 Display touch bus and RGB stability
date: 2026-10-28
status: open (workarounds in place)
devices: [CrowPanel5 Display (Elecrow CrowPanel HMI 5.0in V3, ESP32-S3 N4R8)]
components: [RGB panel 800x480, GT911, PCA9557, lvgl_micropython]
code:
  - Bag3/Code/Stations/CrowPanel5 Display/board.py
  - Bag3/Code/Stations/CrowPanel5 Display/display_lvgl.py
  - Bag3/Code/Stations/CrowPanel5 Display/firmware/CROWPANEL_S3_5/
open:
  - Touch bus dead after a software reset; root cause unknown
  - Count button does not register taps; touch axis orientation unchecked
keywords: [CrowPanel, Elecrow, GT911, PCA9557, I2C, GPIO19, GPIO20, USB-Serial-JTAG, RGB, drift, PCLK, soft reset]
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

## Image drifts sideways at 15 MHz

At Elecrow's 15 MHz pixel clock the image creeps sideways, faster while touching, and the
frame shows a slant. At 12 MHz (ESPHome's value) it is stable. lvgl_micropython's RGB bus
does not use ESP-IDF's bounce buffer.

**Setting:** `LCD_PCLK_HZ = 12_000_000` in `board.py`.
