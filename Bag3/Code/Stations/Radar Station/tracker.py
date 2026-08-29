"""
tracker.py -- turns per-frame LD2450 targets (positional slots 0..2 that
can swap between people frame to frame) into stable tracks with a
persistent id, smoothed position, and a derived ground-speed/heading that
the raw sensor can't give us on its own.

Why this exists: the LD2450 reports up to 3 targets per frame with NO
identity across frames -- slot 0 this frame might be a different person
than slot 0 last frame. And its own "speed" field is RADIAL ONLY (the
component of velocity along the sensor's line of sight), so it can't
tell a person walking across the field from one standing still. This
module does simple nearest-neighbour association frame-to-frame to
assign stable ids, and derives true ground velocity from position deltas
so walk/run classification (see events.py) has something meaningful to
work from.

Deliberately simple: no Kalman filter, no multi-hypothesis tracking --
this is a demo-grade tracker for a 3-target sensor at 10Hz. See the plan
for what Gate B's traces should tell us to tune (TRACK_GATE_MM,
TRACK_MAX_MISSES, TRACK_SMOOTH_ALPHA in config.py).
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
    # extremely unlikely fallback path (math should always exist on
    # MicroPython) -- coarse quadrant-only heading, better than crashing
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
        self.sp = 0.0       # true ground speed, mm/s (magnitude of vx,vy)
        self.hd = 0.0        # heading, degrees, atan2(vy, vx)
        self.radial_v = 0    # most recent raw sensor speed (cm/s, radial/line-of-sight)
        self.age = 0          # frames this track has existed
        self.misses = 0       # consecutive frames with no matching detection

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
        """targets: list of ld2450.Target for this frame (already fused if
        multi-sensor, but that's out of scope for this plan -- see
        priority 4). Returns the current list of live Track objects."""
        unmatched_tracks = list(self.tracks)
        unmatched_targets = list(targets)
        matches = []  # (track, target)

        # greedy nearest-neighbour: repeatedly pick the closest still-
        # unmatched (track, target) pair within the gate radius. Fine for
        # up to 3 targets; would need a real assignment algorithm (e.g.
        # Hungarian) at higher target counts.
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

    def _apply_measurement(self, track, target):
        prev_x, prev_y = track.x, track.y
        a = self.alpha
        track.x = a * track.x + (1 - a) * target.x
        track.y = a * track.y + (1 - a) * target.y
        track.radial_v = target.speed
        # ground velocity from smoothed-position delta, not from the
        # sensor's radial speed field -- see module docstring
        track.vx = (track.x - prev_x) / self.dt_s
        track.vy = (track.y - prev_y) / self.dt_s
        track.sp = (track.vx * track.vx + track.vy * track.vy) ** 0.5
        if track.sp > 1e-6:
            track.hd = _atan2_deg(track.vy, track.vx)
