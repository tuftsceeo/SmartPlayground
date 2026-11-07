"""All icons in icons/, grouped by category, on one labelled sheet.
New icons not yet approved get an orange name. Run: python3 category_sheet.py"""
import glob, os, re
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(HERE, "..", "icons")
CATS = [
 ("Animals", "bat bee bird bunny butterfly camel cat chicken deer dog dolphin dove duck elephant elephant2 fish frog goat shrimp hedgehog lion monarch monkey mouse octopus owl parrot penguin pig polar_bear shark sheep snake spider swan teddy_bear torogoz trex turtle whale worm griffin"),
 ("Faces and feelings", "happy sad mad laugh love embarrassed silly sleepy surprised ready"),
 ("Food", "apple banana cherries grapes lemon orange strawberry watermelon pizza cookie icecream milk sandwich candy candy_corn agua_fresca beans churro concha elote hot_chocolate paleta pupusa taco pan_de_muerto"),
 ("Nature, weather, places", "sun moon cloud rain_cloud lightning rainbow snowflake star sparkles leaf tree flower sunflower cactus mushroom grass sprout marigold ocean forest desert pond igloo"),
 ("Vehicles", "car bus train airplane rocket ship helicopter bicycle tricycle fire_truck ambulance dump_truck"),
 ("Community and people", "house school hospital barn doctor police firefighter fireperson mail_carrier astronaut mail book shopping_cart"),
 ("Playground and toys", "ball balloon kite blocks sandcastle slide swings seesaw monkey_bars sandbox bubbles jump_rope splat"),
 ("Halloween and Día de los Muertos", "jack_o_lantern ghost skull witch_hat cauldron monster eyes calavera ofrenda_candle papel_picado"),
 ("Other", ""),
]
NEW = set("""bicycle fire_truck goat grass griffin helicopter mail_carrier monkey mouse sandwich shark slide sparkles
swings tricycle splat seesaw monkey_bars sandbox bubbles jump_rope
penguin frog lion octopus bee ocean desert ambulance book tooth sprout hand owl mail shopping_cart igloo forest pond polar_bear worm dump_truck""".split())
PRIM = [(0.7006, 0.2993, 400), (0.0743, 0.8338, 1150), (0.1241, 0.0578, 250)]
PRIM = [((x / y) * I, I, ((1 - x - y) / y) * I) for x, y, I in PRIM]
LY = sum(p[1] for p in PRIM)
BAL = (255 / 185, 171 / 255, 93 / 150)   # measured white -> datasheet neutral
def scr(d):
    if not any(d): return (26, 26, 28)
    X, Y, Z = [sum(d[j] * BAL[j] / 255 * PRIM[j][i] for j in range(3)) / LY for i in range(3)]
    lin = (3.2406*X - 1.5372*Y - 0.4986*Z, -0.9689*X + 1.8758*Y + 0.0415*Z, 0.0557*X - 0.204*Y + 1.057*Z)
    f = lambda v: max(0, min(1, v)); g = lambda v: 12.92*v if v <= 0.0031308 else 1.055*v**(1/2.4) - 0.055
    return tuple(round(g(f(v)) * 255) for v in lin)
def load(n):
    t = [tuple(map(int, m)) for m in re.findall(r"\((\d+),\s*(\d+),\s*(\d+)\)", open(os.path.join(ICONS, n + ".py")).read())]
    return t[-256:]
names = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(ICONS, "*.py")))
placed = set(" ".join(c for _, c in CATS).split())
CATS[-1] = ("Other", " ".join(n for n in names if n not in placed))
C, TW, TH, COLS = 6, 112, 128, 12
try: font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 13); hf = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 20)
except OSError: font = hf = ImageFont.load_default()
rows = []
for title, s in CATS:
    ns = [n for n in s.split() if n in names]
    if ns: rows.append((title, ns))
H = sum(34 + ((len(ns) + COLS - 1) // COLS) * TH for _, ns in rows) + 10
img = Image.new("RGB", (COLS * TW + 10, H), "white"); d = ImageDraw.Draw(img); y = 6
for title, ns in rows:
    d.text((8, y), f"{title} ({len(ns)})", fill="black", font=hf); y += 32
    for k, n in enumerate(ns):
        x0, y0 = 8 + (k % COLS) * TW, y + (k // COLS) * TH
        d.rectangle([x0, y0, x0 + 16 * C + 4, y0 + 16 * C + 4], fill=(10, 10, 11))
        for i, px in enumerate(load(n)):
            cx, cy = x0 + 3 + (i % 16) * C, y0 + 3 + (i // 16) * C
            d.rectangle([cx, cy, cx + C - 2, cy + C - 2], fill=scr(px))
        d.text((x0, y0 + 16 * C + 8), n, fill=(220, 90, 0) if n in NEW else "black", font=font)
    y += ((len(ns) + COLS - 1) // COLS) * TH
img.save(os.path.join(HERE, "all_icons.png")); print(sum(len(ns) for _, ns in rows), "icons")
