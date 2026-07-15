"""
test_full_assembly.py
=====================
PlaygroundV5 - Full assembly test
Tests ALL components in order:
  Side 1 : Button (Pin 0), Motor (Pin 21), NeoPixel 6×10 (Pin 20),
           MAX17048 battery gauge (I2C 0x36), OPT3002 light sensor (I2C 0x44-47)
  Side 2 : LIS2DW12TR accelerometer (I2C 0x18/19), Battery connector,
           M5Stack RFID2 WS1850S (I2C 0x28 (dec 40), Grove)
  Final  : Buzzer (Pin 19), Power switch (passive MOSFET — manual check)
I2C: SDA=22, SCL=23

Requires ws1850s.py on the device (copy alongside this file).
"""

import machine
import time
import struct
from neopixel import NeoPixel
from ws1850s import WS1850S

# ── Pin definitions ────────────────────────────────────────────────────────────
I2C_SDA  = 22
I2C_SCL  = 23
MOTOR    = 21
NEOPIXEL = 20
NUM_LEDS = 60
BUTTON   = 0
BUZZER   = 19
RFID_ADDR = 0x28  # decimal 40 = 0x28 (WS1850S default)

# ── Result tracking ────────────────────────────────────────────────────────────
PASS, WARN, FAIL = 0, 1, 2
results = {}

def section(title):
    print(f"\n{'═'*46}")
    print(f"  {title}")
    print('═'*46)

def ok(msg):   print(f"  ✓  {msg}")
def warn(msg): print(f"  ⚠  {msg}")
def fail(msg): print(f"  ✗  {msg}")
def info(msg): print(f"     {msg}")

def record(name, status, msg=""):
    results[name] = status
    if msg:
        [ok, warn, fail][status](msg)

def sak_card_type(sak):
    if sak == 0x00: return "Mifare Ultralight / NTAG21x"
    if sak == 0x08: return "Mifare Classic 1K"
    if sak == 0x18: return "Mifare Classic 4K"
    if sak == 0x09: return "Mifare Mini"
    if sak & 0x20:  return "Mifare Classic (ISO 14443-4)"
    return f"Unknown (SAK=0x{sak:02X})"

# ── Init ───────────────────────────────────────────────────────────────────────
print("\n╔════════════════════════════════════════════╗")
print("║   PlaygroundV5 — Full Assembly Test        ║")
print("╚════════════════════════════════════════════╝")

i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA),
                       scl=machine.Pin(I2C_SCL),
                       freq=400_000)
devices = i2c.scan()
info(f"I2C bus scan: {[hex(a) for a in devices]}")

# ════════════════════════════════════════════════════════════════════════
#  SIDE 1
# ════════════════════════════════════════════════════════════════════════

# ── 1 · Button ────────────────────────────────────────────────────────
section("1 · Button  (Pin 0)")
try:
    btn = machine.Pin(BUTTON, machine.Pin.IN, machine.Pin.PULL_UP)
    ok(f"Pin reads: {'PRESSED' if btn.value() == 0 else 'released'}")
    info("Press button within 5 s to confirm...")
    t0 = time.time()
    pressed = False
    while time.time() - t0 < 5:
        if btn.value() == 0:
            pressed = True
            while btn.value() == 0:
                time.sleep_ms(10)
            ok("Press confirmed ✓")
            break
        time.sleep_ms(20)
    if not pressed:
        warn("No press in timeout — check wiring")
    record("button", PASS if pressed else WARN)
except Exception as e:
    fail(f"Button: {e}"); record("button", FAIL)

# ── 2 · Buzzer ────────────────────────────────────────────────────────
section("2 · Buzzer  (Pin 19)")
try:
    buz = machine.PWM(machine.Pin(BUZZER), freq=2000, duty_u16=0)
    for freq, dur in [(1000, 120), (2000, 120), (3000, 120), (2000, 350)]:
        buz.freq(freq); buz.duty_u16(32768)
        time.sleep_ms(dur)
        buz.duty_u16(0); time.sleep_ms(60)
    buz.deinit()
    ok("4 tones played — confirm audible")
    record("buzzer", PASS)
