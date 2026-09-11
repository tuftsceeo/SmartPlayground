# SmartPlayground — ICON DISPLAY STATION (hubtype: icon_station)
# ==============================================================
# Read core.py first; this file adds only what the icon display has.
#
# A 16x16 full-colour panel that shows one named icon at a time. It has
# no button, no accelerometer and no card reader: a wand drives it, or
# its own role file reacts to what wands report.
#
# ═══════════════════════════════════════════════════════════════════
# I1. WHAT THE STATION GIVES YOU
# ═══════════════════════════════════════════════════════════════════
# dev.icon    the panel (section I2)
# dev.matrix  the raw 16x16 frame buffer, for a game that draws its own
#             pixels rather than showing a stored icon (section I4)
#
# There is no dev.leds, dev.buz, dev.accel, dev.button or dev.nfc on this
# device. Code that touches them fails at the first pass.
#
# ═══════════════════════════════════════════════════════════════════
# I2. THE PANEL
# ═══════════════════════════════════════════════════════════════════
# dev.icon.show(name)
#     Draw a stored icon by name, e.g. dev.icon.show("tree"). Raises if
#     no icon of that name is on the station, so name only icons the
#     game ships (section I5).
#
# dev.icon.off()
#     Blank the panel and stop any cycle.
#
# dev.icon.cycle(names, hold_ms)
#     Step through a list of icons, hold_ms apart, advancing on its own
#     while the game loop runs. dev.icon.show() or dev.icon.off() ends it.
#
# dev.icon.matrix.set_intensity(v)
#     0.0 to 0.50. The panel clamps at 0.50: at full brightness 256
#     pixels draw more current than the supply allows. After changing it,
#     dev.icon.matrix.redraw() repaints the current frame.
#
# ═══════════════════════════════════════════════════════════════════
# I3. WHAT A WAND SENDS IT
# ═══════════════════════════════════════════════════════════════════
# A wand with no station role file of its own can still drive the panel,
# by addressing the hubtype:
#
#     dev.net.broadcast_cap("icon_station", "icon",  {"n": "tree"})
#     dev.net.broadcast_cap("icon_station", "clear")
#     dev.net.broadcast_cap("icon_station", "bright", {"v": 0.3})
#     dev.net.broadcast_cap("icon_station", "cycle", {"names": ["a", "b"],
#                                                     "ms": 800})
#
# The framework handles these; the station's role file never sees them.
# Use this when the display only mirrors what one wand decides.
#
# Give the station a role file instead when the display has logic of its
# own — a score, a first-to-tap race, a state machine. Then the wands
# report with broadcast_evt and the station's play(dev) decides:
#
#     wand:     dev.net.broadcast_evt("goal", {"team": "a"}, slug=dev.slug)
#     station:  ev = dev.event()
#               if ev and ev[0] == "goal":
#                   dev.icon.show(ICONS[ev[1]["team"]])
#
# ═══════════════════════════════════════════════════════════════════
# I4. DRAWING PIXELS DIRECTLY
# ═══════════════════════════════════════════════════════════════════
# Only when a named icon will not do. The panel is 16 wide, 16 high,
# origin top-left, and a pixel is addressed by index:
#
#     index = row * 16 + col          row 0 is the top, col 0 the left
#
#     dev.matrix.set_pixels([(idx, r, g, b), ...])   draw these pixels
#     dev.matrix.clear()                             blank the panel
#
# set_pixels draws immediately, so pass every pixel that changes in one
# call rather than calling it per pixel. Colours are 0-255 per channel and
# are scaled by the intensity setting before they reach the strip.
#
# ═══════════════════════════════════════════════════════════════════
# I5. SHIPPING ICONS WITH A GAME
# ═══════════════════════════════════════════════════════════════════
# Any icon a role file names must travel with the game. Emit one icon
# block per icon, after the code blocks, marked with its name:
#
#     [ICON: tree]
#     ```json
#     {"w": 16, "h": 16, "px": [[0,0,0], [0,0,0], ... ]}
#     ```
#
# px is 256 [r, g, b] triples, row by row from the top-left. Each channel
# is 0-255. Keep icons bold and flat: at 16x16 across a room, a silhouette
# in two or three colours reads and a detailed picture does not.
#
# An icon name is lowercase letters, digits and underscore, does not start
# with a digit, and is at most 24 characters.
#
# Icons already on the station can be named without shipping them. The
# app tells you which ones it has; if it has not said, ship what you use.
#
# ═══════════════════════════════════════════════════════════════════
# I6. STATION ROLE FILE TEMPLATE
# ═══════════════════════════════════════════════════════════════════
# """
# Tag Chase — icon display
# ========================
# Shows the creature of whichever team last scored.
#
# Entry point:
#     play(dev)
# """
#
# LOOP_MS = 20
#
# CREATURES = {"a": "tree", "b": "whale"}
#
#
# def play(dev):
#     dev.icon.show("start")
#     while dev.running():
#         ev = dev.event()
#         if ev and ev[0] == "score":
#             team = ev[1].get("c")
#             if team in CREATURES:
#                 dev.icon.show(CREATURES[team])
#         dev.tick(LOOP_MS)
#
# ═══════════════════════════════════════════════════════════════════
# I7. CHECKLIST BEFORE YOU ANSWER
# ═══════════════════════════════════════════════════════════════════
#  - def play(dev); while dev.running(); dev.tick(ms) once per pass
#  - only dev.icon and dev.matrix — this device has no other hardware
#  - every icon the file names is either shipped in an [ICON:] block or
#    already on the station
#  - event names and data keys match what the wand file broadcasts
#  - [ROLE: <role> icon_station] before the block
