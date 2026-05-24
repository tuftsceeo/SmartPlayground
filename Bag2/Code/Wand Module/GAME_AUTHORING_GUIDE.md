# Wand Game Authoring Guide

This guide provides the patterns and practices for creating games for the SmartPlayground wand. Use it as context when generating new game modules.

## Hardware Available

| Component          | API                    | Notes                                                                 |
| ------------------ | ---------------------- | --------------------------------------------------------------------- |
| **5x5 LED Matrix** | `leds` (Leds class)    | RGB NeoPixels, auto-scales with ambient brightness                    |
| **NFC Reader**     | `nfc` (PN532)          | MIFARE Classic tags, NDEF text payloads                               |
| **Buzzer**         | `buz` (Buzzer class)   | PWM tones, NOTE_FREQ dict available                                   |
| **Button**         | GPIO 0, active LOW     | Pull-up enabled, debounce required                                    |
| **Accelerometer**  | `accel` (may be None)  | Motion detection, shake gestures                                      |
| **I2C Bus**        | `i2c`                  | Shared bus at 100kHz                                                  |
| **ESP-NOW**        | `enow` (ESPNowManager) | Passed from `main.py`; do not create a second radio stack in `play()` |

### ESP-NOW

`main.py` initializes one `ESPNowManager` as `enow` and passes it into every game's `play()`. Do not call `espnow.ESPNow()` or a local `espnow_init()` inside `play()` — only one ESP-NOW stack should be active. Standalone `main()` in a game file may create its own `ESPNowManager()` for bench testing.

## Module Template

Template Overview
Entry points:
play(nfc, leds, buz, accel, i2c, enow) — called from main.py
main() — standalone testing

Template Pattern: 1. GameClass with **init**() and run() 2. play() for wand integration (hardware + enow passed in) 3. main() for standalone testing (initializes hardware) 4. CRITICAL: ESP-NOW stop + NFC stop checked at START of every loop

```python
"""
Game Name — Short Description
=============================
Explain gameplay in 2-3 sentences.
"""

import machine, time
from machine import Pin
from pn532 import PN532
from nfc_reader import NfcReader
from leds import RED, GREEN, BLUE, YELLOW, OFF, SHAPE_CHECK, SHAPE_X, SHAPE_HAPPY_FACE, SHAPE_SAD_FACE
from buzzer import NOTE_FREQ



# ─── Hardware Config (only used in main()) ───
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN, BUTTON_PIN, PN532_ADDR = 19, 0, 0x24

# ─── Game Config ───
COMMANDS = {"action1", "action2", "stop"}  # NFC tag command examples
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 40

# ─── Sound Sequences ───
SOUNDS = {
    'start':   [(523, 80, 40), (659, 80, 40), (784, 120, 0)],
    'success': [(880, 60, 30), (1100, 80, 0)],
    'fail':    [(400, 150, 60), (250, 200, 0)],
} # example unique per game entry fanfare for user

def _play_sound(buz, name):
    for freq, dur, gap in SOUNDS.get(name, []):
        buz.beep(freq, dur)
        if gap: time.sleep_ms(gap)


class YourGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)  # Avoid false trigger
        self._frame = 0

    def _check_stop(self):
        msg_type, _, _ = self.enow.poll()
        if msg_type == "stop":
            return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            return cmd == "stop"
        except Exception:
            return False

    def _render(self):
        """Update LED display based on game state."""
        pass  # Implement display logic here

    def run(self):
        print("  Game instructions here")
        print("  Tap STOP tag or station stop to exit\n")

        while True:
            # ── STOP CHECK FIRST ──
            if self._check_stop():
                print("  Stop detected")
                return

            # ── GAME LOGIC ──
            # ... your game code ...

            self._render()
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    _play_sound(buz, 'start')
    print("\n  === GAME NAME ===")
    try:
        YourGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """Standalone testing."""
    print("\n" + "=" * 45)
    print("  Game Name — Description")
    print("=" * 45)

    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)

    import brightness
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c); light.init()
        mult, lux = brightness.calibrate(light)
        if lux: print("  Light: %.0f lux -> brightness x%.2f" % (lux, mult))
    except Exception as e:
        print("  [WARN] OPT3002: %s" % e)

    from leds import Leds
    from buzzer import Buzzer
    leds, buz = Leds(), Buzzer(BUZZER_PIN)

    nfc = PN532(i2c, PN532_ADDR)
    try:
        nfc.begin()
        print("  NFC ready")
    except Exception as e:
        print("  NFC init failed: %s" % e)
        return

    accel = None
    try:
        from lis2dw12 import LIS2DW12, RANGE_4G
        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)
    except Exception as e:
        print("  [WARN] Accel: %s" % e)

    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    enow.init()

    play(nfc, leds, buz, accel, i2c, enow)


if __name__ == "__main__":
    main()
```

## LED API (leds.py)

### Colors (auto-scale with brightness)

```python
from leds import (
    OFF, RED, GREEN, BLUE, YELLOW, PURPLE, PINK, WHITE, AMBER, TEAL,
    RED_DIM, GREEN_DIM, BLUE_DIM, YELLOW_DIM,  # For visual hierarchy
)
```

### Shapes (5x5 patterns)

