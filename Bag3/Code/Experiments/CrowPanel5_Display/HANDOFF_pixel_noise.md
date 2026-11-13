# Handoff: CrowPanel pixel noise / shifted rows

Written 2026-11-10. Board: Elecrow CrowPanel HMI 5.0in V3 (ESP32-S3 N4R8, 800x480 RGB565),
`/dev/cu.usbserial-310` (also appears as usbmodem3101). Firmware: lvgl_micropython on ESP-IDF
v5.5.1, board `CROWPANEL_S3_5`, PSRAM octal at 80 MHz.

Read first: `Bag3/Code/HARDWARE_PROTOCOL.md` (ask before opening a port, `mpremote ... resume`),
`Bag3/Code/known_issues/2026-10-28-crowpanel5-display.md`, `firmware/BUILD.md`.

## Current state

**The fault came back after being marked fixed.** On 2026-11-10 the user reported the board
still shows jittery/pixel noise about every tenth row. Nothing has been checked on the board
since: no port was opened, so it is **unknown whether the board runs the patched build**.

Symptom as first described (2026-11-02): the first ~100 left-hand columns of every tenth pixel
row are shifted sideways, top to bottom. Ten rows is the bounce-buffer size, so the fault sits at
bounce-buffer boundaries.

## Attempts, in order

| # | Attempt | Result |
|---|---|---|
| 1 | Pixel clock 15 MHz to 12 MHz (earlier, 2026-10-28) | Slowed the sideways drift under redraw load, did not stop it. |
| 2 | SRAM bounce buffers, 10 lines each (`firmware/rgb_bus_bounce_buffer.patch`, sets `bounce_buffer_size_px = width * 10` in `rgb_bus.c`) plus `CONFIG_LCD_RGB_RESTART_IN_VSYNC=y` | Fixed the drift. This is where the every-tenth-row shift appeared. |
| 3 | Pixel clock 12 MHz to 10 MHz (`board.py` `LCD_PCLK_HZ`), reflashed | **No change** to the row shift. Reverted to 12 MHz. |
| 4 | Dirty-rows copy (`firmware/rgb_bus_dirty_rows_copy.patch`), rebuilt and flashed | Looked fixed on 2026-11-02 (user: "Fixed"). **Now reported as recurring.** |

### What the dirty-rows patch does

`rgb_bus_rotation.c` (in the build clone, `ext_mod/lcd_bus/esp32_src/`, gitignored) ran a
full-frame 768 KB PSRAM-to-PSRAM `memcpy` after every buffer swap. That competes with the
bounce-buffer refill interrupt, which also reads PSRAM. The patch tracks the min `y_start` and
max `y_end` of rows updated since the last swap and copies only those rows. When the display is
rotated it marks every row dirty, so the full copy still happens.

Theory (unproven): the refill interrupt misses its deadline while the copy runs, so a bounce
buffer is refilled late and its first part is displayed shifted.

## Why it may still happen

1. **Board not running the patched build.** A later re-flash or another tool could have put an
   unpatched binary back. Check the build string and compare with the build in `build/`.
2. **The copy is reduced, not removed.** Large redraws (screen transitions, animation) still copy
   many rows. If the shift appears only while the screen changes and not on a static screen, this
   is the cause.
3. **Radio load on core 0.** WiFi/ESP-NOW runs on the same core. The shift was first seen with the
   radio running. ESP-NOW has not been tested since the flash.
4. **Marginal hardware**: PSRAM at 80 MHz or this board's timing.

## Untried ideas

- Larger or smaller bounce buffers (20 lines, 5 lines).
- Place the bounce-buffer refill and copy task on core 1, away from the radio.
- Raise the priority of the RGB refill interrupt (IRAM-safe placement), or lower the copy task's.
- Drop the second frame buffer / the post-swap copy entirely (single frame buffer or direct mode).
- PSRAM at 40 MHz as a test of whether PSRAM bandwidth is the limit.
- Reduce LVGL redraw size (smaller dirty areas, partial refresh settings).
- Compare against the ESPHome Elecrow 5-inch settings
  (https://devices.esphome.io/devices/elecrow-5inch-esp32-display/) and the Elecrow 7-inch timing
  post (https://www.espboards.dev/blog/esphome-configuring-elecrow-7-inch-display/), which
  reports similar tuning difficulty. Their pixel clock and porch values were not fully compared
  against `board.py`.

## Other facts that constrain a fix

- **Reset through EN only** (RST button, RTS pulse, power). After `machine.reset()` or
  `mpremote reset` the touch I2C bus (GPIO19/20, GT911 + PCA9557) is dead.
- Backlight on PWM shimmers (38 kHz), and `set_backlight(100)` is not fully on; see the
  known-issues note.
- The application partition has about 0% free.
- After editing `sdkconfig.board`, delete
  `lib/micropython/ports/esp32/build-CROWPANEL_S3_5-SPIRAM_OCT` and build from clean.
- The firmware sdkconfig matched the previous build except for the partition-table path. The
  only source change in the 2026-11-02 build was the dirty-rows copy.

## Where things are

- Build clone: `build/lvgl_micropython_crowpanel/` in this folder (gitignored), at lvgl_micropython
  commit `d2d26467fa4cb9e99e569d899709043d086f7a6f`.
- Previous firmware and device files: `firmware/backup_2026-11-02/` (old `.bin`, `sdkconfig`,
  `boot.py`, `main_normal.py`, `/flash` state files). Old `.bin` sha256 starts `d664e4f9`.
- Rebuilt firmware size: 2,964,256 bytes.
- Flash command: in `firmware/BUILD.md` (full erase wipes `/flash`, including custom games under
  `/flash/games`; the user says those are not critical).
- Commit with the patch, rename and docs: `3b14955`.

## Open items

- Read the build string from the board and confirm it is the patched build.
- Find out when the shift appears: static screen, during redraws, or with the radio busy.
- Test ESP-NOW on the board. The wand reported a failed code pull from the panel after the
  2026-11-02 flash; this is unresolved and may or may not be related.

## Update (2026-11-10)

Not resolved; see the known-issues note (2026-11-10 entry). The pre-flash firmware on 310 is unknown.
