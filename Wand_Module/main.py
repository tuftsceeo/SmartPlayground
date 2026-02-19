"""
PlaygroundV5 – NFC Programmable Trigger → Action Engine
========================================================
Board: Seeed XIAO ESP32-C6

Tap sequence:
  1. TRIGGER tag     (waitbutton / waitshake)
  2. ACTION tag      (playnote / turnpurple)
  3. Optional: AND/THEN + more actions
  4. START tag       → runs trigger→action loop
  5. STOP tag        → back to programming

AND  = simultaneous (only works across different hardware resources)
THEN = sequential (always works)

Requires in /lib/:
    pn532.py, lis2dw12.py, max17048.py, opt3002.py
"""

import machine
import time
import math
import sys
import _thread
from neopixel import NeoPixel

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from lis2dw12 import LIS2DW12, RANGE_4G
from max17048 import MAX17048

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
TRIGGERS    = {"waitbutton", "waitshake"}
ACTIONS     = {
    "playnote", "turnpurple",
    "turnred", "turnblue", "turngreen", "turnwhite", "turnyellow", "turnoff",
    "notea", "noteb", "notec", "noted", "notee", "notef", "noteg",
}
COMBINATORS = {"and", "then"}
CONTROLS    = {"start", "stop"}
UTILITY     = {"battery"}
ALL_COMMANDS = TRIGGERS | ACTIONS | COMBINATORS | CONTROLS | UTILITY

# ─────────────────────────────────────────────
# ACTION RESOURCE MAP
# Actions sharing a resource cannot run simultaneously.
# If AND'd together, last one wins for that resource.
# ─────────────────────────────────────────────
ACTION_RESOURCE = {
    "playnote":   "buzzer",
    "notea":      "buzzer",
    "noteb":      "buzzer",
    "notec":      "buzzer",
    "noted":      "buzzer",
    "notee":      "buzzer",
    "notef":      "buzzer",
    "noteg":      "buzzer",
    "turnpurple": "led",
    "turnred":    "led",
    "turnblue":   "led",
    "turngreen":  "led",
    "turnwhite":  "led",
    "turnyellow": "led",
    "turnoff":    "led",
    # future: "vibrate": "motor"
}

# ─────────────────────────────────────────────
# PN532 NFC TAG READING
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
            if i + 1 >= len(data): break
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
        return text, uid_hex

    text = try_find_text_in_raw(ndef_data)
    if text:
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
    leds_pulse_color(127, 0, 127, duration_ms)

def leds_pulse_color(r, g, b, duration_ms=600):
    """Pulse LEDs in a given color: ramp up then down."""
    steps = 20
    for s in range(steps):
        scale = math.sin(math.pi * s / steps)
        leds_solid(int(r * scale), int(g * scale), int(b * scale))
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

def play_note(freq, ms=400):
    """Play a single note at given frequency."""
    buz = machine.PWM(machine.Pin(BUZZER_PIN))
    buz.freq(freq); buz.duty_u16(32768)
    time.sleep_ms(ms)
    buz.duty_u16(0); buz.deinit()

# 4th octave frequencies
NOTE_FREQ = {
    "notec": 262,
    "noted": 294,
    "notee": 330,
    "notef": 349,
    "noteg": 392,
    "notea": 440,
    "noteb": 494,
}

def beep_confirm():
    beep(880, 60); time.sleep_ms(40); beep(1200, 80)

def beep_start():
    beep(660, 80); time.sleep_ms(30)
    beep(880, 80); time.sleep_ms(30)
    beep(1100, 120)

def beep_stop():
    beep(800, 80); time.sleep_ms(30); beep(400, 200)

# ─────────────────────────────────────────────
# BATTERY DISPLAY
# ─────────────────────────────────────────────
batt = None

def show_battery():
    if batt is None:
        print("  [WARN] Battery sensor not available")
        beep(200, 300); return
    try:
        voltage, soc = batt.read_all()
    except Exception as e:
        print("  [WARN] Battery read failed: %s" % str(e))
        beep(200, 300); return

    soc_clamped = max(0, min(100, soc))
    lit = int(soc_clamped / 100 * NUM_LEDS)

    if soc_clamped > 50:
        r, g, b = 0, 40, 0
    elif soc_clamped > 20:
        r, g, b = 40, 25, 0
    else:
        r, g, b = 40, 0, 0

    for i in range(NUM_LEDS):
        np[i] = (r, g, b) if i < lit else (0, 0, 0)
    np.write()

    print("  Battery: %.1f%%  (%.2fV)" % (soc, voltage))
    beep(600, 60)
    time.sleep_ms(2000)
    for step in range(10, -1, -1):
        scale = step / 10
        for i in range(NUM_LEDS):
            if i < lit:
                np[i] = (int(r * scale), int(g * scale), int(b * scale))
            else:
                np[i] = (0, 0, 0)
        np.write()
        time.sleep_ms(40)
    leds_off()

