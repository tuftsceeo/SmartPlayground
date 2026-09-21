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

## Driving the pull path without a person

Set the flag the tap would have set, then reset:
`pull_flag.set_pending('<slug>')`, then `machine.reset()`.

Tag-text parsing can be driven the same way: call
`NfcReader._match_prefixed()` / `is_valid_slug()` on-device against
synthetic strings. This does not exercise the NDEF decode path — a real
card read is a separate check.

## Wand tree invariants

On-device layout: `/lib` for libraries, flash root for `main.py` and the
built-in games, `/games/<slug>.py` for pulled games. `/games` is appended to
`sys.path` by `main.py`. Pulled games must never land in the root — root
precedes `/games` on the path and would shadow the new copy with a stale one.

Load-bearing, must survive any future edit:

- The pull-flag check is `main()`'s first statement — a pull must happen
  before `ESPNowManager` is constructed.
- No ESP-NOW in the pull path — a WiFi join only succeeds on a radio
  ESP-NOW has never touched this boot.
- `machine.reset()` between radio modes — the tap queues the pull and
  resets; the pull succeeds and resets again.
- The attempt budget is spent before each attempt (`pull_flag.bump()`), so a
  crash mid-pull cannot boot-loop.

## Slugs are module names

A slug is the filename on both devices and a MicroPython module name, since
`_load_play()` does `__import__(slug)`. Must be a legal identifier:
lowercase, leading letter, `[a-z0-9_]`, max 16 chars. Hyphens are invalid —
any surviving hyphenated game must be renamed on flash along with its
`index.json` key.

Three places enforce this and must agree:

- `ChatBroadcast/js/gameName.js` — `slugify()` / `isValidSlug()`, plus the
  reserved list (Python keywords, module names, wand built-in game tags).
- `MockWand/lib/nfc_reader.py` — `is_valid_slug()`, what a card may say.
- `MockWand/lib/game_store.py` — what is allowed on flash.

## Direct-USB push (no Box in the loop)

ChatBroadcast's connect overlay also takes a wand plugged straight into USB
— `ChatBroadcast/js/device/wandDeviceLink.js` and `wandGameInstaller.js`.
The Box is transport only; the payload is wand source
(`def play(nfc, leds, buz, accel, i2c, enow)`), so this path writes the
identical bytes directly to `/games/<slug>.py` over the raw REPL instead of
routing through `/flash/games/<slug>.py` and an ESP-NOW pull.

```
raw REPL: verify hubtype.txt == "wand", os.mkdir('/games') if needed,
          write /games/<slug>.py, game_store.set_last_pulled('<slug>')
exit raw REPL, Ctrl-D (soft reset)
```

`set_last_pulled()` reuses the auto-launch path a real ESP-NOW pull uses
(`MockWand/lib/game_store.py`, `MockWand/main.py`'s "Auto-launch a
just-pulled game") — the wand plays the game on the next boot, no card
involved.

The wand has no command listener. `MockWand/main.py` prints one JSON line
per event (`_emit()`), never reads one. Shapes mirror the Box's
`identity`/`heartbeat` so `bboxLink.js`'s NDJSON reader parses either device
unchanged:

```
{"type":"identity","device":"wand","version":<str>,"hub":<HUB_TYPE>,"games":[<slug>,...]}   — once, after boot completes
{"type":"heartbeat","up":<ticks_ms>}                                                        — every 5s, idle loop only
{"type":"game_start","slug":<slug>}  /  {"type":"game_end","slug":<slug>}                   — around _launch_game()'s body
{"type":"error","where":"game_load","slug":<slug>,"err":<str>}                              — from _game_load_failed()
```

`heartbeat` is idle-loop-only — a running game blocks the wand's main loop
for its duration, same as Box `SERVE` mode. ChatBroadcast's
`game_start`/`game_end` handlers raise and lower the silence watchdog the
same way its Box `mode`/`armed` handlers do for `SERVE`.

## Deploy

Copy all `.py` files and `hubtype.txt` to the wand's flash root (same layout as
Bag3 Wand Module).
