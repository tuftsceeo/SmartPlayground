# BDialEUM: Broadcast Dial with code over ESP-NOW

A copy of `BroadcastDial/BDialFirmware/` that sends game code to wands over ESP-NOW through an external ESP-NOW UART modem (EUM). The WiFi Dial uses a SoftAP and TCP instead (`code_server.py`). **This Dial uses no WiFi.** Its own radio stays off, and the modem (`EspnowModem/modem/main.py`) owns ESP-NOW.

**It pairs only with `EspnowModem/MockWandEUM` wands.** Stock wands pull code over WiFi (`code_puller.py`) and cannot get code from this Dial. Card writing, the menu and the serial contract are otherwise the WiFi Dial's.

Status: the code is covered in CPython simulation (`../tests/test_bdial_eum.py`). **It has not run on a real Dial.** See `HARDWARE_TEST.md`.

## What changed from the WiFi Dial

| | WiFi Dial (`BDialFirmware`) | BDialEUM |
|---|---|---|
| Code transport | SoftAP `SP-FILEPUSH-<id>` + TCP, `code_server.py` | ESP-NOW via modem on UART1, `code_link.py` → `code_sender.py` |
| When code is served | Only in SERVE mode (`DONE` + ACT, exit by hold or CLOSE) | Always, in every mode |
| Modes | IDLE / WRITE / SERVE | IDLE / WRITE |
| Menu | games, Utility Tags, `Enable Share` | games, Utility Tags |
| Wands served at once | 4 (`MAX_CLIENTS`) | 6 (`code_sender.MAX_SESSIONS`); the rest get busy and retry |
| Card text | `getcode:<slug>@<HOST_ID>` | same, same `HOST_ID` (last 2 bytes of `machine.unique_id()`) |
| Host pinning | wand joins the SSID named by `@<id>` | wand sends `host` in `code_req`; other hosts stay silent |
| Icon-display pulls (`_icon.py`) | yes | no (not in `code_sender.py`) |
| Heap guard | `serve_guard.py`, `prewarm_ap()`, H5 | none needed: no radio on the Dial |

**Why always serving:** serving over ESP-NOW does not conflict with the NFC field, because the modem is a separate chip. That removes the reason SERVE mode existed. The main loop calls `CodeLink.service()` every tick. Result-screen holds (`_hold()`) keep servicing it, so a card write does not stall a wand that is mid-pull.

## Screen

The top-level breadcrumb shows the share state:

| Crumb | Meaning |
|---|---|
| `Sharing <id>` | modem up, idle, serving |
| `Sending` / `N Wands` | transfers in flight |
| `Pull Failed` | a pull failed or was dropped in the last 3 s (`PULL_FAIL_NOTE_MS`) |
| `No Modem` | the modem did not answer at boot; retried every 5 s (`code_link.RETRY_MS`, 150 ms HELLO per retry) |
| `Modem Lost` | the link went down after boot; the manager reconnects on its own |

Group screens keep their group-name crumb. The state appears again on the next return to the top level.

## Serial contract changes

The wire contract is otherwise the WiFi Dial's (see `BroadcastDial/README.md`).

- **`identity`:** `device` stays `"broadcast_dial"` so ChatBroadcast accepts the link. It adds `"variant": "eum"`.
- **`mode`:** `mode` is never `SERVE`, and `ssid` is always `null`. No `armed` event is sent.
- **`arm`:** replies `ok` with `"modem": bool` when a game is loaded, and changes nothing.
- **`disarm`:** replies `error` `always_serving`.
- **`info`:** adds `modem`, `modem_error`, `wands`, `served`, `failed`, `busy_replies` and `ignored`. `armed` means "modem linked".
- **New event `pull`:** sent once per finished or dropped transfer, as `{"type":"pull","mac","slug","ok","why","bytes","ms"}`. It is also recorded with `stats_log.record_pull()`.
- **New event `modem`:** `{"type":"modem","up":bool,"why":str|null}` on link up, down or restore.

**ChatBroadcast's firmware installer must not be used on this Dial.** It picks the WiFi Dial's `manifest.js` for any `broadcast_dial` identity, so it would overwrite this build with the WiFi one. Game uploads (`pushPayload`) are unaffected: they only write `/flash/games/`.

## Wiring

| Dial (Port B) | Modem (StickS3 / S3) |
|---|---|
| GPIO2 (TX) | GPIO44 (RX) |
| GPIO1 (RX) | GPIO43 (TX) |
| GND | GND |

