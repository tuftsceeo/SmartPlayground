import math

def srgb_to_linear(c):
    c = c / 255.0
    if c <= 0.04045: return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4

def rgb_to_oklab(r, g, b):
    r_lin = srgb_to_linear(r); g_lin = srgb_to_linear(g); b_lin = srgb_to_linear(b)
    l = 0.4122214708*r_lin + 0.5363325363*g_lin + 0.0514459929*b_lin
    m = 0.2119034982*r_lin + 0.6806995451*g_lin + 0.1073969566*b_lin
    s = 0.0883024619*r_lin + 0.2817188376*g_lin + 0.6299787005*b_lin
    l_ = l**(1/3) if l > 0 else 0
    m_ = m**(1/3) if m > 0 else 0
    s_ = s**(1/3) if s > 0 else 0
    L = 0.2104542553*l_ + 0.7936177850*m_ - 0.0040720468*s_
    a = 1.9779984951*l_ - 2.4285922050*m_ + 0.4505937099*s_
    b_ok = 0.0259040371*l_ + 0.7827717662*m_ - 0.8086757660*s_
    return L, a, b_ok

def dE(c1, c2):
    L1, a1, b1 = rgb_to_oklab(*c1)
    L2, a2, b2 = rgb_to_oklab(*c2)
    return math.sqrt((L1-L2)**2 + (a1-a2)**2 + (b1-b2)**2)

# Proposed: keep names, retune values for separation, add tertiaries.
# All max channel ~200 so brightness scaling lands sensibly.
proposed = {
    # ── Existing names, retuned ──
    'RED':       (200, 0,   0),     # unchanged - anchor
    'ORANGE':    (220, 60,  0),     # pulled redder (was 220,80,0)
    'AMBER':     (200, 130, 0),     # pulled yellower (was 200,100,0)
    'YELLOW':    (200, 200, 0),     # unchanged
    'GREEN':     (0,   200, 0),     # unchanged
    'TEAL':      (0,   180, 110),   # pulled greener (was 0,150,150 - was just dim cyan)
    'CYAN':      (0,   170, 210),   # pulled slightly bluer (was 0,200,200)
    'BLUE':      (0,   0,   200),   # unchanged
    'PURPLE':    (110, 0,   200),   # actually purple now (was 180,0,180 - was magenta)
    'MAGENTA':   (200, 0,   180),   # cleaner magenta (was 200,0,120)
    'PINK':      (220, 120, 160),   # more pastel (was 200,80,120 - was rose-ish)
    'WHITE':     (140, 140, 140),   # unchanged

    # ── New tertiary colors ──
    'LIME':      (130, 200, 0),     # yellow-green, between YELLOW and GREEN
    'SPRING':    (0,   200, 100),   # green-cyan, between GREEN and TEAL
    'AZURE':     (0,   100, 220),   # cyan-blue, between CYAN and BLUE
    'INDIGO':    (60,  0,   180),   # blue-purple, between BLUE and PURPLE
    'ROSE':      (220, 30,  90),    # red-pink, between RED and MAGENTA
}

items = list(proposed.items())
pairs = []
for i in range(len(items)):
    for j in range(i+1, len(items)):
        n1, c1 = items[i]
        n2, c2 = items[j]
        pairs.append((dE(c1, c2), n1, n2))
pairs.sort()

print(f"PROPOSED PALETTE — {len(proposed)} colors")
print(f"Total pairs: {len(pairs)}")
print()
print("15 smallest distances (worst-case separation):")
print("-" * 55)
for d, n1, n2 in pairs[:15]:
    flag = ""
    if d < 0.15: flag = "  COLLAPSE"
    elif d < 0.20: flag = "  close"
    elif d < 0.25: flag = "  ok"
    else: flag = "  good"
    print(f"  {n1:8s} vs {n2:8s}  ΔE = {d:.3f}{flag}")

print()
print("Distance distribution:")
buckets = {'<0.15': 0, '0.15-0.20': 0, '0.20-0.25': 0, '0.25-0.35': 0, '>0.35': 0}
for d, _, _ in pairs:
    if d < 0.15: buckets['<0.15'] += 1
    elif d < 0.20: buckets['0.15-0.20'] += 1
    elif d < 0.25: buckets['0.20-0.25'] += 1
    elif d < 0.35: buckets['0.25-0.35'] += 1
    else: buckets['>0.35'] += 1
for k, v in buckets.items():
    print(f"  ΔE {k}: {v} pairs")
"""
Total pairs: 136

15 smallest distances (worst-case separation):
-------------------------------------------------------
  GREEN    vs SPRING    ΔE = 0.062  COLLAPSE
  TEAL     vs SPRING    ΔE = 0.064  COLLAPSE
  GREEN    vs LIME      ΔE = 0.072  COLLAPSE
  RED      vs ORANGE    ΔE = 0.074  COLLAPSE
  LIME     vs SPRING    ΔE = 0.079  COLLAPSE
  BLUE     vs INDIGO    ΔE = 0.079  COLLAPSE
  YELLOW   vs LIME      ΔE = 0.089  COLLAPSE
  RED      vs ROSE      ΔE = 0.090  COLLAPSE
  ORANGE   vs ROSE      ΔE = 0.093  COLLAPSE
  PURPLE   vs INDIGO    ΔE = 0.106  COLLAPSE
  GREEN    vs TEAL      ΔE = 0.108  COLLAPSE
  TEAL     vs LIME      ΔE = 0.123  COLLAPSE
  CYAN     vs WHITE     ΔE = 0.135  COLLAPSE
  ORANGE   vs AMBER     ΔE = 0.141  COLLAPSE
  PINK     vs WHITE     ΔE = 0.143  COLLAPSE

Distance distribution:
  ΔE <0.15: 16 pairs
  ΔE 0.15-0.20: 18 pairs
  ΔE 0.20-0.25: 17 pairs
  ΔE 0.25-0.35: 27 pairs
  ΔE >0.35: 58 pairs
Adding tertiary colors actuall
"""