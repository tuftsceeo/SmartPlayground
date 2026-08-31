"""Browser stub — fixed full brightness for simulation."""

MULTIPLIER = 1.0
LAST_LUX = None


def calibrate(opt3002):
    return 1.0, 500.0


def set_multiplier(value):
    global MULTIPLIER
    MULTIPLIER = value


def get_multiplier():
    return MULTIPLIER


def get_lux():
    return LAST_LUX


def scale(r, g, b):
    return int(r * MULTIPLIER), int(g * MULTIPLIER), int(b * MULTIPLIER)
