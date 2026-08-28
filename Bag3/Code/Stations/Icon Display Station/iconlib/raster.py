"""
raster.py -- turn per-segment full-res coverage into a single 16x16 grid of
winning colors. Priority is the primary thin-feature-survival mechanism
(continuous, local, works on real coverage data); dilation is a last-resort
per-segment `grow` flag applied to already-thresholded data, i.e. after the
coverage information priority needs is already gone.
"""

from segment import segment_coverage, W, H

CELL_ON = 0.35
DEFAULT_PRIORITY = 1.0
MIN_FEATURE_CELLS = 4


def score_grid(fills, labels, decisions):
    """
    decisions: list parallel to fills, each a dict with at least
        "role" ("color"|"off"|"merge"), "color", "priority", and for
        "merge" a "merge_into" segment index.
    Returns (coverage_by_seg, score_by_seg) -- coverage_by_seg[i] is the
    16x16 coverage grid for fills[i]; score_by_seg[i] is coverage*priority
    for segments with role != "off" (merged segments score under their
    target's priority but keep their own coverage grid).
    """
    coverage_by_seg = [segment_coverage(labels, i, W, H) for i in range(len(fills))]
    score_by_seg = [None] * len(fills)
    for i, d in enumerate(decisions):
        if d["role"] == "off":
            score_by_seg[i] = None
            continue
        target = i
        if d["role"] == "merge":
            target = d["merge_into"]
        priority = decisions[target].get("priority", DEFAULT_PRIORITY)
        score_by_seg[i] = [[coverage_by_seg[i][y][x] * priority for x in range(W)] for y in range(H)]
    return coverage_by_seg, score_by_seg


def _effective_color(decisions, seg_id):
    d = decisions[seg_id]
    if d["role"] == "merge":
        return decisions[d["merge_into"]]["color"]
    return d["color"]


def rasterize(fills, labels, decisions):
    """
    Winner-take-all per cell: among segments with role != "off" whose
    coverage in this cell is >= CELL_ON, the winner is argmax(score).
    A cell with no such segment is off (background).

    Then a connect pass: for every ON cell (r,c) belonging to segment S,
    if a diagonal neighbor also belongs to S but NEITHER orthogonal cell
    between them belongs to S, promote whichever of the two orthogonal
    cells has the higher S-coverage to S as well -- this is exactly what
    breaks a single-cell-wide diagonal feature (e.g. a stem) into a
    disconnected dashed line.

    Returns a flat 256-entry list of (r,g,b) tuples, row-major top-left --
    the device contract (see emit.py).
    """
    coverage_by_seg, score_by_seg = score_grid(fills, labels, decisions)
    winner = [[None] * W for _ in range(H)]

    for y in range(H):
        for x in range(W):
            best_seg, best_score = None, 0.0
            for i in range(len(fills)):
                if score_by_seg[i] is None:
                    continue
                if coverage_by_seg[i][y][x] < CELL_ON:
                    continue
                s = score_by_seg[i][y][x]
                if s > best_score:
                    best_score, best_seg = s, i
            winner[y][x] = best_seg

    # connect pass
    for y in range(H):
        for x in range(W):
            seg = winner[y][x]
            if seg is None:
                continue
            for dy, dx in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                ny, nx = y + dy, x + dx
                if not (0 <= ny < H and 0 <= nx < W):
                    continue
                if winner[ny][nx] != seg:
                    continue
                oy, ox = y + dy, x  # vertical neighbor
                py, px = y, x + dx  # horizontal neighbor
                orth_has_seg = (
                    (0 <= oy < H and winner[oy][ox] == seg)
                    or (0 <= py < H and 0 <= px < W and winner[py][px] == seg)
                )
                if orth_has_seg:
                    continue
                cov_o = coverage_by_seg[seg][oy][ox] if 0 <= oy < H else -1
                cov_p = coverage_by_seg[seg][py][px] if (0 <= py < H and 0 <= px < W) else -1
                if cov_o >= cov_p and cov_o >= 0:
                    winner[oy][ox] = seg
                elif cov_p >= 0:
                    winner[py][px] = seg

    pixels = []
    for y in range(H):
        for x in range(W):
            seg = winner[y][x]
            if seg is None:
                pixels.append((0, 0, 0))
            else:
                pixels.append(_effective_color(decisions, seg) or (0, 0, 0))
    return pixels


def apply_overlay(pixels, overlay):
    """overlay: dict of {flat_index (int or str): [r,g,b]} -- per-cell hand
    edits, applied last, always win. Returns a new pixel list."""
    out = list(pixels)
    for k, rgb in (overlay or {}).items():
        idx = int(k)
        if 0 <= idx < len(out):
            out[idx] = tuple(rgb)
    return out


def cells_won(fills, labels, decisions):
    """Count of cells each segment actually wins after rasterize + connect
    pass -- surfaced in the editor so 'a colored segment won zero cells'
    is visible before --check flags it."""
    coverage_by_seg, score_by_seg = score_grid(fills, labels, decisions)
    counts = [0] * len(fills)
    winner = [[None] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            best_seg, best_score = None, 0.0
            for i in range(len(fills)):
                if score_by_seg[i] is None:
                    continue
                if coverage_by_seg[i][y][x] < CELL_ON:
                    continue
                s = score_by_seg[i][y][x]
                if s > best_score:
                    best_score, best_seg = s, i
            winner[y][x] = best_seg
            if best_seg is not None:
                counts[best_seg] += 1
    return counts
