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
