# SmartPlayground Wand — API Reference for LLM Game Code Generation
# ==================================================================
# This file is the SOLE context for generating or modifying jumpin.py.
#
# SCOPE: The LLM agent may ONLY generate or modify ONE file: jumpin.py
# All other game files (jump.py, shake.py, color_quest.py, etc.) are
# read-only reference. Do NOT create new game files. Do NOT modify
# main.py or any library file.
#
# jumpin.py is the "Jump In" game — the placeholder game students and
# teachers customize. It runs on a Seeed XIAO ESP32-C6 under MicroPython
# v1.27.0 and is launched when a kid taps the "jumpin" NFC tag on their wand.
# It must exit cleanly when any exit tag is tapped or ESP-NOW stop is received.
#
# IMPORTANT: Do NOT use f-strings — they crash on this MicroPython build.
# Use % formatting only: "value = %d" % val
#
# ═══════════════════════════════════════════════════════════════════
# 0. CRITICAL CONTRACT — READ FIRST (common generation mistakes)
# ═══════════════════════════════════════════════════════════════════
# main.py ALWAYS calls play() with exactly 6 positional arguments:
#   play_func(nfc, leds, buz, accel, i2c, enow)
# The 6th argument is an ESP-NOW manager (sometimes wrapped for game switching).
# Omitting enow causes: TypeError: function takes 5 positional arguments
# but 6 were given
#
# REQUIRED signature (copy exactly — all 6 parameters, in this order):
#   def play(nfc, leds, buz, accel, i2c, enow):
#
# FORBIDDEN signatures (will crash at launch):
#   def play(nfc, leds, buz, accel, i2c):          # WRONG — missing enow
#   def play(nfc, leds, buz, accel, enow):           # WRONG — missing i2c
#   def play(nfc, leds, buz, i2c, enow):             # WRONG — missing accel
#
# FORBIDDEN docstrings / comments (do not write these):
#   play(nfc, leds, buz, accel, i2c)                 # WRONG — omits enow
#
# FORBIDDEN NFC patterns (do not copy from older jumpin.py revisions):
#   - _read_tag_text() + _decode_ndef_text + COMMON_KEYS manual MIFARE reads
#   - Checking only text == "stop" (misses all other game exit tags)
#   Use NfcReader + exit_tags_excluding("jumpin") + _EXIT_TAGS instead.
#
# FORBIDDEN LED patterns:
#   - GREEN = (0, 127, 0)  or other raw RGB tuples for palette colors
#   - Hand-drawn bullseye index lists when SHAPE_BULLSEYE exists
#   Import colors from leds.py: from leds import GREEN, OFF, SHAPE_BULLSEYE
#
# Game-specific NFC tags (e.g. "go_for_it") are allowed during play ONLY if
# added to COMMANDS:
#   COMMANDS = _EXIT_TAGS | {"go_for_it"}
# Exit is still required on ANY tag in _EXIT_TAGS or enow stop/start_game.
#
# Follow THIS file and section 4 template only. Do not infer the play()
# signature from other game files or from an existing jumpin.py on disk.

# ═══════════════════════════════════════════════════════════════════
# 1. NATURAL LANGUAGE → API MAPPING
# ═══════════════════════════════════════════════════════════════════
# Non-technical users describe games using everyday words. Map them:
#
# "turn red" / "light up red" / "go red"
#     → leds.fill(RED)  or  leds.solid(130, 0, 0)
#
# "turn off" / "go dark" / "all off"
#     → leds.off()
#
# "flash" / "blink" / "flicker"
#     → leds.flash_color(RED)  or  leds.flash(130, 0, 0, times=3)
#
# "show a heart" / "display heart" / "heart shape"
#     → leds.show_shape(SHAPE_HEART, RED)
#
# "show a smiley" / "happy face"
#     → leds.show_shape(SHAPE_HAPPY_FACE, YELLOW)
#
# "show a star"
#     → leds.show_shape(SHAPE_STAR, YELLOW)
#
# "show a bullseye" / "target" / "bullseye pattern"
#     → leds.show_shape(SHAPE_BULLSEYE, GREEN)
#
# "show an arrow pointing up"
#     → leds.show_shape(SHAPE_ARROW_UP, WHITE)
#
# "rainbow" / "all different colors" / "colorful"
#     → iterate over [RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE]
#        and cycle with (frame // N) % len(colors)
#
# "pulse" / "breathe" / "glow in and out"
#     → leds.breathe(130, 0, 0, frame)  (call each loop iteration)
#     → or leds.breathe_shape(SHAPE_HEART, RED, frame)
#
# "spin" / "rotate" / "spinning light"
#     → leds.animate_spin(frame, BLUE)
#
# "dancing" / "dancer"
#     → leds.animate_dancer(frame, PURPLE)
#
# "firework" / "burst" / "explosion"
#     → leds.animate_firework(frame, ORANGE)
#
# "growing" / "expanding"
#     → leds.animate_grow(frame, GREEN)
#
# "make a sound" / "beep" / "play a tone"
#     → buz.beep(1000, 200)
#
# "happy sound" / "success sound" / "winning sound"
#     → buz.confirm()  or  buz.melody()
#
# "sad sound" / "wrong sound" / "error"
#     → buz.reject()
#
# "press the button" / "when button pressed" / "tap the button"
#     → btn.value() == 0  (active LOW — 0 means pressed)
#
# "shake it" / "when shaken" / "shake the wand"
#     → x,y,z = accel.read(); magnitude = math.sqrt(x*x+y*y+z*z); magnitude > 1.4
#
# "tilt left" / "lean left"
#     → x, y, z = accel.read(); y > 0.5   (positive Y = tilt left)
#
# "tilt right" / "lean right"
#     → x, y, z = accel.read(); y < -0.5
#
# "tilt forward" / "point down" / "tip forward"
#     → x, y, z = accel.read(); z < -0.5
#
# "jump" / "leap" / "freefall"
#     → magnitude < 0.3  (brief near-zero gravity during a jump)
#
# "wand face up" / "holding it flat"
#     → z < -0.8  (LED face pointing up)
#
# "tap a tag" / "scan a tag" / "touch an NFC sticker"
#     → cmd, uid = reader.read_command(timeout=100)
#
# "send a message to another wand" / "tell the speaker"
#     → enow.broadcast(["turnred"])
#
# "play music" / "start the music"
#     → enow.broadcast("FD_GO")
#
# "pause music" / "freeze" / "stop the music"
#     → enow.broadcast("FD_FREEZE")
#
# "show a number" / "display 3"
#     → leds.show_shape(SHAPE_3, GREEN)
#
# "show a letter" / "display the letter A"
#     → leds.show_shape(SHAPE_A, BLUE)
#
# "vibrate" / "rumble" / "shake the motor"
#     → import machine; motor = machine.Pin(21, machine.Pin.OUT); motor.value(1); time.sleep_ms(200); motor.value(0)

