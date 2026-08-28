"""
emit.py -- write the final ICON tuple (device contract unchanged: a 16-line,
16-tuples-per-line `ICON = (...)` file, same shape icon_test.py/main.py
already read) and the --check lint pass.
"""

W = 16
H = 16
CH_FLOOR = 20          # nonzero authored channel below this truncates to
                        # <1 on-device at INTENSITY=0.30 -- see main.py scale()
MAX_LIT_COLORS = 8
MIN_FEATURE_CELLS = 4
SEPARATION_MIN = 25    # min max-channel delta between two adjacent distinct colors


def enforce_floor(pixels, floor=CH_FLOOR):
    """Any nonzero channel below `floor` is raised to `floor` -- keeps icon
    files robust to future INTENSITY changes instead of baking in today's
    value. Zero stays zero (that's an intentional off, not a dim color)."""
    out = []
    for r, g, b in pixels:
        out.append(tuple(c if c == 0 else max(floor, c) for c in (r, g, b)))
    return out


def write_icon(pixels, out_path, name_comment=None):
    with open(out_path, "w") as f:
        if name_comment:
            f.write("# %s\n" % name_comment)
        f.write("ICON = (\n")
        for row in range(H):
            f.write("    " + ", ".join(str(p) for p in pixels[row * W:(row + 1) * W]) + ",\n")
        f.write(")\n")


def lint(pixels, fills, decisions, cells_won, intensity):
    """
    Returns a list of human-readable warning/error strings. Empty list =
    clean. Checks (see design doc §Emit & lint):
      - unmapped fill above MIN_FRAC threshold (caller passes only mapped
        fills, so this is really "every fill decided")
      - a colored segment winning zero cells
      - more than MAX_LIT_COLORS distinct lit colors
      - a lit segment under MIN_FEATURE_CELLS
      - any lit channel that truncates to 0 on-device at `intensity`
      - two adjacent regions whose colors are within SEPARATION_MIN
    """
    problems = []

    lit_colors = set(p for p in pixels if p != (0, 0, 0))
    if len(lit_colors) > MAX_LIT_COLORS:
        problems.append("%d distinct lit colors on the grid (max recommended %d)"
                         % (len(lit_colors), MAX_LIT_COLORS))

    for i, d in enumerate(decisions):
        if d["role"] != "color":
            continue
        won = cells_won[i] if i < len(cells_won) else 0
        if won == 0:
            problems.append("segment %d (%s) is colored but won zero cells" % (i, fills[i][0]))
        elif won < MIN_FEATURE_CELLS:
            problems.append("segment %d (%s) only won %d cell(s) (min feature size %d)"
                             % (i, fills[i][0], won, MIN_FEATURE_CELLS))

    for r, g, b in pixels:
        for c in (r, g, b):
            if 0 < c and int(c * intensity) == 0:
                problems.append("channel value %d truncates to 0 on-device at intensity=%.2f" % (c, intensity))
                break

    for row in range(H):
        for col in range(W):
            idx = row * W + col
            c1 = pixels[idx]
            for dr, dc in ((0, 1), (1, 0)):
                r2, c2 = row + dr, col + dc
                if r2 >= H or c2 >= W:
                    continue
                c2v = pixels[r2 * W + c2]
                if c1 == (0, 0, 0) or c2v == (0, 0, 0) or c1 == c2v:
                    continue
                delta = max(abs(a - b) for a, b in zip(c1, c2v))
                if delta < SEPARATION_MIN:
                    problems.append(
                        "adjacent cells (%d,%d) %s and (%d,%d) %s differ by only %d"
                        % (row, col, c1, r2, c2, c2v, delta))

    # de-dupe truncation warnings (they repeat per-channel-value)
    seen = set()
    deduped = []
    for p in problems:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped
