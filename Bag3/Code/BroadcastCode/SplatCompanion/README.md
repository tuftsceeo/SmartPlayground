# Splat Companion (EUM)

Bag3 Splat Companion that runs ESP-NOW and BLE at the same time on separate radios:
- **ESP-NOW** (to wands and remotes) goes through an EUM modem: an M5StickS3 running `../modem/main.py`, on UART1.
- **BLE** (to a stock Splat toy) runs on the companion's own radio, a Seeed XIAO ESP32-C6.

Status: tested only in the CPython simulation (`../tests/test_splat_companion.py`). Not yet run on hardware; see `HARDWARE_TEST.md`.

## How it differs from the Bag2 companion

`Bag2/Code/Splat Companion/main.py` has one C6 radio. It connects BLE first, then brings up ESP-NOW, and services both in one loop. It does not switch radios; it relies on the IDF's WiFi/BLE coexistence. The Jan 2026 wand-side controller (`legacy_jan26_wand_ble_splat_ctrl.py`) paused ESP-NOW around BLE work because BLE writes were unreliable under that time-sharing.

| | Bag2 companion | This companion |
|---|---|---|
| ESP-NOW | C6 radio, shared with BLE | EUM modem over UART |
| BLE connect / reconnect | Blocking `connect()`, up to 30 s; ESP-NOW not polled meanwhile | Non-blocking state machine (`splat_link.py`); ESP-NOW polled throughout |
| Splat press handling | BLE writes inside the BLE IRQ callback | IRQ records raw state; main loop debounces and writes |
| Chain playback | `sleep_ms(400)` between groups, loop blocked | Non-blocking player |
| Config after BLE loss | Cleared | Kept |
| Press relay to wands | None | `splat_event` to the owner |
| Direct commands | None | `splat_cmd` |
| Note names | `notea` … `noteb` | Card names `note_c` … `note_c_high` |
| Release | noteOff per note, allLEDsOff, soundOff | allTasksOff, allLEDsOff |
| Errors | several `except Exception: pass` | every failed write printed with a counter |

The Bag2 companion is unchanged.

## Files

| Path | Purpose |
|---|---|
| `main.py` | Boot shim: `ubluetooth.BLE().active(True)` first, then imports `splat_companion` |
| `splat_companion.py` | Entry point: pins, modem init, main loop, fault handling |
| `companion.py` | Logic (hardware-free): message handling, chain player, relay, status LED state |
| `splat_link.py` | `SplatLink(OpenSplat)`: non-blocking connect / reconnect, IRQ-safe button debounce |
| `status_leds.py` | Companion's 3 NeoPixels |
| `companion_probe.py` | Periodic diagnostics, imported only when `DEBUG_PROBE = True` |
| `bench_wand.py` | Stand-in wand for bench tests (runs on a MockWand) |
| `hubtype.txt` | `splat_companion` |
| `lib/espnow_manager.py`, `lib/eum_proto.py` | Byte copies of `../host/lib/` |
| `lib/ble_splat.py`, `lib/hubtype.py` | Byte copies of `Bag3/Code/lib/` |

`../tests/test_splat_companion.py` checks that the four `lib/` copies match their sources.

## Wiring (XIAO ESP32-C6 ↔ M5StickS3 modem)

| XIAO C6 | StickS3 modem |
|---|---|
| D0 = GPIO0 (TX) | GPIO44 (RX) |
| D1 = GPIO1 (RX) | GPIO43 (TX) |
| GND | GND |

- **Why GPIO0/1:** on the companion, GPIO20 drives the LEDs (D9) and GPIO22/23 are I2C (D4/D5, battery gauge). D6/D7 (GPIO16/17) are the C6's UART0 default pins, which carry the ROM boot log. GPIO0/1 are not strapping pins on the C6. This pin choice has not been checked on a board yet.
- **Changing pins:** `MODEM_UART_TX` / `MODEM_UART_RX` at the top of `splat_companion.py`. They are set on `espnow_manager` before `init()`, so `lib/espnow_manager.py` stays a byte copy.
- **Power:** the modem needs its own supply (see `../README.md`).