except Exception as e:
    fail(f"Buzzer: {e}"); record("buzzer", FAIL)

# ── 3 · Power switch (manual note) ────────────────────────────────────
section("3 · Power Switch  (passive MOSFET — no GPIO)")
info("Hardware MOSFET circuit — nothing to assert via code.")
info("Manual checks:")
info("  • USB-C connected    → USB powers board, battery charges")
info("  • USB-C disconnected → board runs from battery")
info("  • Measure 3V3 rail with multimeter to confirm rail is up")
record("power_switch", WARN, "Manual verification needed")

# ── 4 · Motor ─────────────────────────────────────────────────────────
section("4 · Motor  (Pin 21)")
try:
    mp = machine.Pin(MOTOR, machine.Pin.OUT)
    info("Digital ON — 0.8 s"); mp.value(1); time.sleep_ms(800); mp.value(0)
    ok("Digital drive OK")
    info("PWM ramp up / down...")
    pwm = machine.PWM(machine.Pin(MOTOR), freq=1000)
    for d in range(0, 65536, 4096): pwm.duty_u16(d); time.sleep_ms(60)
    for d in range(65535, -1, -4096): pwm.duty_u16(d); time.sleep_ms(60)
    pwm.duty_u16(0); pwm.deinit()
    ok("PWM ramp OK")
    record("motor", PASS)
except Exception as e:
    fail(f"Motor: {e}"); record("motor", FAIL)

# ── 5 · NeoPixel 6×10 ─────────────────────────────────────────────────
section("5 · NeoPixel 6×10 matrix  (Pin 20, 60 LEDs, GRB)")
try:
    np = NeoPixel(machine.Pin(NEOPIXEL), NUM_LEDS)

    def fill(r, g, b):
        for i in range(NUM_LEDS): np[i] = (g, r, b)  # GRB order
        np.write()

    fill(0,0,0); time.sleep_ms(100)
    for name, r, g, b in [("Red",10,0,0),("Green",0,10,0),
                           ("Blue",0,0,10),("White",6,6,6)]:
        info(name); fill(r,g,b); time.sleep_ms(350)

    info("Column sweep...")
    fill(0,0,0)
    # Row-major wiring: index = row*6 + col. A physical column is the set of
    # cells (row, col) for row 0..9 -> indices row*6 + col.
    for col in range(6):
        for row in range(10): np[row*6+col] = (0, 8, 0)  # GRB green
        np.write(); time.sleep_ms(100)
        for row in range(10): np[row*6+col] = (0, 0, 0)
        np.write()

    fill(0,0,0)
    ok("NeoPixel matrix OK")
    record("neopixel", PASS)
except Exception as e:
    fail(f"NeoPixel: {e}"); record("neopixel", FAIL)

# ── 6 · MAX17048 Battery Gauge ────────────────────────────────────────
section("6 · MAX17048 Battery Gauge  (I2C 0x36)")
try:
    BATT = 0x36
    if BATT not in devices: raise RuntimeError("0x36 not on bus")
    raw = i2c.readfrom_mem(BATT, 0x02, 2)
    v   = ((raw[0] << 8) | raw[1]) * 78.125 / 1_000_000
    raw = i2c.readfrom_mem(BATT, 0x04, 2)
    soc = raw[0] + raw[1] / 256.0
    raw = i2c.readfrom_mem(BATT, 0x16, 2)
    rate = struct.unpack('>h', raw)[0] * 0.208
    ok(f"Voltage : {v:.3f} V")
    ok(f"SOC     : {soc:.1f} %")
    ok(f"C-rate  : {rate:+.2f} %/hr")
    if v < 3.0 or v > 4.25:
        warn("Voltage outside 3.0–4.25 V"); record("max17048", WARN)
    else:
        record("max17048", PASS)
except Exception as e:
    fail(f"MAX17048: {e}"); record("max17048", FAIL)

