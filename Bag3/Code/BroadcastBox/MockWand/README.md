# Mock Wand — Bag3 wand copy for Broadcast Box tap-to-pull

Copy of `Bag3/Code/Wand Module/` plus `code_puller.py` for Phase 1 end-to-end
testing. Same C6 hardware and pin map as the fielded Bag3 wand.

## lib/ copies

`lib/opcodes.py` and `lib/game_tags.py` are **further uncoordinated copies** of
the tag vocabulary (alongside each Bag's `lib/`, `hubCode2/game_tags.py`,
`commands.json`, and `wand_icons.html`).

**`getcode` must match** `BBoxFirmware/opcodes.py` byte-for-byte. After editing
either file, `diff` the two copies.

## getcode flow

1. Box writes a `getcode` opcode card.
2. Wand taps card in idle loop.
3. `code_puller.pull()` shuts down ESP-NOW, joins `SP-FILEPUSH`, pulls
   `jumpin.py`, verifies sha256, promotes atomically.
4. `machine.reset()` — next boot runs the new game via `from jumpin import play`.

On pull failure the existing `jumpin.py` on flash is untouched.

## Boot grace

Five-second countdown at the top of `main()` before NFC/ESP-NOW init. Ctrl-C
during the window reaches the REPL — recovery if a pull loop wedges.

## Deploy

Copy all `.py` files and `hubtype.txt` to the wand's flash root (same layout as
Bag3 Wand Module).