# ═══════════════════════════════════════════════════════════════════
# 2. HARDWARE OVERVIEW
# ═══════════════════════════════════════════════════════════════════
# Board:  Seeed XIAO ESP32-C6 (RISC-V 160MHz, 4MB flash, 512KB SRAM)
# Framework: MicroPython v1.27.0
# Logic: 3.3V
#
# GPIO Map:
#   GPIO0  (D0)  — Button (active LOW, internal pull-up; also boot pin)
#   GPIO1  (D1)  — Accelerometer INT1 (wake-up interrupt, working)
#   GPIO2  (D2)  — Accelerometer INT2 (routed but does NOT fire — do not use)
#   GPIO3        — WiFi enable (used by ESPNowManager.init() — do not touch)
#   GPIO14       — Antenna select (used by ESPNowManager.init() — do not touch)
#   GPIO19 (D8)  — Buzzer (piezo, PWM)
#   GPIO20 (D9)  — NeoPixel data (25× SK6812, GRB byte order)
#   GPIO21 (D3)  — Vibration motor (digital on/off or PWM)
#   GPIO22 (D4)  — I2C SDA (shared bus, locked at 100kHz)
#   GPIO23 (D5)  — I2C SCL
#
# I2C Devices (all on GPIO22/23 at 100kHz — PN532 requires slow bus):
#   0x24 — PN532 NFC reader
#   0x19 — LIS2DW12 accelerometer (SDO/SA0=HIGH)
#   0x36 — MAX17048 battery fuel gauge
#   0x44 — OPT3002 ambient light sensor (no INT pin routed — polling only)
#
# LED Layout: 25 LEDs in a 5×5 grid (index = row * 5 + col):
#   [ 0  1  2  3  4]  ← top row
#   [ 5  6  7  8  9]
#   [10 11 12 13 14]
#   [15 16 17 18 19]
#   [20 21 22 23 24]  ← bottom row
#
# NeoPixel byte order is GRB (SK6812). The Leds class accepts (R, G, B) —
# it handles the swap. Raw leds.np[i] = (r, g, b) is also (R, G, B) because
# the _ScaledNeoPixel wrapper converts before writing.
#
# Accelerometer Orientation (re-verified against on-hand hardware with a
# live per-orientation LED-color test; the previous "confirmed from
# calibration" table had tip up/down on the wrong axis AND sign):
#   accel.read() → (x, y, z) in g units
#       Wand held upright (tip up, handle down)   → x ≈ -1.0g
#       FACE up  (front up, LED side down)        → z ≈ -1.0
#       BACK up                     → z ≈ +1.0
#       LEFT side up                → y ≈ +1.0
#       RIGHT side up               → y ≈ -1.0
#       HANDLE up  (upside-down)    → x ≈ +1.0
#
# Vibration Motor (GPIO21):
#   motor = machine.Pin(21, machine.Pin.OUT, value=0)
#   motor.value(1)  # on — keep bursts short, draws significant current
#   motor.value(0)  # off
#
# ESP-NOW Devices (devices games can message via enow):
#   Speaker (standalone I2S player)   — broadcasts: "FD_GO", "FD_FREEZE", "stop"
#   DialSpeaker (M5Stack Dial)        — broadcasts: "FD_GO", "FD_FREEZE", "stop"
#   Slide Score Station (40-LED bar)  — enow.send_score(SCORE_MAC, colors, ms)
#                                        enow.broadcast(["turnred","turnblue",...])

