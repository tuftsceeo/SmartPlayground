# Wand Module Code Reference v6

---

### Code Generation Context

## Project Overview

The Wand Module is a handheld, child-carried device for the Smart Playground, an educational technology system designed for kindergarten classrooms. The wand is one of several ESP32-based modules that communicate over ESP-NOW. It is operated entirely through NFC tags, requires no keyboard or screen, and is intended to be picked up and used by young children without adult intervention beyond the initial tag layout.

The wand has two interaction modes, both driven from a single `main.py` state machine:

**Programming mode.** Children tap NFC tags to build a simple `trigger → action` rule of the form "when this happens, do that." Triggers are physical events (`buttondown`, `buttonup`, `shake`); actions are LED, buzzer, or motor outputs (notes, colors, animal sounds). AND and THEN combinator tags let multiple actions run simultaneously or in sequence. Scanning the `start` tag enters running mode, where the rule loops until the `stop` tag is scanned.

**Game dispatch.** Several standalone games (`jumpin`, `cooking`, `melody`, `colorquest`, `freezedance`) are bundled as separate Python modules in the `Wand Module/` folder. Tapping a game's control tag transfers hardware to that game's `play()` entry point. The game exits on NFC `stop` or ESP-NOW `stop`. Games may use ESP-NOW to communicate with other Smart Playground devices, including the Programming
Station, the Scoreboard, and other wands.

---

## Table of Contents

