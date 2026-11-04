"""Fake LIS2DW12 accelerometer — reads (x, y, z) from sim_state."""

import sim_state

RANGE_2G = 2
RANGE_4G = 4
RANGE_8G = 8
RANGE_16G = 16


class LIS2DW12:
    def __init__(self, i2c, addr=0x19):
        self.i2c = i2c
        self.addr = addr
        self._range = RANGE_4G

    def init(self, odr_mode=0x54, fs_range=RANGE_4G):
        self._range = fs_range

    def read(self):
        return (sim_state.accel_x, sim_state.accel_y, sim_state.accel_z)

    @property
    def data_ready(self):
        return True

    def enable_wake_int1(self, threshold=8, duration=0x00):
        pass

    def enable_wake_int2(self, threshold=8, duration=0x00):
        pass

    def clear_wake(self):
        pass

    @property
    def wake_threshold_g(self):
        return 0.5

    @property
    def device_id(self):
        return 0x44
