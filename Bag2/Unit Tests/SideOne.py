import machine
import time
import struct
from micropython import const

# Pin definitions
I2C_SDA = 22
I2C_SCL = 23
MOTOR = 21

# PN532 Constants
_PREAMBLE = const(0x00)
_STARTCODE1 = const(0x00)
_STARTCODE2 = const(0xFF)
_POSTAMBLE = const(0x00)
_HOSTTOPN532 = const(0xD4)
_PN532TOHOST = const(0xD5)
_COMMAND_GETFIRMWAREVERSION = const(0x02)
_COMMAND_SAMCONFIGURATION = const(0x14)
_COMMAND_INLISTPASSIVETARGET = const(0x4A)
_MIFARE_ISO14443A = const(0x00)
_ACK = b"\x00\x00\xff\x00\xff\x00"
_WAKEUP = const(0x55)
_PN532_I2C_ADDRESS = const(0x24)

class PN532_I2C:
    """Simplified PN532 driver for testing"""
    def __init__(self, i2c, address=_PN532_I2C_ADDRESS):
        self.i2c = i2c
        self.address = address
        self._wakeup()
        time.sleep(0.5)
    
    def _wakeup(self):
        try:
            self.i2c.writeto(self.address, bytes([_WAKEUP]))
            time.sleep(0.1)
        except: pass
    
    def _write_data(self, framebytes):
        self.i2c.writeto(self.address, framebytes)
    
    def _read_data(self, count):
        data = self.i2c.readfrom(self.address, count + 1)
        if data[0] != 0x01: return bytes()
        return data[1:count + 1]
    
    def _wait_ready(self, timeout=1.0):
        start = time.time()
        while (time.time() - start) < timeout:
            try:
                status = self.i2c.readfrom(self.address, 1)
                if len(status) > 0 and status[0] == 0x01:
                    return True
            except: pass
            time.sleep(0.02)
        return False
    
    def _write_frame(self, data):
        length = len(data)
        frame = bytearray(length + 8)
        frame[0] = _PREAMBLE
        frame[1] = _STARTCODE1
        frame[2] = _STARTCODE2
        frame[3] = length & 0xFF
        frame[4] = (~length + 1) & 0xFF
        frame[5:-2] = data
        checksum = sum(frame[0:3]) + sum(data)
        frame[-2] = ~checksum & 0xFF
        frame[-1] = _POSTAMBLE
        self._write_data(bytes(frame))
    
    def _read_frame(self, length):
        response = self._read_data(length + 7)
        if len(response) == 0: raise RuntimeError("No response")
        offset = 0
        while offset < len(response) - 1 and response[offset] == 0x00:
            offset += 1
        if offset >= len(response) or response[offset] != 0xFF:
            raise RuntimeError("Invalid preamble")
        offset += 1
        frame_len = response[offset]
        return response[offset + 2 : offset + 2 + frame_len]
    
    def _send_command(self, command, params=b"", timeout=1.0):
        self._wakeup()
        data = bytearray(2 + len(params))
        data[0] = _HOSTTOPN532
        data[1] = command & 0xFF
        for i, val in enumerate(params):
            data[2 + i] = val
        self._write_frame(data)
        time.sleep(0.05)
        start = time.time()
        while (time.time() - start) < timeout:
            try:
                if self._wait_ready(0.1):
                    ack = self._read_data(len(_ACK))
                    if ack == _ACK: return True
            except: pass
            time.sleep(0.02)
        return False
    
    def _process_response(self, command, response_length=0, timeout=1.0):
        if not self._wait_ready(timeout): return None
        response = self._read_frame(response_length + 2)
        if response[0] != _PN532TOHOST or response[1] != (command + 1):
            raise RuntimeError("Unexpected response")
        return response[2:]
    
    def _call_function(self, command, response_length=0, params=b"", timeout=1.0):
        if not self._send_command(command, params=params, timeout=timeout):
            return None
        return self._process_response(command, response_length=response_length, timeout=timeout)
    
    def get_firmware_version(self):
        response = self._call_function(_COMMAND_GETFIRMWAREVERSION, response_length=4, timeout=0.5)
        if response is None: raise RuntimeError("Failed to detect PN532")
        return tuple(response)
    
    def SAM_configuration(self):
        self._call_function(_COMMAND_SAMCONFIGURATION, params=[0x01, 0x14, 0x01])
    
    def read_passive_target(self, card_baud=_MIFARE_ISO14443A, timeout=1.0):
        if not self._send_command(_COMMAND_INLISTPASSIVETARGET, params=[0x01, card_baud], timeout=timeout):
            return None
        response = self._process_response(_COMMAND_INLISTPASSIVETARGET, response_length=30, timeout=timeout)
        if response is None or response[0] != 0x01: return None
        if response[5] > 7: return None
        return response[6 : 6 + response[5]]