# ═══════════════════════════════════════════════════════════════════
# 3. ENTRY POINT CONTRACT — jumpin.py ONLY
# ═══════════════════════════════════════════════════════════════════
# main.py dispatches the "jumpin" NFC tag via _launch_game(), which calls:
#   play_func(nfc, leds, buz, accel, i2c, enow)   # 6 positional args always
# (rainbow is the only game that also receives batt= as a keyword argument.)
#
# jumpin.py MUST define this exact function at module level:
#
#   def play(nfc, leds, buz, accel, i2c, enow):
#
# The 6-argument signature is REQUIRED — all six parameters must appear even
# if a game does not use i2c or accel. enow is always passed — never None.
# Do NOT create a second ESPNowManager or call network.WLAN — it is already
# initialized by main.py. Use the enow object passed in.
#
# Arguments:
#   nfc   — PN532 driver (already initialized)
#   leds  — Leds instance; leds.np is the scaled NeoPixel object
#   buz   — Buzzer instance
#   accel — LIS2DW12 (already initialized at ±4g, 100Hz); may be None
#   i2c   — machine.SoftI2C (100kHz; available for additional sensors)
#   enow  — ESPNowManager (already initialized; poll every loop iteration)
#
# play() MUST:
#   - Use "jumpin" as the game tag name: exit_tags_excluding("jumpin")
#   - Poll enow.poll() every loop iteration for stop/start_game
#   - Poll NFC every ~10-15 frames for exit tags (not every frame — too slow)
#   - Exit (return) when any _EXIT_TAGS tag is scanned or enow stop is received
#   - Call leds.off() in a try/finally block
#   - NOT use f-strings
#   - Also define main() for standalone testing

# ═══════════════════════════════════════════════════════════════════
# 4. COMPLETE CANONICAL TEMPLATE FOR jumpin.py
# ═══════════════════════════════════════════════════════════════════
# This is the exact structure jumpin.py must follow.
# The game tag name is always "jumpin" — do not change it.

"""
Jump In — <short description of what this version does>
=========================================================
<1-3 sentences describing the game for students.>

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py (6 args required)
    main()                                   — standalone testing

DO NOT shorten play() to 5 arguments. main.py always passes 6 positional args.
"""

import machine
import time
import math
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding

_EXIT_TAGS = exit_tags_excluding("jumpin")  # always "jumpin" — do not change

from leds import (
    OFF, RED, GREEN, BLUE, YELLOW, PURPLE, PINK, WHITE, ORANGE, TEAL,
    SHAPE_HEART, SHAPE_STAR, SHAPE_HAPPY_FACE, SHAPE_ARROW_UP, SHAPE_BULLSEYE,
    # ... import the specific constants you need
)

# ─── Hardware Config ───────────────────────────────────────────────
I2C_SDA    = 22
I2C_SCL    = 23
BUZZER_PIN = 19
BUTTON_PIN = 0
PN532_ADDR = 0x24

# ─── Game Config ───────────────────────────────────────────────────
COMMANDS          = _EXIT_TAGS  # add game-specific tag names: _EXIT_TAGS | {"scan"}
NFC_POLL_INTERVAL = 10          # poll NFC every N frames (~500ms at 50ms loop)
LOOP_DELAY_MS     = 50


class JumpInGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc   = nfc
        self.leds  = leds
        self.buz   = buz
        self.accel = accel
        self.enow  = enow

        self.reader = NfcReader(nfc, COMMANDS)

        # Button: active LOW. Read initial state so first press is detected correctly.
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)

        self._frame = 0
        # ... initialize game state variables here

    def _check_stop(self):
        """Poll ESP-NOW (every frame) and NFC (every N frames) for exit signals."""
        # Always check ESP-NOW first — teacher can force-exit any running game
        msg_type, _, _ = self.enow.poll()
        if msg_type in ("stop", "start_game"):
            return True

        # NFC is slow (~200-500ms) — only poll every NFC_POLL_INTERVAL frames
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            return cmd in _EXIT_TAGS
        except Exception:
            return False

    def _check_button(self):
        """Edge-detection for button press. Returns True on press edge."""
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)           # debounce
            if self.btn.value() == 0:
                self._btn_was_down = True
                return True             # press event
        elif not down and self._btn_was_down:
            self._btn_was_down = False  # release
        return False

    def run(self):
        while True:
            # ── Exit check MUST be first in every loop iteration ──
            if self._check_stop():
                return

            # ── Button ────────────────────────────────────────────
            if self._check_button():
                pass  # handle button press

            # ── Accelerometer ──────────────────────────────────────
            if self.accel:
                try:
                    x, y, z = self.accel.read()
                    magnitude = math.sqrt(x*x + y*y + z*z)
                    # magnitude > 1.4  → shake
                    # magnitude < 0.3  → freefall / jump
                except Exception:
                    pass

            # ── Game logic here ────────────────────────────────────

            # ── Animations driven by frame counter ─────────────────
            # self.leds.breathe(130, 0, 0, self._frame)
            # self.leds.animate_dancer(self._frame, PURPLE)

            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    """Called from main.py when the 'jumpin' tag is tapped."""
    # Entry fanfare for Jump In — keep this distinct from other games
    buz.beep(523, 80); time.sleep_ms(40)
    buz.beep(659, 80); time.sleep_ms(40)
    buz.beep(784, 120)

    print("\n  === JUMP IN ===")
    try:
        JumpInGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """Standalone entry — run directly: import jumpin; jumpin.main()"""
    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)

    import brightness
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c); light.init()
        mult, lux = brightness.calibrate(light)
        if lux is not None:
            print("  Light: %.0f lux -> brightness x%.2f" % (lux, mult))
    except Exception as e:
        print("  [WARN] OPT3002: %s" % e)

    from leds import Leds
    from buzzer import Buzzer
    leds = Leds()
    buz  = Buzzer(BUZZER_PIN)

    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % e); return

    accel = None
    try:
        from lis2dw12 import LIS2DW12, RANGE_4G
        accel = LIS2DW12(i2c); accel.init(fs_range=RANGE_4G)
        print("  Accelerometer OK")
    except Exception as e:
        print("  [WARN] Accel: %s" % e)

    from espnow_manager import ESPNowManager
    enow = ESPNowManager(); enow.init()

    play(nfc, leds, buz, accel, i2c, enow)


