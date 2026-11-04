"""Pack drafts/holiday.json clips into games/halloween_frames.bin (768-byte RGB frames)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
CLIPS = ["jack_o_lantern", "take_one_bold", "bat", "ghost", "eyes"]
d = json.load(open(os.path.join(HERE, "holiday.json")))
# Old datasheet neutrals -> white measured on the panel 2026-10-31 (calibration
# grid photographed beside a laptop screen), greys scaled from it.
WHITE = (185, 255, 150)
NEUTRALS = {(255, 171, 93): 1.0, (180, 120, 65): 0.706, (110, 74, 40): 0.431, (30, 20, 10): 0.118}
def fix(rgb):
    k = NEUTRALS.get(tuple(rgb))
    return tuple(round(c * k) for c in WHITE) if k else tuple(rgb)
out = bytearray()
for name in CLIPS:
    e = d[name]
    frames = e.get("frames") or [e["rows"]]
    for rows in frames:
        for row in rows:
            for c in row:
                out += bytes(fix(e["key"][c])) if c in e["key"] else b"\0\0\0"
    print(name, len(frames), "frames", e.get("fps"))
open(os.path.join(HERE, "..", "games", "halloween_frames.bin"), "wb").write(out)
print(len(out) // 768, "frames total")