# Initialize I2C
i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=400_000)

print("=== PlaygroundV5 Component Test ===\n")

# Scan I2C bus
print("Scanning I2C bus...")
devices = i2c.scan()
print(f"Found devices at addresses: {[hex(addr) for addr in devices]}\n")

# === Test 1: Accelerometer (LIS2DW12) ===
print("--- Testing Accelerometer ---")
try:
    ACCEL_ADDR = 0x19 if 0x19 in devices else 0x18
    who_am_i = i2c.readfrom_mem(ACCEL_ADDR, 0x0F, 1)[0]
    print(f"WHO_AM_I: 0x{who_am_i:02X} {'✓ OK' if who_am_i == 0x44 else '✗ FAIL'}")
    
    i2c.writeto_mem(ACCEL_ADDR, 0x21, bytes([0x40]))  # soft reset
    time.sleep_ms(10)
    i2c.writeto_mem(ACCEL_ADDR, 0x20, bytes([0x54]))  # 100Hz
    i2c.writeto_mem(ACCEL_ADDR, 0x25, bytes([0x14]))  # ±4g
    time.sleep_ms(20)
    
    print("Reading accelerometer (5 samples):")
    for _ in range(5):
        data = i2c.readfrom_mem(ACCEL_ADDR, 0x28, 6)
        x = struct.unpack('<h', data[0:2])[0] * 0.000488
        y = struct.unpack('<h', data[2:4])[0] * 0.000488
        z = struct.unpack('<h', data[4:6])[0] * 0.000488
        print(f"  X:{x:+.3f}g  Y:{y:+.3f}g  Z:{z:+.3f}g")
        time.sleep_ms(100)
    print("✓ Accelerometer OK\n")
except Exception as e:
    print(f"✗ Accelerometer FAILED: {e}\n")

# === Test 2: Battery Gauge (MAX17048) ===
print("--- Testing Battery Gauge ---")
try:
    BATT_ADDR = 0x36
    ver = i2c.readfrom_mem(BATT_ADDR, 0x08, 2)
    version = (ver[0] << 8) | ver[1]
    print(f"Version: 0x{version:04X} {'✓ OK' if version != 0 else '✗ FAIL'}")
    
    vc = i2c.readfrom_mem(BATT_ADDR, 0x02, 2)
    voltage = ((vc[0] << 8) | vc[1]) * 78.125 / 1_000_000
    
    sc = i2c.readfrom_mem(BATT_ADDR, 0x04, 2)
    soc = sc[0] + sc[1] / 256.0
    
    print(f"Battery: {voltage:.3f}V, {soc:.1f}% SOC")
    print("✓ Battery Gauge OK\n")
except Exception as e:
    print(f"✗ Battery Gauge FAILED: {e}\n")

# === Test 3: NFC Reader (PN532) ===
print("--- Testing NFC ---")
try:
    nfc = PN532_I2C(i2c)
    ic, ver, rev, support = nfc.get_firmware_version()
    print(f"PN532 Firmware: {ver}.{rev} ✓ OK")
    nfc.SAM_configuration()
    
    print("Tap NFC card within 10 seconds...")
    card_detected = False
    start = time.time()
    
    while (time.time() - start) < 10:
        try:
            uid = nfc.read_passive_target(timeout=0.5)
            if uid:
                uid_hex = ':'.join([f'{b:02X}' for b in uid])
                print(f"✓ Card detected! UID: {uid_hex}")
                card_detected = True
                break
        except Exception as e:
            if "No response" not in str(e):
                print(f"Read error: {e}")
        time.sleep(0.1)
    
    if not card_detected:
        print("⚠ No card detected (timeout)")
    print()
except Exception as e:
    print(f"✗ NFC FAILED: {e}\n")

# === Test 4: Motor ===
print("--- Testing Motor ---")
try:
    
    
    motor = machine.Pin(MOTOR, machine.Pin.OUT)
    
    print("Motor ON (1 second)...")
    motor.value(1)
    time.sleep(1)
    
    print("Motor OFF")
    motor.value(0)
    time.sleep(0.5)
    
    print("Motor PWM test (ramping)...")
    mpwm = machine.PWM(machine.Pin(MOTOR), freq=1000)
    for duty in range(0, 65536, 8192):
        mpwm.duty_u16(duty)
        time.sleep_ms(200)
    mpwm.duty_u16(0)
    mpwm.deinit()
    
    print("✓ Motor OK\n")
except Exception as e:
    print(f"✗ Motor FAILED: {e}\n")

print("=== Test Complete ===")