if __name__ == "__main__":
    main()

# ═══════════════════════════════════════════════════════════════════
# 5. LED API
# ═══════════════════════════════════════════════════════════════════
# from leds import Leds, RED, GREEN, BLUE, ...  (leds already passed in)
# All LED values are auto-scaled by ambient brightness — use the
# constants, not raw RGB tuples.
#
# ── COLOR CONSTANTS ─────────────────────────────────────────────────
# OFF / BLACK  = (0,0,0)
# RED          = (130,0,0)          ROSE    = (120,10,20)
# ORANGE       = (120,40,0)         AMBER   = (120,80,0)
# YELLOW       = (110,120,0)        LIME    = (50,210,0)
# GREEN        = (0,230,0)          TEAL    = (0,180,100)
# CYAN         = (0,180,240)        BLUE    = (0,20,255)
# INDIGO       = (30,0,255)         PURPLE  = (50,0,250)
# MAGENTA      = (120,0,160)        PINK    = (200,80,120)
# WHITE        = (140,150,150)      PEACH   = (180,120,30)
# MINT         = (30,190,50)        SKY     = (60,150,250)
#
# Dim variants (~50% brightness, for backgrounds / status):
# RED_DIM  GREEN_DIM  BLUE_DIM  YELLOW_DIM  WHITE_DIM
# ORANGE_DIM  AMBER_DIM  PINK_DIM  PURPLE_DIM
#
# ── SHAPE CONSTANTS — LED index tuples for show_shape() ─────────────
# Numbers:   SHAPE_0 through SHAPE_9
# Letters:   SHAPE_A through SHAPE_Z
#
# Symbols:
#   SHAPE_HEART       ♥   SHAPE_STAR        ★   SHAPE_DIAMOND     ◆
#   SHAPE_CHECK       ✓   SHAPE_LIGHTNING   ⚡   SHAPE_MUSIC       ♫
#   SHAPE_QUESTION    ?   SHAPE_EXCLAIM     !   SHAPE_PLUS        +
#   SHAPE_HOUSE       🏠  SHAPE_TREE        🌲  SHAPE_FLAME       🔥
#   SHAPE_MOON        🌙  SHAPE_RAINDROP    💧  SHAPE_FISH        🐟
#   SHAPE_BIRD        🐦  SHAPE_PACMAN          SHAPE_INVADER
#   SHAPE_GHOST           SHAPE_CHECKERS        SHAPE_SPIRAL
#   SHAPE_HOURGLASS       SHAPE_BULLSEYE        SHAPE_WIFI
#   SHAPE_PLAY        ▶   SHAPE_PAUSE       ⏸   SHAPE_POINTER
#   SHAPE_BATTERY_FULL    SHAPE_BATTERY_HALF    SHAPE_BATTERY_EMPTY
#   SHAPE_POWER           SHAPE_FASTFORWARD     SHAPE_REWIND
#   SHAPE_RECTANGLE
#
# Faces:
#   SHAPE_HAPPY_FACE  😊  SHAPE_SAD_FACE   😢  SHAPE_ANGRY_FACE  😠
#   SHAPE_NEUTRAL_FACE    SHAPE_SL_FACE        SHAPE_SLEEPY_FACE
#
# Dancers (use with animate_dancer):
#   SHAPE_DANCER1  SHAPE_DANCER2  SHAPE_DANCER3
#
# Arrows:
#   SHAPE_ARROW_UP  SHAPE_ARROW_DN  SHAPE_ARROW_L  SHAPE_ARROW_R
#   SHAPE_DIAG_L  SHAPE_DIAG_R
#
# Grid utilities:
#   SHAPE_TOP_ROW   SHAPE_ROW2      SHAPE_ROW3    SHAPE_ROW4  SHAPE_BOT_ROW
#   SHAPE_LEFT_COL  SHAPE_COL2      SHAPE_COL3    SHAPE_COL4  SHAPE_RIGHT_COL
#   SHAPE_BORDER    SHAPE_INNER_3x3 SHAPE_CORNERS SHAPE_CENTER
#   SHAPE_SLASH_L   SHAPE_SLASH_R
#
# ── CORE METHODS ────────────────────────────────────────────────────
# leds.off()
#     Turn all 25 LEDs off.
#
# leds.fill(color)
#     Fill all LEDs with a color tuple. e.g. leds.fill(RED)
#
# leds.solid(r, g, b)
#     Fill all LEDs with explicit r/g/b values. e.g. leds.solid(130, 0, 0)
#
# leds.flash(r, g, b, times=2, on_ms=120, off_ms=80)
#     Flash all LEDs N times (blocking).
#
# leds.flash_color(color, times=2, on_ms=120, off_ms=80)
#     Flash a color tuple N times (blocking). e.g. leds.flash_color(RED, 3)
#
# leds.show_shape(indices, color, bg=OFF)
#     Light specific LEDs (indices tuple) in color; all others in bg.
#     e.g. leds.show_shape(SHAPE_HEART, RED)
#     e.g. leds.show_shape(SHAPE_HEART, RED, bg=WHITE_DIM)
#
# leds.show_pattern(color_to_indices_dict, bg=OFF)
#     Light multiple groups in different colors.
#     e.g. leds.show_pattern({RED: (0,4), YELLOW: (12,), GREEN: (20,24)})
#
# leds.breathe(r, g, b, frame)
#     Breathing brightness on all LEDs, driven by frame counter.
#     Call each loop iteration. ~3s cycle at 40ms loop.
#
# leds.breathe_shape(indices, color, frame, bg=OFF, speed=0.08, min_level=2)
#     Breathing animation on a shape only.
#     e.g. leds.breathe_shape(SHAPE_HEART, RED, self._frame)
#
# leds.pulse_color(r, g, b, duration_ms=600)
#     Single sine pulse from full brightness to off (blocking).
#
# leds.fade_shape(indices, color, duration_ms, bg=OFF)
#     Linear fade from color to bg over duration_ms (blocking, ~20 steps).
#
# leds.np[i] = (r, g, b)   — set individual LED (auto-scaled)
# leds.np.write()            — push all np[] changes to hardware
# leds.num                   — total LED count (25 on wand)
#
# ── ANIMATION METHODS (call each frame with self._frame) ────────────
# All accept (frame, color, bg=OFF, frames_per_step=6).
# Larger frames_per_step = slower animation.
#
# leds.animate_dancer(frame, color)
#     Cycle DANCER1→DANCER2→DANCER3→DANCER2 (dancing figure).
#
# leds.animate_rows(frame, color)
#     Sweep rows top→bottom: TOP_ROW, ROW2, ROW3, ROW4, BOT_ROW.
#
# leds.animate_columns(frame, color)
#     Sweep columns left→right.
#
# leds.animate_spin(frame, color)
#     Rotating bar through center: ROW3, SLASH_L, COL3, SLASH_R.
#
# leds.animate_grow(frame, color)
#     Expand outward: CENTER → INNER_3x3 → BORDER → blank.
#
# leds.animate_shrink(frame, color)
#     Contract inward: BORDER → INNER_3x3 → CENTER → blank.
#
# leds.animate_arrow_spin(frame, color)
#     Rotate arrow direction: UP → LEFT → DOWN → RIGHT.
#
# leds.animate_firework(frame, color)
#     Burst: CENTER → STAR → CORNERS → blank.

# ═══════════════════════════════════════════════════════════════════
# 6. BUZZER API
# ═══════════════════════════════════════════════════════════════════
# from buzzer import Buzzer, NOTE_FREQ  (buz already passed in)
#
# buz.beep(freq=1000, ms=100)
#     Single tone at freq Hz for ms milliseconds (blocking).
#     Common frequencies: 262=C4, 330=E4, 392=G4, 440=A4, 523=C5,
#                         659=E5, 784=G5, 1047=C6
#
# buz.play_note(freq, ms=400)
#     Alias for beep with longer default duration.
#
# buz.melody()
#     Short ascending melody: C5-E5-G5-C6 (~800ms, blocking).
#
# buz.confirm()   — two rising tones (tag accepted / correct answer)
# buz.start()     — three rising tones (entering a mode)
# buz.stop()      — descending tone (stopping / exiting)
# buz.reject()    — double low tone (wrong / invalid)
# buz.warn()      — single low tone (warning)
#
# NOTE_FREQ dict (4th octave):
#   notec=262  noted=294  notee=330  notef=349
#   noteg=392  notea=440  noteb=494  notechigh=523
#
# Custom sequence pattern (used by jump.py):
#   for freq, dur, gap in [(523,80,40),(659,80,40),(784,120,0)]:
#       buz.beep(freq, dur)
#       if gap: time.sleep_ms(gap)
#
# Sound design rule:
#   - Each game MUST have a unique entry fanfare (different from all others)
#   - Victory / correct → buz.confirm() or buz.melody()
#   - Wrong / miss → buz.reject()
#   - Exit / stop → buz.stop()

