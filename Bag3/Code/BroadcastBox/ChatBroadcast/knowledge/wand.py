# SmartPlayground — WAND (hubtype: wand)
# =====================================
# Read core.py first; this file adds only what a wand has. A wand role
# file is `def play(dev)` and nothing else.
#
# ═══════════════════════════════════════════════════════════════════
# W1. WHAT A WAND GIVES YOU
# ═══════════════════════════════════════════════════════════════════
# dev.leds    Leds — the 5x5 face (section W4)
# dev.buz     Buzzer (section W5)
# dev.accel   LIS2DW12 accelerometer, or None if it failed to start
# dev.button  machine.Pin on GPIO0, active LOW: pressed is value() == 0
# dev.motor   machine.Pin on GPIO21, vibration: value(1) on, value(0) off
# dev.nfc     PN532 driver. A game does NOT read it directly — tapped
#             cards arrive as ("tag", text, uid) events.
# dev.batt    MAX17048 fuel gauge, or absent
# dev.i2c     the shared SoftI2C bus
#
# dev.nfc_every = N
#     How many loop passes between card reads. The default is 15. A game
#     played by tapping cards should set it to 3-5 at the top of play();
#     reading every pass starves the rest of the loop.
#
# ═══════════════════════════════════════════════════════════════════
# W2. HARDWARE
# ═══════════════════════════════════════════════════════════════════
# Board: Seeed XIAO ESP32-C6 (RISC-V 160MHz, 4MB flash, 512KB SRAM), 3.3V
#
#   GPIO0  (D0)  Button (active LOW, internal pull-up; also the boot pin)
#   GPIO1  (D1)  Accelerometer INT1
#   GPIO2  (D2)  Accelerometer INT2 — routed but does not fire, unusable
#   GPIO19 (D8)  Buzzer (piezo, PWM)
#   GPIO20 (D9)  NeoPixel data (25x SK6812)
#   GPIO21 (D3)  Vibration motor
#   GPIO22 (D4)  I2C SDA — shared bus, locked at 100kHz
#   GPIO23 (D5)  I2C SCL
#
# I2C devices (100kHz; the PN532 fails at 400kHz — never change the freq):
#   0x24 PN532 NFC reader     0x19 LIS2DW12 accelerometer
#   0x36 MAX17048 fuel gauge  0x44 OPT3002 ambient light sensor
#
# LED layout: 25 LEDs in a 5x5 grid, index = row * 5 + col
#   [ 0  1  2  3  4]  <- top row
#   [ 5  6  7  8  9]
#   [10 11 12 13 14]
#   [15 16 17 18 19]
#   [20 21 22 23 24]  <- bottom row
#
# The strip is GRB, but the Leds class takes (R, G, B) and converts.
#
# ═══════════════════════════════════════════════════════════════════
# W3. EVERYDAY WORDS → WAND API
# ═══════════════════════════════════════════════════════════════════
# "turn red" / "light up red"      dev.leds.fill(RED)
# "turn off" / "go dark"           dev.leds.off()
# "flash" / "blink"                dev.leds.flash_color(RED)
# "show a heart"                   dev.leds.show_shape(SHAPE_HEART, RED)
# "show a smiley"                  dev.leds.show_shape(SHAPE_HAPPY_FACE, YELLOW)
# "show a star"                    dev.leds.show_shape(SHAPE_STAR, YELLOW)
# "show an arrow up"               dev.leds.show_shape(SHAPE_ARROW_UP, WHITE)
# "show the number 3"              dev.leds.show_shape(SHAPE_3, GREEN)
# "rainbow"                        cycle a colour list on (frame // N) % len
# "pulse" / "breathe"              dev.leds.breathe(130, 0, 0, frame)
# "spin"                           dev.leds.animate_spin(frame, BLUE)
# "dancing"                        dev.leds.animate_dancer(frame, PURPLE)
# "firework"                       dev.leds.animate_firework(frame, ORANGE)
# "beep" / "make a sound"          dev.buz.beep(1000, 200)
# "happy sound" / "you win"        dev.buz.confirm() or dev.buz.melody()
# "wrong sound"                    dev.buz.reject()
# "press the button"               dev.button.value() == 0
# "vibrate" / "rumble"             dev.motor.value(1); time.sleep_ms(150); dev.motor.value(0)
# "shake it"                       magnitude > 1.4 (section W6)
# "jump"                           magnitude < 0.3 (freefall)
# "tap a card"                     ev = dev.event(); ev[0] == "tag"
# "tell the display to show X"     dev.net.broadcast_cap("icon_station", "icon", {"n": "X"})
# "tell the other wands"           dev.net.broadcast_evt("name", data, slug=dev.slug)
#
# ═══════════════════════════════════════════════════════════════════
# W4. LED API
# ═══════════════════════════════════════════════════════════════════
# Import the constants; the Leds object itself is dev.leds.
#   from leds import RED, GREEN, SHAPE_HEART, ...
# Every colour is auto-scaled by ambient brightness, so use the named
# constants rather than raw RGB tuples.
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
# dev.leds.off()
#     Turn all 25 LEDs off.
#
# dev.leds.fill(color)
#     Fill all LEDs with a color tuple. e.g. leds.fill(RED)
#
# dev.leds.solid(r, g, b)
#     Fill all LEDs with explicit r/g/b values. e.g. leds.solid(130, 0, 0)
#
# dev.leds.flash(r, g, b, times=2, on_ms=120, off_ms=80)
#     Flash all LEDs N times (blocking).
#
# dev.leds.flash_color(color, times=2, on_ms=120, off_ms=80)
#     Flash a color tuple N times (blocking). e.g. leds.flash_color(RED, 3)
#
# dev.leds.show_shape(indices, color, bg=OFF)
#     Light specific LEDs (indices tuple) in color; all others in bg.
#     e.g. leds.show_shape(SHAPE_HEART, RED)
#     e.g. leds.show_shape(SHAPE_HEART, RED, bg=WHITE_DIM)
#
# dev.leds.show_pattern(color_to_indices_dict, bg=OFF)
#     Light multiple groups in different colors.
#     e.g. leds.show_pattern({RED: (0,4), YELLOW: (12,), GREEN: (20,24)})
#
# dev.leds.breathe(r, g, b, frame)
#     Breathing brightness on all LEDs, driven by frame counter.
#     Call each loop iteration. ~3s cycle at 40ms loop.
#
# dev.leds.breathe_shape(indices, color, frame, bg=OFF, speed=0.08, min_level=2)
#     Breathing animation on a shape only.
#     e.g. leds.breathe_shape(SHAPE_HEART, RED, self._frame)
#
# dev.leds.pulse_color(r, g, b, duration_ms=600)
#     Single sine pulse from full brightness to off (blocking).
#
# dev.leds.fade_shape(indices, color, duration_ms, bg=OFF)
#     Linear fade from color to bg over duration_ms (blocking, ~20 steps).
#
# dev.dev.leds.np[i] = (r, g, b)   — set individual LED (auto-scaled)
# dev.dev.leds.np.write()            — push all np[] changes to hardware
# dev.leds.num                   — total LED count (25 on wand)
#
# ── ANIMATION METHODS (call each frame with self._frame) ────────────
# All accept (frame, color, bg=OFF, frames_per_step=6).
# Larger frames_per_step = slower animation.
#
# dev.leds.animate_dancer(frame, color)
#     Cycle DANCER1→DANCER2→DANCER3→DANCER2 (dancing figure).
#
# dev.leds.animate_rows(frame, color)
#     Sweep rows top→bottom: TOP_ROW, ROW2, ROW3, ROW4, BOT_ROW.
#
# dev.leds.animate_columns(frame, color)
#     Sweep columns left→right.
#
# dev.leds.animate_spin(frame, color)
#     Rotating bar through center: ROW3, SLASH_L, COL3, SLASH_R.
#
# dev.leds.animate_grow(frame, color)
#     Expand outward: CENTER → INNER_3x3 → BORDER → blank.
#
# dev.leds.animate_shrink(frame, color)
#     Contract inward: BORDER → INNER_3x3 → CENTER → blank.
#
# dev.leds.animate_arrow_spin(frame, color)
#     Rotate arrow direction: UP → LEFT → DOWN → RIGHT.
#
# dev.leds.animate_firework(frame, color)
#     Burst: CENTER → STAR → CORNERS → blank.

