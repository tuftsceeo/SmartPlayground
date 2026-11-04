"""Fake OPT3002 ambient light sensor — lux from sim_state."""

import sim_state


class OPT3002:
    def __init__(self, i2c, addr=0x44):
        self.i2c = i2c
        self.addr = addr

    def init(self):
        pass

    @property
    def lux(self):
        return sim_state.ambient_lux

    def read(self):
        return self.lux
