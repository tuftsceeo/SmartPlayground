"""
Drive the Music Board Station's song handling under stubs.

Checks: addressing by HOST_ID, ack contents, retry de-dup, person+ append,
the 64-note cap, rejection of malformed songs, that every note file the
board can request exists, song-clock timing per voice, and that MockWand
melody.py's NOTE_CHAR encodes the same notes the board parses.

Run from anywhere: python3 music_board_song.py
"""
import ast
import os
import sys
import types
import time as _time

_HERE = os.path.dirname(os.path.abspath(__file__))
_BC = os.path.dirname(os.path.dirname(_HERE))                  # BroadcastCode/
STATION = os.path.join(os.path.dirname(_BC), "Experiments", "Music Board Station")
MELODY = os.path.join(_BC, "..", "Wand Module", "melody.py")

_clock = [0]
_time.ticks_ms = lambda: _clock[0]
_time.ticks_diff = lambda a, b: a - b
_time.sleep_ms = lambda ms: None


class _Pin:
    IN = OUT = PULL_UP = IRQ_FALLING = 0

    def __init__(self, *a, **k):
        pass

    def irq(self, **k):
        pass

    def value(self):
        return 0       # buttons read as still held when take() checks


class _I2S:
    TX = MONO = 0

    def __init__(self, *a, **k):
        pass

    def write(self, b):
        return len(b)

    def deinit(self):
        pass


class _NeoPixel(list):
    def __init__(self, pin, n):
        super().__init__([(0, 0, 0)] * n)
        self.writes = 0

    def write(self):
        self.writes += 1


machine = types.ModuleType("machine")
machine.Pin = _Pin
machine.I2S = _I2S
machine.unique_id = lambda: b"\x00\x00\x7a\x3f"
sys.modules["machine"] = machine
neopixel = types.ModuleType("neopixel")
neopixel.NeoPixel = _NeoPixel
sys.modules["neopixel"] = neopixel
sys.modules["espnow_manager"] = types.ModuleType("espnow_manager")

os.chdir(STATION)              # audio paths are relative ("notes/...")
sys.path.insert(0, STATION)
import music_board as mb      # noqa: E402


class FakeEnow:
    def __init__(self):
        self.sent = []

    def add_peer(self, mac):
        pass

    def remove_peer(self, mac):
        pass

    def send_to(self, mac, data):
        self.sent.append((mac, data))

    def poll(self, timeout_ms=0):
        return None, None, None


def song(n, seq, to="7a3f"):
    return {"type": "song", "to": to, "n": n, "seq": seq}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"  ok  {msg}")


def main():
    enow = FakeEnow()
    b = mb.MusicBoard(enow)
    check(mb.HOST_ID == "7a3f", "HOST_ID from unique_id")

    b._on_song(song("cde", 1), "AA")
    check(enow.sent[-1] == ("AA", {"type": "song_ack", "seq": 1, "len": 3}), "ack carries seq and len")
    check(b.playing, "auto-play on receipt")

    n = len(enow.sent)
    b._on_song(song("cde", 1, to="ffff"), "AA")
    check(len(enow.sent) == n, "other board's song ignored, no ack")

    b._on_song(song("cde", 1), "AA")
    check(enow.sent[-1][1]["len"] == 3 and len(b.song) == 3, "retry re-acked, not appended or replayed")

    b._on_song(song("g", 2), "AA")
    check(b.song == [(5, 2)], "new song replaces without person+")

    b.btn_add.pressed = True
    b._poll_buttons()
    b._on_song(song("a+", 1), "BB")
    check(b.song == [(5, 2), (6, 4)], "person+ appends next song")
    check(b.adding_since is None, "person+ is one-shot")

    b.btn_add.pressed = True
    b._poll_buttons()
    b._on_song(song("c" * 70, 2), "BB")
    check(len(b.song) == mb.MAX_TOKENS and enow.sent[-1][1]["len"] == mb.MAX_TOKENS - 2,
          "64-note cap, ack reports notes taken")

    for bad in ("", "x", "+c", None, 5):
        b._on_song(song(bad, 99), f"BAD{bad!r}")
        check(enow.sent[-1][1]["len"] == 0, f"malformed {bad!r} acked with len 0")

    check(mb.parse_song("ce-e-g+r") == [(1, 2), (3, 1), (3, 1), (5, 4), (0, 2)],
          "length marks and rest parse")

    missing = [f"{v}_{n}_{f}.wav" for v, _ in mb.VOICES for n in range(1, 9)
               for f in mb.LENGTH_FILE.values()
               if not os.path.exists(os.path.join(mb.NOTE_DIR, f"{v}_{n}_{f}.wav"))]
    check(not missing, f"all {len(mb.VOICES) * 8 * len(mb.LENGTH_FILE)} note files present {missing[:3]}")

    for v, (name, _) in enumerate(mb.VOICES):
        b._on_song(song("cg+e-r", 10 + v), "TIME")
        b.voice = v
        b.play()
        start = _clock[0]
        while b.playing:
            _clock[0] += 5
            b._step_playback()
        expect = (2 + 4 + 1 + 2) * mb.EIGHTH_MS
        took = _clock[0] - start
        check(abs(took - expect) <= 5 and b._tok >= len(b.song),
              f"{name}: 4 tokens in {took} ms (expect {expect}), all files written")

    tree = ast.parse(open(MELODY).read())
    note_char = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "NOTE_CHAR":
            note_char = ast.literal_eval(node.value)
    order = ["note_c", "note_d", "note_e", "note_f", "note_g", "note_a", "note_b", "note_c_high"]
    check(note_char is not None and "".join(note_char[k] for k in order) == mb.NOTE_CHARS,
          "melody.py NOTE_CHAR matches board NOTE_CHARS")
    import staff as st
    b.stop()
    w0 = b.staff.np.writes
    b.staff.buttons((1, 1, 1), (0, 0, 0), (0, 0, 0))
    check(b.staff.np.writes - w0 == (2 if st.WRITE_TWICE else 1), "WRITE_TWICE repeats each frame")
    w0 = b.staff.np.writes
    for _ in range(1000):          # 1000 ms idle
        _clock[0] += 1
        b.staff.refresh()
    per = 2 if st.WRITE_TWICE else 1
    check((b.staff.np.writes - w0) // per == 1000 // st.REFRESH_MS,
          f"idle refresh every {st.REFRESH_MS} ms")
    print("music_board_song: all checks passed")


if __name__ == "__main__":
    main()
