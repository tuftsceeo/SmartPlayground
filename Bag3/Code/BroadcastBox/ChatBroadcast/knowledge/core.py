# SmartPlayground — core contract for LLM game code generation
# ============================================================
# This file is always in context. One device file per reply is loaded
# alongside it (wand.py, icon_station.py, ...) and describes the hardware
# that device actually has. Generate code only for the devices whose file
# you were given.
#
# Games run on MicroPython v1.27.0 on ESP32-C6 boards.
#
# ═══════════════════════════════════════════════════════════════════
# 0. WHAT A GAME IS
# ═══════════════════════════════════════════════════════════════════
# A game is not one file sent to every device. It is one file per ROLE,
# and each device runs the file for the role it was given:
#
#     tagchase_wand.py    what a wand does
#     tagchase_icon.py    what the icon display does
#
# The file name is <slug> for a single-device game, or <slug>_<role> for
# one role of a multi-device game. Naming rules, enforced on the device:
#
#     slug   lowercase letters and digits, starts with a letter, NO
#            underscore, at most 14 characters      e.g. tagchase
#     role   lowercase letters, digits, underscore, starts with a
#            letter, at most 9 characters           e.g. wand, icon, teama
#     whole module name at most 24 characters
#
# Every role file has the same entry point and the same shape:
#
#     def play(dev):
#         while dev.running():
#             ev = dev.event()
#             ...
#             dev.tick(20)
#
# ═══════════════════════════════════════════════════════════════════
# 1. REPLY FORMAT
# ═══════════════════════════════════════════════════════════════════
# Emit one fenced python code block per role, each immediately preceded
# by a role marker on its own line:
#
#     [ROLE: wand wand]
#     ```python
#     ...
#     ```
#     [ROLE: icon icon_station]
#     ```python
#     ...
#     ```
#
# The marker is [ROLE: <role> <hubtype>]. The hubtype names the kind of
# device that runs the file, and must be one you were given a device file
# for. A single-device game still gets one marker.
#
# After the code blocks, emit exactly one game-name marker — short,
# human-readable, no file extension:
#
#     [GAME_NAME: Tag Chase]
#
# The app slugifies it; the teacher may edit the pretty name before
# sending.
#
# If the game reads named NFC cards during play, list them:
#
#     [NFC_CARDS: red, green, blue]
#
# List only cards the game itself reads. The framework already handles
# the stop card and every other game's launch card.
#
# ═══════════════════════════════════════════════════════════════════
# 2. THE DEVICE OBJECT
# ═══════════════════════════════════════════════════════════════════
# play(dev) receives one argument. Everything the game touches hangs off
# it. Which hardware attributes exist depends on the device — see the
# device file you were given.
#
# ── The loop ────────────────────────────────────────────────────────
# dev.running() → bool
#     Call it as the while condition and nothing else. It services the
#     radio, the card reader and the station hardware, and returns False
#     when the game must end: a stop card or a stop broadcast, another
#     game's card, or a start broadcast naming a different game. A loop
#     that does not call it cannot be stopped.
#
# dev.event() → (name, data, mac) or None
#     The next thing that happened, or None. Call it once per pass and
#     act on what comes back; events queue, so a slow loop does not lose
#     any. See section 3 for what arrives.
#
# dev.tick(ms=20)
#     Per-frame sleep. Always call it once per pass: it is what lets the
#     serial link and the radio breathe. Use time.sleep_ms() only inside
#     a short deliberate effect, never as the loop's own pacing.
#
# dev.stop()
#     End the game from inside it, e.g. when a round is won.
#
# ── Identity ────────────────────────────────────────────────────────
# dev.slug   the game's slug, e.g. "tagchase"
# dev.role   this device's role, e.g. "wand", or None for a single-role
#            game
# dev.net    the ESP-NOW manager (section 3)
#
# ═══════════════════════════════════════════════════════════════════
# 3. TALKING TO OTHER DEVICES
# ═══════════════════════════════════════════════════════════════════
# Three kinds of message travel over ESP-NOW. The framework sends and
# receives the first kind for you; a game only ever uses the other two.
#
#   sys   framework business: stop, start, who/here, battery. Handled by
#         dev.running(). Never send one from a game.
#   cap   a command to a station, addressed by hubtype, not by MAC.
#   evt   anything a device reports. Every game device hears it.
#
# ── Commanding a station ────────────────────────────────────────────
# dev.net.broadcast_cap(hubtype, op, args=None)
#
#     dev.net.broadcast_cap("icon_station", "icon", {"n": "tree"})
#
# Every station of that hubtype acts on it. The station's own verbs are
# listed in its device file. A station's role file does not need this:
# it drives its own hardware directly (dev.icon.show("tree")).
#
# ── Reporting something ─────────────────────────────────────────────
# dev.net.broadcast_evt(name, data=None, slug=dev.slug)
#
#     dev.net.broadcast_evt("goal", {"team": "a"}, slug=dev.slug)
#
# Always pass slug=dev.slug. It is what keeps one game's events out of
# another's. Every other device running the same game receives it from
# dev.event() as:
#
#     ("goal", {"team": "a"}, mac)
#
# mac is the sender's address, so a device can tell who reported.
#
# ── Events a game receives ──────────────────────────────────────────
# ("tag", "<card text>", uid)   a card this game reads was tapped. uid is
#                               the physical card's id, so two cards with
#                               the same text are still distinguishable.
# ("<name>", data, mac)         an evt another device broadcast.
#
# Choose short event names. An ESP-NOW message is limited to ~240 bytes.
#
# ═══════════════════════════════════════════════════════════════════
# 4. MICROPYTHON CONSTRAINTS
# ═══════════════════════════════════════════════════════════════════
# 1. f-strings CRASH on this build. Use % formatting only:
#        print("score = %d" % score)
# 2. No type annotations.
# 3. time.sleep_ms() takes milliseconds; time.sleep() takes seconds.
# 4. RAM is ~512KB. Avoid large allocations. A game is imported when it
#    starts and unloaded when it ends, so module-level state is fresh
#    each run, but keep tables small.
# 5. Do NOT create an ESPNowManager or touch network.WLAN. The radio is
#    already up; use dev.net.
# 6. Do NOT write or import main.py, boot.py or any library file. One
#    role file per device, nothing else.
# 7. Catch nothing you cannot handle. A game that swallows an error
#    leaves a device that looks alive and does nothing; a traceback on
#    the serial console is what gets a bug fixed.
#
# Standard modules available: machine, time, math, random, json, struct,
# sys, gc, _thread, neopixel.
#
# ═══════════════════════════════════════════════════════════════════
# 5. SHAPE OF A ROLE FILE
# ═══════════════════════════════════════════════════════════════════
# """
# Tag Chase — wand
# ================
# <1-3 sentences describing what this device does in the game.>
#
# Entry point:
#     play(dev)
# """
#
# LOOP_MS = 20
#
#
# def play(dev):
#     # set up state here
#     while dev.running():
#         ev = dev.event()
#         if ev and ev[0] == "tag":
#             pass          # a card was tapped: ev[1] is its text
#         # read inputs, drive outputs
#         dev.tick(LOOP_MS)
#
# No try/finally, no stop-tag table, no exit check of your own: the
# framework restores the outputs when play() returns and dev.running()
# is the only exit check a game needs.
