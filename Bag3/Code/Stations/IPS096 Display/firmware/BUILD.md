# Firmware build

## Path A: lvgl_micropython

Build host: Linux or macOS with git, Python 3, cmake and ninja. The build script downloads ESP-IDF.

```sh
git clone https://github.com/lvgl-micropython/lvgl_micropython
cd lvgl_micropython
git rev-parse HEAD            # record below
python3 make.py esp32 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT \
    --flash-size=16 DISPLAY=st7789
```

Flash. Use the port from `ls /dev/tty*`, and hold BOOT while plugging in if the board isn't detected.

```sh
esptool.py --chip esp32s3 --port <PORT> erase_flash
esptool.py --chip esp32s3 --port <PORT> write_flash 0x0 build/lvgl_micropy_ESP32_GENERIC_S3-SPIRAM_OCT-16.bin
```

The file name of the merged `.bin` is printed at the end of the build.

Check in the REPL:

```python
import gc, lvgl; gc.collect(); print(gc.mem_free(), lvgl.version_major(), lvgl.version_minor())
```

`mem_free` should be about 8 MB. If it is about 300 KB, PSRAM isn't enabled. Check that the build used the `SPIRAM_OCT` variant.

| Item | Value |
|---|---|
| lvgl_micropython commit | |
| LVGL version | |
| ESP-IDF version | |

## Path B: stock MicroPython

1. **Download** `ESP32_GENERIC_S3` SPIRAM_OCT firmware from https://micropython.org/download/ESP32_GENERIC_S3/.
2. **Erase and flash** it as above.
3. **Copy** `lib/st7789py.py` and `fonts/romfonts/vga1_8x8.py` from https://github.com/russhughes/st7789py_mpy to the board root.

| Item | Value |
|---|---|
| MicroPython version | |
| st7789py_mpy commit | |
