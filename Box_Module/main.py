"""
PlaygroundV5 – NFC Programmable Trigger → Action Engine
========================================================
Board: Seeed XIAO ESP32-C6

Requires in /lib/:
    pn532.py, lis2dw12.py, max17048.py, opt3002.py
"""

import machine
import time
import math
import sys
from neopixel import NeoPixel

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from lis2dw12 import LIS2DW12, RANGE_4G

# ─────────────────────────────────────────────
# PIN CONSTANTS
# ─────────────────────────────────────────────
I2C_SDA      = 22
I2C_SCL      = 23
NEOPIXEL_PIN = 20
NUM_LEDS     = 25
BUZZER_PIN   = 19
MOTOR_PIN    = 21
SWITCH_PIN   = 0
ACCEL_INT1   = 1
PN532_ADDR   = 0x24

# ─────────────────────────────────────────────
# HARDWARE INIT
# ─────────────────────────────────────────────
i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=100_000)
np = NeoPixel(machine.Pin(NEOPIXEL_PIN), NUM_LEDS)
btn = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
int1_pin = machine.Pin(ACCEL_INT1, machine.Pin.IN)

# ─────────────────────────────────────────────
# TAG COMMANDS
# ─────────────────────────────────────────────
TRIGGERS = {"waitbutton", "waitshake"}
ACTIONS  = {"playnote", "turnpurple"}
CONTROLS = {"start", "stop"}
ALL_COMMANDS = TRIGGERS | ACTIONS | CONTROLS

# ─────────────────────────────────────────────
# NFC TAG READING
# ─────────────────────────────────────────────
COMMON_KEYS = [
    b'\xFF\xFF\xFF\xFF\xFF\xFF',
    b'\xD3\xF7\xD3\xF7\xD3\xF7',
    b'\xA0\xA1\xA2\xA3\xA4\xA5',
    b'\xB0\xB1\xB2\xB3\xB4\xB5',
    b'\x00\x00\x00\x00\x00\x00',
]


def read_mifare_classic_data(nfc, tag):
    ndef_data = bytearray()
    for sector in (1, 2):
        first_block = sector * 4
        authed = False
        for key in COMMON_KEYS:
            for key_type in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                resel = nfc.read_passive_target(timeout=150)
                if resel is None:
                    continue
                if nfc.mifare_auth_block(resel['uid'], first_block, key, key_type):
                    for blk in range(first_block, first_block + 3):
                        try:
                            ndef_data.extend(nfc.mifare_read_block(blk))
                        except Exception:
                            ndef_data.extend(b'\x00' * 16)
                    authed = True
                    break
            if authed:
                break
        if not authed:
            ndef_data.extend(b'\x00' * 48)
    return ndef_data


def read_ntag_data(nfc):
    ndef_data = bytearray()
    for page in range(4, 20):
        try:
            ndef_data.extend(nfc.ntag_read_page(page))
        except Exception:
            break
    return ndef_data


def decode_ndef_text(data):
    if not data or len(data) < 4:
        return None
    i = 0
    while i < len(data):
        t = data[i]
        if t == 0x00:
            i += 1; continue
        if t == 0xFE:
            break
        if t == 0x03:
            if i + 1 >= len(data):
                break
            length = data[i + 1]
            off = i + 2
            if length == 0xFF:
                if i + 3 >= len(data): break
                length = (data[i + 2] << 8) | data[i + 3]
                off = i + 4
            ndef = data[off:off + length]
            if len(ndef) > 3:
                flags = ndef[0]; type_len = ndef[1]
                sr = flags & 0x10
                if sr:
                    pl = ndef[2]; ho = 3
                else:
                    if len(ndef) < 6: break
                    pl = (ndef[2] << 24) | (ndef[3] << 16) | (ndef[4] << 8) | ndef[5]
                    ho = 6
                rec_type = ndef[ho:ho + type_len]
                payload = ndef[ho + type_len:ho + type_len + pl]
                if bytes(rec_type) == b'T' and len(payload) > 1:
                    lang_len = payload[0] & 0x3F
                    return bytes(payload[1 + lang_len:]).decode('utf-8', 'replace').strip().lower()
                elif bytes(rec_type) == b'U' and len(payload) > 1:
                    prefixes = ["", "http://www.", "https://www.", "http://", "https://", "tel:", "mailto:"]
                    pre = prefixes[payload[0]] if payload[0] < len(prefixes) else ""
                    return (pre + bytes(payload[1:]).decode('utf-8', 'replace')).strip().lower()
            break
        else:
            if i + 1 < len(data): i += 2 + data[i + 1]
            else: break
    return None


def try_find_text_in_raw(data):
    if not data:
        return None
    try:
        raw_str = bytes(data).decode('ascii', 'replace').lower()
    except Exception:
        return None
    for cmd in ALL_COMMANDS:
        if cmd in raw_str:
            return cmd
    return None


