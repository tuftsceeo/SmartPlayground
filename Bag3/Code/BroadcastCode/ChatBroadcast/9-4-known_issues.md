**OUTDATED — dated 9/4, kept per the user's direction rather than deleted (see
`PHASE6_HANDOFF.md` §5.8). Entries below may already be resolved or
superseded by later work; check the current tree before acting on any of
them.**

---

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

--> Games now come from Bag3/Code/BroadcastCode/BroadcastBox/MockWand. lib/ still comes from
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

---

**Added 2026-09-26 (current, not covered by the OUTDATED note above).**

No file size check before sending a game to wands. What should the limit be?

--> Add a check in ChatBroadcast, before Send to Box / ESP-NOW send.

STILL OPEN. The wand compiles a pulled game in its running heap, and on the
XIAO ESP32-C6 (no PSRAM) that needs one contiguous block the heap does not
always have. The limit has been hit on the WiFi pull path as well as the
ESP-NOW one; it is a wand heap limit, not a transport limit. Measured on
the MockWand, 2026-09-26 (see
`../docs_and_design/2026-09-26-eum-bench-results.md`):

- 27,870 B (`gestures.py`) and 33,004 B compile, cold and warm.
- 56,926 B fails: `compile()` asks for 41,216 B; the largest free internal
  block is 40,960 B, unchanged across every run.
- The threshold lies between 33 KB and 57 KB and has not been narrowed.

The WiFi pull (`code_puller._compiles()`) and the ESP-NOW receiver
(`MockWandEUM/lib/espnow_code.py`) both reject an over-size file after the
full transfer, leaving the previous copy in place. The teacher only sees the
wand's failure display. A check in ChatBroadcast would refuse, or warn about,
an over-size generated game before sending it, and could ask the model to
shorten it. The threshold must be measured first, and it may differ per
board.
