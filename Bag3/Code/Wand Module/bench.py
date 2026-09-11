"""
bench.py -- build a wand Device at the REPL, for running one game by hand.

    import bench, jumpin
    jumpin.play(bench.device())

main.py is how a wand normally runs a game; this is the same hardware, brought
up on its own so a single game can be exercised without the idle loop. Bench
only -- nothing imports it at boot.
"""

import machine

import gamelib
from hubtype import HUB_CONFIG
from espnow_manager import ESPNowManager
from leds import Leds
from buzzer import Buzzer
from pn532 import PN532
from nfc_reader import NfcReader
from lis2dw12 import LIS2DW12, RANGE_4G


def device():
    """A wand Device with the radio up and every peripheral attached."""
    leds = Leds()

    # Radio first: esp_wifi_init() needs contiguous heap that driver imports
    # fragment. Same order main.py uses.
    net = ESPNowManager()
    net.init()

    i2c = machine.SoftI2C(sda=machine.Pin(HUB_CONFIG["i2c_sda"]),
                          scl=machine.Pin(HUB_CONFIG["i2c_scl"]),
                          freq=HUB_CONFIG["i2c_freq"])

    dev = gamelib.Device(net)
    dev.leds = leds
    dev.buz = Buzzer(HUB_CONFIG["buzzer_pin"])
    dev.i2c = i2c
    dev.button = machine.Pin(HUB_CONFIG["button_pin"], machine.Pin.IN,
                             machine.Pin.PULL_UP)
    dev.motor = machine.Pin(HUB_CONFIG["motor_pin"], machine.Pin.OUT, value=0)

    dev.accel = LIS2DW12(i2c)
    dev.accel.init(fs_range=RANGE_4G)

    dev.nfc = PN532(i2c, addr=HUB_CONFIG["nfc_addr"])
    dev.nfc.begin()
    dev.reader = NfcReader(dev.nfc, ("stop",), prefixes=("getcode",))

    dev.begin("bench")
    return dev
