# ═══════════════════════════════════════════════════════════════════
# SPLAT COMPANION — knowledge base
# ═══════════════════════════════════════════════════════════════════
# The Splat Companion is an independent game station, like the icon
# display: a XIAO ESP32-C6 that runs games on a stock, unmodified Splat toy
# over BLE, and talks to the rest of the playground over ESP-NOW (through a
# paired modem board). It has a PN532 card reader (same wiring as the
# wand), a battery gauge, and a 3-pixel status strip. It has NO buzzer,
# motor or accelerometer, and NO 5x5 matrix -- do not treat `leds` as a
# wand's LED matrix.
#
# Between games the station does nothing on its own: a Splat press while no
# game is running plays nothing and sends nothing. Everything the Splat
# does comes from a game file for this station.
#
# A game that involves both a wand and the Splat Companion is TWO FILES --
# one per device, each in its own fenced block with its own [DEVICE:]
# marker. They are separate programs that talk over ESP-NOW. Never write
# one file with a mode switch, and never import one device's game from the
# other's.
#
#   [DEVICE: wand]   -> def play(nfc, leds, buz, accel, i2c, enow, batt=None)
#   [DEVICE: icon]   -> def play(nfc, panel, enow)
#   [DEVICE: splat]  -> def play(splat, leds, enow, batt=None)
#
# Everything in this file is about the Splat Companion half. The wand half
# is documented in knowledge.py.

# ═══════════════════════════════════════════════════════════════════
# 0. CRITICAL CONTRACT — READ FIRST
# ═══════════════════════════════════════════════════════════════════
# main.py ALWAYS calls a Splat Companion game with these positional
# arguments (batt may be omitted; an older 3-arg play() still runs):
#   play_func(splat, leds, enow, batt)
#
# REQUIRED signature (copy exactly):
#   def play(splat, leds, enow, batt=None):
#
# FORBIDDEN signatures (will crash at launch):
#   def play(leds, enow):                          # WRONG — missing splat
#   def play(nfc, leds, buz, accel, i2c, enow):    # WRONG — that is a wand
#   def play(nfc, panel, enow):                    # WRONG — that is the icon display
#
# Arguments:
#   splat — the Splat, over BLE. See section 1. NEVER construct BLE or an
#           ESPNowManager yourself; splat and enow are already built.
#   leds  — this device's 3-pixel status strip: leds.fill((r,g,b)),
#           leds.off(). Not a wand's 25-pixel matrix -- do not import
#           anything from the wand's leds.py or address individual pixels.
#   enow  — ESPNowManager, already initialized. Poll it EVERY loop
#           iteration. Never construct another one.
#   batt  — a MAX17048 gauge, or None if the gauge failed at boot. Guard
#           every use with `if batt is not None:`.
#
# This device has no NFC access inside a game (nfc is not one of the
# parameters) -- a game never reads cards itself. The station does it for
# the game: a stop card or another game's card tapped mid-game arrives
# through enow as "stop" or "start_game", exactly like the ESP-NOW
# messages. So returning on those two message types is all a game needs
# to exit on a card as well.
#
# No f-strings — they crash on this MicroPython build. Use % formatting.
# No type annotations. time.sleep_ms() is milliseconds; time.sleep() is
# seconds.

# ═══════════════════════════════════════════════════════════════════
# 1. THE SPLAT API
# ═══════════════════════════════════════════════════════════════════
# splat is a splat_api.SplatAPI. Every call is safe to make even when the
# Splat is not connected -- it returns False and prints, rather than
# raising, so a dropped BLE link never crashes a game.
#
#   splat.connected              True once the BLE link is up.
#   splat.poll()                 MUST be called every loop iteration --
#                                 it services the BLE link (reconnect,
#                                 keepalive, button debounce) and returns
#                                 "press", "release", or None.
#   splat.color(name)            solid color, e.g. splat.color("turnred")
#   splat.sound(name)             animal sound, e.g. splat.sound("cat")
#   splat.note(name)              one note, e.g. splat.note("note_c").
#                                 Replaces any note already held.
#   splat.play([names])          a group of names together (colors, a
#                                 sound and a note may all be named in one
#                                 call) -- one AND-group, same idea as a
#                                 wand action chain's inner list.
#   splat.off()                  stop everything: the held note, then
#                                 allTasksOff and allLEDsOff.
#
# Action names are the wand's action-card names. The full list for each
# call is appended to this prompt under "SPLAT ACTION NAMES ON THE SPLAT
# COMPANION" -- use only those. A Splat game naming anything else is
# refused before it is sent. (On the device an unknown name prints [ERR]
# and does nothing; it does not raise.)