## Deploying

The XIAO C6 runs plain MicroPython, so files go at `/` and `/lib/`:

```bash
cd Bag3/Code/BroadcastCode/EspnowModem/SplatCompanionEUM
python3 -m mpremote connect $COMP_PORT resume \
  fs cp main.py splat_companion.py companion.py splat_link.py status_leds.py \
        companion_probe.py hubtype.txt : + \
  fs mkdir :lib + \
  fs cp lib/espnow_manager.py lib/eum_proto.py lib/ble_splat.py lib/hubtype.py :lib/
python3 -m mpremote connect $COMP_PORT reset
```

`fs mkdir` fails if `/lib` already exists; drop that step then. The modem runs the unchanged `../modem/` firmware. No new message codes were added, so the modem needs no reflash.

## Memory order

`main.py` contains no strings and imports only `ubluetooth` before calling `BLE().active(True)`, so the BLE controller gets its memory before anything else allocates (`AGENTS.md`). The companion never imports `network` or `espnow`. Diagnostics live in `companion_probe.py`, imported after bring-up.

## Main loop

`splat_companion.main()` calls `Companion.step()`, then `time.sleep_ms(1)`, forever. One step:
1. `SplatLink.service()` advances the connection: IDLE → CONNECTING → SETTLING (200 ms) → READY. An attempt that is not ready after 20 s is torn down and retried after 2 s. A drop from READY retries at once.
2. Button events: the BLE IRQ records raw state changes, and `service()` debounces them (80 ms) into press/release events.
3. Keepalive every 2500 ms, and `readSwitches` every 150 ms while READY (`SWITCH_POLL_MS`, 0 = off).
4. The chain player plays at most one group per step, one group every 400 ms.
5. ESP-NOW: up to 8 `mgr.poll()` results per step, with a 5 ms gap after a poll that came back empty.
6. Status LEDs.

**Longest waits in a step:**
- the BLE driver's 20 ms pacing between writes (a group is up to 3 writes)
- a unicast `splat_event` waiting for its ESP-NOW ACK (host timeout 300 ms)

In the simulation the longest step was about 40 ms, and keepalive and switch-poll gaps stayed on schedule during a 60-message burst.

**Faults:** an exception from `step()` prints its traceback. More than 5 in 10 s calls `machine.reset()`. Ctrl-C runs `shutdown()`, which removes peers first so the owner wand is not sent `stop`.

## Messages

| Direction | Message | Effect |
|---|---|---|
| in | `{"type": "splat_config", "actions": [[...], ...]}` | Chain to play on each splat press. The sender becomes the owner. |
| in | `{"type": "splat_cmd", "actions": [[...], ...]}` | Play now. Notes stop 400 ms after the last group. The sender becomes the owner. Dropped with `[WARN]` while BLE is not ready. |
| in | `{"type": "splat_cmd", "off": true}` | `allTasksOff` + `allLEDsOff` |
| in | `{"type": "stop"}` / `["stop"]` | Clear config, stop the splat, forget the owner |
| out | `{"type": "splat_event", "event": "press" \| "release", "splat": "<BLE MAC>"}` | Unicast to the owner (ESP-NOW peer, ACKed). Broadcast when there is no owner, or when `RELAY_TO_OWNER = False`. |

**Press and release:**
- **Press** (with a config): groups play every 400 ms and notes stay on.
- **Release:** remaining groups are dropped, then `allTasksOff` and `allLEDsOff`.
- **Relay:** every press and release is relayed, with or without a config. A BLE drop while pressed relays a release.

**Actions** use the card names from `lib/actions.py`:
- colors: `turnred`, `turngreen`, `turnblue`, `turnpurple`, `turnyellow`, `turnwhite`, `turnoff`
- notes: `note_c` … `note_b`, `note_c_high`, `playnote`
- sounds: `cat`, `chicken`, `cow`, `dog`, `pig`, `duck`, `elephant`, `horse`, `goat`

