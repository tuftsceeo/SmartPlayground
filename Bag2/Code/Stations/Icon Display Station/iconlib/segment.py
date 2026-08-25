"""
segment.py -- turn a source image into a label map of exact-fill segments,
plus the auto-color-proposal step that gives the editor its starting point.

Segmentation: these are flat vector icons -- a handful of exact fills plus
anti-aliased edge pixels that are literal RGB blends of two fills. So the
correct segmentation *is* the exact-color histogram, not an approximation
of one. `quantize()` is a fallback for a source image that turns out not
to look like that (a photo, a gradient-heavy icon).
"""

import math
from PIL import Image

from ledcolor import oklab_from_srgb, hue_deg, is_brown, purify
from palette import PALETTE_DIRECTIONS

W = 16
H = 16

ALPHA_THRESH = 128
MIN_FRAC = 0.004        # fills below this share of opaque pixels don't get their own segment
MAX_SEGMENTS = 12


def load_rgba(path):
    """Load and return the image as RGBA, untouched -- no compositing onto
    black. Compositing onto black turns anti-aliased transparent edges into
    fake dark fills that then get segmented as if they were real content."""
    return Image.open(path).convert("RGBA")


def histogram_fills(img, alpha_thresh=ALPHA_THRESH, min_frac=MIN_FRAC, max_segments=MAX_SEGMENTS):
    """
    Exact-color histogram of opaque pixels. Returns (fills, mode) where
    fills is a list of (rgb, count, frac) sorted by (-count, rgb), and mode
    is 'exact' or 'quantize' depending on which path was taken.
    """
    colors = img.getcolors(1 << 24)
    if colors is None:
        colors = []
    opaque = [(cnt, rgba[:3]) for cnt, rgba in colors if rgba[3] >= alpha_thresh]
    n_opaque = sum(c for c, _ in opaque)
    if n_opaque == 0:
        return [], "exact"

    merged = {}
    for cnt, rgb in opaque:
        merged[rgb] = merged.get(rgb, 0) + cnt
    fills = [(rgb, cnt, cnt / n_opaque) for rgb, cnt in merged.items()]
    fills.sort(key=lambda f: (-f[1], f[0]))

    big = [f for f in fills if f[2] >= min_frac]
    covered = sum(f[2] for f in big)

    if len(big) <= max_segments and covered >= 0.90:
        return big[:max_segments], "exact"
    return quantize_fills(img, max_segments), "quantize"


