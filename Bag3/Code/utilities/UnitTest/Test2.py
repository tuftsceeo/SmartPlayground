"""
test_side2.py
=============
PlaygroundV5 - Side 2 component test
Tests: LIS2DW12TR accelerometer (I2C 0x18/0x19),
       Battery connector (voltage via MAX17048 0x36),
       M5Stack RFID2 — WS1850S Mifare/NTAG reader (I2C 0x28 (dec 40), Grove)
I2C: SDA=22, SCL=23

Requires ws1850s.py on the device (copy alongside this file).
"""

import machine
import time
import struct
from ws1850s import WS1850S

# ── Pin definitions ────────────────────────────────────────────────────────────
I2C_SDA = 22
I2C_SCL = 23

# ── Helpers ────────────────────────────────────────────────────────────────────
def section(title):
    print(f"\n{'─'*42}")
    print(f"  {title}")
    print('─'*42)

def ok(msg):   print(f"  ✓  {msg}")
def fail(msg): print(f"  ✗  {msg}")
def info(msg): print(f"     {msg}")

def sak_card_type(sak):
    """Decode SAK byte to a human-readable card type string."""
    if sak & 0x20:
        return "Mifare Classic (ISO 14443-4)"
    elif sak == 0x00:
        return "Mifare Ultralight / NTAG21x"
    elif sak == 0x08:
        return "Mifare Classic 1K"
    elif sak == 0x18:
        return "Mifare Classic 4K"
    elif sak == 0x09:
        return "Mifare Mini"
    else:
        return f"Unknown (SAK=0x{sak:02X})"

# ── Init I2C ───────────────────────────────────────────────────────────────────
i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA),
                       scl=machine.Pin(I2C_SCL),
                       freq=400_000)

print("\n══════════════════════════════════════════")
print("   PlaygroundV5 — Side 2 Test")
print("══════════════════════════════════════════")

devices = i2c.scan()
info(f"I2C devices found: {[hex(a) for a in devices]}")

# ── Test 1: LIS2DW12TR Accelerometer ──────────────────────────────────────────
section("1 · LIS2DW12TR Accelerometer  (0x18 / 0x19)")
try:
    ACCEL_ADDR = 0x19 if 0x19 in devices else 0x18
    if ACCEL_ADDR not in devices:
        raise RuntimeError("Not found at 0x18 or 0x19")

    who = i2c.readfrom_mem(ACCEL_ADDR, 0x0F, 1)[0]
    if who != 0x44:
        raise RuntimeError(f"WHO_AM_I = 0x{who:02X}, expected 0x44")
    ok(f"WHO_AM_I = 0x{who:02X} ✓  (at 0x{ACCEL_ADDR:02X})")

    i2c.writeto_mem(ACCEL_ADDR, 0x21, bytes([0x40]))   # CTRL2: soft reset
    time.sleep_ms(10)
    i2c.writeto_mem(ACCEL_ADDR, 0x20, bytes([0x54]))   # CTRL1: 100 Hz, high-perf
    i2c.writeto_mem(ACCEL_ADDR, 0x25, bytes([0x14]))   # CTRL6: ±4 g, low-noise
    time.sleep_ms(20)

    info("5 readings:")
    for _ in range(5):
        d = i2c.readfrom_mem(ACCEL_ADDR, 0x28, 6)
        x = struct.unpack('<h', d[0:2])[0] * 0.000488
        y = struct.unpack('<h', d[2:4])[0] * 0.000488
        z = struct.unpack('<h', d[4:6])[0] * 0.000488
        info(f"  X:{x:+.3f}g  Y:{y:+.3f}g  Z:{z:+.3f}g")
        time.sleep_ms(100)
    ok("LIS2DW12TR OK")
except Exception as e:
    fail(f"LIS2DW12TR FAILED: {e}")