# ═══════════════════════════════════════════════════════════════════
# 7. NFC PATTERNS
# ═══════════════════════════════════════════════════════════════════
# from nfc_reader import NfcReader
# from game_tags import exit_tags_excluding
#
# DO NOT use _read_tag_text(), _decode_ndef_text, or manual MIFARE sector
# loops. Those are legacy patterns; they only recognize hard-coded tag names
# like "stop" and will NOT exit on other game tags or ESP-NOW stop.
# Always use NfcReader + _EXIT_TAGS for exit handling.
#
# ── EXIT TAG SETUP (required in every game) ─────────────────────────
# _EXIT_TAGS = exit_tags_excluding("jumpin")   # always "jumpin" for this file
#   Returns EXIT_TAGS minus this game's own tag so an immediate re-scan
#   on entry doesn't cause instant exit. EXIT_TAGS = all game tags + "stop".
#
# ── NfcReader (recommended pattern) ─────────────────────────────────
# reader = NfcReader(nfc, COMMANDS)
#   where COMMANDS = _EXIT_TAGS  (or _EXIT_TAGS | {"scan", "blue", ...})
#
# reader.read_command(timeout=100) → (command_str, uid_hex)
#   command_str: one of COMMANDS if recognized, else None
#   uid_hex:     tag UID string (unique per physical tag)
#   Returns (None, None) if no tag present.
#
# reader.detect_tag(timeout=250) → (uid_hex, sak) or (None, None)
#   Fast presence check without reading NDEF. Use for quick "was a tag
#   tapped?" detection before doing the slower full read.
#
# ── Repeat-scan guard (prevent re-triggering same tag) ───────────────
# _last_uid = None
# cmd, uid = reader.read_command(timeout=100)
# if cmd and uid != _last_uid:
#     _last_uid = uid
#     # process cmd
# elif uid is None:
#     _last_uid = None  # tag removed — allow re-scan
#
# ── NFC polling rate ─────────────────────────────────────────────────
# NFC reads take 200-500ms. Use NFC_POLL_INTERVAL = 10-15 to poll only
# every N frames. Polling every frame stalls the game loop.
# if self._frame % NFC_POLL_INTERVAL == 0:
#     cmd, uid = self.reader.read_command(timeout=100)
#
# ── All current game tag names (as of this knowledgebase) ────────────
# "colorquest"  "freezedance"  "jumpin"     "cooking"
# "melody"      "shake"        "shakerainbow" "rainbow"
# "jump"        "sound"        "nfcsound"   "simpleicecream"
# "multiicecream" "gestures"

# ═══════════════════════════════════════════════════════════════════
# 8. BUTTON HANDLING
# ═══════════════════════════════════════════════════════════════════
# Button is on GPIO0, active LOW with internal pull-up.
#   btn = Pin(0, Pin.IN, Pin.PULL_UP)
#   btn.value() == 0  → pressed
#   btn.value() == 1  → released
#
# ── Edge detection with debounce (copy this pattern) ────────────────
#   self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
#   self._btn_was_down = (self.btn.value() == 0)  # snapshot initial state!
#
#   def _check_button(self):
#       down = (self.btn.value() == 0)
#       if down and not self._btn_was_down:
#           time.sleep_ms(30)              # debounce
#           if self.btn.value() == 0:
#               self._btn_was_down = True
#               return True                # press event — handle it
#       elif not down and self._btn_was_down:
#           self._btn_was_down = False     # release
#       return False
#
# Taking the initial state snapshot prevents a phantom "press" if the
# button happens to be held down when the game starts.
#
# NOTE: GPIO0 is also the boot pin — holding it during reset enters
# the MicroPython bootloader. This is normal behavior.

# ═══════════════════════════════════════════════════════════════════
# 9. ACCELEROMETER
# ═══════════════════════════════════════════════════════════════════
# from lis2dw12 import LIS2DW12, RANGE_4G  (accel already passed in; may be None)
# Always guard with: if self.accel: try: ... except: pass
#
# x, y, z = accel.read()          — returns acceleration in g units (float)
# magnitude = math.sqrt(x*x + y*y + z*z)
#
#
# ── Orientation / tilt  ───────────────────
# Wand held upright (tip up, handle down)   → x ≈ -1.0g 
# FACE up  (front up, LED side down)        → z ≈ -1.0
# BACK up                                   → z ≈ +1.0
# LEFT side up                              → y ≈ +1.0 (left when upright))
# RIGHT side up                             → y ≈ -1.0
# HANDLE up  (upside-down)                  → x ≈ +1.0
#
# ── Common gestures and motions ────────────────────────────────────────────────
# Freefall / jump:  magnitude < 0.3
# Shake / hit:      magnitude > 1.4
# Gentle motion:    magnitude > 0.3 and < 1.4
#
# -- Axes of Motion --
# x → down-and-up
# y → left-and-right
# z → backward-and-forward
#
# ── Calibrated orientation detection ────────────────────────────────
# FACE_UP_THRESHOLD  = 0.8   # e.g., -z > this → LED face pointing up; -x > this → upright (tip up, handle down)
# SHAKE_THRESHOLD    = 1.4    # magnitude > this → shaking 
# FREEFALL_THRESHOLD = 0.3    # magnitude < this → jump / freefall
# TILT_THRESHOLD     = 0.5    # |x| or |y| > this → tilted that axis
#
# ── Usage pattern ────────────────────────────────────────────────────
# if self.accel:
#     try:
#         x, y, z = self.accel.read()
#         magnitude = math.sqrt(x*x + y*y + z*z)
#         if magnitude > 1.4:
#             # shaken!
#     except Exception:
#         pass
#