# ── 7 · OPT3002 Light Sensor ──────────────────────────────────────────
section("7 · OPT3002 Light Sensor  (I2C 0x44–0x47)")
try:
    LADDR = None
    for addr in [0x44, 0x45, 0x46, 0x47]:
        if addr in devices:
            try:
                raw = i2c.readfrom_mem(addr, 0x7F, 2)
                if ((raw[0]<<8)|raw[1]) == 0x3001:
                    LADDR = addr; break
            except: pass
    if LADDR is None: raise RuntimeError("OPT3002 not found (0x44–0x47)")
    ok(f"Found at 0x{LADDR:02X}")
    i2c.writeto_mem(LADDR, 0x01, struct.pack('>H', 0xC610))
    time.sleep_ms(120)
    info("3 lux readings:")
    for _ in range(3):
        raw  = i2c.readfrom_mem(LADDR, 0x00, 2)
        word = (raw[0]<<8)|raw[1]
        lux  = 0.01 * ((word & 0x0FFF) << ((word>>12)&0x0F))
        info(f"  {lux:.2f} lux")
        time.sleep_ms(200)
    ok("OPT3002 OK")
    record("opt3002", PASS)
except Exception as e:
    fail(f"OPT3002: {e}"); record("opt3002", FAIL)

# ════════════════════════════════════════════════════════════════════════
#  SIDE 2
# ════════════════════════════════════════════════════════════════════════

# ── 8 · LIS2DW12TR Accelerometer ──────────────────────────────────────
section("8 · LIS2DW12TR Accelerometer  (I2C 0x18/0x19)")
try:
    ACCEL = 0x19 if 0x19 in devices else 0x18
    if ACCEL not in devices: raise RuntimeError("Not on bus")
    who = i2c.readfrom_mem(ACCEL, 0x0F, 1)[0]
    if who != 0x44: raise RuntimeError(f"WHO_AM_I=0x{who:02X}, expected 0x44")
    ok(f"WHO_AM_I = 0x{who:02X} ✓  (at 0x{ACCEL:02X})")
    i2c.writeto_mem(ACCEL, 0x21, bytes([0x40])); time.sleep_ms(10)
    i2c.writeto_mem(ACCEL, 0x20, bytes([0x54]))
    i2c.writeto_mem(ACCEL, 0x25, bytes([0x14])); time.sleep_ms(20)
    info("3 readings:")
    for _ in range(3):
        d = i2c.readfrom_mem(ACCEL, 0x28, 6)
        x = struct.unpack('<h', d[0:2])[0] * 0.000488
        y = struct.unpack('<h', d[2:4])[0] * 0.000488
        z = struct.unpack('<h', d[4:6])[0] * 0.000488
        info(f"  X:{x:+.3f}g  Y:{y:+.3f}g  Z:{z:+.3f}g")
        time.sleep_ms(100)
    ok("LIS2DW12TR OK")
    record("lis2dw", PASS)
except Exception as e:
    fail(f"LIS2DW12TR: {e}"); record("lis2dw", FAIL)

# ── 9 · Battery Connector ─────────────────────────────────────────────
section("9 · Battery Connector  (via MAX17048)")
try:
    BATT = 0x36
    if BATT not in devices: raise RuntimeError("MAX17048 not on bus")
    raw = i2c.readfrom_mem(BATT, 0x02, 2)
    v   = ((raw[0]<<8)|raw[1]) * 78.125 / 1_000_000
    raw = i2c.readfrom_mem(BATT, 0x04, 2)
    soc = raw[0] + raw[1] / 256.0
    ok(f"Battery: {v:.3f} V  |  {soc:.1f} % SOC")
    if 3.0 <= v <= 4.25:
        ok("Voltage healthy"); record("battery_conn", PASS)
    else:
        warn("Voltage outside 3.0–4.25 V"); record("battery_conn", WARN)
except Exception as e:
    fail(f"Battery connector: {e}"); record("battery_conn", FAIL)

