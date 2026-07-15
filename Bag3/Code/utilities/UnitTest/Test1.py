"""
test_side1.py
=============
PlaygroundV5 - Side 1 component test
Tests: Button (Pin 0), Motor (Pin 21), NeoPixel 6x10 (Pin 20),
       MAX17048 battery gauge (I2C), OPT3002 light sensor (I2C)
I2C: SDA=22, SCL=23
"""

import machine
import time
import struct
from neopixel import NeoPixel

# ── Pin definitions ────────────────────────────────────────────────────────────
I2C_SDA  = 22
I2C_SCL  = 23
MOTOR    = 21
NEOPIXEL = 20
NUM_LEDS = 60   # 6 x 10 matrix
BUTTON   = 0

# ── Helpers ────────────────────────────────────────────────────────────────────
def section(title):
    print(f"\n{'─'*40}")
    print(f"  {title}")
    print('─'*40)

def ok(msg):  print(f"  ✓  {msg}")
def fail(msg): print(f"  ✗  {msg}")
def info(msg): print(f"     {msg}")

# ── Init I2C ───────────────────────────────────────────────────────────────────
i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA),
                       scl=machine.Pin(I2C_SCL),
                       freq=400_000)

print("\n══════════════════════════════════════")
print("   PlaygroundV5 — Side 1 Test")
print("══════════════════════════════════════")

devices = i2c.scan()
info(f"I2C devices found: {[hex(a) for a in devices]}")

# ── Test 1: Button ─────────────────────────────────────────────────────────────
section("1 · Button (Pin 0)")
try:
    btn = machine.Pin(BUTTON, machine.Pin.IN, machine.Pin.PULL_UP)
    state = "PRESSED" if btn.value() == 0 else "released"
    ok(f"Button reads: {state}")
    info("Press the button within 5 seconds to confirm...")
    deadline = time.time() + 5
    detected = False
    while time.time() < deadline:
        if btn.value() == 0:
            ok("Button press detected!")
            detected = True
            # debounce
            while btn.value() == 0:
                time.sleep_ms(10)
            break
        time.sleep_ms(20)
    if not detected:
        info("⚠  No press detected (timeout — wiring OK if state read succeeded)")
except Exception as e:
    fail(f"Button FAILED: {e}")

# ── Test 2: Motor (Pin 21) ─────────────────────────────────────────────────────
section("2 · Motor (Pin 21)")
try:
    motor_pin = machine.Pin(MOTOR, machine.Pin.OUT)

    info("Motor ON — 1 s")
    motor_pin.value(1)
    time.sleep(1)
    motor_pin.value(0)
    ok("Digital ON/OFF OK")

    info("PWM ramp 0→100%→0...")
    pwm = machine.PWM(machine.Pin(MOTOR), freq=1000)
    for duty in range(0, 65536, 4096):
        pwm.duty_u16(duty)
        time.sleep_ms(80)
    for duty in range(65535, -1, -4096):
        pwm.duty_u16(duty)
        time.sleep_ms(80)
    pwm.duty_u16(0)
    pwm.deinit()
    ok("PWM ramp OK")
except Exception as e:
    fail(f"Motor FAILED: {e}")

# ── Test 3: NeoPixel 6×10 (Pin 20) ────────────────────────────────────────────
section("3 · NeoPixel 6×10 matrix (Pin 20, 60 LEDs, GRB)")
try:
    np = NeoPixel(machine.Pin(NEOPIXEL), NUM_LEDS)

    def fill(r, g, b):
        for i in range(NUM_LEDS):
            np[i] = (g, r, b)   # GRB order
        np.write()

    def clear():
        fill(0, 0, 0)

    clear()
    time.sleep_ms(200)

    for name, r, g, b in [("Red", 10, 0, 0),
                           ("Green", 0, 10, 0),
                           ("Blue", 0, 0, 10),
                           ("White", 8, 8, 8)]:
        info(f"{name}...")
        fill(r, g, b)
        time.sleep_ms(400)

    # Snake chase across matrix
    info("Chase pattern...")
    clear()
    for i in range(NUM_LEDS):
        np[i] = (0, 8, 0)           # GRB green
        if i >= 3:
            np[i - 3] = (0, 0, 0)
        np.write()
        time.sleep_ms(30)

    # Column-by-column (6 columns × 10 rows).
    # Row-major wiring: index = row*6 + col, so a physical column is the
    # cells (row, col) for row 0..9 -> indices row*6 + col.
    info("Column sweep (6 cols × 10 rows)...")
    clear()
    for col in range(6):
        for row in range(10):
            np[row * 6 + col] = (8, 0, 0)  # GRB red
        np.write()
        time.sleep_ms(120)
        for row in range(10):
            np[row * 6 + col] = (0, 0, 0)
        np.write()

    clear()
    ok("NeoPixel matrix OK")