# ─────────────────────────────────────────────
# ACTION CHAIN BUILDER
# ─────────────────────────────────────────────

def resolve_and_group(group):
    """
    Deduplicate actions within an AND group by resource.
    If two actions share a resource, keep only the last one.
    Returns deduplicated list.
    """
    by_resource = {}
    for action in group:
        res = ACTION_RESOURCE.get(action, action)
        by_resource[res] = action  # last one wins
    return list(by_resource.values())


def chain_to_str(chain):
    """Pretty-print an action chain for display."""
    parts = []
    for i, group in enumerate(chain):
        if len(group) > 1:
            parts.append(" & ".join(group))
        else:
            parts.append(group[0])
    return " -> ".join(parts)


# ─────────────────────────────────────────────
# ACTION EXECUTION
# ─────────────────────────────────────────────

ACTION_FNS = {
    # Melody
    "playnote":   play_melody,
    # Individual notes (4th octave, 400ms each)
    "notea":      lambda: play_note(440),
    "noteb":      lambda: play_note(494),
    "notec":      lambda: play_note(262),
    "noted":      lambda: play_note(294),
    "notee":      lambda: play_note(330),
    "notef":      lambda: play_note(349),
    "noteg":      lambda: play_note(392),
    # LED colors (pulse for 600ms)
    "turnpurple": lambda: leds_pulse_color(127, 0, 127),
    "turnred":    lambda: leds_pulse_color(127, 0, 0),
    "turnblue":   lambda: leds_pulse_color(0, 0, 127),
    "turngreen":  lambda: leds_pulse_color(0, 127, 0),
    "turnwhite":  lambda: leds_pulse_color(80, 80, 80),
    "turnyellow": lambda: leds_pulse_color(127, 80, 0),
    "turnoff":    leds_off,
}


def run_and_group(group):
    """
    Run all actions in a group simultaneously using threads.
    If only one action, just run it directly.
    """
    if len(group) == 1:
        ACTION_FNS[group[0]]()
        return

    # Multiple actions — run all but last in threads, last on main
    done = [0]

    def thread_action(name):
        try:
            ACTION_FNS[name]()
        except Exception as e:
            print("  [ERR] %s:" % name); sys.print_exception(e)
        done[0] += 1

    for action in group[:-1]:
        _thread.start_new_thread(thread_action, (action,))

    # Run last action on main thread
    ACTION_FNS[group[-1]]()

    # Wait for threads to finish (with timeout)
    timeout = time.ticks_ms() + 3000
    while done[0] < len(group) - 1:
        if time.ticks_diff(time.ticks_ms(), timeout) > 0:
            break
        time.sleep_ms(10)


def run_chain(chain):
    """Execute the full action chain: AND groups run together, THEN groups run sequentially."""
    for group in chain:
        run_and_group(group)


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
    accel.clear_wake()
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


TRIGGER_FNS = {"waitbutton": wait_for_button, "waitshake": wait_for_shake}

# ─────────────────────────────────────────────
# STATE MACHINE
# ─────────────────────────────────────────────
STATE_IDLE        = 0   # waiting for trigger
STATE_TRIGGER_SET = 1   # trigger chosen, waiting for first action
STATE_BUILDING    = 2   # action(s) entered, waiting for and/then/action/start
STATE_RUNNING     = 3   # executing trigger→chain loop

