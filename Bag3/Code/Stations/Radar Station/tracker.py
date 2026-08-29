"""
tracker.py -- assigns persistent ids to LD2450 targets (slots 0..2 are
positional, not identities) via nearest-neighbour association. Derives
ground velocity/heading from position deltas; the sensor's own speed
field is radial-only. Greedy nearest-neighbour, EMA smoothing, no
Kalman filter.
"""

import config

try:
    import math
except ImportError:
    math = None


def _dist2(ax, ay, bx, by):
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy


def _atan2_deg(y, x):
    if math is not None:
        return math.degrees(math.atan2(y, x))
    if x == 0 and y == 0:
        return 0.0
    if x >= 0:
        return 0.0 if y == 0 else (90.0 if y > 0 else -90.0)
    return 180.0 if y == 0 else (90.0 if y > 0 else -90.0)


class Track:
    __slots__ = ("id", "x", "y", "vx", "vy", "sp", "hd", "age", "misses", "radial_v")

    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.sp = 0.0        # ground speed, mm/s
        self.hd = 0.0        # heading, degrees
        self.radial_v = 0    # last raw sensor speed, cm/s, radial
        self.age = 0         # frames this track has existed
        self.misses = 0      # consecutive frames unmatched

    def to_dict(self):
        return {
            "id": self.id, "x": int(self.x), "y": int(self.y),
            "vx": int(self.vx), "vy": int(self.vy), "sp": int(self.sp),
            "hd": round(self.hd, 1), "age": self.age,
        }


class Tracker:
    def __init__(self, gate_mm=None, max_misses=None, alpha=None, dt_s=0.1):
        self.gate2 = (gate_mm if gate_mm is not None else config.TRACK_GATE_MM) ** 2
        self.max_misses = max_misses if max_misses is not None else config.TRACK_MAX_MISSES
        self.alpha = alpha if alpha is not None else config.TRACK_SMOOTH_ALPHA
        self.dt_s = dt_s
        self._next_id = 1
        self.tracks = []

    def update(self, targets):
        """targets: list of ld2450.Target for this frame. Returns the
        current list of live Track objects."""
        unmatched_tracks = list(self.tracks)
        unmatched_targets = list(targets)
        matches = []  # (track, target)

        while unmatched_tracks and unmatched_targets:
            best = None
            best_d2 = self.gate2
            for t in unmatched_tracks:
                for g in unmatched_targets:
                    d2 = _dist2(t.x, t.y, g.x, g.y)
                    if d2 <= best_d2:
                        best_d2 = d2
                        best = (t, g)
            if best is None:
                break
            matches.append(best)
            unmatched_tracks.remove(best[0])
            unmatched_targets.remove(best[1])

        for track, target in matches:
            self._apply_measurement(track, target)
            track.misses = 0
            track.age += 1

        for track in unmatched_tracks:
            track.misses += 1
            track.age += 1

        for target in unmatched_targets:
            track = Track(self._next_id, target.x, target.y)
            self._next_id += 1
            track.radial_v = target.speed
            track.age = 1
            self.tracks.append(track)

        self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]
        return self.tracks

    def set_params(self, gate_mm=None, max_misses=None, alpha=None):
        """Live tuning from radar_server.py's 'tune' command. Any argument
        left None keeps its current value."""
        if gate_mm is not None:
            self.gate2 = gate_mm ** 2
        if max_misses is not None:
            self.max_misses = max_misses
        if alpha is not None:
            self.alpha = alpha

    def _apply_measurement(self, track, target):
        prev_x, prev_y = track.x, track.y
        a = self.alpha
        track.x = a * track.x + (1 - a) * target.x
        track.y = a * track.y + (1 - a) * target.y
        track.radial_v = target.speed
        track.vx = (track.x - prev_x) / self.dt_s
        track.vy = (track.y - prev_y) / self.dt_s
        track.sp = (track.vx * track.vx + track.vy * track.vy) ** 0.5
        if track.sp > 1e-6:
            track.hd = _atan2_deg(track.vy, track.vx)
