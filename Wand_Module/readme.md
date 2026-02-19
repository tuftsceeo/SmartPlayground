# PlaygroundV5 NFC Trigger→Action Engine — Project Reference
### One-pager for code generation context

---

## Project Overview

A programmable NFC-driven state machine on a custom PCB. Users tap NFC tags in sequence to program a **trigger → action** pair, then tap START to run the loop continuously until STOP is tapped.

**Flow:** Tap TRIGGER → Tap ACTION → [optional: AND/THEN → ACTION]... → Tap START → (loops until STOP)

**Available triggers:** `waitbutton` (physical button press), `waitshake` (accelerometer shake)
**Available actions:**

| Tag | Resource | Description |
|-----|----------|-------------|
| `playnote` | buzzer | Short ascending melody (C5-E5-G5-C6) |
| `notec` | buzzer | C4 — 262 Hz, 400ms |
| `noted` | buzzer | D4 — 294 Hz, 400ms |
| `notee` | buzzer | E4 — 330 Hz, 400ms |
| `notef` | buzzer | F4 — 349 Hz, 400ms |
| `noteg` | buzzer | G4 — 392 Hz, 400ms |
| `notea` | buzzer | A4 — 440 Hz, 400ms |
| `noteb` | buzzer | B4 — 494 Hz, 400ms |
| `turnred` | led | Pulse all 25 LEDs red |
| `turngreen` | led | Pulse all 25 LEDs green |
| `turnblue` | led | Pulse all 25 LEDs blue |
| `turnpurple` | led | Pulse all 25 LEDs purple |
| `turnyellow` | led | Pulse all 25 LEDs yellow |
| `turnwhite` | led | Pulse all 25 LEDs white |
| `turnoff` | led | Turn off all LEDs instantly |

**Combinator tags:** `and` (simultaneous), `then` (sequential)
**Control tags:** `start`, `stop`
**Utility tags:** `battery` (shows battery level on LEDs, works in any state)

### AND / THEN Chaining

Actions are stored as a **chain of groups**: `[["playnote", "turnpurple"], ["playnote"]]`
This means: (playnote AND turnpurple) THEN playnote.

**AND** runs actions simultaneously using `_thread`. Only works across different hardware resources:

| Resource | Actions | Can AND together? |
|----------|---------|-------------------|
| Buzzer | playnote, notea–noteg | ✗ Only one at a time (last wins) |
| LEDs | turnred/green/blue/purple/yellow/white/off | ✗ Only one at a time (last wins) |
| Buzzer + LEDs | e.g. notea + turnred | ✓ Different hardware |

If two actions in an AND group share the same resource, last one wins (silently replaces).
**THEN** always works — actions run one after the other.

**Tap sequence during programming:**
- Action without combinator → replaces entire chain with that single action
- AND → next action added to current group (simultaneous)
- THEN → next action starts a new group (sequential)
- Tapping a trigger at any point restarts programming

---

## Hardware

| Field | Value |
|-------|-------|
| **Board** | Seeed XIAO ESP32-C6 (RISC-V, 160MHz, WiFi 6, BLE 5.0) |
| **Framework** | MicroPython v1.27.0 |
| **Logic** | 3.3V |
| **Flash / RAM** | 4MB / 512KB SRAM |

---

## Pin Map

| GPIO | Function | Notes |
|------|----------|-------|
| GPIO0 (D0) | **Button** | Active LOW, internal pull-up |
| GPIO1 (D1) | **Accel INT1** | LIS2DW12 wake-up interrupt (**confirmed working**) |
| GPIO2 (D2) | **Accel INT2** | Routed but **does NOT fire** — do not use for wake-up |
| GPIO21 (D3) | **Motor** | Vibration motor, digital/PWM |
| GPIO22 (D4) | **I2C SDA** | Shared bus, 100kHz for NFC compatibility |
| GPIO23 (D5) | **I2C SCL** | Shared bus |
| GPIO19 (D8) | **Buzzer** | Piezo, PWM for pitch, duty for volume |
| GPIO20 (D9) | **NeoPixel** | 25× SK6812, chain DIN, GRB byte order |
| GPIO18 (D10) | **Batt Alert** | MAX17048 ALRT pin |
| GPIO16 (D6) | TX — unused | Available |
| GPIO17 (D7) | RX — unused | Available |

