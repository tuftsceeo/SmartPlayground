"""
Fake MicroPython `machine` module for the wand simulator.

Pin GPIO0  — button (active LOW, reads sim_state.button_pressed)
Pin GPIO21 — vibration motor (writes call sim_state.emit_motor)
PWM        — buzzer (freq/duty -> sim_state.emit_pwm)
SoftI2C    — inert stub (drivers are faked; never actually read)
"""

import sim_state

# Pin modes
IN = 0
OUT = 1
OPEN_DRAIN = 2

# Pull
PULL_UP = 1
PULL_DOWN = 2

# IRQ triggers (stubs)
IRQ_RISING = 1
IRQ_FALLING = 2


class Pin:
    IN = IN
    OUT = OUT
    OPEN_DRAIN = OPEN_DRAIN
    PULL_UP = PULL_UP
    PULL_DOWN = PULL_DOWN
    IRQ_RISING = IRQ_RISING
    IRQ_FALLING = IRQ_FALLING

    def __init__(self, id, mode=IN, pull=None, value=None):
        self.id = int(id) if not isinstance(id, Pin) else id.id
        self.mode = mode
        self.pull = pull
        self._value = 0 if value is None else int(value)
        if self.id == 21 and value is not None:
            sim_state.emit_motor(bool(self._value))

    def init(self, mode=None, pull=None, value=None):
        if mode is not None:
            self.mode = mode
        if pull is not None:
            self.pull = pull
        if value is not None:
            self.value(value)

    def value(self, v=None):
        if v is None:
            if self.id == 0:
                # Active LOW: pressed -> 0
                return 0 if sim_state.button_pressed else 1
            return self._value
        self._value = 1 if v else 0
        if self.id == 21:
            sim_state.emit_motor(bool(self._value))
        return None

    def on(self):
        self.value(1)

    def off(self):
        self.value(0)

    def irq(self, *args, **kwargs):
        return None

    def __call__(self, v=None):
        return self.value(v)


class PWM:
    def __init__(self, pin, freq=5000, duty=0, duty_u16=0):
        if isinstance(pin, Pin):
            self._pin = pin.id
        else:
            self._pin = int(pin)
        self._freq = int(freq)
        self._duty = int(duty_u16) if duty_u16 else int(duty)
        self._active = True
        sim_state.emit_pwm(self._freq, self._duty)

    def freq(self, f=None):
        if f is None:
            return self._freq
        self._freq = int(f)
        if self._active:
            sim_state.emit_pwm(self._freq, self._duty)

    def duty(self, d=None):
        if d is None:
            return self._duty >> 6
        self._duty = int(d) << 6
        if self._active:
            sim_state.emit_pwm(self._freq, self._duty)

    def duty_u16(self, d=None):
        if d is None:
            return self._duty
        self._duty = int(d)
        if self._active:
            sim_state.emit_pwm(self._freq, self._duty)

    def deinit(self):
        self._active = False
        sim_state.emit_pwm(0, 0)


class SoftI2C:
    """Inert I2C — real drivers are replaced by fakes in py/devices/."""

    def __init__(self, scl=None, sda=None, freq=100000):
        self.scl = scl
        self.sda = sda
        self.freq = freq

    def scan(self):
        return [0x19, 0x24, 0x36, 0x44]

    def readfrom_mem(self, addr, memaddr, nbytes, *, addrsize=8):
        return bytes(nbytes)

    def writeto_mem(self, addr, memaddr, buf, *, addrsize=8):
        return None

    def readfrom(self, addr, nbytes):
        return bytes(nbytes)

    def writeto(self, addr, buf):
        return len(buf)


class I2C(SoftI2C):
    pass


class Timer:
    ONE_SHOT = 0
    PERIODIC = 1

    def __init__(self, id=-1):
        self.id = id

    def init(self, *args, **kwargs):
        pass

    def deinit(self):
        pass


class ADC:
    def __init__(self, pin):
        self.pin = pin

    def read_u16(self):
        return 32768

    def read(self):
        return 2048


def reset():
    pass


def unique_id():
    return b"\x01\x02\x03\x04\x05\x06"


def freq(f=None):
    if f is None:
        return 160_000_000
    return f


mem32 = {}
