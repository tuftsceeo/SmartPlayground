# SPDX-FileCopyrightText: 2024 M5Stack Technology CO LTD
#
# SPDX-License-Identifier: MIT
# boot.py -- identical in spirit to ../M5Paper Remote/boot.py.
import esp32

"""
boot_option:
    0 -> Run main.py directly
    1 -> Show startup menu and network setup
    2 -> Only network setup

If you don't want anything special at boot, you can delete this whole file --
UIFlow2 firmware ships with an equivalent default.
"""

NETWORK_TIMEOUT = 60
