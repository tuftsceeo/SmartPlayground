"""
Programmable tag PoC: XIAO ESP32-C6 + NFC Tag 2 Click (NT3H2111).

BOOT button (GPIO9): short press = next preset, long press = write it.
OLED shows UID, current tag contents, RF field state and write result.
"""

import time
from machine import Pin, SoftI2C

import ssd1306
from nt3h import NT3H
import ndef

I2C_SDA = 22
I2C_SCL = 23
I2C_FREQ = 100_000
OLED_ADDR = 0x3C
BUTTON_PIN = 9
LONG_PRESS_MS = 600

# ("label", kind, value). "text" writes an NDEF text record; "page5" writes
# 4 raw bytes at page 5 (the wand-card opcode slot) after clearing NDEF.
PRESETS = [
    ("hello", "text", "hello"),
    ("tap-1", "text", "tap-1"),
    ("tap-2", "text", "tap-2"),
    ("page5 01", "page5", b'\x01\x00\x00\x00'),
]

i2c = SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=I2C_FREQ)
oled = ssd1306.SSD1306_I2C(128, 64, i2c, OLED_ADDR)
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
tag = NT3H(i2c)


def show(lines):
    oled.fill(0)
    for n, line in enumerate(lines[:8]):
        oled.text(line[:16], 0, n * 8)
    oled.show()


def tag_contents():
    area = tag.read_tlv_area(2)
    text = ndef.decode_ndef_text(area)
    if text is not None:
        return f"txt:{text}"
    return "p5:" + tag.read_page(5).hex()


def write_preset(preset):
    label, kind, value = preset
    if kind == "text":
        ok = tag.write_ndef(ndef.build_ndef_text(value))
    else:
        ok = tag.write_ndef(b'\x03\x00\xfe') and tag.write_page(5, value)
    return ok and tag_contents().endswith(value if kind == "text" else value.hex())


def main():
    if not tag.present():
        show(["NT3H not found", f"addr {tag.addr:#x}", "check wiring"])
        return
    uid = tag.read_uid().hex()
    sel = 0
    result = ""
    pressed_at = None
    last_draw = 0
    while True:
        now = time.ticks_ms()
        if button.value() == 0:
            if pressed_at is None:
                pressed_at = now
        elif pressed_at is not None:
            held = time.ticks_diff(now, pressed_at)
            pressed_at = None
            if held >= LONG_PRESS_MS:
                result = "OK" if write_preset(PRESETS[sel]) else "FAIL"
                last_draw = 0
            else:
                sel = (sel + 1) % len(PRESETS)
                result = ""
                last_draw = 0
        if time.ticks_diff(now, last_draw) > 250 or last_draw == 0:
            last_draw = now
            try:
                rf = "RF" if tag.rf_field_present() else "--"
                cur = tag_contents()
            except OSError:
                rf, cur = "??", "read err"
            show([
                uid[:16], uid[16:], f"now {cur}",
                f"sel {PRESETS[sel][0]}", f"write {result}", rf,
                "short=next", "long=write",
            ])
        time.sleep_ms(1)


main()
