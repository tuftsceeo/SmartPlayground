"""
Shared simulator input/output state.

JS (or the CPython harness) updates inputs; Python shims/devices read them.
A single module so Pin, lis2dw12, NfcReader, ESPNowManager, and neopixel
all see the same live state.
"""

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


def tap_nfc(cmd, uid="sim0001"):
    global pending_nfc_cmd, pending_nfc_uid
    pending_nfc_cmd = str(cmd).lower() if cmd is not None else None
    pending_nfc_uid = str(uid) if uid is not None else None


def consume_nfc():
    """Return and clear pending NFC (cmd, uid), or (None, None)."""
    global pending_nfc_cmd, pending_nfc_uid
    cmd, uid = pending_nfc_cmd, pending_nfc_uid
    pending_nfc_cmd = None
    pending_nfc_uid = None
    if cmd is None:
        return None, None
    return cmd, uid


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
    global pending_nfc_cmd, pending_nfc_uid, led_frame, pwm_freq, pwm_duty
    button_pressed = False
    motor_on = False
    accel_x, accel_y, accel_z = 0.0, 1.0, 0.0
    pending_nfc_cmd = None
    pending_nfc_uid = None
    enow_queue.clear()
    led_frame = [(0, 0, 0)] * 25
    pwm_freq = 0
    pwm_duty = 0
