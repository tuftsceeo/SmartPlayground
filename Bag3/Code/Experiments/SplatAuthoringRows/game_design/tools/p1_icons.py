#!/usr/bin/env python3
"""Write the P1 16x16 icons (icon_needs.md) into Stations/IconDisplay/icons/.

circle, triangle, square: the built-in games' color table (blue circle, yellow
triangle, purple square; white star already exists as `star`, in orange).
check: the shared "right" cue (green). cross: a neutral mark (white), not
"wrong" in red.

Each shape differs in outline, not only color (icon_needs.md, "Access").
Duty values are linear PWM, in the range the existing icons use.

    python3 p1_icons.py            # write the five files
    python3 p1_icons.py --preview  # print them as text, write nothing
"""

import os
import sys

W = H = 16
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "Stations",
                                    "IconDisplay", "icons"))

BLUE = (0, 60, 220)
YELLOW = (230, 200, 0)
PURPLE = (120, 0, 230)
GREEN = (0, 200, 40)
WHITE = (185, 200, 200)

HEADER = "# Hand-edited 16x16 icon -- linear PWM duty bytes, row-major from top-left.\n"


# Row widths for rows 2..13, centred: a 12x12 disc with no single-pixel tips.
_DISC = (4, 8, 10, 12, 12, 12, 12, 12, 12, 10, 8, 4)


def circle(r, c):
    if not 2 <= r <= 13:
        return False
    half = _DISC[r - 2] / 2.0
    return abs(c - 7.5) < half


def triangle(r, c):
    # Apex at row 2, base on row 13 spanning cols 1-14.
    if not 2 <= r <= 13:
        return False
    half = 0.5 + (r - 2) * 6.5 / 11
    return abs(c - 7.5) <= half


def square(r, c):
    return 2 <= r <= 13 and 2 <= c <= 13


def _near(r, c, r0, c0, r1, c1, w):
    """True if (r, c) is within w of segment (r0, c0)-(r1, c1)."""
    dr, dc = r1 - r0, c1 - c0
    t = ((r - r0) * dr + (c - c0) * dc) / float(dr * dr + dc * dc)
    t = max(0.0, min(1.0, t))
    pr, pc = r0 + t * dr, c0 + t * dc
    return (r - pr) ** 2 + (c - pc) ** 2 <= w * w


def check(r, c):
    return _near(r, c, 8, 2, 12, 6, 1.1) or _near(r, c, 12, 6, 3, 13, 1.1)


def cross(r, c):
    return _near(r, c, 3, 3, 12, 12, 1.1) or _near(r, c, 3, 12, 12, 3, 1.1)


ICONS = {
    "circle": (circle, BLUE),
    "triangle": (triangle, YELLOW),
    "square": (square, PURPLE),
    "check": (check, GREEN),
    "cross": (cross, WHITE),
}


def render(fn, color):
    rows = []
    for r in range(H):
        rows.append([color if fn(r, c) else (0, 0, 0) for c in range(W)])
    return rows


def to_file(rows):
    out = [HEADER, "SIZE = (16, 16)\n", "ICON = (\n"]
    for row in rows:
        out.append("    " + ", ".join("(%d, %d, %d)" % px for px in row) + ",\n")
    out.append(")\n")
    return "".join(out)


def main():
    preview = "--preview" in sys.argv
    for name, (fn, color) in ICONS.items():
        rows = render(fn, color)
        if preview:
            print(name)
            for row in rows:
                print("".join("#" if px != (0, 0, 0) else "." for px in row))
            print()
            continue
        with open(os.path.join(OUT, name + ".py"), "w") as f:
            f.write(to_file(rows))
        print("wrote", name)


if __name__ == "__main__":
    main()
