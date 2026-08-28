"""
mapio.py -- load/save maps/<name>.json (the human's committed per-segment
decisions) and tie segmentation + auto-propose + the saved map together
into one `decisions` list, keyed by exact source RGB so decisions survive
a re-run after the source art changes (see design doc §Architecture --
"Mapping is keyed by (icon, source_rgb), not source_rgb").
"""

import json
import os

from segment import load_rgba, histogram_fills, label_map, auto_propose

DEFAULT_INTENSITY = 0.30
DEFAULT_MAX_SEGMENTS = 12


def rgb_key(rgb):
    return "%d,%d,%d" % tuple(rgb)


def load_map(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_map(path, map_obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(map_obj, f, indent=2)
        f.write("\n")


def _decision_from_saved(saved):
    d = {"role": saved["role"], "priority": saved.get("priority", 1.0)}
    if saved["role"] == "merge":
        d["merge_into"] = saved["merge_into"]
        d["color"] = None
    elif saved["role"] == "color":
        d["color"] = tuple(saved["color"])
    else:  # off
        d["color"] = None
    return d


def build(png_path, existing_map=None, max_segments=DEFAULT_MAX_SEGMENTS, intensity=None):
    """
    Segment `png_path`, then for each fill: use the decision from
    `existing_map` if that exact source RGB is present, otherwise fall
    back to auto_propose(). Segment ids ("merge_into" targets, cells-won
    indices, etc.) are always indices into the freshly-computed `fills`
    list for THIS call -- saved merge targets are re-resolved by rgb key,
    not by the old index, since re-segmentation can reorder segments.

    Returns (img, fills, labels, decisions, overlay, mode) where `mode` is
    "exact"|"quantize" from histogram_fills, and `overlay` is the
    per-cell hand-edit dict carried over unchanged from existing_map.
    """
    img = load_rgba(png_path)
    fills, mode = histogram_fills(img, max_segments=max_segments)
    labels = label_map(img, fills)
    proposed = auto_propose(fills, labels, img)

    saved_by_key = {}
    if existing_map:
        for key, saved in existing_map.get("decisions", {}).items():
            saved_by_key[key] = saved

    key_to_idx = {rgb_key(f[0]): i for i, f in enumerate(fills)}

    decisions = []
    for i, (rgb, cnt, frac) in enumerate(fills):
        key = rgb_key(rgb)
        saved = saved_by_key.get(key)
        if saved is not None:
            d = _decision_from_saved(saved)
            if d["role"] == "merge":
                target_key = saved.get("merge_into_key")
                target_idx = key_to_idx.get(target_key, i)
                d["merge_into"] = target_idx
        else:
            p = proposed[i]
            d = {"role": p["role"], "color": p["color"], "priority": p["priority"]}
        decisions.append(d)

    overlay = dict(existing_map.get("overlay", {})) if existing_map else {}
    intensity = intensity if intensity is not None else (existing_map or {}).get("intensity", DEFAULT_INTENSITY)
    return img, fills, labels, decisions, overlay, mode, intensity


def to_map_obj(png_path, fills, decisions, overlay, intensity, max_segments):
    decisions_by_key = {}
    for i, (rgb, cnt, frac) in enumerate(fills):
        d = decisions[i]
        entry = {"role": d["role"], "priority": d.get("priority", 1.0)}
        if d["role"] == "merge":
            target_idx = d["merge_into"]
            entry["merge_into_key"] = rgb_key(fills[target_idx][0])
            entry["merge_into"] = target_idx
        elif d["role"] == "color":
            entry["color"] = list(d["color"])
        decisions_by_key[rgb_key(rgb)] = entry

    return {
        "source": png_path,
        "max_segments": max_segments,
        "intensity": intensity,
        "fills": [{"rgb": list(rgb), "count": cnt, "frac": round(frac, 5)} for rgb, cnt, frac in fills],
        "decisions": decisions_by_key,
        "overlay": overlay,
    }
