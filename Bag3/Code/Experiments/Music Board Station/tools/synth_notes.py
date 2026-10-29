"""
Render the Music Board's note WAVs with FluidSynth and a General MIDI SoundFont.

Writes notes/{voice}_{n}_{len}.wav for voice in piano/guitar/violin, n = 1..8
(C4 D4 E4 F4 G4 A4 B4 C5) and len = 8 / 4 / 2 (eighth / quarter / half) at
quarter = 500 ms. Each file is exactly its beat length, 8 kHz 16-bit mono, with
the instrument's release inside the file, so files played back to back keep
time.

Requires the fluidsynth CLI and a GM SoundFont (default FluidR3_GM, MIT
licence: apt install fluidsynth fluid-soundfont-gm). Python needs numpy.

    python3 synth_notes.py              # render all 72 files
    python3 synth_notes.py --check      # verify files exist and have exact lengths
    python3 synth_notes.py --sf2 PATH   # use another SoundFont
"""

import argparse
import os
import struct
import subprocess
import sys
import tempfile
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NOTES_DIR = os.path.join(os.path.dirname(HERE), "notes")
DEFAULT_SF2 = "/usr/share/sounds/sf2/FluidR3_GM.sf2"

OUT_RATE = 8000
RENDER_RATE = 44100
QUARTER_MS = 500
LENGTHS = {8: QUARTER_MS // 2, 4: QUARTER_MS, 2: QUARTER_MS * 2}   # name -> ms
MIDI_NOTES = (60, 62, 64, 65, 67, 69, 71, 72)                       # C4 .. C5
FADE_MS = 30          # final raised-cosine fade so every file ends on zero
MIN_HOLD = 0.35       # key held for at least this fraction of the note
PEAK = 0.89           # -1 dBFS for the loudest note of each voice

# voice -> (GM program, ms before the end at which the key is released)
VOICES = {
    "piano": (0, 200),     # Acoustic Grand Piano
    "guitar": (24, 150),   # Acoustic Guitar (nylon); FluidR3 rings past release on eighths
    "violin": (40, 220),   # Violin
}

TICKS = 480           # per quarter; tempo 500000 us/quarter -> 1 tick = 500/480 ms


def file_name(voice, n, length):
    return f"{voice}_{n}_{length}.wav"


def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def _midi(program, note, on_ms, total_ms):
    """Single-track MIDI: program, note on at 0, off at on_ms, end at total_ms + 1 s."""
    to_ticks = lambda ms: int(round(ms * TICKS / QUARTER_MS))
    off = to_ticks(on_ms)
    end = to_ticks(total_ms + 1000) - off
    ev = b"".join((
        _vlq(0), b"\xFF\x51\x03", (QUARTER_MS * 1000).to_bytes(3, "big"),
        _vlq(0), bytes((0xC0, program)),
        _vlq(0), bytes((0x90, note, 100)),
        _vlq(off), bytes((0x80, note, 0)),
        _vlq(end), b"\xFF\x2F\x00",
    ))
    head = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TICKS)
    return head + b"MTrk" + struct.pack(">I", len(ev)) + ev


def _render(sf2, midi_bytes, tmp):
    mid = os.path.join(tmp, "n.mid")
    raw = os.path.join(tmp, "n.wav")
    with open(mid, "wb") as f:
        f.write(midi_bytes)
    subprocess.run(
        ["fluidsynth", "-n", "-i", "-q", "-R", "0", "-C", "0", "-g", "1.0",
         "-r", str(RENDER_RATE), "-F", raw, "-T", "wav", sf2, mid],
        check=True)
    with wave.open(raw) as w:
        if w.getsampwidth() != 2:
            raise RuntimeError(f"fluidsynth wrote {w.getsampwidth() * 8}-bit audio, expected 16")
        ch = w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)
    return data.reshape(-1, ch).mean(axis=1) / 32768.0


def _resample(x, n_out):
    """FFT resample from RENDER_RATE to n_out samples (band-limits at the new Nyquist)."""
    n_in = len(x)
    spec = np.fft.rfft(x)
    keep = n_out // 2 + 1
    return np.fft.irfft(spec[:keep], n_out) * (n_out / n_in)


def render_voice(sf2, voice, tmp):
    program, release_ms = VOICES[voice]
    out = {}
    for n, midi_note in enumerate(MIDI_NOTES, 1):
        for length, ms in LENGTHS.items():
            on_ms = max(ms - release_ms, int(ms * MIN_HOLD))
            x = _render(sf2, _midi(program, midi_note, on_ms, ms), tmp)
            n_in = RENDER_RATE * ms // 1000
            if len(x) < n_in:
                raise RuntimeError(f"{voice} {n} {length}: render too short ({len(x)} < {n_in})")
            y = _resample(x[:n_in], OUT_RATE * ms // 1000)
            fade = OUT_RATE * FADE_MS // 1000
            y[-fade:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, fade))
            out[(n, length)] = y
    peak = max(np.abs(y).max() for y in out.values())
    if peak <= 0:
        raise RuntimeError(f"{voice}: SoundFont rendered silence")
    gain = PEAK / peak
    for (n, length), y in out.items():
        pcm = np.clip(np.round(y * gain * 32767), -32768, 32767).astype("<i2")
        path = os.path.join(NOTES_DIR, file_name(voice, n, length))
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(OUT_RATE)
            w.writeframes(pcm.tobytes())
    print(f"  {voice}: 24 files, gain {gain:.2f}")


def check():
    bad = 0
    for voice in VOICES:
        for n in range(1, 9):
            for length, ms in LENGTHS.items():
                path = os.path.join(NOTES_DIR, file_name(voice, n, length))
                if not os.path.exists(path):
                    print(f"  missing {path}")
                    bad += 1
                    continue
                with open(path, "rb") as f:
                    head = f.read(44)
                with wave.open(path) as w:
                    fmt = (w.getframerate(), w.getsampwidth(), w.getnchannels(), w.getnframes())
                want = (OUT_RATE, 2, 1, OUT_RATE * ms // 1000)
                if fmt != want or head[36:40] != b"data":
                    print(f"  wrong format {path}: {fmt}, want {want} with 44-byte header")
                    bad += 1
    if bad:
        print(f"{bad} problem(s)")
        return 1
    print(f"all {len(VOICES) * 8 * len(LENGTHS)} note files present and exact")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sf2", default=DEFAULT_SF2)
    args = ap.parse_args()
    if args.check:
        return check()
    if not os.path.exists(args.sf2):
        raise SystemExit(f"SoundFont not found: {args.sf2}")
    os.makedirs(NOTES_DIR, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for voice in VOICES:
            render_voice(args.sf2, voice, tmp)
    return check()


if __name__ == "__main__":
    sys.exit(main())
