"""Browser stub for LIS2DW12 accelerometer."""

RANGE_2G = 2
RANGE_4G = 4
RANGE_8G = 8
RANGE_16G = 16


class LIS2DW12:
    def __init__(self, i2c, addr=0x19):
        self.i2c = i2c
        self.addr = addr

    def init(self, odr_mode=0x54, fs_range=RANGE_4G):
        pass

    def read(self):
        from sim_bootstrap import input_state
        return tuple(input_state.get("accel", (0, 0, 1)))

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
