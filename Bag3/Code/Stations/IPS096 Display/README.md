# IPS096 Display (bench)

Bench evaluation of the Seeed XIAO 0.96" IPS Display (ESP32-S3). It is not used by teachers.

- **SoC:** ESP32-S3R8, 8 MB octal PSRAM, 16 MB flash.
- **Display:** ST7789, 80x160, SPI. The backlight starts off, and `init()` turns it on.
- **Other:** LSM6DS3 IMU (I2C), PDM mic, two active-low buttons, VBAT divider.

## Status

Path A works on the board: test pattern aligned, colours correct, both buttons work. Path B is
untested.

- **Path A (LVGL, `display_lvgl.py`):** primary.
- **Path B (stock MicroPython + st7789py, `display_st7789.py`):** fallback.

Fall back to B if any of these happens:
- **The LVGL build fails** and can't be fixed.
- **The panel can't be aligned or coloured correctly.**
- **DRAM is too short** for the project's needs.

## Files

- `board.py`: pin constants (no allocation, safe to import first).
- `display_lvgl.py`, `display_st7789.py`: the display setup for each path.
- `main.py`: minimal demo. Test pattern plus a counter: USR1 increments, USR2 resets. Set `DISPLAY_PATH` to choose the path. No radio; playground integration is out of scope.
- `firmware/BUILD.md`: build and flash steps, with a version record.
- `firmware/flash.sh`: flashes the firmware and demo files to a board; see `firmware/BUILD.md`.

## Pins

The XIAO pin and net come from Seeed's schematic table. The GPIO numbers come from the XIAO
ESP32-S3 Plus pin map.

| XIAO | Net | GPIO |
|---|---|---|
| D2 | LCD_CS | 3 |
| D3 | LCD_DC | 4 |
| D8 | LCD_SCK | 7 |
| D10 | LCD_MOSI | 9 |
| D17 | LCD_RST | 13 |
| D18 | LCD_BL_PWM | 12 |
| D6 | BTN_USR1 | 43 |
| D7 | BTN_USR2 | 44 |
| D4 / D5 | I2C SDA / SCL | 5 / 6 |
| D14 | IMU_INT | 41 |
| D0 / D1 | PDM CLK / DATA | 1 / 2 |
| D11 / D12 / D13 | I2S SD / SCK / WS | 38 / 39 / 40 |
| D16 | VBAT_ADC | 10 |

The buttons sit on GPIO43/44, which are UART0. If a button reads stuck or the REPL echoes
garbage, the firmware has a REPL on UART0 and it needs to be disabled.

## Bring-up checklist

1. **Confirm the firmware in the REPL:** `mem_free` is about 8 MB and `import lvgl` works (Path A).
2. **Run `main.py`:** the white border sits flush at every edge, and the bars read red, green, blue from left to right.
   - **Bars and border misaligned:** change `LCD_X_OFF`/`LCD_Y_OFF` in `board.py` (try 24/0 and 26/1).
   - **Colours swapped:** flip `LCD_BGR`.
   - **Colours look like a negative:** flip `LCD_INVERT`.
3. **Press each button:** USR1 increments the count, USR2 resets it, and serial prints each press.

## Results

| Check | Path | Result | Notes |
|---|---|---|---|
| Firmware | A | Pass | `mem_free` 8,320,496; `import lvgl` works, LVGL 9.4.0 |
| `display_lvgl.py` | A | Pass | Driver arguments matched the source; bars set non-scrollable |
| Alignment | A | Pass | `LCD_X_OFF = 24`, `LCD_Y_OFF = 0`; 26/1 clipped one long edge and left spare rows at the bottom |
| Colours | A | Pass | `LCD_BGR = True`, `LCD_INVERT = False`; inversion on gave a negative |
| Buttons | A | Pass | USR1 increments, USR2 resets, serial prints each; no UART0 REPL conflict |
| Soft reboot | A | Fail | After Ctrl-D, `main.py` raises `TypeError` in `machine.SPI.Bus`; hard reset or power cycle runs it |

Path A was used: the LVGL build and driver worked, so the fallback was not needed.
