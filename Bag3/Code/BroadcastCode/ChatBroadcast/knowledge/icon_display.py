# ═══════════════════════════════════════════════════════════════════
# ICON DISPLAY — knowledge base
# ═══════════════════════════════════════════════════════════════════
# The icon display is a 16x16 WS2812B panel (256 pixels) on a XIAO
# ESP32-C6. It is a SHARED OUTPUT: one big picture a whole class can see
# from across a room. It has no buzzer, no accelerometer and no button.
#
# A game that involves both a wand and the display is TWO FILES — one per
# device, each in its own fenced block with its own [DEVICE:] marker. They
# are separate programs that talk over ESP-NOW. Never write one file with a
# mode switch, and never import one device's game from the other's.
#
#   [DEVICE: wand]   -> def play(nfc, leds, buz, accel, i2c, enow, batt=None)
#   [DEVICE: icon]   -> def play(nfc, panel, enow)
#
# Everything in this file is about the icon-display half. The wand half is
# documented in knowledge.py.

# ═══════════════════════════════════════════════════════════════════
# 0. CRITICAL CONTRACT — READ FIRST
# ═══════════════════════════════════════════════════════════════════
# main.py ALWAYS calls an icon display game with exactly 3 positional
# arguments:
#   play_func(nfc, panel, enow)
#
# REQUIRED signature (copy exactly):
#   def play(nfc, panel, enow):
#
# FORBIDDEN signatures (will crash at launch):
#   def play(panel, enow):                        # WRONG — missing nfc
#   def play(nfc, leds, buz, accel, i2c, enow):   # WRONG — that is a wand
#
# Arguments:
#   nfc   — an NfcReader, ALREADY BUILT, or None while no card reader is
#           fitted. Note this differs from a wand game, which is handed the
#           raw PN532 and builds its own reader. Always guard with
#           `if nfc is not None:` before calling it.
#   panel — the Matrix (icon_matrix.py). Draws the 16x16 picture.
#   enow  — ESPNowManager, already initialized. Poll it EVERY loop
#           iteration. Never construct another one.
#
# No f-strings — they crash on this MicroPython build. Use % formatting.
# No type annotations. time.sleep_ms() is milliseconds; time.sleep() is
# seconds.

# ═══════════════════════════════════════════════════════════════════
# 1. THE PANEL API
# ═══════════════════════════════════════════════════════════════════
# panel is an icon_matrix.Matrix:
#
#   panel.set_intensity(v)      0.0-0.50. Rebuilds the brightness LUT.
#   panel.draw_bytes(src)       src is 768 bytes: 256 (r,g,b) triples,
#                               row-major from the TOP-LEFT. Pushes to the
#                               strip.
#   panel.set_pixels(triples)   sparse update; triples is an iterable of
#                               (index, r, g, b) with index 0..255.
#   panel.clear()               all pixels off.
#   panel.redraw()              re-apply the last frame at the current
#                               intensity (after set_intensity).
#   panel.src                   the cached 768-byte frame. Use it as your
#                               scratch buffer rather than allocating one.
#
# Pixel index from a column and row, both 0..15, counting from the top-left:
#   idx = row * 16 + col
# The panel's physical wiring is serpentine and possibly mirrored, but
# Matrix already folds that in — always address it as plain row-major.
#
# MAX_INTENSITY = 0.50 is a MEASURED SUPPLY CEILING, not a preference: 256
# pixels at full brightness exceed the driver board. set_intensity() clamps
# to it. Static content that sits lit for a whole session should run well
# under it (0.10-0.15); save 0.25-0.35 for a moment that must carry.

# ═══════════════════════════════════════════════════════════════════
# 2. NAMED ICONS
# ═══════════════════════════════════════════════════════════════════
# Pictures are stored on the device as icons/<name>.py and loaded by name.
# Do NOT paste pixel data into a game — refer to an icon by name and the app
# sends the file alongside the game.
#
#   import icon_store
#   icon_store.read_icon("whale", into=panel.src)
#   panel.draw_bytes(panel.src)
#
# read_icon() raises if the icon is missing or malformed. Let it raise: a
# display that looks alive and shows nothing is the hardest failure to
# diagnose from across a room.
#
# Icon names: lowercase letters, digits and underscore, not starting with a
# digit, 24 characters or fewer.
#
# Only refer to icons that exist. The app checks every name a game uses
# before it sends, and refuses rather than shipping a blank.

