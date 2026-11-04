# Firmware build

## Flashing more boards

`firmware/flash.sh` writes the Path A firmware to a board (erasing it first), checks it in the
REPL, copies `board.py`, `display_lvgl.py` and `main.py`, and hard-resets it. It needs
`esptool` and `mpremote` (`pip install esptool mpremote`) on `PATH`, and the merged `.bin`
from the build below. The `.bin` is not in the repo.

```sh
cd "Bag3/Code/Experiments/IPS096 Display"
firmware/flash.sh path/to/lvgl_micropy_ESP32_GENERIC_S3-SPIRAM_OCT-16.bin
```

- **Port:** with one board plugged in, the script finds it. With several, pass the port as
  the second argument, e.g. `firmware/flash.sh <bin> /dev/cu.usbmodem3101`.
- **Demo files only:** `firmware/flash.sh --files-only [port]` skips the erase and flash and
  copies the three files to a board that already has the firmware.
- **Output:** the REPL check prints `mem_free` (about 8,300,000) and `lvgl 9 4`. When it
  finishes, the board shows the test pattern; USR1 counts and USR2 resets.
- **Board not detected:** hold BOOT while plugging it in, then run the script again.
- **Erase and write in one call:** a separate `erase_flash` resets the board and the USB
  port drops out before the write.

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

The application partition has about 4 KB free with this build.

Check in the REPL:

```python
import gc, lvgl; gc.collect(); print(gc.mem_free(), lvgl.version_major(), lvgl.version_minor())
```

`mem_free` should be about 8 MB. If it is about 300 KB, PSRAM isn't enabled. Check that the build used the `SPIRAM_OCT` variant.

| Item | Value |
|---|---|
| lvgl_micropython commit | `d2d26467fa4cb9e99e569d899709043d086f7a6f` (MicroPython `78ff170`) |
| LVGL version | 9.4.0 |
| ESP-IDF version | v5.5.1 |

## Path B: stock MicroPython

1. **Download** `ESP32_GENERIC_S3` SPIRAM_OCT firmware from https://micropython.org/download/ESP32_GENERIC_S3/.
2. **Erase and flash** it as above.
3. **Copy** `lib/st7789py.py` and `fonts/romfonts/vga1_8x8.py` from https://github.com/russhughes/st7789py_mpy to the board root.

| Item | Value |
|---|---|
| MicroPython version | |
| st7789py_mpy commit | |
