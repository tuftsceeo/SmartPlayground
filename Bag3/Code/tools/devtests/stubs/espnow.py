"""Stub: MicroPython espnow."""
class ESPNow:
    def active(self, *a): return True
    def add_peer(self, *a): pass
    def send(self, *a, **k): return True
    def irecv(self, timeout=0): return (None, None)
    def config(self, *a, **k): pass
