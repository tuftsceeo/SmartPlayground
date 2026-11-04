# Unit Tests

Hardware validation scripts for PCB bring-up and troubleshooting. These are standalone scripts that test individual components on the wand module board **without requiring the `lib/` folder** — each script contains its own inline driver code so it can run on a freshly flashed device.

## Test Scripts

### SideOne.py

Tests components on one side of the PCB:

- **Accelerometer (LIS2DW12)** — WHO_AM_I register check, 5 sample readings at ±4g
- **Battery Gauge (MAX17048)** — version register, voltage and state-of-charge readout
- **NFC Reader (PN532)** — firmware version, SAM configuration, 10-second tag detection window
- **Vibration Motor** — digital on/off test followed by PWM ramp

### SideTwo.py

Tests all components including those on the other side:

- **Accelerometer (LIS2DW12)** — same as SideOne
- **Battery Gauge (MAX17048)** — same as SideOne
- **Light Sensor (OPT3002)** — manufacturer/device ID check, 5 lux readings at 100ms continuous mode
- **NeoPixels (25× SK6812)** — red/green/blue solid fill, rainbow chase animation
- **NFC Reader (PN532)** — same as SideOne
- **Vibration Motor** — same as SideOne

## Usage

1. Connect the wand module via USB and open Thonny (or any MicroPython REPL).
2. Copy the desired test script to the device as `main.py`, or run it directly from the REPL.
3. Watch the serial output for pass/fail results on each component. NFC tests will wait up to 10 seconds for you to tap a tag.

## Notes

- These scripts use `f-strings` for readability. The production code in `Code/` avoids f-strings due to compatibility issues on some MicroPython builds — if a test crashes on string formatting, that itself is useful diagnostic information.
- The accelerometer sensitivity value used in these tests (`0.000488`) differs from the corrected value in the production drivers (`0.000122`). The tests are meant to confirm the sensor responds, not to provide calibrated readings.
- I2C runs at 400 kHz in these tests for faster scanning. Production code uses 100 kHz for PN532 compatibility.