def quantize_fills(img, n_segments=MAX_SEGMENTS):
    """Fallback for images that aren't a small set of flat fills (photos,
    gradients). FASTOCTREE is the only PIL quantize method that accepts
    RGBA directly."""
    q = img.quantize(colors=n_segments, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    q_rgb = q.convert("RGB")
    alpha = img.split()[-1]
    counts = {}
    for x in range(img.width):
        for y in range(img.height):
            if alpha.getpixel((x, y)) < ALPHA_THRESH:
                continue
            rgb = q_rgb.getpixel((x, y))
            counts[rgb] = counts.get(rgb, 0) + 1
    total = sum(counts.values()) or 1
    fills = [(rgb, cnt, cnt / total) for rgb, cnt in counts.items()]
    fills.sort(key=lambda f: (-f[1], f[0]))
    return fills[:n_segments]


def _nearest_fill_idx(rgb, fill_rgbs):
    best_i, best_d = 0, None
    for i, frgb in enumerate(fill_rgbs):
        d = sum((a - b) ** 2 for a, b in zip(rgb, frgb))
        if best_d is None or d < best_d:
            best_d, best_i = d, i
    return best_i


def label_map(img, fills, alpha_thresh=ALPHA_THRESH):
    """
    Assign every pixel in the full-res image to a segment id (index into
    `fills`) or None for background/transparent. Anti-aliased edge pixels
    are literal linear blends of two fills, so nearest-fill-by-RGB is the
    mathematically correct assignment, not a heuristic.
    """
    fill_rgbs = [f[0] for f in fills]
    w, h = img.size
    px = img.load()
    labels = [[None] * w for _ in range(h)]
    cache = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < alpha_thresh:
                continue
            key = (r, g, b)
            idx = cache.get(key)
            if idx is None:
                idx = _nearest_fill_idx(key, fill_rgbs)
                cache[key] = idx
            labels[y][x] = idx
    return labels


def segment_coverage(labels, seg_id, out_w=W, out_h=H):
    """
    Per-16x16-cell coverage fraction [0,1] for one segment, computed as an
    exact box-mean downscale (source size assumed a multiple of 16 in each
    dimension -- true for the 512x512 source assets; falls back to nearest
    ratio otherwise).
    """
    h = len(labels)
    w = len(labels[0]) if h else 0
    if w == 0 or h == 0:
        return [[0.0] * out_w for _ in range(out_h)]
    mask = Image.new("L", (w, h), 0)
    mpx = mask.load()
    for y in range(h):
        row = labels[y]
        for x in range(w):
            if row[x] == seg_id:
                mpx[x, y] = 255
    small = mask.resize((out_w, out_h), Image.Resampling.BOX)
    spx = small.load()
    return [[spx[x, y] / 255.0 for x in range(out_w)] for y in range(out_h)]


def opaque_coverage(img, out_w=W, out_h=H, alpha_thresh=ALPHA_THRESH):
    """Per-cell fraction of full-res pixels that are opaque (any segment) --
    used to distinguish 'off because background' from 'off because a
    segment was explicitly turned off'."""
    alpha = img.split()[-1].point(lambda a: 255 if a >= alpha_thresh else 0)
    small = alpha.resize((out_w, out_h), Image.Resampling.BOX)
    spx = small.load()
    return [[spx[x, y] / 255.0 for x in range(out_w)] for y in range(out_h)]


def ring_contact(labels, seg_id, other=None):
    """
    Fraction of this segment's boundary ring (opaque pixels of the segment
    that have at least one 4-neighbor outside the segment) touching either
    background (other=None) or a specific other segment id. Used to detect
    'interior dark detail fully enclosed by one other segment' (seeds,
    shadows) vs. 'exterior feature mostly touching background' (stems).
    """
    h = len(labels)
    w = len(labels[0]) if h else 0
    ring_total = 0
    ring_match = 0
    for y in range(h):
        for x in range(w):
            if labels[y][x] != seg_id:
                continue
            neighbors = []
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    neighbors.append(labels[ny][nx])
                else:
                    neighbors.append(None)  # off-canvas counts as background
            is_boundary = any(n != seg_id for n in neighbors)
            if not is_boundary:
                continue
            ring_total += 1
            for n in neighbors:
                if n == seg_id:
                    continue
                if other is None:
                    if n is None:
                        ring_match += 1
                        break
                else:
                    if n == other:
                        ring_match += 1
                        break
    if ring_total == 0:
        return 0.0
    return ring_match / ring_total


def encloser_of(labels, seg_id, fills):
    """Return (encloser_seg_id, contact_frac) for whichever OTHER segment
    has the highest ring contact with `seg_id` -- 'what mostly surrounds
    this segment'. Returns (None, 0.0) if nothing does."""
    best_id, best_frac = None, 0.0
    for other in range(len(fills)):
        if other == seg_id:
            continue
        frac = ring_contact(labels, seg_id, other=other)
        if frac > best_frac:
            best_id, best_frac = other, frac
    return best_id, best_frac


# ══════════════════════════════════════════════
# AUTO-PROPOSE -- the editor's starting point, always human-overridable
# ══════════════════════════════════════════════
THIN_FRAC = 0.03            # segments smaller than this are treated as thin features
ENCLOSE_OFF = 0.85           # encloser ring-contact needed to propose OFF
BG_CONTACT_MAX = 0.15        # background ring-contact ceiling to propose OFF
BROWN_AMBER = (60, 40, 0)    # honest LED approximation of "brown" -- dim, desaturated amber
BROWN_A_MAX = 0.45
MAX_CH_BODY = 220            # amplitude ceiling for a normal (non-brown) segment
CH_FLOOR_HINT = 20           # matches emit.CH_FLOOR; enforced for real in emit.py


def _nearest_palette_direction(rgb):
    """Hue-only match: compare the purified (fully-saturated) source color's
    unit direction against each palette color's unit direction by cosine
    similarity, never by magnitude. Near-gray sources (tiny purified norm)
    fall back to WHITE's direction -- there's no hue to match."""
    pure = purify(rgb)
    norm = math.sqrt(sum(c * c for c in pure))
    if norm < 12:  # ~S_FLOOR-equivalent in raw units
        return "WHITE", PALETTE_DIRECTIONS["WHITE"]
    unit = tuple(c / norm for c in pure)
    best_name, best_sim = None, -2.0
    for name, direction in PALETTE_DIRECTIONS.items():
        dnorm = math.sqrt(sum(c * c for c in direction))
        if dnorm == 0:
            continue
        dunit = tuple(c / dnorm for c in direction)
        sim = sum(a * b for a, b in zip(unit, dunit))
        if sim > best_sim:
            best_sim, best_name = sim, name
    return best_name, PALETTE_DIRECTIONS[best_name]


def auto_propose(fills, labels, img):
    """
    Returns a list, parallel to `fills`, of proposal dicts:
        {"role": "color"|"off", "color": (r,g,b) or None,
         "priority": float, "palette_hint": name or None}
    This is only ever a starting point for the editor -- see design doc
    §Auto-propose colors.
    """
    n = len(fills)
    lightness = []
    for rgb, cnt, frac in fills:
        L, _, _ = oklab_from_srgb(rgb)
        lightness.append(L)

    proposals = [None] * n
    for i, (rgb, cnt, frac) in enumerate(fills):
        if is_brown(rgb):
            proposals[i] = {
                "role": "color",
                "color": BROWN_AMBER,
                "priority": 2.5 if frac < THIN_FRAC else 1.0,
                "palette_hint": "AMBER (brown approximation)",
            }
            continue

        encloser, enc_frac = encloser_of(labels, i, fills)
        bg_frac = ring_contact(labels, i, other=None)
        if (encloser is not None and enc_frac >= ENCLOSE_OFF
                and bg_frac <= BG_CONTACT_MAX
                and lightness[i] < lightness[encloser]):
            proposals[i] = {"role": "off", "color": None, "priority": 0.0, "palette_hint": None}
            continue

        # Snap to the PALETTE color's own direction, not the source's --
        # that's the actual "hue-only match" step. Re-deriving `unit` from
        # the source's own purified color here would just rescale the
        # source's hue unchanged, defeating the snap entirely (and was a
        # real bug in an earlier draft of this function: distinct source
        # hues that both nearest-matched the same palette name still came
        # out looking distinct, instead of collapsing onto one shared,
        # separated palette hue the way they're supposed to).
        name, unit = _nearest_palette_direction(rgb)
        amplitude = max(CH_FLOOR_HINT, min(MAX_CH_BODY, round(MAX_CH_BODY * lightness[i])))
        color = tuple(min(255, round(c * amplitude)) for c in unit)

        if frac < THIN_FRAC:
            priority = 2.5
        elif encloser is not None and lightness[i] > lightness[encloser] and frac < 0.10:
            priority = 0.6  # small + lighter than its encloser -> likely a highlight
        else:
            priority = 1.0

        proposals[i] = {"role": "color", "color": color, "priority": priority, "palette_hint": name}

    return proposals
