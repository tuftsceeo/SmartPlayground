#!/usr/bin/env python3
"""
hand_author_icons.py -- generate 16x16 device icons that have no source
photo, as a companion to image_to_icon.py (which needs a PNG/JPEG to
segment). Icons here are built directly from geometric primitives (circle,
ellipse, rect, triangle) against a small vetted color list, instead of a
photo histogram.

Reuses the same device-format writer (iconlib.emit.write_icon) and preview
renderer (iconlib.preview.render_preview) as image_to_icon.py, so output is
byte-identical in shape to the photo-derived pipeline's output, and writes
maps/<name>.json alongside icons/<name>.py and previews/<name>.png exactly
like image_to_icon.py does -- "source": "hand-authored" instead of a PNG
path is the only difference in the map shape.

Run: python3 hand_author_icons.py
Add a new icon: write a draw_<name>(g) function using the primitives below,
then add ("<name>", "<category>", draw_<name>) to RECIPES.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "iconlib"))

from emit import enforce_floor, write_icon, W, H, MAX_LIT_COLORS, SEPARATION_MIN  # noqa: E402
from preview import render_preview  # noqa: E402

ICONS_DIR = os.path.join(HERE, "icons")
MAPS_DIR = os.path.join(HERE, "maps")
PREVIEWS_DIR = os.path.join(HERE, "previews")

INTENSITY = 0.30

# ---------------------------------------------------------------- drawing --

def new_grid():
    return [[(0, 0, 0)] * W for _ in range(H)]


def flatten(grid):
    return [grid[r][c] for r in range(H) for c in range(W)]


def px(grid, r, c, color):
    if 0 <= r < H and 0 <= c < W:
        grid[r][c] = color


def clear(grid, r, c):
    px(grid, r, c, (0, 0, 0))


def rect(grid, r0, c0, r1, c1, color):
    for r in range(max(0, r0), min(H, r1 + 1)):
        for c in range(max(0, c0), min(W, c1 + 1)):
            grid[r][c] = color


def circle(grid, cx, cy, radius, color):
    for r in range(H):
        for c in range(W):
            if (c + 0.5 - cx) ** 2 + (r + 0.5 - cy) ** 2 <= radius * radius:
                grid[r][c] = color


def ellipse(grid, cx, cy, rx, ry, color):
    for r in range(H):
        for c in range(W):
            dx = (c + 0.5 - cx) / rx
            dy = (r + 0.5 - cy) / ry
            if dx * dx + dy * dy <= 1.0:
                grid[r][c] = color


def triangle(grid, p1, p2, p3, color):
    """p1/p2/p3 are (row, col) points, matching every other helper here."""
    (r1, c1), (r2, c2), (r3, c3) = p1, p2, p3

    def sign(pr, pc, ar, ac, br, bc):
        return (pr - br) * (ac - bc) - (ar - br) * (pc - bc)

    for r in range(H):
        for c in range(W):
            pr, pc = r + 0.5, c + 0.5
            d1 = sign(pr, pc, r1, c1, r2, c2)
            d2 = sign(pr, pc, r2, c2, r3, c3)
            d3 = sign(pr, pc, r3, c3, r1, c1)
            neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
            pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
            if not (neg and pos):
                grid[r][c] = color


# ------------------------------------------------------------ vetted colors --
# Chosen so any two used together in one icon differ by >=SEPARATION_MIN on
# at least one channel, per iconlib.emit's adjacency lint.
RED = (230, 20, 20)
ORANGE = (255, 140, 0)
YELLOW = (255, 210, 0)
GREEN = (0, 200, 60)
LIME = (120, 220, 0)
TEAL = (0, 180, 140)
SKY = (60, 160, 255)
PURPLE = (150, 30, 220)
PINK = (255, 90, 160)
MAGENTA = (200, 0, 120)
BROWN = (120, 70, 20)
DKBROWN = (70, 40, 10)
CREAM = (255, 220, 160)

# ------------------------------------------------------------- local lint --
# Same checks as iconlib.emit.lint(), adapted for hand-authored pixels that
# have no fills/decisions/cells_won (there's no source photo segmentation).

def check(name, grid):
    pixels = flatten(grid)
    problems = []
    lit = set(p for p in pixels if p != (0, 0, 0))
    if len(lit) > MAX_LIT_COLORS:
        problems.append("%d distinct lit colors (max %d)" % (len(lit), MAX_LIT_COLORS))

    seen = [[False] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            if seen[r][c] or grid[r][c] == (0, 0, 0):
                continue
            color = grid[r][c]
            stack = [(r, c)]
            seen[r][c] = True
            size = 0
            while stack:
                rr, cc = stack.pop()
                size += 1
                for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    nr, nc = rr + dr, cc + dc
                    if 0 <= nr < H and 0 <= nc < W and not seen[nr][nc] and grid[nr][nc] == color:
                        seen[nr][nc] = True
                        stack.append((nr, nc))
            if size < 4:
                problems.append("component of color %s has only %d cell(s) at (%d,%d)" % (color, size, r, c))

    for r in range(H):
        for c in range(W):
            c1 = grid[r][c]
            for dr, dc in ((0, 1), (1, 0)):
                r2, c2 = r + dr, c + dc
                if r2 >= H or c2 >= W:
                    continue
                c2v = grid[r2][c2]
                if c1 == (0, 0, 0) or c2v == (0, 0, 0) or c1 == c2v:
                    continue
                delta = max(abs(a - b) for a, b in zip(c1, c2v))
                if delta < SEPARATION_MIN:
                    problems.append("adjacent (%d,%d)%s / (%d,%d)%s differ by only %d" % (r, c, c1, r2, c2, c2v, delta))

    for r, g, b in pixels:
        for v in (r, g, b):
            if 0 < v and int(v * INTENSITY) == 0:
                problems.append("channel %d truncates to 0 at intensity=%.2f" % (v, INTENSITY))
                break

    if problems:
        print("== %s: %d problem(s) ==" % (name, len(problems)))
        for p in problems:
            print("  ! " + p)
    return problems


# --------------------------------------------------------------- icon defs --

def draw_dog(g):
    ellipse(g, 8, 9.5, 6, 5.5, BROWN)      # head
    triangle(g, (2, 3), (5, 6), (2, 7), DKBROWN)   # left ear
    triangle(g, (14, 3), (11, 6), (14, 7), DKBROWN)  # right ear
    clear(g, 6, 6); clear(g, 6, 10)         # eyes
    ellipse(g, 8, 12, 2.2, 1.6, DKBROWN)    # snout
    clear(g, 8, 12)                          # nose


def draw_cat(g):
    triangle(g, (1, 2), (5, 6), (1, 8), ORANGE)   # left ear
    triangle(g, (14, 2), (10, 6), (14, 8), ORANGE)  # right ear
    ellipse(g, 8, 9, 6, 6, ORANGE)
    clear(g, 6, 6); clear(g, 6, 11)
    rect(g, 9, 8, 10, 9, DKBROWN)  # nose


def draw_fish(g):
    ellipse(g, 6, 8, 5, 4.5, SKY)
    triangle(g, (13, 8), (15, 4), (15, 12), TEAL)  # tail
    clear(g, 4, 4)  # eye
    rect(g, 8, 7, 10, 8, TEAL)  # top fin


def draw_bird(g):
    ellipse(g, 9, 8, 5, 4.5, SKY)
    circle(g, 4, 6, 2.4, SKY)
    triangle(g, (2, 6), (2, 9), (0, 7.5), ORANGE)  # beak
    clear(g, 3, 5)
    triangle(g, (13, 9), (15, 6), (15, 12), TEAL)  # wing/tail


def draw_butterfly(g):
    ellipse(g, 4, 5, 3.4, 3.6, PURPLE)
    ellipse(g, 12, 5, 3.4, 3.6, PURPLE)
    ellipse(g, 4, 11, 2.6, 2.8, PINK)
    ellipse(g, 12, 11, 2.6, 2.8, PINK)
    rect(g, 3, 7, 12, 8, DKBROWN)  # body


def draw_surprised(g):
    circle(g, 8, 8, 7, YELLOW)
    circle(g, 5, 6, 1.4, DKBROWN); circle(g, 5, 10, 1.4, DKBROWN)
    circle(g, 11, 8, 2.0, DKBROWN)  # open mouth "O"
    clear(g, 11, 8)


def draw_sleepy(g):
    circle(g, 8, 8, 7, TEAL)
    rect(g, 5, 4, 6, 7, DKBROWN)   # closed eye lines
    rect(g, 5, 9, 6, 12, DKBROWN)
    rect(g, 11, 6, 11, 10, DKBROWN)  # small closed mouth


def draw_love(g):
    # face with heart-shaped eyes -- distinct from the plain "heart" concept icon
    circle(g, 8, 9, 6.5, YELLOW)
    circle(g, 4, 6.5, 1.6, PINK); circle(g, 6.5, 6.5, 1.6, PINK)
    triangle(g, (5, 8), (8, 8), (6.5, 11), PINK)
    circle(g, 4, 11, 1.6, PINK); circle(g, 6.5, 11, 1.6, PINK)
    triangle(g, (5, 12.5), (8, 12.5), (6.5, 15.5), PINK)
    rect(g, 12, 6, 12, 11, DKBROWN)  # smile


def draw_silly(g):
    circle(g, 8, 8, 7, LIME)
    rect(g, 4, 4, 5, 6, DKBROWN)  # winking eye
    circle(g, 5, 10, 1.3, DKBROWN)
    triangle(g, (10, 5), (10, 11), (13, 8), DKBROWN)  # tongue-out grin


def draw_flower(g):
    circle(g, 8, 5, 2.6, PINK)
    circle(g, 4.5, 8, 2.6, PINK)
    circle(g, 11.5, 8, 2.6, PINK)
    circle(g, 8, 10.5, 2.6, PINK)
    circle(g, 8, 8, 2.0, YELLOW)
    rect(g, 11, 7, 15, 8, GREEN)  # stem


def draw_sunflower(g):
    import math
    for ang in range(0, 360, 30):
        cx = 8 + 5.5 * math.cos(math.radians(ang))
        cy = 6 + 5.5 * math.sin(math.radians(ang))
        circle(g, cx, cy, 1.8, YELLOW)
    circle(g, 8, 6, 3.2, DKBROWN)
    rect(g, 10, 7, 15, 8, GREEN)


def draw_cactus(g):
    rect(g, 5, 7, 15, 9, GREEN)
    rect(g, 7, 4, 9, 6, GREEN)
    rect(g, 5, 4, 6, 4, GREEN)
    rect(g, 6, 10, 8, 12, GREEN)
    rect(g, 4, 10, 5, 10, GREEN)
    rect(g, 13, 3, 15, 12, BROWN)  # pot


def draw_mushroom(g):
    ellipse(g, 8, 6, 6, 4.5, RED)
    rect(g, 4, 3, 5, 4, CREAM); rect(g, 4, 8, 5, 9, CREAM)
    rect(g, 6, 5, 7, 6, CREAM); rect(g, 6, 10, 7, 11, CREAM)
    rect(g, 9, 6, 15, 9, CREAM)


def draw_pizza(g):
    triangle(g, (1, 8), (15, 2), (15, 14), YELLOW)
    circle(g, 5, 8, 1.1, RED)
    circle(g, 8, 6, 1.0, RED)
    circle(g, 8, 10, 1.0, RED)
    circle(g, 11, 8, 1.1, RED)
    rect(g, 0, 1, 1, 15, BROWN)  # crust edge


def draw_cookie(g):
    circle(g, 8, 8, 7, BROWN)
    circle(g, 5, 5, 1.1, DKBROWN)
    circle(g, 5, 11, 1.1, DKBROWN)
    circle(g, 9, 8, 1.1, DKBROWN)
    circle(g, 12, 5, 1.1, DKBROWN)
    circle(g, 11, 12, 1.1, DKBROWN)


def draw_icecream(g):
    triangle(g, (7, 5), (7, 11), (15, 8), BROWN)  # cone
    circle(g, 5, 8, 5, PINK)
    circle(g, 2, 8, 3.6, CREAM)
    clear(g, 7, 10); clear(g, 10, 9)  # stray anti-aliased cone slivers the scoop didn't cover


def draw_banana(g):
    rect(g, 1, 2, 2, 5, DKBROWN)  # stem
    for r in range(3, 14):
        c0 = 3 + int(9 * ((r - 3) / 11.0) ** 0.6)
        rect(g, r, c0, r, c0 + 3, YELLOW)


def draw_sun(g):
    circle(g, 8, 8, 4.5, YELLOW)
    rect(g, 0, 7, 1, 8, ORANGE); rect(g, 14, 7, 15, 8, ORANGE)     # N/S
    rect(g, 7, 0, 8, 1, ORANGE); rect(g, 7, 14, 8, 15, ORANGE)     # W/E
    rect(g, 1, 2, 3, 4, ORANGE); rect(g, 1, 11, 3, 13, ORANGE)     # NW/NE
    rect(g, 12, 2, 14, 4, ORANGE); rect(g, 12, 11, 14, 13, ORANGE)  # SW/SE


def draw_moon(g):
    circle(g, 7, 8, 6.5, SKY)
    circle(g, 10, 5.5, 6.8, (0, 0, 0))  # bite out a crescent


def draw_star(g):
    import math
    pts_outer = [(8 + 7 * math.sin(math.radians(a)), 8 - 7 * math.cos(math.radians(a))) for a in range(0, 360, 72)]
    pts_inner = [(8 + 3 * math.sin(math.radians(a)), 8 - 3 * math.cos(math.radians(a))) for a in range(36, 360, 72)]
    star_pts = []
    for i in range(5):
        star_pts.append(pts_outer[i])
        star_pts.append(pts_inner[i])
    for i in range(len(star_pts)):
        p1 = star_pts[i]
        p2 = star_pts[(i + 1) % len(star_pts)]
        triangle(g, (8, 8), p1, p2, YELLOW)


def draw_heart(g):
    circle(g, 5, 5.5, 3.4, RED)
    circle(g, 11, 5.5, 3.4, RED)
    triangle(g, (2, 7), (14, 7), (8, 15.5), RED)


def draw_rainbow(g):
    # concentric half-domes, largest first, each next band drawn over it --
    # thickness is whatever's left uncovered, so bands stay solid (no 1px rings).
    bands = (RED, ORANGE, YELLOW, GREEN, SKY, PURPLE)
    radius = 15.0
    step = 15.0 / len(bands)
    for color in bands:
        ellipse(g, 8, 15, radius, radius, color)
        radius -= step
    radius = max(radius, 0.5)
    ellipse(g, 8, 15, radius, radius, (0, 0, 0))  # hollow center
    for r in range(11, 16):
        rect(g, r, 0, r, 15, (0, 0, 0))  # keep only the upper arch


def draw_house(g):
    triangle(g, (1, 8), (7, 2), (7, 14), RED)   # roof
    rect(g, 7, 2, 15, 14, CREAM)
    rect(g, 6, 0, 8, 1, (0, 0, 0))  # stray slivers off the roof's shallow left edge
    rect(g, 10, 6, 15, 10, BROWN)  # door
    rect(g, 9, 3, 11, 5, SKY)      # window
    rect(g, 9, 11, 11, 13, SKY)


def draw_umbrella(g):
    ellipse(g, 8, 5, 7.5, 4.5, TEAL)
    rect(g, 5, 7, 5, 8, (0, 0, 0))
    rect(g, 5, 8, 14, 9, BROWN)


def draw_ball(g):
    circle(g, 8, 8, 7, ORANGE)
    rect(g, 8, 1, 8, 15, DKBROWN)
    rect(g, 1, 8, 15, 8, DKBROWN)


def draw_kite(g):
    triangle(g, (1, 8), (8, 2), (8, 14), MAGENTA)
    triangle(g, (8, 2), (8, 14), (14, 8), SKY)
    rect(g, 14, 8, 15, 8, DKBROWN)
    px(g, 15, 7, DKBROWN); px(g, 15, 9, DKBROWN)


def draw_music(g):
    circle(g, 6, 12, 2.6, PURPLE)      # note head
    rect(g, 2, 8, 12, 9, PURPLE)       # stem, touching the head's right edge
    triangle(g, (2, 9), (2, 13), (5, 9), PURPLE)  # flag


RECIPES = [
    ("dog", "animals", draw_dog),
    ("cat", "animals", draw_cat),
    ("fish", "animals", draw_fish),
    ("bird", "animals", draw_bird),
    ("butterfly", "animals", draw_butterfly),
    ("surprised", "emotions", draw_surprised),
    ("sleepy", "emotions", draw_sleepy),
    ("love", "emotions", draw_love),
    ("silly", "emotions", draw_silly),
    ("flower", "plants", draw_flower),
    ("sunflower", "plants", draw_sunflower),
    ("cactus", "plants", draw_cactus),
    ("mushroom", "plants", draw_mushroom),
    ("pizza", "foods", draw_pizza),
    ("cookie", "foods", draw_cookie),
    ("icecream", "foods", draw_icecream),
    ("banana", "foods", draw_banana),
    ("sun", "ideas", draw_sun),
    ("moon", "ideas", draw_moon),
    ("star", "ideas", draw_star),
    ("heart", "ideas", draw_heart),
    ("rainbow", "ideas", draw_rainbow),
    ("house", "places", draw_house),
    ("umbrella", "places", draw_umbrella),
    ("ball", "activities", draw_ball),
    ("kite", "activities", draw_kite),
    ("music", "activities", draw_music),
]


def main():
    os.makedirs(ICONS_DIR, exist_ok=True)
    os.makedirs(MAPS_DIR, exist_ok=True)
    os.makedirs(PREVIEWS_DIR, exist_ok=True)

    icons = {}
    categories = {}
    for name, category, fn in RECIPES:
        grid = new_grid()
        fn(grid)
        icons[name] = enforce_floor(flatten(grid))
        categories[name] = category

    problem_count = 0
    for name, pixels in icons.items():
        grid = [[pixels[r * W + c] for c in range(W)] for r in range(H)]
        if check(name, grid):
            problem_count += 1
    print("\n%d icons defined, %d with problems" % (len(icons), problem_count))
    if problem_count:
        print("fix the problems above before committing -- exiting without writing files")
        return 1

    for name, pixels in icons.items():
        write_icon(
            pixels,
            os.path.join(ICONS_DIR, name + ".py"),
            name_comment="Hand-authored by hand_author_icons.py -- edit maps/%s.json, not this file." % name,
        )
        render_preview(pixels, INTENSITY, os.path.join(PREVIEWS_DIR, name + ".png"))

        lit = sorted(set(p for p in pixels if p != (0, 0, 0)))
        fills = [{"rgb": list(c), "count": pixels.count(c), "frac": round(pixels.count(c) / float(W * H), 5)} for c in lit]
        decisions = {"%d,%d,%d" % c: {"role": "color", "priority": 1.0, "color": list(c)} for c in lit}
        map_obj = {
            "source": "hand-authored",
            "max_segments": len(lit),
            "intensity": INTENSITY,
            "fills": fills,
            "decisions": decisions,
            "overlay": {},
        }
        with open(os.path.join(MAPS_DIR, name + ".json"), "w") as f:
            json.dump(map_obj, f, indent=2)
            f.write("\n")

    print("wrote %d icons to %s" % (len(icons), ICONS_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