- [Hardware](#hardware)
    - [On-Board Peripherals](#on-board-peripherals)
    - [Wireless](#wireless)
    - [NeoPixel Layout](#neopixel-layout)
- [Pin Map](#pin-map)
- [I2C Bus](#i2c-bus-all-on-gpio22gpio23)
- [File Structure](#file-structure)
- [Driver APIs](#driver-apis)
    - [pn532.py](#pn532py--pn532i2c-addr0x24)
    - [lis2dw12.py](#lis2dw12py--lis2dw12i2c-addr0x19)
    - [max17048.py](#max17048py--max17048i2c-addr0x36)
    - [opt3002.py](#opt3002py--opt3002i2c-addr0x44)
    - [buzzer.py](#buzzerpy--buzzerpin)
    - [leds.py](#ledspy--ledspinnone-numnone)
    - [nfc_reader.py](#nfc_readerpy--tag-scanning-helpers)
    - [brightness.py](#brightnesspy--ambient-adaptive-led-brightness)
    - [battery.py](#batterypy--battery-display-helper)
- [main.py — Core Trigger→Action Engine](#mainpy--core-triggeraction-engine)
    - [Programming Mode](#programming-mode-nfc-state-machine)
    - [AND / THEN Chaining](#and--then-chaining)
    - [NFC Tags — Known Working Setup](#nfc-tags--known-working-setup)
    - [State Machine](#state-machine-mainpy)
- [Existing Games Reference](#existing-games-reference)
- [Adding a New Game](#adding-a-new-game)
    - [Game Module Pattern](#game-module-pattern)
    - [Step-by-Step Instructions](#step-by-step-instructions)
- [Known Issues & Gotchas](#known-issues--gotchas)

## Hardware

Custom PCB

| Field           | Value                                                 |
| --------------- | ----------------------------------------------------- |
| **Board**       | Seeed XIAO ESP32-C6 (RISC-V, 160MHz, WiFi 6, BLE 5.0) |
| **Framework**   | MicroPython v1.27.0                                   |
| **Logic**       | 3.3V                                                  |
| **Flash / RAM** | 4MB / 512KB SRAM                                      |

## On-Board Peripherals

The wand PCB integrates the following sensors and actuators around the XIAO ESP32-C6. Pin assignments are in the Pin Map; I2C addresses and drivers are in the I2C Bus table.

| Role       | Component                    | Bus / Interface    | Purpose                                  |
| ---------- | ---------------------------- | ------------------ | ---------------------------------------- |
| **Input**  | Tactile push button          | GPIO (active LOW)  | Primary user input                       |
| **Input**  | LIS2DW12 accelerometer       | I2C, INT1 → GPIO   | Shake detection, motion-driven games     |
| **Input**  | PN532 NFC reader             | I2C                | Tag scanning (programming and game flow) |
| **Input**  | OPT3002 ambient light        | I2C, polled        | Adaptive LED brightness                  |
| **Output** | 25× SK6812 NeoPixels         | GPIO (1-wire)      | 5×5 matrix display, GRB byte order       |
| **Output** | Piezo buzzer                 | GPIO (PWM)         | Tones, notes, feedback chirps            |
| **Output** | Vibration motor              | GPIO (digital/PWM) | Haptic feedback on tag scan              |
| **Power**  | MAX17048 fuel gauge          | I2C, ALRT → GPIO   | Battery state-of-charge reporting        |
| **Power**  | LiPo battery + USB-C charger | —                  | Portable operation; charges over USB-C   |

### Wireless

The ESP32-C6 supports WiFi 6, Bluetooth LE 5.x, Zigbee, and Thread. In this codebase only **ESP-NOW** (over the WiFi 6 radio) is used, for low-latency peer-to-peer messaging with other Smart Playground devices. BLE hardware is present and initialized on boot but is not actively used by the wand in the current release.

### NeoPixel Layout

The 25 NeoPixels are arranged as a **5×5 matrix** addressed by linear index 0–24 (row-major, top-left origin). All shape constants in `leds.py` (`SHAPE_HEART`, `SHAPE_ARROW_UP`, etc.) assume this layout. This is the only LED layout the `leds` library has been validated against.

---

## Pin Map

| GPIO         | Function       | Notes                                                 |
| ------------ | -------------- | ----------------------------------------------------- |
| GPIO0 (D0)   | **Button**     | Active LOW, internal pull-up                          |
| GPIO1 (D1)   | **Accel INT1** | LIS2DW12 wake-up interrupt (**confirmed working**)    |
| GPIO2 (D2)   | **Accel INT2** | Routed but **does NOT fire** — do not use for wake-up |
| GPIO21 (D3)  | **Motor**      | Vibration motor, digital/PWM                          |
| GPIO22 (D4)  | **I2C SDA**    | Shared bus, 100kHz for NFC compatibility              |
| GPIO23 (D5)  | **I2C SCL**    | Shared bus                                            |
| GPIO19 (D8)  | **Buzzer**     | Piezo, PWM for pitch, duty for volume                 |
| GPIO20 (D9)  | **NeoPixel**   | 25× SK6812, chain DIN, GRB byte order                 |
| GPIO18 (D10) | **Batt Alert** | MAX17048 ALRT pin                                     |
| GPIO16 (D6)  | TX — unused    | Available                                             |
| GPIO17 (D7)  | RX — unused    | Available                                             |

---

## I2C Bus (all on GPIO22/GPIO23)

| Device           | Address  | Driver File   | Notes                                       |
| ---------------- | -------- | ------------- | ------------------------------------------- |
| PN532 NFC        | **0x24** | `pn532.py`    | Use `freq=100_000` — fails at 400kHz        |
| LIS2DW12 Accel   | **0x19** | `lis2dw12.py` | SDO/SA0=HIGH. May be 0x18, run `i2c.scan()` |
| MAX17048 Battery | **0x36** | `max17048.py` | Fixed address, auto-starts                  |
| OPT3002 Light    | **0x44** | `opt3002.py`  | ADDR pin dependent. No INT routed to MCU    |

**Critical:** I2C bus runs at **100kHz** because the PN532 shares the bus and is unreliable at 400kHz. Other sensors are fine with this.

---

## File Structure

```
/lib/
  pn532.py         # NFC reader driver (PN532 over I2C)
  lis2dw12.py      # Accelerometer driver (LIS2DW12)
  max17048.py      # Battery fuel gauge driver (MAX17048)
  opt3002.py       # Ambient light sensor driver (OPT3002)
  buzzer.py        # Piezo buzzer sound helpers
  leds.py          # NeoPixel control and status display
  nfc_reader.py    # Tag scanning and command extraction
  brightness.py    # Ambient light brightness scaling
  battery.py       # Battery level display helper
main.py            # NFC trigger→action state machine (with AND/THEN chaining)
```

---

## Driver APIs

### pn532.py — `PN532(i2c, addr=0x24)`

```python
nfc.begin()                                    # → (ic, ver, rev) tuple
nfc.read_passive_target(timeout=500)           # → {uid, uid_hex, atqa, sak} or None
nfc.mifare_auth_block(uid, block, key, type)   # → True/False
nfc.mifare_read_block(block)                   # → 16 bytes
nfc.ntag_read_page(page)                       # → 4 bytes
```

Constants: `MIFARE_AUTH_A`, `MIFARE_AUTH_B`, `MIFARE_READ`

### lis2dw12.py — `LIS2DW12(i2c, addr=0x19)`

```python
accel.init(odr_mode=0x54, fs_range=RANGE_4G)  # 100Hz high-perf, ±4g
accel.read()                                    # → (x, y, z) in g
accel.enable_wake_int1(threshold=8)             # route shake detect to INT1
accel.enable_wake_int2(threshold=8)             # route to INT2 (broken on this board)
accel.clear_wake()                              # clear interrupt, returns WAKE_UP_SRC
accel.data_ready                                # bool
accel.device_id                                 # should be 0x44
```

Constants: `RANGE_2G`, `RANGE_4G`, `RANGE_8G`, `RANGE_16G`

**Sensitivity fix:** Raw int16 values are 14-bit left-justified. Correct conversion factor is `range / 32768`, NOT the datasheet's mg/LSB value directly. At ±4g: `0.000122 g/LSB` (not 0.000488). The driver handles this internally.

**Wake-up threshold:** At ±4g, 1 LSB = 0.0625g. `threshold=8` → 0.5g, `threshold=12` → 0.75g, `threshold=16` → 1.0g. Value of 8 works well for deliberate shakes.

### max17048.py — `MAX17048(i2c, addr=0x36)`

```python
batt.voltage     # Volts (float)
batt.soc         # State of charge 0–100+ (float)
batt.version     # IC version (non-zero = working)
batt.read_all()  # → (voltage, soc) tuple
batt.reset()     # power-on-reset
batt.quick_start()
```

No init needed — auto-starts when battery connected.

### opt3002.py — `OPT3002(i2c, addr=0x44)`

```python
light.init(mode=MODE_CONTINUOUS_100MS)
light.lux                # ambient light in lux
light.read_single()      # one-shot 800ms measurement
light.conversion_ready   # bool
light.shutdown()
```

Constants: `MODE_CONTINUOUS_100MS`, `MODE_CONTINUOUS_800MS`, `MODE_SINGLE_800MS`

**Note:** INT pin is NOT routed to any GPIO. Use polling only.

### buzzer.py — `Buzzer(pin)`

```python
buz.beep(freq=1000, ms=100)           # Play a tone at given frequency/duration
buz.play_note(freq, ms=400)           # Play a single note
buz.melody()                          # Short ascending melody (C5-E5-G5-C6)
buz.confirm()                         # Two rising tones — tag accepted
buz.start()                           # Three rising tones — entering run mode
buz.stop()                            # Descending tone — stopping
buz.reject()                          # Double low tone — invalid action
buz.warn()                            # Single low tone — warning
```

Constants: `NOTE_FREQ` dict maps note tags (`"notec"` through `"noteb"`) to 4th-octave frequencies.

### leds.py — `Leds(pin=None, num=None)`

Auto-configures from `hubtype`. All writes are scaled by `brightness.MULTIPLIER` automatically.

```python
leds.off()                                      # Turn off all LEDs
leds.solid(r, g, b)                             # Fill all LEDs with color
leds.fill(color)                                # Tuple-friendly solid()
leds.flash(r, g, b, times=2, on_ms=120, off_ms=80)
leds.flash_color(color, times=2, on_ms=120, off_ms=80)
leds.show_shape(indices, color, bg=OFF)         # Light specific LED indices
leds.show_pattern(color_to_indices, bg=OFF)     # Multiple groups in different colors
leds.pulse_color(r, g, b, duration_ms=600)      # Fade up then down
leds.breathe(r, g, b, frame)                    # Continuous breathing animation
leds.np[i] = (r, g, b)                          # Direct pixel access (also scaled)
```

**Boot sequence:** `boot_power()`, `boot_battery(soc)`, `boot_ready(soc)`, `boot_clear()`

**Idle/status:** `idle_default(soc)`, `idle_low_blink(frame)`, `idle_sleep()`, `breathe_sleep(frame)`

**Battery display:** `show_battery_level(soc)` → returns `(r, g, b, lit)`, `fade_out_battery(r, g, b, lit)`

**Color constants (module-level):** `OFF`, `RED`, `GREEN`, `BLUE`, `YELLOW`, `AMBER`, `ORANGE`, `PURPLE`, `MAGENTA`, `CYAN`, `TEAL`, `WHITE`, `PINK` — plus `_DIM` variants (e.g., `RED_DIM`, `BLUE_DIM`)

**Shape constants (module-level):** `SHAPE_SAD_FACE`, `SHAPE_HAPPY_FACE`, `SHAPE_NEUTRAL`, `SHAPE_X`, `SHAPE_PLUS`, `SHAPE_HEART`, `SHAPE_CHECK`, `SHAPE_PLAY`, `SHAPE_DANCER`, `SHAPE_ARROW_UP`, `SHAPE_ARROW_DOWN`, `SHAPE_ARROW_LEFT`, `SHAPE_ARROW_RIGHT`, `SHAPE_BORDER`, `SHAPE_INNER_3x3`, `SHAPE_CORNERS`, `SHAPE_CENTER`, `SHAPE_TOP_ROW`, `SHAPE_BOT_ROW`, `SHAPE_LEFT_COL`, `SHAPE_RIGHT_COL`

### nfc_reader.py — Tag scanning helpers

Higher-level wrappers around `pn532.py` with NDEF decoding and command matching.

```python
# For game code — simple text + UID extraction
from nfc_reader import read_ndef_text
text, uid = read_ndef_text(nfc, timeout=500)    # → (text, uid_hex) or (None, None)

# For main loop — command dispatch with callbacks
from nfc_reader import NfcReader
reader = NfcReader(nfc, commands)               # commands = set of valid strings
uid, sak = reader.detect_tag(timeout=250)       # Quick presence check
cmd, uid = reader.read_command(
    timeout=250,
    on_detect=fn,      # called when tag detected
    on_progress=fn,    # called during slow read (for animation)
    on_complete=fn     # called when read finished
)
```

Supports MIFARE Classic 1K (auth + block read) and NTAG/Ultralight (page read). Falls back to raw-byte search if NDEF decode fails.

### brightness.py — Ambient-adaptive LED brightness

On boot, `calibrate(opt3002)` reads the light sensor and sets `MULTIPLIER`. All NeoPixel writes through `leds.py` are automatically scaled.

```python
import brightness
brightness.calibrate(opt3002)          # Set MULTIPLIER from sensor → (mult, lux)
brightness.set_multiplier(0.4)         # Manual override, clamped to [0.05, 1.0]
brightness.get_multiplier()            # Current multiplier value
brightness.get_lux()                   # Last lux reading (or None)
brightness.scale(r, g, b)              # Manual scale — ONLY for raw NeoPixels
```

Global state: `brightness.MULTIPLIER` (default 1.0), `brightness.LAST_LUX`

Lux → multiplier mapping (log scale): <32 lux → 0.15, 100 lux → 0.32, 500 lux → 0.55, 2000 lux → 0.76, 10000+ lux → 1.00

### battery.py — Battery display helper

```python
from battery import show_battery
show_battery(batt, leds, buzzer)       # buzzer can be None
```

Reads battery SoC, displays level on LEDs (green/yellow/red), beeps, waits 2.5s, then fades out.

---

## main.py — Core Trigger→Action Engine

This section documents `main.py`, the primary firmware that runs on boot. It provides:

1. **Programming mode** — Tap NFC tags to build trigger→action rules
2. **Running mode** — Execute programmed rules when triggers fire
3. **Game dispatch** — Launch standalone games (`colorquest`, `freezedance`, `jumpin`, `cooking`, `melody`) when their control tags are scanned

Games are separate modules (e.g., `color_quest.py`) that temporarily take control when launched. Exit conditions: NFC `stop` tag **or** station ESP-NOW broadcast `["stop"]` / `{"type":"stop"}`. Control then returns to `main.py`.

### Programming Mode (NFC State Machine)

Users tap NFC tags in sequence to program a **trigger → action** pair, then tap START to run the loop continuously until STOP is tapped.

**Flow:** Tap TRIGGER → Tap ACTION → [optional: AND/THEN → ACTION]... → Tap START → (loops until STOP)

**Available triggers:** `buttondown` (button pressed), `buttonup` (button released), `shake` (accelerometer shake)
**Available actions:**

| Tag          | Resource | Description                          |
| ------------ | -------- | ------------------------------------ |
| `playnote`   | buzzer   | Short ascending melody (C5-E5-G5-C6) |
| `notec`      | buzzer   | C4 — 262 Hz, 400ms                   |
| `noted`      | buzzer   | D4 — 294 Hz, 400ms                   |
| `notee`      | buzzer   | E4 — 330 Hz, 400ms                   |
| `notef`      | buzzer   | F4 — 349 Hz, 400ms                   |
| `noteg`      | buzzer   | G4 — 392 Hz, 400ms                   |
| `notea`      | buzzer   | A4 — 440 Hz, 400ms                   |
| `noteb`      | buzzer   | B4 — 494 Hz, 400ms                   |
| `turnred`    | led      | Pulse all 25 LEDs red                |
| `turngreen`  | led      | Pulse all 25 LEDs green              |
| `turnblue`   | led      | Pulse all 25 LEDs blue               |
| `turnpurple` | led      | Pulse all 25 LEDs purple             |
| `turnyellow` | led      | Pulse all 25 LEDs yellow             |
| `turnwhite`  | led      | Pulse all 25 LEDs white              |
| `turnoff`    | led      | Turn off all LEDs instantly          |

**Combinator tags:** `and` (simultaneous), `then` (sequential)
**Control tags:** `start`, `stop`, `colorquest`, `freezedance`, `jumpin`, `cooking`, `melody`
**Utility tags:** `battery` (shows battery level on LEDs, works in any state)

### AND / THEN Chaining

Actions are stored as a **chain of groups**: `[["playnote", "turnpurple"], ["playnote"]]`
This means: (playnote AND turnpurple) THEN playnote.

**AND** runs actions simultaneously using `_thread`. Only works across different hardware resources:

| Resource      | Actions                                    | Can AND together?                |
| ------------- | ------------------------------------------ | -------------------------------- |
| Buzzer        | playnote, notea–noteg                      | ✗ Only one at a time (last wins) |
| LEDs          | turnred/green/blue/purple/yellow/white/off | ✗ Only one at a time (last wins) |
| Buzzer + LEDs | e.g. notea + turnred                       | ✓ Different hardware             |

If two actions in an AND group share the same resource, last one wins (silently replaces).
**THEN** always works — actions run one after the other.

**Tap sequence during programming:**

- Action without combinator → replaces entire chain with that single action
- AND → next action added to current group (simultaneous)
- THEN → next action starts a new group (sequential)
- Tapping a trigger at any point restarts programming

### NFC Tags — Known Working Setup

- **Tag type:** MIFARE Classic 1K (ATQA=0x0004, SAK=0x08)
- **NDEF location:** Sector 1 (blocks 4–6), starting at byte offset 0 of sector 1
- **NDEF format:** TLV type 0x03 → NDEF message → Text record (type 'T', lang 'en')
- **Auth key:** Default `FF FF FF FF FF FF` with Key A
- **Sector 0 must be skipped** — contains manufacturer data that corrupts TLV parsing

**All NFC tag texts:** `waitbutton`, `waitshake`, `playnote`, `notea`, `noteb`, `notec`, `noted`, `notee`, `notef`, `noteg`, `turnred`, `turngreen`, `turnblue`, `turnpurple`, `turnyellow`, `turnwhite`, `turnoff`, `and`, `then`, `start`, `stop`, `battery

**Tag UIDs observed:**

| UID         | Command                         |
| ----------- | ------------------------------- |
| 89:35:55:91 | `buttondown`                    |
| 19:0D:54:91 | `playnote`                      |
| B9:44:53:91 | (read issues — sometimes fails) |
| 09:36:55:91 | (read issues — sometimes fails) |

**Raw NDEF example** (buttondown, at sector 1):

```
03 13 D1 01 0F 54 02 65 6E 62 75 74 74 6F 6E 64  .....T.enbuttond
6F 77 6E FE                                        own.
```

### State Machine (main.py)

```
STATE_IDLE (battery-colored inner ring)
  ├─ tap game tag → launch game module → (returns here on stop)
  ├─ tap battery → show battery level on LEDs → return to current state
  ├─ tap trigger → STATE_TRIGGER_SET (programming LEDs)
  │     ├─ tap battery → show battery level → stay
  │     ├─ tap action → STATE_BUILDING (green LEDs)
  │     │     │   chain = [[action]]
  │     │     ├─ tap battery → show battery level → stay
  │     │     ├─ tap AND → set pending=and
  │     │     │     └─ tap action → add to current group → stay
  │     │     ├─ tap THEN → set pending=then
  │     │     │     └─ tap action → new group appended → stay
  │     │     ├─ tap action (no combinator) → replace chain → stay
  │     │     ├─ tap start → STATE_RUNNING (LEDs off)
  │     │     │     ├─ trigger fires → run_chain(groups) → loop
  │     │     │     └─ tap stop → STATE_IDLE
  │     │     ├─ tap trigger → restart programming
  │     │     └─ tap stop → reset to STATE_IDLE
  │     ├─ tap trigger → change trigger (stay)
  │     └─ other → rejected
  └─ tap action/start → rejected (wrong order)
```

Status indicator: first 3 NeoPixels glow dim in state color.
Tag debounce: same UID ignored until tag is removed (uid == None resets).

---

## Existing Games Reference

| File              | Complexity | Hardware Used                | Notes                                                                            |
| ----------------- | ---------- | ---------------------------- | -------------------------------------------------------------------------------- |
| `jumpin.py`       | Simple     | LEDs, buzzer                 | Simplest template; also serves as the hook for user-authored chatbot code        |
| `cooking.py`      | Simple     | LEDs, buzzer, NFC            | Cooking simulation game with ingredient scanning                                 |
| `melody.py`       | Simple     | LEDs, buzzer, NFC            | Music/melody creation game                                                       |
| `color_quest.py`  | Medium     | LEDs, buzzer, NFC            | Color matching game with NFC tag scanning                                        |
| `freeze_dance.py` | Complex    | LEDs, buzzer, accel, ESP-NOW | Multi-role game with accelerometer-driven freeze detection and ESP-NOW messaging |

---

## Adding a New Game

Each game is a separate Python module in the `Wand Module/` folder that exposes a single `play(...)` entry
point. The wand's main loop calls this function when the corresponding NFC tag is scanned, and the function
returns control when the `stop` tag is scanned **or** `msg_type == "stop"` from within the game. Instructions in GAME_AUTHORING_GUIDE.md.

### Game Module Pattern

Template Pattern: 1. YourGame class with `__init__()` and `run()` 2. `play()` for wand integration (hardware
passed in) 3. `main()` for standalone testing (initializes hardware) 4. CRITICAL: NFC and ESPNow stop check at start of run loop. Full template in GAME_AUTHORING_GUIDE.md.

### Step-by-Step Instructions

1. **Create the game module:** Create `Wand Module/yourgame.py` with a `def play(...)` function as shown above.

2. **Add the import:** In `main.py`, add near the other game imports:

    ```python
    from yourgame import play as play_yourgame
    ```

3. **Register the control tag:** Add `"yourgame"` to the `CONTROLS` set in `main.py`.

4. **Add the dispatch branch:** In `main.py`'s main loop, after the existing game branches (search for `cmd == "jumpin"`), add:

    ```python
    if cmd == "yourgame":
        leds.off()
        play_yourgame(nfc, leds, buz, accel, i2c)
        last_activity_ms = time.ticks_ms()
        idle_frame = 0
        show_idle(last_soc, 0); last_uid = None; continue
    ```

5. **Print the NFC tag:** Create an NFC tag with NDEF text payload `yourgame`. Tapping it from idle enters the game.

---

---

## Known Issues & Gotchas

1. **INT2 (GPIO2) does not fire** for accelerometer wake-up — always use **INT1 (GPIO1)**
2. **I2C at 100kHz** — PN532 is unreliable at higher speeds on shared bus
3. **MIFARE Classic re-select required** before each auth attempt — tag loses state
4. **Some tags intermittently fail** to read (B9:44:53:91, 09:36:55:91) — likely weak coupling or positioning
5. **f-strings crash** on this MicroPython build — use `%` formatting only
6. **`_thread` for AND groups** — ESP32-C6 MicroPython supports `_thread.start_new_thread()` for running buzzer + LEDs simultaneously
7. **NeoPixel color order** is GRB. If colors wrong, try `bpp=4` for RGBW variant
8. **GPIO0 is boot pin** — holding button during reset may enter bootloader
9. **Accelerometer sensitivity** — raw 16-bit values need `range/32768` factor, not datasheet mg/LSB values directly
10. **NDEF on MIFARE Classic** — always skip sector 0 (manufacturer block), NDEF starts at sector 1
11. **Fallback text search** — if NDEF decode fails, code brute-force scans raw bytes for command strings
