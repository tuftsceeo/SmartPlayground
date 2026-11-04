"""Host tool: convert icons/*.png to icons/*.a8 (width byte, height byte, then one alpha byte per pixel).

Run after adding or changing a PNG: python3 make_icons.py
"""

import os

from PIL import Image

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

for name in sorted(os.listdir(HERE)):
    if not name.endswith(".png"):
        continue
    im = Image.open(os.path.join(HERE, name)).convert("RGBA")
    if im.width > 255 or im.height > 255:
        raise SystemExit(f"{name}: larger than 255 px")
    out = os.path.join(HERE, name[:-4] + ".a8")
    with open(out, "wb") as f:
        f.write(bytes([im.width, im.height]) + im.split()[3].tobytes())
    print(out)