# ═══════════════════════════════════════════════════════════════════
# 2. ESP-NOW — HOW THE WAND AND THE SPLAT COMPANION TALK
# ═══════════════════════════════════════════════════════════════════
# enow.poll() returns (msg_type, data, mac) and never blocks.
#
#   msg_type "stop" or "start_game"  -> RETURN from play() immediately.
#                                       This is how a game is switched out.
#   msg_type "raw"                   -> data is whatever the other device
#                                       broadcast, usually a dict.
#
# A wand tells this device something with a plain broadcast of a plain
# dict, same as with the icon display:
#
#   # in the wand's file
#   enow.broadcast({"type": "goal", "team": "green"})
#
#   # in the splat companion's file
#   msg_type, data, mac = enow.poll()
#   if msg_type == "raw" and isinstance(data, dict) and data.get("type") == "goal":
#       ...
#
# Keep the type name and the keys SHORT: an ESP-NOW message caps at about
# 240 bytes.
#
# This device can broadcast back the same way -- for example, reporting a
# score after a splat press:
#
#   ev = splat.poll()
#   if ev == "press":
#       enow.broadcast({"type": "score", "hit": True})
#
# Nothing relays Splat presses for you: a game that wants another device
# to know about a press must broadcast its own message, as above.

# ═══════════════════════════════════════════════════════════════════
# 3. CANONICAL TEMPLATE
# ═══════════════════════════════════════════════════════════════════
"""
Short title — one line on what the game does
================================================
<1-3 sentences describing what happens on the Splat.>

Entry point:
    play(splat, leds, enow, batt=None)  — called from main.py
"""

import time

IDLE_MS = 500


def play(splat, leds, enow, batt=None):
    print("\n  === YOUR GAME (splat companion) ===")
    try:
        leds.fill((10, 10, 10))
        while True:
            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if msg_type == "raw" and isinstance(data, dict):
                if data.get("type") == "yourmsg":
                    splat.color("turnblue")

            ev = splat.poll()
            if ev == "press":
                splat.play(["turngreen", "cat"])
                enow.broadcast({"type": "score", "hit": True})
            elif ev == "release":
                splat.off()

            time.sleep_ms(1)
    finally:
        splat.off()
        leds.off()


# ═══════════════════════════════════════════════════════════════════
# 4. CONSTRAINTS AND GOTCHAS
# ═══════════════════════════════════════════════════════════════════
# 1. No f-strings. Use % formatting: print("team %s" % team)
# 2. play() takes (splat, leds, enow, batt=None) -- batt may be omitted.
# 3. Do NOT create ubluetooth.BLE(), ESPNowManager() or a splat_link.SplatLink
#    inside a game. splat and enow are the only radio you get.
# 4. splat.poll() MUST run every iteration, exactly like enow.poll() --
#    skipping it drops button presses and lets the BLE link starve.
# 5. There is no NFC parameter. A game cannot read cards while it runs.
# 6. Do NOT register a callback on enow, or keep a reference to splat,
#    leds or enow in a module-level name. A game is imported and unloaded
#    on every play; a retained reference pins the whole module in RAM.
# 7. Always call splat.off() in a finally block, so a game that exits
#    mid-note or mid-color does not leave the Splat lit or sounding.
# 8. ESP-NOW messages cap at ~240 bytes. Short type names, short keys.
# 9. time.sleep_ms(1) every loop iteration, minimum -- the BLE driver
#    needs it serviced promptly.

# ═══════════════════════════════════════════════════════════════════
# 5. CHECKLIST
# ═══════════════════════════════════════════════════════════════════
# [ ] The block is preceded by [DEVICE: splat]
# [ ] play() has (splat, leds, enow, batt=None)
# [ ] splat.poll() and enow.poll() both run every loop iteration
# [ ] Every action name used is one of the card names in section 1
# [ ] Every batt use is guarded with `if batt is not None:`
# [ ] splat.off() runs in a finally block
# [ ] No f-strings
# [ ] The game returns on enow "stop" or "start_game" (cards arrive that way too)
