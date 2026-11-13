"""
display_station.py -- icon display station mode (gaps D3 and D2, M3 target rule).

With no game running, the display obeys any wand:

    {"type": "show", "icon": "<name>"}                 an icon from icons/
    {"type": "show", "px": [[row, col, [r, g, b]], ...]}  pixels on a dark panel
    {"type": "show", "text": "<up to 4 chars>"}        draw16 font: 0-9 space - : .
    {"type": "dance", "s": ["jump", "spin", ...]}      loop a dance (Move Mixer)

Optional on every message: "to": "<mac>" (M3). Without it every display obeys;
with it only the display whose MAC matches does. Nothing filters by sender,
and nothing about the sender is shown.

A show replaces whatever is up (a dance included) and holds SHOW_HOLD_MS. A
dance shows one step every STEP_MS with a beat bar and step dots, runs at
least MIN_LOOPS loops before a newer dance replaces it, keeps only the newest
waiting dance, and stops after DANCE_MAX_MS without a new one. A bad message
prints [ERR] and is ignored.

Imported lazily by main.py, on the first "raw" ESP-NOW message while idle --
after the radio is up (AGENTS.md radio-first rule). main.py drops the Station
instance on a stop, a card tap or a game start, which ends whatever it shows.
"""

import time

import draw16
import icon_store

SHOW_HOLD_MS = 60000
STEP_MS = 2000
MIN_LOOPS = 2
DANCE_MAX_MS = 600000
MAX_STEPS = 6
MAX_PX = 64
MAX_TEXT = 4
INTENSITY = 0.15

# Move name -> icon. Move Mixer sends these (its `twice` card is expanded on
# the wand before sending, so it never appears here).
MOVE_ICONS = {
    "jump": "bunny",
    "spin": "sunflower",
    "wave": "hand",
    "freeze": "snowflake",
}

# Dance layout: a 12x12 icon in rows 0-11, beat bar on row 14, step dots on 15.
_ICON_N = 12
_ICON_COL = 2
_BEAT_ROW = 14
_DOT_ROW = 15
BEAT_COLOR = (0, 60, 220)
DOT_ON = (185, 200, 200)
DOT_OFF = (30, 32, 32)
TEXT_COLOR = (185, 255, 150)


def _shrink(src, dst):
    """Nearest-neighbour 16x16 -> 12x12, into a 432-byte buffer."""
    for r in range(_ICON_N):
        sr = r * 16 // _ICON_N
        for c in range(_ICON_N):
            sc = c * 16 // _ICON_N
            s = (sr * 16 + sc) * 3
            d = (r * _ICON_N + c) * 3
            dst[d] = src[s]
            dst[d + 1] = src[s + 1]
            dst[d + 2] = src[s + 2]