- **Why Port B:** GPIO1/2 are its two signal pins, unused by the LCD, touch, encoder, button, speaker or either I2C bus. Port A (13/15) carries the external NFC reader.
- **Unconfirmed:** which Grove wire colour is GPIO1 versus GPIO2 has not been checked on hardware. Read the silkscreen. If the modem never answers, swap TX and RX first.
- **Where the pins live:** `EUM_UART_TX` / `EUM_UART_RX` in `dial_board.py`. `code_link.py` writes them into `espnow_manager` before the link is built. The modem's pins are constants in `modem/main.py`.
- **Power:** power the modem from its own USB, not from the Dial's rail (see `../README.md`, Wiring).
- **UART:** UART1 at 921600 baud, as on the bench. Drop both sides to 460800 if CRC counters climb.

## Files

| File | Source |
|---|---|
| `bdial_server.py` | modified: no SERVE mode, `CodeLink` serving, `_hold()`, new events |
| `dial_ui.py` | modified: no serve page or `DONE` row; `share_crumb()` / `set_share_crumb()` |
| `dial_board.py` | modified: `EUM_UART_TX/RX` |
| `main.py`, `manifest.js`, `tools/deploy_dial.py`, `tools/dial_menu_check.py` | modified (docstrings, file list, paths, no `DONE`) |
| `code_link.py` | new: `ESPNowManager` + `CodeSender`, modem retry, events, `HOST_ID` |
| `code_sender.py` | **byte-identical** copy of `../host/code_sender.py` |
| `espnow_manager.py`, `eum_proto.py` | **byte-identical** copies of `../host/lib/` |
| `card_writer.py`, `ws1850s.py`, `json_link.py`, `reset_log.py`, `stats_log.py`, `dial_input.py`, `boot.py`, `games/` | verbatim copies of `BDialFirmware/` (their `PEER:` headers still name the Box originals) |

**Not copied:** `code_server.py`, `serve_guard.py`, `serve_probe.py`, `tools/probe_dial.py` (SoftAP stages), `tools/pull_bench.py` (TCP), and `tools/BENCH_TEST_PLAN.md`.

**Keeping the copies in sync:**
- **Shared modules:** change `code_sender.py`, `espnow_manager.py` or `eum_proto.py` in `../host/` and copy them here. `../tests/test_bdial_eum.py` fails if they differ.
- **Protocol partner:** `code_sender.py`'s message format is shared with `../MockWandEUM/lib/espnow_code.py`. Change both in the same commit.
- **Dial copies:** a fix in `BDialFirmware/` does not reach this tree. Port it and say which tree you touched.

## Memory order

The Dial brings up no radio, so the SoftAP rule (nothing may allocate before the AP claims its block) does not constrain this build. If anything that needs a large contiguous IDF block is added to the Dial later, the rule in `AGENTS.md` applies to it again.

## UIFlow boot option

UIFlow2's `boot_option` 1 or 2 starts UIFlow's own network setup (WiFi) before `main.py`. It must be 0 on this Dial. Check it with:

```bash
python3 -m mpremote connect $PORT resume exec "import esp32; print(esp32.NVS('uiflow').get_u8('boot_option'))"
```

## Deploy

Pass `resume` on every `mpremote` call, write only under `/flash`, and ask which port is which (`Bag3/Code/HARDWARE_PROTOCOL.md`).

```bash
# Modem (UIFlow StickS3): firmware + protocol lib
cd Bag3/Code/BroadcastCode/EspnowModem
MODEM=/dev/cu.usbmodemXXXX   # ask
python3 -m mpremote connect $MODEM resume \
  fs cp modem/main.py :/flash/main.py + \
  fs cp modem/lib/eum_proto.py :/flash/lib/eum_proto.py + \
  fs cp modem/lib/eum_classify.py :/flash/lib/eum_classify.py
python3 -m mpremote connect $MODEM reset

# Dial: per-file, verified (reads manifest.js)
cd BDialEUM
DIAL=/dev/cu.usbmodemYYYY    # ask
python3 tools/deploy_dial.py $DIAL
python3 -m mpremote connect $DIAL reset
```

- **Stale WiFi-build files:** a Dial that ran the WiFi build keeps `code_server.py`, `serve_guard.py`, `serve_probe.py` and `/flash/serve_guard.txt`. Nothing in this build imports them, so they are harmless and can be deleted.
- **Games:** go in `/flash/games/`, the same place the WiFi Dial uses.

## Tests

```bash
python ../tests/test_bdial_eum.py      # Dial main loop + modem + wand receiver, simulated
python tools/dial_menu_check.py        # menu logic, card text, card parsing
```

## Open

- **Hardware:** not run on a Dial. Unverified: the Port B pins, UART1 at 921600 on the StampS3A, LVGL responsiveness while `service()` runs, and a real card → wand → launch round trip (`HARDWARE_TEST.md`).
- **Multiple wands:** real multi-wand throughput is unmeasured, as for the EUM bench.
- **ChatBroadcast:** it shows this Dial as a WiFi Dial that is never serving. It does not use `variant`, `pull` or `modem`.