# ── 10 · WS1850S RFID Reader ──────────────────────────────────────────
section("10 · M5Stack RFID2 / WS1850S  (I2C 0x28 (dec 40), Grove)")
try:
    if RFID_ADDR not in devices:
        raise RuntimeError(f"0x{RFID_ADDR:02X} not on bus — check Grove cable")

    rfid = WS1850S(i2c)  # 0x28 is the driver default
    ver  = rfid.version()
    ok(f"Module at 0x{RFID_ADDR:02X}  |  VersionReg = 0x{ver:02X}")
    if ver in (0x00, 0xFF):
        warn("VersionReg reads 0x00/0xFF — check wiring (may still work)")

    info("Waiting for card — 10 s, tap one now...")
    found = False
    deadline = time.time() + 10

    while time.time() < deadline:
        result = rfid.read_uid_full()
        if result is not None:
            uid, sak = result
            uid_hex  = ':'.join(f'{b:02X}' for b in uid)
            ok(f"Card detected!")
            info(f"  UID  : {uid_hex}  ({len(uid)} bytes)")
            info(f"  Type : {sak_card_type(sak)}")

            # Mifare Classic — read block 0 with default key
            if sak in (0x08, 0x18, 0x09):
                info("  Auth sector 0 (key FF×6)...")
                if rfid.auth(WS1850S.PICC_AUTHENT1A, 0,
                             WS1850S.DEFAULT_KEY, uid) == WS1850S.MI_OK:
                    st, blk = rfid.read_block(0)
                    if st == WS1850S.MI_OK:
                        info(f"  Block 0: {bytes(blk).hex()}")
                    else:
                        info("  Block 0 read failed")
                else:
                    info("  Auth failed (non-default key?)")
                rfid.halt()

            # Ultralight / NTAG — read pages 0-3
            elif sak == 0x00:
                info("  Reading pages 0-3...")
                st, pg = rfid.ul_read(0)
                if st == WS1850S.MI_OK:
                    info(f"  Pages 0-3: {bytes(pg).hex()}")
                    serial = pg[0:3] + pg[4:8]
                    info(f"  Serial   : {bytes(serial).hex()}")
                else:
                    info("  Page read failed")
                rfid.halt()

            found = True
            break

        time.sleep_ms(100)

    if found:
        record("rfid2", PASS)
    else:
        info("⚠  No card in timeout (comms OK)")
        record("rfid2", WARN)
except Exception as e:
    fail(f"RFID2: {e}"); record("rfid2", FAIL)

# ════════════════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ════════════════════════════════════════════════════════════════════════
section("SUMMARY")
labels = {
    "button":       "Button          (Pin 0)",
    "buzzer":       "Buzzer          (Pin 19)",
    "power_switch": "Power switch    (MOSFET — manual)",
    "motor":        "Motor           (Pin 21)",
    "neopixel":     "NeoPixel 6×10   (Pin 20)",
    "max17048":     "MAX17048        (I2C 0x36)",
    "opt3002":      "OPT3002         (I2C 0x44-47)",
    "lis2dw":       "LIS2DW12TR      (I2C 0x18/19)",
    "battery_conn": "Battery connector",
    "rfid2":        "WS1850S RFID2   (I2C 0x28)",
}
icons = ["✓", "⚠", "✗"]
for key, label in labels.items():
    s = results.get(key, FAIL)
    print(f"  {icons[s]}  {label}")

passing = sum(1 for v in results.values() if v == PASS)
warning = sum(1 for v in results.values() if v == WARN)
failing = sum(1 for v in results.values() if v == FAIL)
total   = len(results)
print(f"\n  Passed: {passing}/{total}   Warnings: {warning}   Failed: {failing}")

print("\n╔════════════════════════════════════════════╗")
if failing == 0 and warning <= 1:   # 1 warn is always power switch
    print("║  ALL TESTS PASSED — board is go! 🎉       ║")
elif failing == 0:
    print("║  No hard failures — review warnings       ║")
else:
    print(f"║  {failing} component(s) FAILED — investigate      ║")
print("╚════════════════════════════════════════════╝\n")
