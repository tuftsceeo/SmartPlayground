# Part B results

Hardware session for [PLAN.md](PLAN.md) Part B. Code: `wands_with_splats` at the merge of
`wands_with_splats-partA` (997c99d).

## Boards

| Port | MAC | Firmware | Flash before deploy |
|---|---|---|---|
| `usbmodem1101` | `A0:F2:62:86:28:FC` | MicroPython v1.28.0 (2026-04-06), ESP32C6 | Older MockWand build plus stale files |
| `usbmodem3101` | `A0:F2:62:87:AF:74` | MicroPython v1.28.0 (2026-04-06), ESP32C6 | Bag2 wand code, no `/games/` |
| `usbmodem3101` | `A0:F2:62:85:CB:FC` | MicroPython v1.29.0 (2026-08-24), ESP32-C6 | Older MockWand build plus stale files |

All three were deployed with `tools/deploy.py --type wand` (52 files, each read back and verified).
Files on flash that are not in the MockWand tree were left in place; nothing in the tree imports
them. 1101 keeps `/games/button_flash_blu.py`, which shows in its game list.

`A0:F2:62:87:AF:74` read 3.67 V, 7.7 % at boot and was replaced on port 3101 by
`A0:F2:62:85:CB:FC` (4.09 V, 87.8 %). Port names below refer to the board by MAC where it matters.
`A0:F2:62:85:CB:FC` keeps `/games/apple_button.py` and `/games/speed_run.py`, which show in its game list.

## B0. Splat scan

`scan_splats.py` on `A0:F2:62:85:CB:FC` (port 3101), one Splat powered: found
`AB:42:00:00:5D:D0`, addr_type 0, rssi -54. Card text: `splat-AB4200005DD0`.

That card was written on the same wand with `Bag2/Utilities/writetoNFCcards.py`'s NDEF writer
(run without its prompt and button). The tag is MIFARE Classic 1K, UID `89:D6:4B:91`. Read
back with MockWand's `read_ndef_text`: `splat-ab4200005dd0`, `parse_splat_card` gives
`AB:42:00:00:5D:D0`. The idle loop's real card path has not read it yet.

| Splat MAC | Card text | Tag | Tag UID | Read back |
|---|---|---|---|---|
| `AB:42:00:00:5D:D0` | `splat-AB4200005DD0` | MIFARE Classic 1K | `89:D6:4B:91` | match |
| `AB:42:00:00:5E:40` | `splat-AB4200005E40` | MIFARE Classic 1K | `99:02:4D:91` | match |
| `AB:42:00:00:20:60` | `splat-AB4200002060` | MIFARE Classic 1K | `19:02:4D:91` | match |
| `AB:42:00:00:6D:27` | `splat-AB4200006D27` | MIFARE Classic 1K | `39:08:4F:91` | match | The board that
reported "no Splat found" in M1 (`A0:F2:62:87:AF:74`) has not been rescanned.

## B1. Unpaired boot memory

Serial log after `machine.reset()`, no `/pairing.json`. `idfmax` is the largest free IDF block.

| Step | `86:28:FC` (v1.28) | `87:AF:74` (v1.28) | `85:CB:FC` (v1.29) | RESULTS-M1 |
|---|---|---|---|---|
| boot | 270336 | 270336 | 270336 | 270336 |
| after imports | 208896 | 208896 | 208896 | 208896 |
| post `enow.init()` | 172032 | 172032 | 163840 | 172032 |

GC free after imports was 234272, 234320 and 232768, against 261616 in RESULTS-M1.

The v1.29.0 board has 8192 bytes less in its largest IDF block after `enow.init()`. RESULTS-M1
measured BLE bring-up taking 172032 down to 143360 on v1.28.0.

All three boards reached `Boot complete`, listed `partytest`, `relaycolor` and `splattag` in the
identity frame, and sent heartbeats for 30 s. No `post-ble` change on an unpaired boot.

Paired boot (BLE up, Splats connecting) is not measured yet.

## B1. Paired boot

`/pairing.json` written over `mpremote`, then `machine.reset()`.

- A file left unclosed before the reset read as empty: both wands printed `syntax error in JSON`,
  emitted `{"type":"error","where":"pairing"}` and booted unpaired.
- With a valid file: `Splat pairing: 2 Splat(s)` on both wands. 3101 (`85:CB:FC`) connected
  `6D:27` 11.7 s after reset. The other three Splats were asleep and not found; each was dropped
  after `PAIR_CONNECT_MS` (30 s) and removed from the file.
- Largest free IDF block after BLE bring-up: 13312 (`86:28:FC`, v1.28), 10240 (`85:CB:FC`, v1.29).
  Boot completed on both.

## B2. Pairing by card

Real cards, NDEF read through the idle loop. Two wands, Splats 3 and 4 awake.

| Action | Log |
|---|---|
| `86:28:FC` taps `20:60` (unheld) | `paired, resetting to connect`; READY 17 s after the tap |
| `85:CB:FC` taps `6D:27`, which it held | `unpairing`, no reset |
| `85:CB:FC` taps `6D:27` (unheld) | paired, reset, READY 14 s after the tap |
| `86:28:FC` taps `6D:27`, held by `85:CB:FC` | `already paired to another wand` |
| `85:CB:FC` taps `20:60`, held by `86:28:FC` | `already paired to another wand` |
| `86:28:FC` taps `20:60` again | `unpairing`; re-tapped 36 s later: paired, READY 13 s after the tap |

`86:28:FC` held `20:60` from 34 s to 387 s of the capture, through NFC sleep from 62 s, with no
link drop logged. `85:CB:FC` logged one `6D:27` drop and reconnect (`drops=2`, `connects=3`)
before the capture.

A Splat that no wand holds stops advertising after about a minute and cannot be paired until it
is woken. A paired Splat in the idle loop stays connected.

## B3. Party game (`partytest`)

Two wands, one Splat each, real `partytest` card tapped on both. `85:CB:FC` led (lower MAC),
`86:28:FC` followed; both logged `game_start` 0.1 s apart. 38 pooled Splat commands, local and
remote presses, all `ok`; time from the leader's send to the Splat write: 1-82 ms. The
follower's lobby hourglass was drawn in its red identity color and read as an error; it is now
`BLUE_DIM`.

## B4. `relaycolor`

Two wands, one Splat each. `85:CB:FC` led. The token passed between the wands 35 times in
47 s (18 from the leader, 17 from the follower), by button and by Splat press, both directions, with no warning or error on either wand.
`splattag` has not run on hardware.

## Built-in party games and boot memory

`partytest`, `splattag` and `relaycolor` are in `GAME_MODULES`, `GAME_ICON` and `game_tags.py`
(files stay in `MockWand/games/`). With that change alone, `idfmax` after imports fell from 208896
to 77824 on both wands (post-enow 35840 on `85:CB:FC`). A/B boots on `85:CB:FC`:

| `main.py` | after-imports idfmax |
|---|---|
| committed (before) | 208896 |
| new entries | 77824 |
| new entries, ~550 bytes of comments removed | 77824 |
| new entries, `_report_installed_games()` not called | 208896 |
| new entries, report called after `enow.init()`, longer docstring | 77824 |
| new entries, report removed | 208896 (`86:28:FC` and `85:CB:FC`); post-enow 172032 / 163840 |

The report (an `os.stat` per built-in at import) is removed. Small edits to `main.py` flip this
result, so its import is at the fragmentation edge described in
[2026-09-23-ap-memory-order.md](../2026-09-23-ap-memory-order.md).
