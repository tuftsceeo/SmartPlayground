"""Stub: MicroPython select. Tests drive JsonLink directly, never via poll."""
POLLIN = 1
class poll:
    def __init__(self): self._r = []
    def register(self, obj, mask=POLLIN): self._r.append(obj)
    def poll(self, timeout=0): return []
