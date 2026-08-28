# Bag3/AGENTS.md — Wand module firmware

Hardware is in flux and new boards are on order. Treat any hardware detail as possibly stale.

## Current hardware config

`Bag3/Code/lib/hubtype.py` is the live source for pin maps, LED geometry, and I2C addresses — read it
rather than relying on documentation, and ask if the code and the board in front of you disagree.

A 5×5 + PN532 @ 0x24 variant was explored on `origin/claude/pn532-5x5` and not merged.

## `Wand Module/readme.md` and `GAME_AUTHORING_GUIDE.md` are unmodified Bag2 copies

Their hardware sections (LED shape, NFC part, I2C addresses, pin map) describe Bag2, not this tree.
If you're working on Bag3 wand firmware or games, update them as you go so they catch up with this
tree rather than staying wrong.

## Adding a game

1. Create `<name>.py` in `Wand Module/` exposing `play(nfc, leds, buz, accel, i2c, enow)`.
2. Add the tag to `lib/game_tags.py`.
3. Add the import and a `GAME_DISPATCH` entry in `main.py`.

`main.py` checks the dispatch table against the tag set at boot and prints `[ERR]` on a mismatch, so
a missing entry is visible rather than silent.

## Layout

Game modules are flat files in `Wand Module/` — there is no `games/` subdirectory. `utilities/` is
bench-only and never deployed to the device.