---

## I2C Bus (all on GPIO22/GPIO23)

| Device | Address | Driver File | Notes |
|--------|---------|-------------|-------|
| PN532 NFC | **0x24** | `pn532.py` | Use `freq=100_000` — fails at 400kHz |
| LIS2DW12 Accel | **0x19** | `lis2dw12.py` | SDO/SA0=HIGH. May be 0x18, run `i2c.scan()` |
| MAX17048 Battery | **0x36** | `max17048.py` | Fixed address, auto-starts |
| OPT3002 Light | **0x44** | `opt3002.py` | ADDR pin dependent. No INT routed to MCU |

**Critical:** I2C bus runs at **100kHz** because the PN532 shares the bus and is unreliable at 400kHz. Other sensors are fine with this.

---

## File Structure

```
/lib/
  pn532.py         # NFC reader driver (PN532 over I2C)
  lis2dw12.py      # Accelerometer driver (LIS2DW12)
  max17048.py      # Battery fuel gauge driver (MAX17048)
  opt3002.py       # Ambient light sensor driver (OPT3002)
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

---

## NFC Tags — Known Working Setup

- **Tag type:** MIFARE Classic 1K (ATQA=0x0004, SAK=0x08)
- **NDEF location:** Sector 1 (blocks 4–6), starting at byte offset 0 of sector 1
- **NDEF format:** TLV type 0x03 → NDEF message → Text record (type 'T', lang 'en')
- **Auth key:** Default `FF FF FF FF FF FF` with Key A
- **Sector 0 must be skipped** — contains manufacturer data that corrupts TLV parsing

**All NFC tag texts:** `waitbutton`, `waitshake`, `playnote`, `notea`, `noteb`, `notec`, `noted`, `notee`, `notef`, `noteg`, `turnred`, `turngreen`, `turnblue`, `turnpurple`, `turnyellow`, `turnwhite`, `turnoff`, `and`, `then`, `start`, `stop`, `battery`

**Tag UIDs observed:**

| UID | Command |
|-----|---------|
| 89:35:55:91 | `waitbutton` |
| 19:0D:54:91 | `playnote` |
| B9:44:53:91 | (read issues — sometimes fails) |
| 09:36:55:91 | (read issues — sometimes fails) |

**Raw NDEF example** (waitbutton, at sector 1):
```
03 11 D1 01 0D 54 02 65 6E 77 61 69 74 62 75 74  .....T.enwaitbut
74 6F 6E FE                                        ton.
```

---

## State Machine

```
STATE_IDLE (blue LEDs)
  ├─ tap battery → show battery level on LEDs → return to current state
  ├─ tap trigger → STATE_TRIGGER_SET (orange LEDs)
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

## Known Issues & Gotchas

1. **INT2 (GPIO2) does not fire** for accelerometer wake-up — always use **INT1 (GPIO1)**
2. **I2C at 100kHz** — PN532 is unreliable at higher speeds on shared bus
3. **MIFARE Classic re-select required** before each auth attempt — tag loses state
4. **Some tags intermittently fail** to read (B9:44:53:91, 09:36:55:91) — likely weak coupling or positioning
5. **f-strings crash** on this MicroPython build — use `%` formatting only
6. **`_thread` for AND groups** — ESP32-C6 MicroPython supports `_thread.start_new_thread()` for running buzzer + LEDs simultaneously
7. **NeoPixel color order** is GRB. If colors wrong, try `bpp=4` for RGBW variant
7. **GPIO0 is boot pin** — holding button during reset may enter bootloader
8. **Accelerometer sensitivity** — raw 16-bit values need `range/32768` factor, not datasheet mg/LSB values directly
9. **NDEF on MIFARE Classic** — always skip sector 0 (manufacturer block), NDEF starts at sector 1
10. **Fallback text search** — if NDEF decode fails, code brute-force scans raw bytes for command strings