"""
Dev-only asset generator for the StickS3 Narrator's spoken phrases.
=====================================================================
NOT deployed to the device -- run this on a laptop to produce the WAV clips
main.py plays back via M5.Speaker.playWavFile(). Same "dev-only Pillow
script" role as ../../M5Paper Remote/assets/_generate_icons.py, just for
audio instead of icons.

Uses `pyttsx3` (the OS's own TTS voice -- SAPI5 on Windows, NSSpeechSynthesizer
on macOS, espeak on Linux) so it works fully offline, no cloud TTS account
needed. Then resamples with the stdlib `wave`/`audioop` modules to the exact
format StickS3's ES8311 codec expects: mono, 16-bit PCM, 16000 Hz.

    pip install pyttsx3
    python _generate_phrases.py

Regenerate whenever phrases.py's GAME_LABELS / SPECIAL_LABELS change, then
upload the whole assets/speech/ folder to /flash/assets/speech/ on the
device (MicroPico manual copy -- there is no Flasher manifest for this
device yet, see README.md).

Multi-word labels ("Shake Fill") are synthesized ONE WORD AT A TIME and
spliced back together with an explicit WORD_PAUSE_MS of silence -- asking
the TTS engine for the whole phrase in one call runs the words together
with no real gap (SAPI5 turned "Shake Fill" into something like
"Shakeville"). Splicing raw PCM gives an exact, engine-independent pause
instead of relying on punctuation tricks that vary by voice.
"""

import audioop
import os
import shutil
import sys
import tempfile
import wave

import pyttsx3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from phrases import FREEZE_DANCE_LABELS, GAME_LABELS, SPECIAL_LABELS  # noqa: E402

TARGET_RATE = 16000
OUT_DIR = os.path.join(os.path.dirname(__file__), "speech")
# The real pause heard between words -- tune this, not SILENCE_TRIM_THRESHOLD.
WORD_PAUSE_MS = 100
EDGE_SILENCE_MS = 80
# pyttsx3's save_to_file() (SAPI5 especially) bakes a surprising amount of
# dead air into each saved clip -- often several hundred ms of near-silence
# before/after the actual word. Left untrimmed, that stacks on top of
# WORD_PAUSE_MS and is what actually caused the "one word per second" feel,
# not the pause value itself. Samples with |amplitude| below this threshold
# (out of a 16-bit range of 32767) count as silence for trimming purposes.
SILENCE_TRIM_THRESHOLD = 400
SILENCE_TRIM_CHUNK_MS = 10
# Kept untrimmed at each end of a trimmed word so onsets/decays (esp. soft
# consonants) don't get clipped.
SILENCE_TRIM_KEEP_CHUNKS = 1


def _resample_to_target(path):
    """Rewrite `path` in place as mono 16-bit PCM at TARGET_RATE Hz."""
    with wave.open(path, "rb") as wf:
        n_channels = wf.getnchannels()
        rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())

    if n_channels == 2:
        frames = audioop.tomono(frames, sampwidth, 0.5, 0.5)
    if sampwidth != 2:
        frames = audioop.lin2lin(frames, sampwidth, 2)
        sampwidth = 2
    if rate != TARGET_RATE:
        frames, _ignored_state = audioop.ratecv(
            frames, sampwidth, 1, rate, TARGET_RATE, None
        )

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(TARGET_RATE)
        wf.writeframes(frames)


def _synthesize_one_word(word, path):
    """Fresh pyttsx3 engine per word.

    Reusing one engine across multiple save_to_file()+runAndWait() calls is
    a well-known way to hang pyttsx3's Windows SAPI5 driver on the second
    (or later) call -- it blocks forever inside driver.startLoop(), which is
    exactly the freeze/KeyboardInterrupt seen in testing. A new engine per
    word costs a fraction of a second and reliably avoids it.
    """
    engine = pyttsx3.init()
    engine.setProperty("rate", 165)  # a bit slower than default, for clarity
    engine.save_to_file(word, path)
    engine.runAndWait()
    try:
        engine.stop()
    except Exception:
        pass
    _resample_to_target(path)


def _read_pcm16_mono(path):
    """Raw frame bytes of a WAV already resampled to mono 16-bit @ TARGET_RATE."""
    with wave.open(path, "rb") as wf:
        return wf.readframes(wf.getnframes())


def _trim_silence(frames):
    """Strip the near-silent lead/trail SAPI5 (etc.) tends to bake into a
    saved word clip, keeping SILENCE_TRIM_KEEP_CHUNKS of buffer at each end.
    Returns `frames` unchanged if the whole clip looks silent (avoids
    trimming a word down to nothing on a bad take)."""
    chunk_samples = max(1, int(TARGET_RATE * SILENCE_TRIM_CHUNK_MS / 1000))
    chunk_bytes = chunk_samples * 2
    n_chunks = len(frames) // chunk_bytes
    if n_chunks == 0:
        return frames

    def _chunk_is_loud(i):
        chunk = frames[i * chunk_bytes : (i + 1) * chunk_bytes]
        return bool(chunk) and audioop.max(chunk, 2) > SILENCE_TRIM_THRESHOLD

    start = 0
    while start < n_chunks and not _chunk_is_loud(start):
        start += 1
    if start == n_chunks:
        return frames  # entirely below threshold -- leave as-is, don't blank a real word

    end = n_chunks
    while end > start and not _chunk_is_loud(end - 1):
        end -= 1

    start = max(0, start - SILENCE_TRIM_KEEP_CHUNKS)
    end = min(n_chunks, end + SILENCE_TRIM_KEEP_CHUNKS)
    return frames[start * chunk_bytes : end * chunk_bytes]


def _silence_frames(ms):
    n_samples = int(TARGET_RATE * ms / 1000)
    return b"\x00\x00" * n_samples


def _speak_to_wav(text, path):
    """Synthesize `text` word-by-word into `path`, trimming each word's
    baked-in dead air and then splicing them with an explicit WORD_PAUSE_MS
    of real silence so multi-word labels stay distinct without the pauses
    compounding into something much longer than intended."""
    words = text.split()
    tmp_dir = tempfile.mkdtemp(prefix="narrator_tts_")
    try:
        word_frames = []
        for i, word in enumerate(words):
            tmp_path = os.path.join(tmp_dir, "word_%d.wav" % i)
            _synthesize_one_word(word, tmp_path)
            word_frames.append(_trim_silence(_read_pcm16_mono(tmp_path)))

        pause = _silence_frames(WORD_PAUSE_MS)
        edge = _silence_frames(EDGE_SILENCE_MS)
        combined = edge + pause.join(word_frames) + edge

        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(TARGET_RATE)
            wf.writeframes(combined)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(
        '  wrote %s  ("%s", %d word%s, %dms pause between)'
        % (path, text, len(words), "" if len(words) == 1 else "s", WORD_PAUSE_MS)
    )


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for key, text in SPECIAL_LABELS.items():
        _speak_to_wav(text, os.path.join(OUT_DIR, "%s.wav" % key))
    for tag, label in GAME_LABELS.items():
        _speak_to_wav(label, os.path.join(OUT_DIR, "%s.wav" % tag))
    for tag, label in FREEZE_DANCE_LABELS.items():
        _speak_to_wav(label, os.path.join(OUT_DIR, "%s.wav" % tag))

    print("\nDone. Upload %s/*.wav to /flash/assets/speech/ on the StickS3." % OUT_DIR)


if __name__ == "__main__":
    main()