STATE_COLORS = {
    STATE_IDLE:        (0, 0, 10),
    STATE_TRIGGER_SET: (10, 5, 0),
    STATE_BUILDING:    (0, 10, 0),
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
accel = None

def main():
    global accel, batt
    print("\n" + "=" * 50)
    print("  PlaygroundV5 — NFC Trigger->Action Programmer")
    print("  Supports: AND (simultaneous) / THEN (sequential)")
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

    # Battery
    try:
        batt = MAX17048(i2c)
        v, s = batt.read_all()
        print("  Battery OK (%.2fV, %.1f%%)" % (v, s))
    except Exception as e:
        batt = None
        print("  [WARN] Battery:"); sys.print_exception(e)

    state = STATE_IDLE
    trigger_name = None
    # Action chain: list of groups, each group is a list of action names
    # e.g. [["playnote", "turnpurple"], ["playnote"]]
    #       = (playnote AND turnpurple) THEN playnote
    chain = []
    pending_combinator = None  # "and" or "then" — waiting for next action
    last_uid = None

    show_state(state)
    print("\n  Step 1: Tap a TRIGGER tag (waitbutton / waitshake)")

    while True:
        try:
            # ── PROGRAMMING PHASE ──
            if state in (STATE_IDLE, STATE_TRIGGER_SET, STATE_BUILDING):
                cmd, uid = read_tag_command(nfc)

                if cmd is None or uid == last_uid:
                    if cmd is None and uid is None:
                        last_uid = None
                    time.sleep_ms(200)
                    continue

                last_uid = uid

                # ── UTILITY: battery works in any state ──
                if cmd == "battery":
                    show_battery()
                    show_state(state)
                    continue

                print("  >> %s" % cmd)

                # ── STATE_IDLE: expecting a trigger ──
                if state == STATE_IDLE:
                    if cmd in TRIGGERS:
                        if cmd == "waitshake" and not accel_ok:
                            print("  [SKIP] Accelerometer not available!")
                            beep(200, 300); continue
                        trigger_name = cmd
                        chain = []
                        pending_combinator = None
                        state = STATE_TRIGGER_SET
                        show_state(state); beep_confirm()
                        print("  > Trigger: %s" % trigger_name)
                        print("  Step 2: Tap an ACTION tag")
                    elif cmd == "stop":
                        print("  Nothing running.")
                    else:
                        print("  Expected a trigger tag")
                        beep(200, 150)

                # ── STATE_TRIGGER_SET: expecting first action ──
                elif state == STATE_TRIGGER_SET:
                    if cmd in ACTIONS:
                        chain = [[cmd]]
                        pending_combinator = None
                        state = STATE_BUILDING
                        show_state(state); beep_confirm()
                        print("  > Program: %s -> [%s]" % (trigger_name, chain_to_str(chain)))
                        print("  Tap AND/THEN for more, or START to run")
                    elif cmd in TRIGGERS:
                        if cmd == "waitshake" and not accel_ok:
                            print("  [SKIP] Accelerometer not available!")
                            beep(200, 300); continue
                        trigger_name = cmd
                        beep_confirm()
                        print("  > Trigger changed: %s" % trigger_name)
                    else:
                        print("  Expected an action tag")
                        beep(200, 150)

                # ── STATE_BUILDING: actions entered, can add more or start ──
                elif state == STATE_BUILDING:
                    if cmd == "and":
                        pending_combinator = "and"
                        beep(500, 40); time.sleep_ms(30); beep(500, 40)
                        print("  > AND — tap next action (simultaneous)")

                    elif cmd == "then":
                        pending_combinator = "then"
                        beep(400, 60); time.sleep_ms(50); beep(600, 60)
                        print("  > THEN — tap next action (sequential)")

                    elif cmd in ACTIONS:
                        if pending_combinator == "and":
                            # Add to current (last) group
                            chain[-1].append(cmd)
                            # Resolve conflicts within group
                            chain[-1] = resolve_and_group(chain[-1])
                        elif pending_combinator == "then":
                            # New sequential group
                            chain.append([cmd])
                        else:
                            # No combinator — replace entire chain with single action
                            chain = [[cmd]]

                        pending_combinator = None
                        beep_confirm()
                        print("  > Program: %s -> [%s]" % (trigger_name, chain_to_str(chain)))
                        print("  Tap AND/THEN for more, or START to run")

                    elif cmd == "start":
                        if pending_combinator:
                            print("  [SKIP] Tap an action after %s first" % pending_combinator)
                            beep(200, 150)
                            continue
                        state = STATE_RUNNING
                        show_state(state); beep_start()
                        leds_flash(0, 40, 0, times=3, on_ms=80, off_ms=60)
                        desc = chain_to_str(chain)
                        print("\n  >>> RUNNING: %s -> [%s]" % (trigger_name, desc))
                        print("  (Tap STOP to end)\n")

                    elif cmd in TRIGGERS:
                        # Restart programming with new trigger
                        if cmd == "waitshake" and not accel_ok:
                            print("  [SKIP] Accelerometer not available!")
                            beep(200, 300); continue
                        trigger_name = cmd
                        chain = []
                        pending_combinator = None
                        state = STATE_TRIGGER_SET
                        show_state(state); beep_confirm()
                        print("  > Reprogramming — trigger: %s" % trigger_name)
                        print("  Step 2: Tap an ACTION tag")

                    elif cmd == "stop":
                        trigger_name = None
                        chain = []
                        pending_combinator = None
                        state = STATE_IDLE
                        show_state(state); beep_stop()
                        print("  Reset. Step 1: Tap a TRIGGER tag")

            # ── RUNNING PHASE ──
            elif state == STATE_RUNNING:
                result = TRIGGER_FNS[trigger_name](nfc)

                if result == "stop":
                    state = STATE_IDLE
                    trigger_name = None; chain = []
                    pending_combinator = None
                    leds_off(); beep_stop(); show_state(state)
                    last_uid = None
                    print("  <<< STOPPED")
                    print("\n  Step 1: Tap a TRIGGER tag to reprogram")
                    continue

                if result == "fired":
                    print("  * %s fired -> [%s]" % (trigger_name, chain_to_str(chain)))
                    run_chain(chain)

                time.sleep_ms(200)

        except KeyboardInterrupt:
            leds_off(); print("\n  Exiting."); break
        except Exception as e:
            print("  [ERR]:"); sys.print_exception(e)
            time.sleep_ms(500)


if __name__ == "__main__":
    main()