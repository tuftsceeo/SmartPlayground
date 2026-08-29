"""
events.py -- turns the tracker's stable tracks into the high-level
signals a wand game would actually consume: presence, per-zone counts,
approach/recede, and a still/walk/run speed bucket. Deliberately thin --
games aren't designed yet, so this exists to show these signals are
*derivable* from the sensor, with thresholds the team can retune against
real Gate B traces rather than guesses baked into a game.

Speed classification uses the tracker's derived ground speed (sp), not
the sensor's raw radial speed -- see tracker.py's docstring for why the
raw field can't distinguish "running across the field" from "standing
still" on its own.

Approach/recede uses the sign of the raw radial speed direction (moving
toward vs. away from the sensor along its line of sight), which is
exactly what the sensor's own speed field is good for -- see the plan's
Gate A step 5 for the sign convention this depends on.
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
        """tracks: list of tracker.Track for this frame. Returns a plain
        dict, ready to hand to json_link.send() as the 'events' message
        body (see radar_server.py)."""
        if tracks:
            self._empty_frames = 0
        else:
            self._empty_frames += 1
        if self._empty_frames == 0:
            self.present = True
        elif self._empty_frames >= config.PRESENCE_DROP_FRAMES:
            self.present = False
        # else: hold the previous `present` value -- hysteresis band

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
