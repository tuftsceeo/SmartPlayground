# MockWandEUM — MockWand copy with ESP-NOW code pull

Copy of `Bag3/Code/BroadcastCode/MockWand/` (taken 2026-09-26) for testing game
transfer over ESP-NOW from an EUM host. The original MockWand tree is untouched;
the two copies are expected to diverge. Differences from MockWand:

- **`lib/espnow_code.py` (new):** receives a game over the ESP-NOW link that is already up, with no WiFi join and no reset. The wand drives the transfer in windows of `WINDOW` (8) chunks and re-requests from the first missing chunk. The file lands as `/games/<slug>.py.part` and is checked (size, SHA-256, `compile()`) before promotion, keeping `.bak`. `receive(enow, slug, hubtype, ..., icon_dir=<dir>)` also fetches the game's icons (hub `icon_display`) into `<dir>`: the offer carries `icons_n` and a trimmed `icons` list, the receiver asks `{"type":"code_req",...,"list_from":k}` for the rest (reply `code_icons`), then one `code_req` with `"file":<name>` per icon. Icons are checked by size and SHA-256 only, not compiled; a failed icon is skipped and does not fail the game. The stock wand does not pass `icon_dir`.
- **`lib/espnow_manager.py`:** sets `ESPNOW_RXBUF = 4096` before `active(True)`, at radio bring-up. The MicroPython default of 526 B holds about 2 frames.
- **`main.py`:**
  - **`_load_play()`:** a game with no `GAME_ICON` entry (every pulled game) shows nothing while it loads, instead of the white music note.
  - **`getcode`:** a tap calls `_espnow_pull_and_launch()`, which receives the game and launches it in place. The card's `@<id>` suffix is sent as `"host"` in `code_req`, so only that sender answers; a card without it is answered by any sender in range.
  - **`REMOTE_GETCODE = True` (bench):** a broadcast `{"type":"getcode","slug":s}` acts as a tap, so transfers can be repeated without a card.
  - **Result line:** each transfer prints a JSON `enx_result` line with total/body ms, bytes and `min_gc_free`, plus the usual `memprobe` lines `enx:pre` / `enx:post`.

The sender is `EspnowModem/host/code_sender.py`, run by `host/code_host.py`. The wire format is described in `lib/espnow_code.py`'s docstring. `MockWand/lib/espnow_code.py` and `IconDisplay/lib/espnow_code.py` are hand-kept copies of this file.

---

# Mock Wand — Bag3 wand copy for Broadcast Box tap-to-pull

Copy of `Bag3/Code/Wand Module/` plus the ESP-NOW code pull. Same C6 hardware and pin map as the fielded Bag3 wand.

## lib/ copies

`lib/opcodes.py` and `lib/game_tags.py` are **further uncoordinated copies** of
the tag vocabulary (alongside each Bag's `lib/`, `hubCode2/game_tags.py`,
`commands.json`, and `wand_icons.html`).

**`getcode` must match** `BBoxFirmware/opcodes.py` byte-for-byte. After editing
either file, `diff` the two copies.

## getcode flow

1. Box or Dial writes a `getcode:<slug>@<id>` card.
2. Wand taps the card in its idle loop.
3. `espnow_code.receive()` pulls the game over the
   ESP-NOW link already up, verifies sha256 and `compile()`, and promotes it.
4. The wand launches the game in place, without a reset.

On failure the existing file on flash is untouched.

## Boot grace

`GRACE_S` seconds of countdown (0 by default) at the top of `main()` before
NFC/ESP-NOW init. Ctrl-C during the window reaches the REPL.

## Driving tag parsing without a card

Call
`NfcReader._match_prefixed()` / `is_valid_slug()` on-device against
synthetic strings. This does not exercise the NDEF decode path — a real
card read is a separate check.

## Wand tree invariants

On-device layout: `/lib` for libraries, flash root for `main.py` and the
built-in games, `/games/<slug>.py` for pulled games. `/games` is appended to
`sys.path` by `main.py`. Pulled games must never land in the root — root
precedes `/games` on the path and would shadow the new copy with a stale one.

Load-bearing, must survive any future edit:

- **Nothing allocates ahead of the radio.** See below — this one is easy to
  break by adding a print.

## Radio memory order — do not add prints ahead of the radio

`esp_wifi_init()`/`esp_wifi_start()` need one large **contiguous** block of
internal IDF heap, and the radio has to take it early: MicroPython's GC heap
is carved out of that same heap in splits that are never returned, so nothing
later can un-fragment it enough to find the block again. `gc.mem_free()` does
not measure this. The failure is **fragmentation, not exhaustion**, and it
reads as a comfortable free-heap number sitting next to
`OSError: WiFi Out of Memory`.

`lib/memprobe.py` exists because of exactly this failure at `enow.init()`.
Its `_idf_free()` returns total free **and largest free block** for that
reason — the second number is the one that decides.

`ESPNowManager.init()` claims the block. `main.py` imports roughly fifteen
modules at module scope before `main()` runs, and every game module it pulls
in costs heap before the radio gets its turn. A new built-in game is not
free, and diagnostics go in a module imported lazily after bring-up.

The same constraint bit the Dial and Box on 2026-09-23, from the server side:
[`docs_and_design/2026-09-23-ap-memory-order.md`](../docs_and_design/2026-09-23-ap-memory-order.md)
has the numbers and the rules for both ends.

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

`set_last_pulled()` marks the game for `MockWand/main.py`'s "Auto-launch a
just-pushed game" block — the wand plays the game on the next boot, no card
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
