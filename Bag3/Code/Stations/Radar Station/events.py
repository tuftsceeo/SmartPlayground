"""
events.py -- derives presence, per-zone counts, approach/recede, and a
still/walk/run speed bucket from tracker.Track objects. Speed bucket
uses tracker ground speed (sp); approach/recede uses sensor radial speed
sign.
"""

import config


def _point_in_zone(x, y, zone):
    return zone["x0"] <= x <= zone["x1"] and zone["y0"] <= y <= zone["y1"]


def _speed_bucket(sp):
    if sp < config.SPEED_WALK_MM_S:
        return "still"
    if sp < config.SPEED_RUN_MM_S:
        return "walk"
    return "run"


class EventEngine:
    def __init__(self):
        self._empty_frames = 0
        self.present = False

    def update(self, tracks):
        """tracks: list of tracker.Track for this frame. Returns a dict
        for the 'events' message body."""
        if tracks:
            self._empty_frames = 0
        else:
            self._empty_frames += 1
        if self._empty_frames == 0:
            self.present = True
        elif self._empty_frames >= config.PRESENCE_DROP_FRAMES:
            self.present = False

        zone_counts = {name: 0 for name in config.ZONES}
        approach = 0
        recede = 0
        buckets = {"still": 0, "walk": 0, "run": 0}

        for t in tracks:
            for name, zone in config.ZONES.items():
                if _point_in_zone(t.x, t.y, zone):
                    zone_counts[name] += 1
            if t.radial_v < 0:
                approach += 1
            elif t.radial_v > 0:
                recede += 1
            buckets[_speed_bucket(t.sp)] += 1

        return {
            "present": self.present,
            "count": len(tracks),
            "zones": zone_counts,
            "approach": approach,
            "recede": recede,
            "still": buckets["still"],
            "walk": buckets["walk"],
            "fast": buckets["run"],
        }