A group plays in the order LED, then sound, then note. Unknown names print `[ERR]` and are skipped.

**Classification:**
- `splat_cmd` and `splat_event` are not classified by the modem. They arrive as `("raw", dict, mac)`, on the EUM and on the built-in manager alike.
- No wand code consumes `splat_event` yet, and no wand code sends `splat_config` or `splat_cmd`: `send_splat_config()` is defined in every `espnow_manager.py` copy but never called. `bench_wand.py` plays the wand for now.
- If wands start using these messages, give them codes per `../README.md` "Adding a message type".

## Status LEDs (companion)

| Color | Meaning |
|---|---|
| Red, solid | Modem link down (or no modem at boot) |
| Blue, solid | BLE not ready (scanning / connecting) |
| Cyan, breathing | Ready, no config |
| Purple, breathing | Ready, config loaded |
| White, solid | Splat held down |

On each BLE connect the splat itself flashes green for 300 ms (`CONNECT_FLASH_MS`). `identifySplat()` is not used: the Jan 2026 controller notes that its LED sequence blocks later `setLEDsON` writes.

## Drift and findings (flagged, not reconciled)

- **Note names:** cards and `lib/actions.py` use `note_a` … `note_c_high`, but the Bag2 companion uses `notea` … `noteb`. Card note names sent to the Bag2 companion are dropped without a message. This companion accepts card names only; `notea` prints `[ERR]`.
- **Note values:** the Bag2 companion uses semitones (`c`=0, `d`=2 … `b`=11), velocity 127, instrument 17. The Jan 2026 wand-side controller used `c`=1, `d`=3, `e`=6, `f`=7, `g`=10, `a`=13, `b`=15, velocity 255, instrument 16. This companion uses the Bag2 companion's values, with `note_c_high` one octave up. Which set is right on a Splat is unverified.
- **Release command:** the Bag2 companion sends noteOff per note + allLEDsOff + soundOff. The Jan 2026 controller found a single allTasksOff more reliable. This companion sends allTasksOff + allLEDsOff; check on hardware.
- **Switch polling:** the Bag2 companion polls `readSwitches` every 150 ms. The Jan 2026 controller says the Splat notifies on button changes without polling. `SWITCH_POLL_MS` keeps polling on; the hardware test checks 0.
- **Notes and button notifications:** the Jan 2026 controller says splat button notifications corrupt the Splat's note engine, and turned off splat-button triggering for chains with notes. This companion does not work around it; the hardware test checks it.
- **`ble_splat.py` debounce:** `OpenSplat._handle_button` drops a change < 80 ms after the previous one and updates `_last_raw_state` anyway. A tap shorter than 80 ms therefore loses its release, and the button stays reported as pressed until the next full press. `SplatLink` overrides `_handle_button`. The driver copies in `Bag2/Code/lib/` and `Bag3/Code/lib/` still have this behaviour, and so does `Bag2/Code/Splat Companion/main.py`.
- **Misnamed file:** `Bag2/Code/Splat Companion/ble_splat.py` contains the wand-side `ble_splat_ctrl.py` controller, not the `OpenSplat` driver. The Bag2 companion's `from ble_splat import OpenSplat` works only if `/lib/ble_splat.py` is found first.
- **Scan race:** a late `SCAN_DONE` IRQ from a stopped scan clears `OpenSplat._scanning` while a new scan runs. The next `gap_scan()` then raises `EALREADY`. `SplatLink` treats that as "still scanning" and counts it in `scan_already`.

## Not done

- Battery gauge and `status_poll` battery reply (the manager's auto-reply sends no battery value).
- Several Splats per companion.
- Wand-side consumers of `splat_event`, and senders of `splat_config` / `splat_cmd`.
- The acknowledged-fetch fix (`../README.md`). A timed-out FETCH still loses up to 4 messages. Wand → companion traffic is light, so this matters less here than for bursts.