# ── Test 2: Battery Connector ──────────────────────────────────────────────────
section("2 · Battery Connector  (MAX17048 at 0x36)")
try:
    BATT = 0x36
    if BATT not in devices:
        raise RuntimeError("MAX17048 not on bus — battery not connected "
                           "or Side 1 not yet soldered")

    raw = i2c.readfrom_mem(BATT, 0x02, 2)
    v   = ((raw[0] << 8) | raw[1]) * 78.125 / 1_000_000
    raw = i2c.readfrom_mem(BATT, 0x04, 2)
    soc = raw[0] + raw[1] / 256.0

    ok(f"Voltage : {v:.3f} V")
    ok(f"SOC     : {soc:.1f} %")
    if v < 3.0:
        info("⚠  Below 3.0 V — battery may be flat or absent")
    elif v > 4.25:
        info("⚠  Above 4.25 V — check cell chemistry")
    else:
        ok("Voltage healthy (3.0–4.25 V range)")
except Exception as e:
    fail(f"Battery connector FAILED: {e}")

# ── Test 3: WS1850S RFID reader ───────────────────────────────────────────────
section("3 · M5Stack RFID2 / WS1850S  (I2C 0x28 (dec 40), Grove)")
try:
    RFID_ADDR = 0x28  # decimal 40 = 0x28 (WS1850S default)
    if RFID_ADDR not in devices:
        raise RuntimeError(f"0x{RFID_ADDR:02X} not on bus — "
                            "check Grove cable and module power")

    # Instantiate driver at custom address
    rfid = WS1850S(i2c)  # 0x28 is the driver default

    ver = rfid.version()
    ok(f"Module detected at 0x{RFID_ADDR:02X}  |  VersionReg = 0x{ver:02X}")
    if ver == 0x00 or ver == 0xFF:
        info("⚠  VersionReg reads 0x00/0xFF — check wiring, but may still work")

    # ── Scan for a card / tag ────────────────────────────────────────────────
    info("Waiting for a Mifare/NTAG card — 10 s, tap one now...")
    found = False
    deadline = time.time() + 10

    while time.time() < deadline:
        result = rfid.read_uid_full()
        if result is not None:
            uid, sak = result
            uid_hex  = ':'.join(f'{b:02X}' for b in uid)
            card_str = sak_card_type(sak)
            ok(f"Card detected!")
            info(f"  UID  : {uid_hex}  ({len(uid)} bytes)")
            info(f"  Type : {card_str}")

            # ── Mifare Classic: try read block 0 (sector 0) ─────────────────
            if sak in (0x08, 0x18, 0x09):
                info("  Authenticating sector 0 with default key FF×6...")
                auth_status = rfid.auth(
                    WS1850S.PICC_AUTHENT1A, 0, WS1850S.DEFAULT_KEY, uid
                )
                if auth_status == WS1850S.MI_OK:
                    rd_status, block_data = rfid.read_block(0)
                    if rd_status == WS1850S.MI_OK:
                        info(f"  Block 0: {bytes(block_data).hex()}")
                    else:
                        info("  Block 0 read failed after auth")
                else:
                    info("  Auth failed — non-default key or Classic-incompatible")
                rfid.halt()

            # ── Ultralight / NTAG: read pages 0–3 (manufacturer data) ───────
            elif sak == 0x00:
                info("  Reading pages 0–3 (NTAG/Ultralight)...")
                rd_status, page_data = rfid.ul_read(0)
                if rd_status == WS1850S.MI_OK:
                    info(f"  Pages 0-3: {bytes(page_data).hex()}")
                    # Serial number is spread across pages 0-1 (bytes 0-6, skip BCC)
                    serial = page_data[0:3] + page_data[4:8]
                    info(f"  Serial No: {bytes(serial).hex()}")
                else:
                    info("  Page read failed")
                rfid.halt()

            found = True
            break

        time.sleep_ms(100)

    if not found:
        info("⚠  No card detected within timeout")
        info("    Comms to module OK — just no card presented")

    ok("WS1850S comms OK")
except Exception as e:
    fail(f"RFID2 FAILED: {e}")

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════")
print("   Side 2 test complete")
print("══════════════════════════════════════════\n")