```python
from leds import (
    # Symbols
    SHAPE_CHECK, SHAPE_X, SHAPE_HEART, SHAPE_QUESTION,
    # Characters/Faces
    SHAPE_SAD_FACE, SHAPE_HAPPY_FACE, SHAPE_NEUTRAL_FACE,
    # Media
    SHAPE_PLAY, SHAPE_PAUSE,
    # Dancers (for animation)
    SHAPE_DANCER1, SHAPE_DANCER2, SHAPE_DANCER3,
    # Arrows
    SHAPE_ARROW_UP, SHAPE_ARROW_DN, SHAPE_ARROW_L, SHAPE_ARROW_R,
)
```

### Methods

```python
leds.fill(color)                    # All LEDs same color
leds.solid(r, g, b)                 # All LEDs RGB value
leds.off()                          # Turn off all LEDs
leds.show_shape(shape, color)       # Display a shape pattern
leds.show_pattern(pattern_dict)     # Multi-color pattern: {color: (indices...)}
leds.flash(r, g, b, times=3)        # Flash all LEDs
leds.flash_color(color, times=3)    # Flash with library color
leds.np[i] = color; leds.np.write() # Direct pixel access
```

## Buzzer API

```python
buz.beep(freq_hz, duration_ms)      # Single tone
buz.play_note(freq, duration_ms)    # Play frequency
buz.confirm()                       # Success sound
buz.reject()                        # Error sound
buz.warn()                          # Warning sound

# Note frequencies available:
from buzzer import NOTE_FREQ
# Keys: "notec", "noted", "notee", "notef", "noteg", "notea", "noteb"
```

## NFC Patterns

### Using NfcReader (recommended)

```python
from nfc_reader import NfcReader

COMMANDS = {"red", "green", "blue", "stop"}
reader = NfcReader(nfc, COMMANDS)

cmd, uid = reader.read_command(timeout=100)
if cmd == "stop":
    return
elif cmd in COMMANDS:
    # Handle command
```

### Repeat Scan Guard

```python
REPEAT_SCAN_GUARD_MS = 1200

if uid == self.last_uid and time.ticks_diff(now, self.last_scan_ms) < REPEAT_SCAN_GUARD_MS:
    return None  # Ignore repeated scan
self.last_uid = uid
self.last_scan_ms = now
```

## Button Handling

```python
# Read initial state to avoid false trigger on game entry
self._btn_was_down = (self.btn.value() == 0)

def _check_button_press(self):
    """Edge detection with debounce."""
    down = (self.btn.value() == 0)
    if down and not self._btn_was_down:
        time.sleep_ms(30)  # Debounce
        if self.btn.value() == 0:
            self._btn_was_down = True
            return True
    elif not down and self._btn_was_down:
        self._btn_was_down = False
    return False
```

## Animation Patterns

### Breathing/Pulse Effect

```python
import math

pulse = (math.sin(frame * 0.15) + 1) / 2  # 0.0 to 1.0
scale = 0.3 + 0.7 * pulse
color = (int(base_r * scale), int(base_g * scale), int(base_b * scale))
```

### Spinner on Perimeter

```python
PERIMETER = [0, 1, 2, 3, 4, 9, 14, 19, 24, 23, 22, 21, 20, 15, 10, 5]
pos = (time.ticks_ms() // 80) % len(PERIMETER)
for offset, level in enumerate((40, 24, 12, 5)):
    leds.np[PERIMETER[(pos - offset) % len(PERIMETER)]] = (level, 0, level)
```

## Sound Design

**Each game should have a unique "Entry" sound fanfare for user recognition.** Other sounds (error, exit, success, victory, etc.) when needed should be similar across games for consistency.

### Entry Fanfare

For example:

```python
buz.beep(523, 80); time.sleep_ms(40)
buz.beep(659, 80); time.sleep_ms(40)
buz.beep(784, 120)
```

### Victory Fanfare

```python
buz.beep(523, 100); time.sleep_ms(50)
buz.beep(659, 100); time.sleep_ms(50)
buz.beep(784, 100); time.sleep_ms(50)
buz.beep(1047, 300)
```

### Error Sound

```python
buz.beep(400, 150); time.sleep_ms(60)
buz.beep(250, 250)
```

## Critical Rules

1. **Stop tag and ESPnow check in each run iteration** — Users must be able to exit
2. **Use try/finally in play()** — Ensure `leds.off()` and other outputs (buzzer, haptic motor, etc.) are stopped on any exit path
3. **No f-strings** — Use `%` formatting only (MicroPython limitation)
4. **Import colors from leds.py** — Don't define RGB tuples; library colors auto-scale with brightness.
5. **Debounce button reads** — GPIO 0 is noisy
6. **Handle NFC errors gracefully** — Wrap reads in try/except, log and continue
7. **Read button state at init** — Prevents false trigger from button held during entry

## Checklist for New Games

- [ ] Docstring with entry points and template pattern
- [ ] Hardware config constants at top
- [ ] Game class with `__init__()` and `run()`
- [ ] Stop tag check at start of every loop
- [ ] `play()` with try/finally for cleanup
- [ ] `main()` for standalone testing
- [ ] `if __name__ == "__main__":` guard
- [ ] Entry fanfare sound
- [ ] Uses library colors (not raw RGB tuples)
- [ ] Button state read at init
- [ ] Error handling around NFC reads
- [ ] Print instructions on game start
