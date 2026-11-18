"""Find icons on a black sheet and preview each at 16x16 (upscaled for viewing)."""
import sys
from collections import deque
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGB")
S = 8  # mask scale
small = im.resize((im.width // S, im.height // S))
w, h = small.size
px = small.load()
mask = [[max(px[x, y]) > 45 for x in range(w)] for y in range(h)]
seen = [[False] * w for _ in range(h)]
boxes = []
for y in range(h):
    for x in range(w):
        if mask[y][x] and not seen[y][x]:
            q = deque([(x, y)]); seen[y][x] = True
            x0 = x1 = x; y0 = y1 = y; n = 0
            while q:
                cx, cy = q.popleft(); n += 1
                x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
                for dx in (-2, -1, 0, 1, 2):
                    for dy in (-2, -1, 0, 1, 2):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True; q.append((nx, ny))
            if n > 60:
                boxes.append((x0 * S, y0 * S, (x1 + 1) * S, (y1 + 1) * S))
# reading order: rows by y center bucket, then x
boxes.sort(key=lambda b: (round(((b[1] + b[3]) / 2) / 150), b[0]))
cell, pad, cols = 16 * 8, 12, 12
rows = (len(boxes) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (cell * 2 + pad * 3), rows * (cell + pad * 2)), (40, 40, 40))
for i, (x0, y0, x1, y1) in enumerate(boxes):
    crop = im.crop((x0, y0, x1, y1))
    side = max(crop.width, crop.height)
    sq = Image.new("RGB", (side, side)); sq.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    orig = sq.resize((cell, cell))
    tiny = sq.resize((16, 16), Image.BOX).quantize(colors=6).convert("RGB").resize((cell, cell), Image.NEAREST)
    cx, cy = (i % cols) * (cell * 2 + pad * 3) + pad, (i // cols) * (cell + pad * 2) + pad
    sheet.paste(orig, (cx, cy)); sheet.paste(tiny, (cx + cell + pad, cy))
sheet.save(out)
print(len(boxes), "icons")
