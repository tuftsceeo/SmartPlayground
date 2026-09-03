"""
Shared simulator input/output state.

JS (or the CPython harness) updates inputs; Python shims/devices read them.
A single module so Pin, lis2dw12, NfcReader, ESPNowManager, and neopixel
all see the same live state.
"""

import time  # patched in-place by time_patch.patch_time_module() during bootstrap

# ── Inputs (host -> Python) ─────────────────────────────────────────
button_pressed = False       # GPIO0 active-low when True
motor_on = False
accel_x = 0.0
accel_y = 1.0                # tip-up default
accel_z = 0.0
battery_volts = 3.9
battery_soc = 85             # percent
ambient_lux = 500.0

pending_nfc_cmd = None       # str or None
pending_nfc_uid = None       # str or None
pending_nfc_until = 0        # ticks_ms() the tag stays "under the reader" until
enow_queue = []              # list of (msg_type, data, mac_str)

# ── Callbacks (Python -> host) ──────────────────────────────────────
_led_frame_cb = None
_pwm_cb = None
_motor_cb = None
_print_cb = None
_log_cb = None

# Last-known outputs (handy for tests / polling)
led_frame = [(0, 0, 0)] * 25
pwm_freq = 0
pwm_duty = 0


def set_button(pressed):
    global button_pressed
    button_pressed = bool(pressed)


def set_accel(x, y, z):
    global accel_x, accel_y, accel_z
    accel_x = float(x)
    accel_y = float(y)
    accel_z = float(z)


def set_battery(volts=None, soc=None):
    global battery_volts, battery_soc
    if volts is not None:
        battery_volts = float(volts)
    if soc is not None:
        battery_soc = max(0, min(100, int(soc)))


def set_ambient_lux(lux):
    global ambient_lux
    ambient_lux = float(lux)


NFC_DEFAULT_DWELL_MS = 600  # how long a tapped tag stays "under the reader"


def tap_nfc(cmd, uid=None, dwell_ms=NFC_DEFAULT_DWELL_MS):
    """Simulate placing a tag under the reader for `dwell_ms`. cmd=None lifts
    it immediately. `uid` defaults to a name stable per tag so per-uid repeat
    guards (e.g. melody.py's REPEAT_SCAN_GUARD_MS) behave as they would with
    a real physical tag."""
    global pending_nfc_cmd, pending_nfc_uid, pending_nfc_until
    if cmd is None:
        pending_nfc_cmd = None
        pending_nfc_uid = None
        pending_nfc_until = 0
        return
    pending_nfc_cmd = str(cmd).lower()
    pending_nfc_uid = str(uid) if uid is not None else ("sim-" + pending_nfc_cmd)
    pending_nfc_until = time.ticks_add(time.ticks_ms(), int(dwell_ms))


def consume_nfc():
    """Return (cmd, uid) while the tapped tag is still within its dwell
    window, else (None, None). Non-destructive: a game may read this more
    than once per polling frame (gestures.py checks it in both _check_stop
    and _poll_tag) and must see the same tag both times, exactly as it
    would if a physical tag were still sitting under the reader."""
    if pending_nfc_cmd is None:
        return None, None
    if time.ticks_diff(pending_nfc_until, time.ticks_ms()) <= 0:
        return None, None
    return pending_nfc_cmd, pending_nfc_uid


def enqueue_enow(msg_type, data=None, mac_str="aa:bb:cc:dd:ee:ff"):
    enow_queue.append((msg_type, data, mac_str))


def dequeue_enow():
    if enow_queue:
        return enow_queue.pop(0)
    return None, None, None


def set_led_callback(cb):
    global _led_frame_cb
    _led_frame_cb = cb


def emit_led_frame(pixels):
    global led_frame
    led_frame = [tuple(p) for p in pixels]
    if _led_frame_cb:
        _led_frame_cb(led_frame)


def set_pwm_callback(cb):
    global _pwm_cb
    _pwm_cb = cb


def emit_pwm(freq, duty):
    global pwm_freq, pwm_duty
    pwm_freq = int(freq)
    pwm_duty = int(duty)
    if _pwm_cb:
        _pwm_cb(pwm_freq, pwm_duty)


def set_motor_callback(cb):
    global _motor_cb
    _motor_cb = cb


def emit_motor(on):
    global motor_on
    motor_on = bool(on)
    if _motor_cb:
        _motor_cb(motor_on)


def set_print_callback(cb):
    global _print_cb
    _print_cb = cb


def emit_print(text):
    if _print_cb:
        _print_cb(str(text))


def set_log_callback(cb):
    global _log_cb
    _log_cb = cb


def emit_log(msg):
    if _log_cb:
        _log_cb(str(msg))


def reset_io():
    """Clear queues / pending one-shots; restore default gravity."""
    global button_pressed, motor_on, accel_x, accel_y, accel_z
    global pending_nfc_cmd, pending_nfc_uid, pending_nfc_until, led_frame, pwm_freq, pwm_duty
    button_pressed = False
    motor_on = False
    pending_nfc_until = 0
    accel_x, accel_y, accel_z = 0.0, 1.0, 0.0
    pending_nfc_cmd = None
    pending_nfc_uid = None
    enow_queue.clear()
    led_frame = [(0, 0, 0)] * 25
    pwm_freq = 0
    pwm_duty = 0
