# Code

All MicroPython application code for the Smart Playground system. Three devices communicate over ESP-NOW: a wand module, a hub station, and a scoreboard.

## Folder Structure

```
Code/
├── lib/                          Shared drivers & helpers (MUST be copied to every device)
│   ├── pn532.py                  PN532 NFC reader driver (I2C)
│   ├── lis2dw12.py               LIS2DW12 accelerometer driver
│   ├── max17048.py               MAX17048 battery fuel gauge driver
│   ├── opt3002.py                OPT3002 ambient light sensor driver
│   ├── nfc_reader.py             NFC tag scanning, NDEF decoding, gesture tag detection
│   ├── leds.py                   NeoPixel control, status indicators, animations
│   ├── buzzer.py                 Piezo buzzer — beeps, melodies, feedback sounds
│   ├── actions.py                Action definitions, resource mapping, AND/THEN chain execution
│   ├── battery.py                Battery level display on LEDs
│   ├── gesture.py                Gesture recording, feature extraction, matching (legacy)
│   └── gesture_engine.py         Gesture recognition with NFC-stored templates
│
├── Wand Module/
│   ├── main.py                   Main entry point — NFC trigger→action programming engine
│   ├── color_quest.py            Color Quest scavenger hunt game
│   ├── target.py                 Scoreboard MAC address configuration
│   └── readme.md                 Detailed hardware reference and API docs
│
└── Stations/
    ├── Programming Station/
    │   └── main.py               4×PN532 NFC hub — reads tags and broadcasts sequences via ESP-NOW
    └── Slide Score Station/
        └── main.py               40-LED scoreboard — receives scores and displays bar graph
```

## Deploying the `lib/` Folder

**The `lib/` folder must be copied to every microcontroller before running any code.** MicroPython looks for imports in `/lib/` on the device's filesystem. Without it, you'll get `ImportError` on boot.

### Step-by-step (using Thonny)

1. Connect the ESP32-C6 to your computer via USB.
2. Open **Thonny** and select the MicroPython interpreter for your board (bottom-right corner).
3. In the **Files** panel (View → Files), you should see your local filesystem on the left and the device filesystem on the right.
4. On the device side, create a folder called `lib` if it doesn't already exist (right-click → New directory).
5. From your local filesystem, navigate to `Bag2/Code/lib/`.
6. Select **all `.py` files** in `lib/` and right-click → **Upload to /lib**.
7. Verify: you should see all the driver files listed under `/lib/` on the device.

### Step-by-step (using mpremote)

If you prefer the command line, `mpremote` (included with MicroPython tools) can copy the folder in one command:

```bash
# From the Bag2/Code/ directory:
mpremote connect <PORT> fs cp -r lib/ :/lib/
```

Replace `<PORT>` with your device's serial port (e.g., `/dev/ttyACM0` on Linux, `COM3` on Windows).

To verify the files are on the device:

```bash
mpremote connect <PORT> fs ls /lib/
```

### Which files go where

| Device | `lib/` | Root files |
|---|---|---|
| **Wand Module** | All of `lib/` | `main.py`, `color_quest.py`, `target.py` |
| **Programming Station** | `pn532.py`, `nfc_reader.py` | `main.py` |
| **Slide Score Station** | *(none required)* | `main.py` |

The wand needs the full library set because it uses every sensor. The programming station only needs the NFC drivers. The scoreboard is self-contained and has no `lib/` dependencies — but copying the full `lib/` to every device does no harm and keeps things simple.

### Configuring `target.py`

Before deploying the wand, update `target.py` with your scoreboard's MAC address. Run this on the scoreboard device to find it:

```python
import network
sta = network.WLAN(network.STA_IF)
sta.active(True)
print(':'.join('%02X' % b for b in sta.config('mac')))
```

Then edit `target.py`:

```python
SCORE_MAC = b'\xAA\xBB\xCC\xDD\xEE\xFF'  # replace with your MAC
```

## I2C Bus Note

The shared I2C bus runs at **100 kHz** because the PN532 is unreliable at higher speeds. All other sensors tolerate this frequency. Use `machine.SoftI2C` with `freq=100_000`.