# ═══════════════════════════════════════════════════════════════════
# 10. ESP-NOW
# ═══════════════════════════════════════════════════════════════════
# from espnow_manager import ESPNowManager  (enow already passed in)
#
# CRITICAL: main.py passes a pre-initialized enow into every game.
# Do NOT create a second ESPNowManager or call network.WLAN yourself.
# Using two radio stacks causes crashes.
#
# ── Receiving (poll EVERY loop iteration) ────────────────────────────
# msg_type, data, mac_str = enow.poll()
#   msg_type values:
#     "stop"       → teacher/station stopped this wand — MUST EXIT immediately
#     "start_game" → another game was requested — MUST EXIT (data has "name" key)
#     "colors"     → color action list sent from programming mode
#     "score"      → score data from another device
#     "battery"    → battery level broadcast
#     "splat_config" → action chain for the speaker Splat device
#     "scan_request" → programming station asking wand to scan
#     "raw"        → unrecognized message
#     None         → nothing received
#
# if msg_type in ("stop", "start_game"):
#     return  # exit game
#
# ── Sending ──────────────────────────────────────────────────────────
# enow.broadcast(["turnred"])           — broadcast action list to all
# enow.broadcast("FD_GO")              — start music on speakers
# enow.broadcast("FD_FREEZE")          — pause music
# enow.broadcast_stop()                — send stop to all known peers
# enow.send_to(mac_str, data)          — send to specific device by MAC
# enow.send_score(mac_bytes, colors, elapsed_ms)  — send score to scoreboard
#
# ── Convenience senders ───────────────────────────────────────────────
# enow.send_stop_to(mac_str)
# enow.send_start_game(mac_str, name)
# enow.broadcast_start_game(name)
# enow.send_scan_request()
#
# Max ~240 bytes per ESP-NOW message.

# ═══════════════════════════════════════════════════════════════════
# 11. FLUID GAME SWITCHING
# ═══════════════════════════════════════════════════════════════════
# Students can exit jumpin.py by tapping ANY game tag or "stop".
# A teacher can force-exit via ESP-NOW. Both must be handled.
# jumpin.py is already registered in main.py — do NOT edit main.py.
#
# Required imports in jumpin.py:
#   from game_tags import exit_tags_excluding
#   _EXIT_TAGS = exit_tags_excluding("jumpin")  # always "jumpin"
#
# Required COMMANDS set:
#   COMMANDS = _EXIT_TAGS  (or _EXIT_TAGS | {"scan", "color1", ...}
#              if the game also reads other NFC tags during play)
#
# Required in every loop iteration:
#   msg_type, _, _ = self.enow.poll()
#   if msg_type in ("stop", "start_game"): return
#   # ... NFC check every NFC_POLL_INTERVAL frames ...
#   cmd, uid = self.reader.read_command(timeout=100)
#   if cmd in _EXIT_TAGS: return

# ═══════════════════════════════════════════════════════════════════
# 12. OTHER AVAILABLE LIBRARIES
# ═══════════════════════════════════════════════════════════════════

# ── actions.py — from actions import ActionRunner, ACTIONS ────────────
# ActionRunner(leds, buzzer) executes named actions.
# runner.run_action("turnred")              — single action
# runner.run_and_group(["turnred","notea"]) — simultaneous (threaded)
# runner.run_chain([["turnred","notea"],["playnote"]]) — sequential groups
# ACTIONS = {"playnote","turnpurple","turnred","turnblue","turngreen",
#            "turnwhite","turnyellow","turnoff","notea".."noteg"}
# ANIMAL_SOUNDS = {"cat","chicken","cow","dog","pig","duck",
#                  "elephant","horse","goat"}  — remote Splat only

# ── max17048.py — from max17048 import MAX17048 ───────────────────────
# batt = MAX17048(i2c)
# v, soc = batt.read_all()   — voltage (V), state-of-charge (0-100)

# ── opt3002.py — from opt3002 import OPT3002 ─────────────────────────
# light = OPT3002(i2c); light.init(); lux = light.lux
# INT pin NOT routed — use polling only.

# ── gesture_engine.py — from gesture_engine import GestureEngine ──────
# ge = GestureEngine(i2c, neopixel_obj, buzzer_pin=19)
# ge.init()
# name, conf, dist = ge.capture_and_classify()  — blocking ~1.5s
# CONFIDENCE_THRESHOLD = 0.60

# ── target.py — from target import SCORE_MAC ─────────────────────────
# SCORE_MAC = b'\xB4\x3A\x45\x86\x1A\x5C'  (Slide Score Station)
# Usage: enow.send_score(SCORE_MAC, colors_list, elapsed_ms)

# ── hubtype.py — from hubtype import HUB_TYPE, HUB_CONFIG ────────────
# HUB_TYPE = "wand"
# HUB_CONFIG = { "num_leds":25, "led_pin":20, "buzzer_pin":19,
#   "motor_pin":21, "button_pin":0, "accel_int1_pin":1,
#   "i2c_sda":22, "i2c_scl":23, "i2c_freq":100000 }

# ── battery.py — from battery import show_battery ────────────────────
# show_battery(batt, leds, buzzer)  — display battery on LEDs for 2.5s