def read_tag_command(nfc):
    tag = nfc.read_passive_target(timeout=250)
    if tag is None:
        return None, None
    sak = tag['sak']
    uid_hex = tag['uid_hex']
    ndef_data = bytearray()
    try:
        if sak in (0x08, 0x18):
            ndef_data = read_mifare_classic_data(nfc, tag)
        else:
            ndef_data = read_ntag_data(nfc)
    except Exception as e:
        sys.print_exception(e)

    text = decode_ndef_text(ndef_data)
    if text and text in ALL_COMMANDS:
        print("  [NFC] %s  (%s)" % (text, uid_hex))
        return text, uid_hex

    text = try_find_text_in_raw(ndef_data)
    if text:
        print("  [NFC] %s  (%s) [raw]" % (text, uid_hex))
        return text, uid_hex

    return None, uid_hex


# ─────────────────────────────────────────────
# LED HELPERS
# ─────────────────────────────────────────────
def leds_off():
    for i in range(NUM_LEDS):
        np[i] = (0, 0, 0)
    np.write()

def leds_solid(r, g, b):
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()

def leds_flash(r, g, b, times=2, on_ms=120, off_ms=80):
    for _ in range(times):
        leds_solid(r, g, b); time.sleep_ms(on_ms)
        leds_off(); time.sleep_ms(off_ms)

