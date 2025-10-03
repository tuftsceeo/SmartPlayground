# getMAC.py (Student - temporary version to get MAC)
from machine import I2C, Pin
import ssd1306
import network

# Set up display
i2c = I2C(scl=Pin(23), sda=Pin(22))
display = ssd1306.SSD1306_I2C(128, 64, i2c)

# Get MAC address
sta = network.WLAN(network.STA_IF)
sta.active(True)
mac = sta.config('mac')
mac_str = ':'.join(['%02X' % b for b in mac])

# Display MAC address
display.fill(0)
display.text('MAC:', 0, 0, 1)
display.text(mac_str[:8], 0, 10, 1)
display.text(mac_str[9:], 0, 20, 1)
display.show()

print("MAC Address:", mac_str)