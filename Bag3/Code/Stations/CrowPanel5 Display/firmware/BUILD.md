# Firmware build

lvgl_micropython with a custom board, `CROWPANEL_S3_5`: `ESP32_GENERIC_S3` with the native USB
peripherals (USB-Serial-JTAG console and TinyUSB CDC) turned off, so GPIO19/20 stay free for
the touch I2C bus. The REPL is on UART0 through the CH340.

Build in a separate clone from the one used for other boards. `make.py` patches files under
`lib/micropython` during a build and restores them at the end; an interrupted build leaves
them patched.

```sh
git clone https://github.com/lvgl-micropython/lvgl_micropython lvgl_micropython_crowpanel
cd lvgl_micropython_crowpanel
git checkout d2d26467fa4cb9e99e569d899709043d086f7a6f
cp -R "<repo>/Bag3/Code/Stations/CrowPanel5 Display/firmware/CROWPANEL_S3_5" \
    lib/micropython/ports/esp32/boards/
cp lib/micropython/ports/esp32/boards/ESP32_GENERIC_S3/board.json \
    lib/micropython/ports/esp32/boards/CROWPANEL_S3_5/
git apply "<repo>/Bag3/Code/Stations/CrowPanel5 Display/firmware/rgb_bus_bounce_buffer.patch"
python3 make.py esp32 BOARD=CROWPANEL_S3_5 BOARD_VARIANT=SPIRAM_OCT --flash-size=4 \
    DISPLAY=rgb_display INDEV=gt911
```

The `make.py` flags `--enable-cdc-repl` / `--enable-jtag-repl` are not used: they edit the
shared `mpconfigport.h`. The board's `mpconfigboard.h` and `sdkconfig.board` set the same things.

The patch gives the RGB panel two SRAM bounce buffers of 10 lines each, which DMA reads
instead of the PSRAM frame buffer. `sdkconfig.board` also sets
`CONFIG_LCD_RGB_RESTART_IN_VSYNC=y`. Without the bounce buffer the image drifts sideways
whenever LVGL redraws a lot.

After changing `sdkconfig.board`, delete the build directory
(`lib/micropython/ports/esp32/build-CROWPANEL_S3_5-SPIRAM_OCT`) and build from clean. Reusing it
failed with `KeyError: 'lv_animimg_get_src'` while generating the LVGL bindings.

Check the build turned the USB console off:

```sh
grep -E "USJ_ENABLE|CONSOLE_SECONDARY" lib/micropython/ports/esp32/build-CROWPANEL_S3_5-SPIRAM_OCT/sdkconfig
# CONFIG_USJ_ENABLE_USB_SERIAL_JTAG is not set
# CONFIG_ESP_CONSOLE_SECONDARY_NONE=y
```

The application partition has about 0% free with this build.

Flash (erase and write in one call):

```sh
python -m esptool --chip esp32s3 -p /dev/cu.usbserial-310 -b 460800 \
    --before default_reset --after hard_reset write_flash --flash_mode dio \
    --flash_size 4MB --flash_freq 80m --erase-all 0x0 build/lvgl_micropy_CROWPANEL_S3_5-4.bin
```

If the port opens but esptool fails with `termios.error: (22, 'Invalid argument')`, unplug
the board, hold BOOT while plugging it back in, and flash again.

Check in the REPL:

```python
import gc, lvgl; gc.collect(); print(gc.mem_free(), lvgl.version_major(), lvgl.version_minor())
```

| Item | Value |
|---|---|
| lvgl_micropython commit | `d2d26467fa4cb9e99e569d899709043d086f7a6f` (MicroPython `78ff170`) |
| LVGL version | 9.4.0 |
| ESP-IDF version | v5.5.1 |
| Firmware | `lvgl_micropy_CROWPANEL_S3_5-4.bin`, 2,963,840 bytes |