def leds_pulse_purple(duration_ms=600):
    steps = 20
    for s in range(steps):
        bright = int(127 * math.sin(math.pi * s / steps))
        leds_solid(bright, 0, bright)
        time.sleep_ms(duration_ms // steps)
    leds_off()

# ─────────────────────────────────────────────
# BUZZER HELPERS
# ─────────────────────────────────────────────
def beep(freq=1000, ms=100):
    buz = machine.PWM(machine.Pin(BUZZER_PIN))
    buz.freq(freq); buz.duty_u16(32768)
    time.sleep_ms(ms)
    buz.duty_u16(0); buz.deinit()

def play_melody():
    notes = [(523, 150), (659, 150), (784, 200), (1047, 300)]
    buz = machine.PWM(machine.Pin(BUZZER_PIN))
    for freq, dur in notes:
        buz.freq(freq); buz.duty_u16(32768)
        time.sleep_ms(dur)
        buz.duty_u16(0); time.sleep_ms(30)
    buz.deinit()

def beep_confirm():
    beep(880, 60); time.sleep_ms(40); beep(1200, 80)

def beep_start():
    beep(660, 80); time.sleep_ms(30)
    beep(880, 80); time.sleep_ms(30)
    beep(1100, 120)

def beep_stop():
    beep(800, 80); time.sleep_ms(30); beep(400, 200)

# ─────────────────────────────────────────────
# TRIGGER FUNCTIONS
# ─────────────────────────────────────────────
def wait_for_button(nfc):
    while True:
        if btn.value() == 0:
            time.sleep_ms(30)
            if btn.value() == 0:
                while btn.value() == 0:
                    time.sleep_ms(10)
                return "fired"
        cmd, _ = read_tag_command(nfc)
        if cmd == "stop":
            return "stop"
        time.sleep_ms(50)

def wait_for_shake(nfc):
    poll_count = 0
    accel.clear_wake()  # clear stale interrupt
    while True:
        if int1_pin.value() == 1:
            accel.clear_wake()
            time.sleep_ms(200)
            accel.clear_wake()
            return "fired"
        poll_count += 1
        if poll_count >= 20:
            poll_count = 0
            cmd, _ = read_tag_command(nfc)
            if cmd == "stop":
                return "stop"
        time.sleep_ms(30)

# ─────────────────────────────────────────────
# ACTION FUNCTIONS
# ─────────────────────────────────────────────
def action_playnote():
    play_melody()

def action_turnpurple():
    leds_pulse_purple(800)

# ─────────────────────────────────────────────
# STATE MACHINE
# ─────────────────────────────────────────────
STATE_IDLE        = 0
STATE_TRIGGER_SET = 1
STATE_ACTION_SET  = 2
STATE_RUNNING     = 3

TRIGGER_FNS = {"waitbutton": wait_for_button, "waitshake": wait_for_shake}
ACTION_FNS  = {"playnote": action_playnote, "turnpurple": action_turnpurple}

STATE_COLORS = {
    STATE_IDLE:        (0, 0, 10),
    STATE_TRIGGER_SET: (10, 5, 0),
    STATE_ACTION_SET:  (0, 10, 0),
    STATE_RUNNING:     (0, 0, 0),
}

def show_state(state):
    r, g, b = STATE_COLORS[state]
    for i in range(NUM_LEDS):
        np[i] = (r, g, b) if i < 3 else (0, 0, 0)
    np.write()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
accel = None  # module-level so wait_for_shake can access it

def main():
    global accel
    print("\n" + "=" * 50)
    print("  PlaygroundV5 — NFC Trigger->Action Programmer")
    print("=" * 50)

    # NFC
    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  [FAIL] NFC:"); sys.print_exception(e); return

    # Accelerometer
    accel_ok = False
    try:
        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)
        accel.enable_wake_int1(threshold=8)
        accel_ok = True
        print("  Accelerometer OK (INT1, threshold=0.5g)")
    except Exception as e:
        print("  [WARN] Accel:"); sys.print_exception(e)

    state = STATE_IDLE
    trigger_name = None
    action_name = None
    last_uid = None

    show_state(state)
    print("\n  Step 1: Tap a TRIGGER tag (waitbutton / waitshake)")

    while True:
        try:
            # ── PROGRAMMING PHASE ──
            if state in (STATE_IDLE, STATE_TRIGGER_SET, STATE_ACTION_SET):
                cmd, uid = read_tag_command(nfc)

                if cmd is None or uid == last_uid:
                    if cmd is None and uid is None:
                        last_uid = None
                    time.sleep_ms(200)
                    continue

                last_uid = uid
                print("  >> Command: '%s'" % cmd)

                if state == STATE_IDLE:
                    if cmd in TRIGGERS:
                        if cmd == "waitshake" and not accel_ok:
                            print("  [SKIP] Accelerometer not available!")
                            beep(200, 300); continue
                        trigger_name = cmd
                        state = STATE_TRIGGER_SET
                        show_state(state); beep_confirm()
                        print("  > Trigger set: %s" % trigger_name)
                        print("  Step 2: Tap an ACTION tag (playnote / turnpurple)")
                    elif cmd == "stop":
                        print("  Nothing running.")
                    else:
                        print("  Expected trigger tag, got '%s'" % cmd)
                        beep(200, 150)

                elif state == STATE_TRIGGER_SET:
                    if cmd in ACTIONS:
                        action_name = cmd
                        state = STATE_ACTION_SET
                        show_state(state); beep_confirm()
                        print("  > Action set: %s" % action_name)
                        print("  Program: %s -> %s" % (trigger_name, action_name))
                        print("  Step 3: Tap START to run")
                    elif cmd in TRIGGERS:
                        if cmd == "waitshake" and not accel_ok:
                            print("  [SKIP] Accelerometer not available!")
                            beep(200, 300); continue
                        trigger_name = cmd
                        beep_confirm()
                        print("  > Trigger changed: %s" % trigger_name)
                        print("  Step 2: Now tap an ACTION tag")
                    else:
                        print("  Expected action tag, got '%s'" % cmd)
                        beep(200, 150)

                elif state == STATE_ACTION_SET:
                    if cmd == "start":
                        state = STATE_RUNNING
                        show_state(state); beep_start()
                        leds_flash(0, 40, 0, times=3, on_ms=80, off_ms=60)
                        print("\n  >>> RUNNING: %s -> %s" % (trigger_name, action_name))
                        print("  (Tap STOP tag to end)\n")
                    elif cmd in TRIGGERS:
                        if cmd == "waitshake" and not accel_ok:
                            print("  [SKIP] Accelerometer not available!")
                            beep(200, 300); continue
                        trigger_name = cmd
                        state = STATE_TRIGGER_SET
                        show_state(state); beep_confirm()
                        print("  > Reprogramming — trigger: %s" % trigger_name)
                        print("  Step 2: Tap an ACTION tag")
                    elif cmd in ACTIONS:
                        action_name = cmd
                        beep_confirm()
                        print("  > Action changed: %s" % action_name)
                        print("  Program: %s -> %s" % (trigger_name, action_name))
                        print("  Tap START to run")
                    elif cmd == "stop":
                        trigger_name = None; action_name = None
                        state = STATE_IDLE
                        show_state(state); beep_stop()
                        print("  Reset. Step 1: Tap a TRIGGER tag")

            # ── RUNNING PHASE ──
            elif state == STATE_RUNNING:
                result = TRIGGER_FNS[trigger_name](nfc)

                if result == "stop":
                    state = STATE_IDLE
                    trigger_name = None; action_name = None
                    leds_off(); beep_stop(); show_state(state)
                    last_uid = None
                    print("  <<< STOPPED")
                    print("\n  Step 1: Tap a TRIGGER tag to reprogram")
                    continue

                if result == "fired":
                    print("  * %s fired -> %s" % (trigger_name, action_name))
                    ACTION_FNS[action_name]()

                time.sleep_ms(200)

        except KeyboardInterrupt:
            leds_off(); print("\n  Exiting."); break
        except Exception as e:
            print("  [ERR]:"); sys.print_exception(e)
            time.sleep_ms(500)


if __name__ == "__main__":
    main()