class Station:
    def __init__(self, enow):
        self._enow = enow
        self._mode = None        # None, "show", "dance"
        self._since = 0
        self._dirty = False
        self._dance = None       # list of step icon buffers (12x12)
        self._dance_n = 0
        self._step = 0
        self._loops = 0
        self._step_at = 0
        self._beat = -1
        self._waiting = None     # newest dance not yet shown
        self._moves = None       # move names of the dance showing
        self._waiting_moves = None
        self._last_share = 0

    # ── messages ──

    def handle(self, data, panel):
        """Act on one "raw" ESP-NOW payload. Returns True if it was a station
        message for this display (main.py then gives the panel to tick())."""
        if not isinstance(data, dict):
            return False
        kind = data.get("type")
        if kind != "show" and kind != "dance":
            return False
        to = data.get("to")
        if to is not None and not self._enow._is_for_me(to):
            return False
        try:
            if kind == "show":
                return self._show(data, panel)
            return self._take_dance(data)
        except Exception as e:
            print(f"  [ERR] station {kind}: {e}")
            return False

    def _show(self, data, panel):
        src = panel.src
        if "icon" in data:
            name = data["icon"]
            try:
                icon_store.read_icon(name, into=src)
            except (OSError, ValueError) as e:
                print(f"  [ERR] station show: no icon {name!r} ({e})")
                return False
        elif "px" in data:
            px = data["px"]
            if not isinstance(px, list) or len(px) > MAX_PX:
                print(f"  [ERR] station show: px must be a list of at most {MAX_PX}")
                return False
            draw16.clear(src)
            for p in px:
                row, col, rgb = p
                draw16.px(src, int(row), int(col), (int(rgb[0]), int(rgb[1]), int(rgb[2])))
        elif "text" in data:
            s = str(data["text"])[:MAX_TEXT]
            draw16.clear(src)
            draw16.text(src, s, 5, (draw16.W - draw16.width(s)) // 2, TEXT_COLOR)
        else:
            print("  [ERR] station show: needs icon, px or text")
            return False
        self._mode = "show"
        self._dance = None
        self._waiting = None
        self._moves = None
        self._waiting_moves = None
        self._since = time.ticks_ms()
        panel.set_intensity(INTENSITY)
        draw16.show(panel)
        return True

    def _take_dance(self, data):
        moves = data.get("s")
        if not isinstance(moves, list) or not moves:
            print("  [ERR] station dance: s must be a non-empty list of moves")
            return False
        # A wand sends each share a few times (broadcasts are not acked):
        # a dance identical to the one showing or waiting is a repeat.
        if (self._mode == "dance" and moves == self._moves) or moves == self._waiting_moves:
            self._last_share = time.ticks_ms()
            return True
        steps = []
        cache = {}
        full = bytearray(768)
        for m in moves[:MAX_STEPS]:
            icon = MOVE_ICONS.get(m)
            if icon is None:
                print(f"  [ERR] station dance: unknown move {m!r}, step dropped")
                continue
            if icon not in cache:
                icon_store.read_icon(icon, into=full)
                small = bytearray(_ICON_N * _ICON_N * 3)
                _shrink(full, small)
                cache[icon] = small
            steps.append(cache[icon])
        if not steps:
            return False
        self._waiting = steps
        self._waiting_moves = moves
        self._last_share = time.ticks_ms()
        if self._mode != "dance":
            self._start_waiting()
        return True

    def _start_waiting(self):
        self._dance = self._waiting
        self._moves = self._waiting_moves
        self._waiting = None
        self._waiting_moves = None
        self._dance_n = len(self._dance)
        self._mode = "dance"
        self._step = 0
        self._loops = 0
        self._step_at = time.ticks_ms()
        self._beat = -1
        self._dirty = True

    # ── per idle frame ──

    def tick(self, panel):
        """Called by main.py's idle loop. Returns True while the station owns
        the panel; False hands it back to the idle display."""
        now = time.ticks_ms()
        if self._mode == "show":
            if time.ticks_diff(now, self._since) < SHOW_HOLD_MS:
                return True
            self._mode = None
            panel.clear()
            return False
        if self._mode != "dance":
            return False
        if time.ticks_diff(now, self._last_share) >= DANCE_MAX_MS:
            self._mode = None
            self._dance = None
            panel.clear()
            return False
        held = time.ticks_diff(now, self._step_at)
        if held >= STEP_MS:
            self._step += 1
            if self._step >= self._dance_n:
                self._step = 0
                self._loops += 1
                if self._loops >= MIN_LOOPS and self._waiting:
                    self._start_waiting()
            self._step_at = now
            self._beat = -1
            self._dirty = True
            held = 0
        beat = held * 16 // STEP_MS
        if beat != self._beat:
            self._beat = beat
            self._dirty = True
        if self._dirty:
            self._draw(panel)
            self._dirty = False
        return True

    def _draw(self, panel):
        src = panel.src
        draw16.clear(src)
        icon = self._dance[self._step]
        for r in range(_ICON_N):
            o = (r * 16 + _ICON_COL) * 3
            i = r * _ICON_N * 3
            src[o:o + _ICON_N * 3] = icon[i:i + _ICON_N * 3]
        if self._beat >= 0:
            draw16.rect(src, _BEAT_ROW, 0, _BEAT_ROW, self._beat, BEAT_COLOR)
        n = self._dance_n
        col = (16 - (2 * n - 1)) // 2
        for k in range(n):
            draw16.px(src, _DOT_ROW, col + 2 * k, DOT_ON if k == self._step else DOT_OFF)
        panel.set_intensity(INTENSITY)
        draw16.show(panel)