# ═══════════════════════════════════════════════════════════════════
# 13. STANDARD MICROPYTHON MODULES
# ═══════════════════════════════════════════════════════════════════
# machine  — Pin, PWM, SoftI2C, Timer, ADC
# time     — sleep_ms(), ticks_ms(), ticks_diff(), ticks_add()
# math     — sin, cos, pi, sqrt, abs
# random   — randint, choice, random, shuffle
# json     — dumps, loads
# struct   — pack, unpack
# sys      — print_exception
# _thread  — start_new_thread
# network  — WLAN (do not activate manually — ESPNowManager owns it)
# espnow   — ESPNow (do not use directly — ESPNowManager owns it)
# neopixel — NeoPixel (use Leds class instead)
# gc       — collect, mem_free

# ═══════════════════════════════════════════════════════════════════
# 14. CONSTRAINTS AND GOTCHAS
# ═══════════════════════════════════════════════════════════════════
# 1. f-strings CRASH on this MicroPython build. Use % formatting ONLY.
#      WRONG:  print(f"value = {x}")
#      RIGHT:  print("value = %d" % x)
#              print("name = %s" % name)
#              print("x=%.2f y=%.2f" % (x, y))
#
# 2. play() takes 6 arguments: (nfc, leds, buz, accel, i2c, enow)
#    Old 5-arg signatures are WRONG and crash at call time, e.g.:
#      play(nfc, leds, buz, accel, i2c)       → TypeError (missing enow)
#      play(nfc, leds, buz, accel, enow)      → TypeError (missing i2c)
#    All six parameter names must appear in the def even if unused.
#
# 3. Do NOT create ESPNowManager() or activate network.WLAN() inside a game.
#    enow is passed in; use it. Two radio stacks crash the device.
#
# 4. Poll enow.poll() EVERY loop iteration (not just on NFC frames).
#    Teachers use ESP-NOW to force-switch games; missing it feels broken.
#
# 5. NFC reads take 200-500ms. Poll NFC_POLL_INTERVAL = 10 (every ~10 frames),
#    not every frame. Polling every frame stalls the entire game loop.
#
# 6. Import colors from leds.py (RED, GREEN, etc.) — do NOT use raw RGB tuples
#    like (127,0,0) unless you have a specific non-palette reason. The constants
#    are tuned for hardware appearance and auto-scale with ambient brightness.
#
# 7. I2C bus is locked at 100kHz. PN532 fails at 400kHz. Never change the freq.
#
# 8. Button on GPIO0 is active LOW. pressed = (btn.value() == 0)
#    Always debounce (time.sleep_ms(30)) and read initial state at __init__.
#
# 9. NeoPixel byte order is GRB, but leds.np[i] = (r,g,b) is correctly RGB
#    because _ScaledNeoPixel handles the swap. No byte-order workarounds needed.
#
# 10. RAM is ~512KB. Avoid large allocations; call gc.collect() if needed.
#
# 11. All NFC tags are MIFARE Classic 1K or NTAG. NfcReader handles both
#     automatically — do not write tag-type branching logic yourself.
#
# 12. Block 7 and block 11 (sector trailers) — never read/write.
#
# 13. Accelerometer at ±4g, 100Hz. accel.read() → (x,y,z) in g.
#     Gravity is always present (~1g); magnitude ≈ 1.0 at rest.
#     Guard with: if self.accel: try: ... except: pass
#
# 14. time.sleep_ms() takes milliseconds. time.sleep() takes seconds (float).
#     Always use sleep_ms() inside game loops to avoid accidental long sleeps.
#
# 15. ESP-NOW messages are limited to ~240 bytes. Use short strings.

# ═══════════════════════════════════════════════════════════════════
# 15. CHECKLIST FOR jumpin.py
# ═══════════════════════════════════════════════════════════════════
# The LLM agent generates or modifies ONLY jumpin.py.
# Before emitting the final file, verify every item:
#
# [ ] File is named jumpin.py — no other files are created or modified
# [ ] play() has exactly 6 parameters: (nfc, leds, buz, accel, i2c, enow)
# [ ] Module docstring shows play(nfc, leds, buz, accel, i2c, enow) — not 5 args
# [ ] No _read_tag_text / _decode_ndef_text — uses NfcReader instead
# [ ] _EXIT_TAGS = exit_tags_excluding("jumpin")  — always "jumpin"
# [ ] Game-specific tags unioned: COMMANDS = _EXIT_TAGS | {"your_tag"} if needed
# [ ] Game class is named JumpInGame (or similar) — not a generic name
# [ ] enow.poll() called every loop iteration; exits on "stop"/"start_game"
# [ ] NFC polled every NFC_POLL_INTERVAL frames; exits on cmd in _EXIT_TAGS
# [ ] leds.off() called in try/finally
# [ ] main() standalone harness present (import jumpin; jumpin.main())
# [ ] No f-strings anywhere in the file
# [ ] Colors imported from leds.py (RED, GREEN, etc.), not raw tuples
# [ ] Button: initial state read at __init__; debounce with sleep_ms(30)
# [ ] Accelerometer guarded with: if self.accel: try: ... except: pass
# [ ] Entry fanfare present in play() (buz.beep sequence)
# [ ] No ESPNowManager() instantiation inside jumpin.py
# [ ] % formatting used for all string interpolation (not f-strings)