# =================================================================
# W5. BUZZER API
# =================================================================
# dev.buz.beep(freq=1000, ms=100)
#     Single tone at freq Hz for ms milliseconds (blocking).
#     Common frequencies: 262=C4, 330=E4, 392=G4, 440=A4, 523=C5,
#                         659=E5, 784=G5, 1047=C6
#
# dev.buz.play_note(freq, ms=400)
#     Alias for beep with longer default duration.
#
# dev.buz.melody()
#     Short ascending melody: C5-E5-G5-C6 (~800ms, blocking).
#
# dev.buz.confirm()   — two rising tones (tag accepted / correct answer)
# dev.buz.start()     — three rising tones (entering a mode)
# dev.buz.stop()      — descending tone (stopping / exiting)
# dev.buz.reject()    — double low tone (wrong / invalid)
# dev.buz.warn()      — single low tone (warning)
#
# NOTE_FREQ dict (4th octave):
#   notec=262  noted=294  notee=330  notef=349
#   noteg=392  notea=440  noteb=494  notechigh=523
#
# Custom sequence pattern (used by jump.py):
#   for freq, dur, gap in [(523,80,40),(659,80,40),(784,120,0)]:
#       dev.buz.beep(freq, dur)
#       if gap: time.sleep_ms(gap)
#
# Sound design rule:
#   - Each game MUST have a unique entry fanfare (different from all others)
#   - Victory / correct → buz.confirm() or buz.melody()
#   - Wrong / miss → buz.reject()
#   - Exit / stop → buz.stop()
# ═══════════════════════════════════════════════════════════════════
# W6. CARDS
# ═══════════════════════════════════════════════════════════════════
# A game does not touch dev.nfc and does not keep a list of exit cards.
# The framework reads the reader, handles stop and every other game's
# launch card itself, and hands the game only the cards the game reads:
#
#     ev = dev.event()
#     if ev and ev[0] == "tag":
#         text = ev[1]      # the card's text, e.g. "red"
#         uid  = ev[2]      # the physical card's id
#
# A card left sitting on the reader is reported once, not repeatedly.
#
# Name the cards in the [NFC_CARDS:] marker so the teacher is told which
# cards to write. Do not use a card named after another game.
#
# ═══════════════════════════════════════════════════════════════════
# W7. ACCELEROMETER
# ═══════════════════════════════════════════════════════════════════
# dev.accel may be None. Guard on it, then read:
#
#     if dev.accel:
#         x, y, z = dev.accel.read()            # g units
#         magnitude = math.sqrt(x*x + y*y + z*z)
#
# Motion thresholds:
#   magnitude > 1.4   shake or hit
#   magnitude < 0.3   freefall / jump
#
# Orientation, as the shipped ice cream games use it (sign to confirm on
# hardware):
#   x > +0.7    upright, tip up
#   x < -0.7    inverted, handle up
#   |y| > 0.5   tilted to one side
#   |z| > 0.8   lying face up or back up
#
# Axes: x is along the wand, y is side to side, z is front to back.
#
# ═══════════════════════════════════════════════════════════════════
# W8. BUTTON
# ═══════════════════════════════════════════════════════════════════
# dev.button is already built. Active LOW: pressed is value() == 0.
#
# Hold-to-act needs no edge detection:
#     if dev.button.value() == 0:
#         dev.leds.fill(RED)
#     else:
#         dev.leds.off()
#
# Act-once-per-press does:
#     was_down = (dev.button.value() == 0)
#     ...
#     down = (dev.button.value() == 0)
#     if down and not was_down:
#         pass          # press
#     was_down = down
#
# Snapshot the initial state before the loop, or a button held at launch
# reads as a phantom press.
#
# ═══════════════════════════════════════════════════════════════════
# W9. OTHER LIBRARIES ON A WAND
# ═══════════════════════════════════════════════════════════════════
# from leds import RED, GREEN, SHAPE_HEART, ...   colours and shapes
# from buzzer import NOTE_FREQ                    note name -> Hz
# from actions import ActionRunner, ACTIONS       named action chains
#   ActionRunner(dev.leds, dev.buz).run_action("turnred")
#   ACTIONS = {"playnote","turnred","turnblue","turngreen","turnpurple",
#              "turnwhite","turnyellow","turnoff","notea".."noteg"}
# from battery import show_battery                show_battery(dev.batt, dev.leds, dev.buz)
#
# ═══════════════════════════════════════════════════════════════════
# W10. WAND ROLE FILE TEMPLATE
# ═══════════════════════════════════════════════════════════════════
# """
# Tag Chase — wand
# ================
# Tap a colour card to pick your team, then press the button to score.
#
# Entry point:
#     play(dev)
# """
#
# import math
#
# from leds import RED, GREEN, BLUE, OFF, SHAPE_STAR
#
# LOOP_MS = 20
# NFC_EVERY = 5
#
# TEAMS = {"red": RED, "green": GREEN, "blue": BLUE}
#
#
# def play(dev):
#     dev.nfc_every = NFC_EVERY
#     dev.buz.start()
#     color = OFF
#     was_down = (dev.button.value() == 0)
#
#     while dev.running():
#         ev = dev.event()
#         if ev and ev[0] == "tag" and ev[1] in TEAMS:
#             color = TEAMS[ev[1]]
#             dev.leds.fill(color)
#             dev.buz.confirm()
#
#         down = (dev.button.value() == 0)
#         if down and not was_down and color != OFF:
#             dev.leds.show_shape(SHAPE_STAR, color)
#             dev.net.broadcast_evt("score", {"c": "red"}, slug=dev.slug)
#         was_down = down
#
#         dev.tick(LOOP_MS)
#
# ═══════════════════════════════════════════════════════════════════
# W11. CHECKLIST BEFORE YOU ANSWER
# ═══════════════════════════════════════════════════════════════════
#  - def play(dev), one role file, no main.py or library edits
#  - while dev.running() is the loop condition
#  - dev.tick(ms) called once per pass
#  - no try/finally, no exit-tag table, no enow.poll()
#  - no f-strings; % formatting only
#  - colours and shapes imported from leds, not raw RGB tuples
#  - a [ROLE: ...] marker before each block, then [GAME_NAME: ...]
#  - [NFC_CARDS: ...] if the game reads cards
