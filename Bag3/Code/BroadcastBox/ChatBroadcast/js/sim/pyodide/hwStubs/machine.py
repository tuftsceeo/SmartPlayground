"""Browser stub for MicroPython machine module."""

IN = 1
OUT = 0
PULL_UP = 1
PULL_DOWN = 0

# Shared input state — updated from JS before each sim tick via sim_bootstrap.
_input_state = {"button": 1, "accel": (0, 0, 1)}


def set_input_state(state):
    global _input_state
    _input_state = state


class Pin:
    def __init__(self, pin_id, mode=IN, pull=None):
        self.pin_id = pin_id
        self.mode = mode
        self.pull = pull
        self._out = 0

    def value(self, v=None):
        if v is not None:
            self._out = v
            return None
        # GPIO0 button is active LOW in wand games.
        if self.pin_id == 0:
            return _input_state.get("button", 1)
        return self._out


class PWM:
    def __init__(self, pin):
        self.pin = pin

    def freq(self, f):
        pass

    def duty_u16(self, d):
        pass

    def deinit(self):
        pass


class SoftI2C:
    def __init__(self, *args, **kwargs):
        pass

    def scan(self):
        return []


I2C = SoftI2C
