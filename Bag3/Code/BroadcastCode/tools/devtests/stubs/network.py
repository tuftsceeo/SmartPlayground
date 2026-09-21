"""Stub: MicroPython network, absent on a dev box. Wire tests never use it."""
AP_IF = 1
STA_IF = 0
AUTH_WPA_WPA2_PSK = 3
class WLAN:
    def __init__(self, *a): pass
    def active(self, *a): return True
    def config(self, *a, **k): pass
    def ifconfig(self): return ("192.168.4.2",)
