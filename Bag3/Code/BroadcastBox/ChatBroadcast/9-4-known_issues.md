The gallery's Python currently comes from hand-written payloads in examples.js, not the real games. Where should the real Wand Module .py be used?

--> Everywhere

RESOLVED. Each entry in `js/examples.js` now names a `vendorGame` instead of
carrying a `startingCode` string, and the seven hand-written `*_CODE`
constants are gone. Previews set `<wand-sim>.game`, so Pyodide loads
`Simulator/vendor/games/<name>.py` directly; remix / use-as-is / the code
drawer / Save / Send to Box all read the same file through
`loadExampleCode()`. Melody was the visible symptom: its payload filled the
matrix with one colour via `leds.fill()`, where the real game lights a pixel
per note and breathes a music shape when idle.

Simulator/tools/sync_sources.py copies vendor/ from Bag2/Code, not Bag3. That is why the vendored melody/jumpin/nfc_sound are stale. Repoint it?

--> Games now come from Bag3/Code/BroadcastBox/MockWand. lib/ still comes from
    Bag2/Code/lib, whose leds.py and hubtype.py define the LED geometry the
    golden-frame tests are pinned to.

Unchanged. `freeze_dance.py` was added to its GAMES list and vendors from
Bag2 like everything else — Bag2's copy carries the same tags, `MSG_*`
constants and `send_raw` API as Bag3's.

The Freeze Dance example has no vendored counterpart — Bag3 has freeze_dance.py, but it is not in the sync list. What should happen to it?

--> Drop the example

SUPERSEDED — kept instead, and vendored. The simulator now stands in for the
missing second wand: role selection works through the game's own `caller` /
`player` tags, the advanced block's "Heard from the caller" buttons queue
the messages a caller would broadcast, and the game's own sends show under
"Sent by this wand". See the Simulator README's "ESP-NOW is one-sided".

Which games should the example gallery show once it is backed by real files?

--> Expose all vendored games

STILL OPEN. The gallery shows 7 of the 13 vendored games. Not yet exposed:
`gestures`, `multiicecream`, `nfc_sound`, `shake`, `simpleicecream`,
`sound` — each needs a name, icon, category, description and starter prompt
written for it.
