"""
Halloween -- bench prototype, not a classroom game
==================================================
Loops four animations from drafts/holiday.json (jack-o'-lantern, bat, ghost,
eyes), each for 10 s, with a 10 s TAKE ONE after every second one. Not interactive; it only watches for stop/exit.

Frames come from /games/halloween_frames.bin (768 RGB bytes each, written by
drafts/export_halloween.py) and are read one at a time into panel.src, so
the clips never sit in RAM.

Entry point:
    play(nfc, panel, enow)  -- called from main.py
"""

import time

from display_tags import exit_tags_excluding

COMMANDS = exit_tags_excluding("halloween")

FRAMES_FILE = "/games/halloween_frames.bin"

# (name, first frame in the file, frames, fps, hold ms). Every clip holds 10 s,
# a whole number of cycles at these rates; TAKE ONE (frame 4) after every
# second animation.
TAKE_ONE = ("take_one", 4, 1, 1, 10000)
CLIPS = (
    ("jack_o_lantern", 0, 4, 6, 10000),
    ("bat", 5, 4, 6, 10000), TAKE_ONE,
    ("ghost", 9, 2, 3, 10000),
    ("eyes", 11, 10, 3, 10000), TAKE_ONE,
)
NFC_POLL_MS = 500


def play(nfc, panel, enow):
    print("\n  === HALLOWEEN ===")
    f = open(FRAMES_FILE, "rb")
    try:
        clip = 0
        frame = 0
        clip_start = time.ticks_ms()
        next_frame = clip_start
        last_nfc = clip_start
        while True:
            msg_type, _data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                print("  stop received")
                return

            now = time.ticks_ms()
            name, first, count, fps, hold = CLIPS[clip]
            if time.ticks_diff(now, clip_start) >= hold:
                clip = (clip + 1) % len(CLIPS)
                frame = 0
                clip_start = now
                next_frame = now
                name, first, count, fps, hold = CLIPS[clip]
                print(f"  clip {name}")

            if time.ticks_diff(now, next_frame) >= 0:
                f.seek((first + frame) * 768)
                f.readinto(panel.src)
                panel.draw_bytes(panel.src)
                frame = (frame + 1) % count
                next_frame = time.ticks_add(now, 1000 // fps)

            if nfc is not None and time.ticks_diff(now, last_nfc) >= NFC_POLL_MS:
                last_nfc = now
                cmd, _uid = nfc.read_command(timeout=50)
                if cmd in COMMANDS:
                    print("  exit tag scanned")
                    return

            time.sleep_ms(10)
    finally:
        f.close()
        panel.clear()
        print("\n  === DISPLAY IDLE ===\n")
