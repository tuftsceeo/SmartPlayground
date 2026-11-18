HOST_NFC_MS = 100          # NFC detect timeout per host-loop pass
CORNERS = ((0, 1, 5, 6), (3, 4, 8, 9), (15, 16, 20, 21), (18, 19, 23, 24))
CROSS_FILL = (7, 11, 13, 17, 2, 10, 14, 22)   # the cross, center outward
CENTER_PIXEL = 12
LOBBY_RGB = (60, 140, 0)   # yellow-green
PLAY_RGB = (0, 180, 240)   # cyan
EMPTY_RGB = (0, 4, 24)
HOLD_RGB = (140, 150, 150)
PAIR_SCALE = 0.4           # a paired corner; a pulsed one is full
FRAME_MS = 40
BOOT_SOLID_MS = 1000       # stored pairs show solid this long after boot
MISSING_FLASH_MS = 400
PULSE_MS = 600
PEEK_MS = 4000
SHORT_PRESS_MS = 400
START_HOLD_MS = 1500
END_HOLD_MS = 3000
FORGET_HOLD_MS = 4000      # one corner goes out per second
ROLES = ("splat_host", "player")
#SPLIT#
def _scale(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))


def _breathe(now, period=2000):
    t = (now % period) / period
    return 0.15 + 0.85 * (1 - abs(2 * t - 1))


def _beat(now, period=1200):
    t = now % period
    return 1.0 if t < 120 or 240 <= t < 360 else 0.15


def frame(slots, present, mode, now, hold=0.0, gone=0, pulse=None, lobby_rgb=None,
          boot=False):
    """The host screen as 25 RGB tuples. slots: per slot None or (rgb A, rgb B);
    present: per slot True when that Splat is connected; mode "idle", "lobby" or
    "playing"; hold 0..1 fills the cross; gone corners from the last are out
    (forget hold); pulse a slot index shown bright; boot shows pairs solid."""
    px = [(0, 0, 0)] * 25
    nxt = None
    for k in range(len(CORNERS)):
        if k < len(slots) and slots[k] is None and nxt is None:
            nxt = k
    for k in range(len(CORNERS)):
        c = CORNERS[k]
        if k >= len(CORNERS) - gone:
            continue
        e = slots[k] if k < len(slots) else None
        if e is None:
            rgb = _scale(EMPTY_RGB, 2 * _breathe(now)) if k == nxt else EMPTY_RGB
            for p in c:
                px[p] = rgb
            continue
        if not (boot or present[k]) and (now // MISSING_FLASH_MS) % 2:
            continue
        f = 1.0 if pulse == k else PAIR_SCALE
        px[c[0]] = px[c[2]] = _scale(e[0], f)
        px[c[1]] = px[c[3]] = _scale(e[1], f)
    if mode == "lobby":
        base = _scale(LOBBY_RGB, _breathe(now))
    elif mode == "playing":
        base = _scale(PLAY_RGB, _beat(now))
    else:
        base = (0, 0, 0)
    n = int(hold * len(CROSS_FILL) + 0.999) if hold > 0 else 0
    for i in range(len(CROSS_FILL)):
        px[CROSS_FILL[i]] = HOLD_RGB if i < n else base
    if lobby_rgb is not None and mode != "idle":
        px[CENTER_PIXEL] = lobby_rgb
    return px


class HostScreen:
    """The host's screen and button, shared by the idle loop (run), the lobby
    (lobby_game.run_lobby) and a running game (lobby_game.Net.poll)."""

    def __init__(self, born=None):
        self.born = time.ticks_ms() if born is None else born
        self.slots = pairing.load_slots()
        self._down_at = None
        self._fired = False
        self.peek_until = None
        self._drawn_at = None
        self._peek_shown = None

    def reload(self):
        self.slots = pairing.load_slots()

    def button(self, down, mode, now, can_start=True):
        """Advance the button state. Returns (action, hold, gone): action None,
        "peek", "start", "refuse", "end" or "forget"."""
        act, hold, gone = None, 0.0, 0
        if down and self._down_at is None:
            self._down_at = now
            self._fired = False
        if self._down_at is None:
            return act, hold, gone
        el = time.ticks_diff(now, self._down_at)
        if not down:
            self._down_at = None
            if el < SHORT_PRESS_MS and not self._fired:
                self.peek_until = time.ticks_add(now, PEEK_MS)
                act = "peek"
            return act, hold, gone
        if self._fired:
            return act, hold, gone
        if mode == "lobby":
            need = START_HOLD_MS
        elif mode == "playing":
            need = END_HOLD_MS
        else:
            need = FORGET_HOLD_MS
        if el >= SHORT_PRESS_MS:
            if mode == "idle":
                gone = min(len(CORNERS), el // 1000)
            else:
                hold = min(1.0, (el - SHORT_PRESS_MS) / (need - SHORT_PRESS_MS))
        if el >= need:
            self._fired = True
            act = {"lobby": "start", "playing": "end", "idle": "forget"}[mode]
            if act == "start" and not can_start:
                act = "refuse"
        return act, hold, gone

    def peeking(self, now):
        if self.peek_until is None:
            return False
        if time.ticks_diff(self.peek_until, now) > 0:
            return True
        self.peek_until = None
        return False

    def draw(self, leds, ctl, mode, now, hold=0.0, gone=0, count=0, lobby_rgb=None):
        """Write the screen (at most every FRAME_MS), or the peeked count."""
        if self.peeking(now):
            if self._peek_shown != count:
                import leds as L
                from leds import WHITE
                leds.show_shape(getattr(L, "SHAPE_%d" % min(count, 9)), WHITE)
                self._peek_shown = count
            return
        self._peek_shown = None
        if self._drawn_at is not None and time.ticks_diff(now, self._drawn_at) < FRAME_MS:
            return
        self._drawn_at = now
        from splatpair import WAND_RGB
        slots, present = [], []
        pulse = None
        for k in range(len(CORNERS)):
            e = self.slots[k] if k < len(self.slots) else None
            slots.append(None if e is None else (WAND_RGB[e[1]], WAND_RGB[e[2]]))
            on = False
            if e is not None and ctl is not None and e[0] in ctl.macs:
                j = ctl.macs.index(e[0])
                on = ctl.hub is not None and ctl.hub.links[j].ready
                if (getattr(ctl, "pulse_mac", None) == e[0]
                        and time.ticks_diff(now, ctl.pulse_at) < PULSE_MS):
                    pulse = k
            present.append(on)
        boot = time.ticks_diff(now, self.born) < BOOT_SOLID_MS
        px = frame(slots, present, mode, now, hold, gone, pulse, lobby_rgb, boot)
        for i in range(min(leds.num, 25)):
            leds.np[i] = px[i]
        leds.np.write()