except Exception as e:
    fail(f"NeoPixel FAILED: {e}")

# ── Test 4: MAX17048 Battery Gauge ─────────────────────────────────────────────
section("4 · MAX17048 Battery Gauge (I2C 0x36)")
try:
    BATT_ADDR = 0x36
    if BATT_ADDR not in devices:
        raise RuntimeError(f"0x36 not found on I2C bus")

    # Version register 0x08
    raw = i2c.readfrom_mem(BATT_ADDR, 0x08, 2)
    version = (raw[0] << 8) | raw[1]
    ok(f"Version register: 0x{version:04X}")

    # VCELL register 0x02  (78.125 µV per LSB)
    raw = i2c.readfrom_mem(BATT_ADDR, 0x02, 2)
    voltage = ((raw[0] << 8) | raw[1]) * 78.125 / 1_000_000
    ok(f"Voltage : {voltage:.3f} V")

    # SOC register 0x04  (1/256 % per LSB)
    raw = i2c.readfrom_mem(BATT_ADDR, 0x04, 2)
    soc = raw[0] + raw[1] / 256.0
    ok(f"State of charge: {soc:.1f} %")

    # CRATE register 0x16  (0.208 %/hr per LSB, signed)
    raw = i2c.readfrom_mem(BATT_ADDR, 0x16, 2)
    crate_raw = struct.unpack('>h', raw)[0]
    crate = crate_raw * 0.208
    ok(f"Charge rate: {crate:+.2f} %/hr")

except Exception as e:
    fail(f"MAX17048 FAILED: {e}")

# ── Test 5: OPT3002 Light Sensor ───────────────────────────────────────────────
section("5 · OPT3002 Light Sensor (I2C 0x44–0x47)")
try:
    LIGHT_ADDR = None
    for addr in [0x44, 0x45, 0x46, 0x47]:
        if addr in devices:
            try:
                raw = i2c.readfrom_mem(addr, 0x7F, 2)
                dev_id = (raw[0] << 8) | raw[1]
                if dev_id == 0x3001:
                    LIGHT_ADDR = addr
                    break
            except:
                pass

    if LIGHT_ADDR is None:
        raise RuntimeError("OPT3002 not found (checked 0x44–0x47, device ID 0x3001)")

    ok(f"Found at 0x{LIGHT_ADDR:02X}")

    raw = i2c.readfrom_mem(LIGHT_ADDR, 0x7E, 2)
    mfg_id = (raw[0] << 8) | raw[1]
    ok(f"Manufacturer ID: 0x{mfg_id:04X} {'(TI ✓)' if mfg_id == 0x5449 else '(unexpected)'}")

    # Configure: auto-range, continuous, 100 ms
    i2c.writeto_mem(LIGHT_ADDR, 0x01, struct.pack('>H', 0xC610))
    time.sleep_ms(120)

    info("5 lux readings:")
    for _ in range(5):
        raw = i2c.readfrom_mem(LIGHT_ADDR, 0x00, 2)
        word = (raw[0] << 8) | raw[1]
        exp  = (word >> 12) & 0x0F
        mant = word & 0x0FFF
        lux  = 0.01 * (mant << exp)
        info(f"  {lux:.2f} lux")
        time.sleep_ms(200)

    ok("OPT3002 OK")
except Exception as e:
    fail(f"OPT3002 FAILED: {e}")

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════")
print("   Side 1 test complete")
print("══════════════════════════════════════\n")
