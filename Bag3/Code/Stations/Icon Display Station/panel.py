"""
panel.py -- this station's hardware: a 16x16 full-colour icon panel.

Verbs, over ESP-NOW "cap" messages addressed to hubtype icon_station:

    icon   {n}            show the stored icon named n
    clear                 blank the panel
    bright {v}            set intensity (Matrix clamps at max_intensity)
    cycle  {names, ms}    cycle a list of icons, ms apart

Icons live in icons/<name>.py and arrive with the game that names them.
icon_matrix.Matrix owns the panel geometry, the intensity clamp and the fast
path into the NeoPixel buffer; icon_store.read_icon() owns parsing and scaling.
Neither is reimplemented here.
"""

import time

from icon_matrix import Matrix, W, H
import icon_store


class IconPanel:

    def __init__(self):
        self.matrix = Matrix()
        self._buf = bytearray(W * H * 3)   # reused; read_icon fills it in place
        self._cycle = ()
        self._hold_ms = 0
        self._at = 0
        self._due = 0
        self.matrix.clear()

    # -- capability interface ----------------------------------------

    def handle(self, op, args):
        if op == "icon":
            self._cycle = ()
            self.show(args["n"])
        elif op == "clear":
            self.off()
        elif op == "bright":
            self.matrix.set_intensity(args["v"])
            self.matrix.redraw()
        elif op == "cycle":
            self.cycle(args["names"], args.get("ms", 1000))
        else:
            raise ValueError("icon_station: unknown op %r" % op)

    def step(self):
        """Advance a running cycle. Returns at once when idle."""
        if not self._cycle:
            return
        if time.ticks_diff(time.ticks_ms(), self._due) < 0:
            return
        self.show(self._cycle[self._at])
        self._at = (self._at + 1) % len(self._cycle)
        self._due = time.ticks_add(time.ticks_ms(), self._hold_ms)

    def off(self):
        self._cycle = ()
        self.matrix.clear()

    # -- verbs -------------------------------------------------------

    def show(self, name):
        """Draw a stored icon. Raises if there is no such icon on flash."""
        icon_store.read_icon(name, into=self._buf)
        self.matrix.draw_bytes(self._buf)

    def cycle(self, names, hold_ms):
        self._cycle = tuple(names)
        self._hold_ms = hold_ms
        self._at = 0
        self._due = time.ticks_ms()