# ═══════════════════════════════════════════════════════════════════
# 3. ESP-NOW — HOW THE TWO DEVICES TALK
# ═══════════════════════════════════════════════════════════════════
# enow.poll() returns (msg_type, data, mac) and never blocks.
#
#   msg_type "stop" or "start_game"  -> RETURN from play() immediately.
#                                       This is how a game is switched out.
#   msg_type "raw"                   -> data is whatever the other device
#                                       broadcast, usually a dict.
#
# A wand tells the display something with a plain broadcast of a plain dict.
# There is no message class to register and no protocol to extend:
#
#   # in the wand's file
#   enow.broadcast({"type": "goal", "team": "green"})
#
#   # in the display's file
#   msg_type, data, mac = enow.poll()
#   if msg_type == "raw" and isinstance(data, dict) and data.get("type") == "goal":
#       ...
#
# Keep the type name and the keys SHORT: an ESP-NOW message caps at about
# 240 bytes.
#
# The display can answer the same way, with enow.broadcast(...), so wands
# can react to what it decided.

# ═══════════════════════════════════════════════════════════════════
# 4. CARDS
# ═══════════════════════════════════════════════════════════════════
# The display reads cards only to LEAVE a game; rounds are driven over
# ESP-NOW. Declare the cards a game reads as string literals in a
# module-level COMMANDS set — four separate consumers read that set
# statically, without running the game:
#
#   from display_tags import exit_tags_excluding
#   _EXIT_TAGS = exit_tags_excluding("yourgame")
#   COMMANDS = _EXIT_TAGS
#
# A card read takes 200-500 ms, so poll every 10-15 frames, never every
# frame, or the loop stalls:
#
#   if nfc is not None and frame % 12 == 0:
#       cmd, uid = nfc.read_command(timeout=100)
#       if cmd in _EXIT_TAGS:
#           return

# ═══════════════════════════════════════════════════════════════════
# 5. CANONICAL TEMPLATE
# ═══════════════════════════════════════════════════════════════════
"""
Short title — one line on what the display shows
================================================
<1-3 sentences describing what a class sees.>

Entry point:
    play(nfc, panel, enow)  — called from main.py
"""

import time

from display_tags import exit_tags_excluding
import icon_store

_EXIT_TAGS = exit_tags_excluding("yourgame")

COMMANDS = _EXIT_TAGS

IDLE_ICON = "ready"
IDLE_INTENSITY = 0.12
ACTIVE_INTENSITY = 0.30
NFC_POLL_FRAMES = 12
LOOP_DELAY_MS = 40


def _show(panel, name, intensity):
    panel.set_intensity(intensity)
    icon_store.read_icon(name, into=panel.src)
    panel.draw_bytes(panel.src)


def play(nfc, panel, enow):
    print("\n  === YOUR GAME (display) ===")
    frame = 0
    try:
        _show(panel, IDLE_ICON, IDLE_INTENSITY)
        while True:
            frame += 1

            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if msg_type == "raw" and isinstance(data, dict):
                if data.get("type") == "yourmsg":
                    _show(panel, "whale", ACTIVE_INTENSITY)

            if nfc is not None and frame % NFC_POLL_FRAMES == 0:
                cmd, _uid = nfc.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return

            time.sleep_ms(LOOP_DELAY_MS)
    finally:
        panel.clear()


# ═══════════════════════════════════════════════════════════════════
# 6. CONSTRAINTS AND GOTCHAS
# ═══════════════════════════════════════════════════════════════════
# 1. No f-strings. Use % formatting: print("team %s" % team)
# 2. play() takes exactly 3 parameters: (nfc, panel, enow)
# 3. Do NOT create ESPNowManager() or touch network.WLAN inside a game.
# 4. Do NOT import icon_matrix and build your own Matrix — the panel you
#    are given is the only one. Two NeoPixel objects on the same pin fight.
# 5. Poll enow EVERY iteration. A game that does not is unswitchable.
# 6. Do NOT register a callback on enow or keep a reference to panel, nfc or
#    enow in a module-level name. A game is imported and unloaded on every
#    play; a retained reference pins the whole module in RAM.
# 7. Always clear the panel in a finally block.
# 8. Keep the loop delay around 40 ms. The panel does not need to be
#    redrawn every frame — draw when something changed.
# 9. ESP-NOW messages cap at ~240 bytes. Short type names, short keys.
# 10. Refer to icons by name only, and only to names that exist.

# ═══════════════════════════════════════════════════════════════════
# 7. CHECKLIST
# ═══════════════════════════════════════════════════════════════════
# [ ] The block is preceded by [DEVICE: icon]
# [ ] play() has exactly 3 parameters: (nfc, panel, enow)
# [ ] enow.poll() runs every loop iteration and returns on stop/start_game
# [ ] Every nfc use is guarded with `if nfc is not None:`
# [ ] Every icon named actually exists
# [ ] set_intensity never asked for more than 0.50
# [ ] panel.clear() in a finally block
# [ ] No f-strings
