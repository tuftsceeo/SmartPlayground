"""Fake MAX17048 fuel gauge — reads volts/soc from sim_state."""

import sim_state


class MAX17048:
    def __init__(self, i2c, addr=0x36):
        self.i2c = i2c
        self.addr = addr

    def read_all(self):
        return (sim_state.battery_volts, sim_state.battery_soc)

    @property
    def volts(self):
        return sim_state.battery_volts

    @property
    def voltage(self):
        return sim_state.battery_volts

    @property
    def soc(self):
        return sim_state.battery_soc
