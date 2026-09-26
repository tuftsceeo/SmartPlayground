# ESP-NOW UART Modem (EUM)

Proof of concept. A dedicated ESP32-S3 (the **modem**) owns the ESP-NOW radio. The main device (the **host**) reaches it over UART through `host/lib/espnow_manager.py`. That file is a drop-in replacement for `Bag3/Code/BroadcastCode/MockWand/lib/espnow_manager.py`: it has the same module-level names and the same `ESPNowManager` methods, and it imports neither `network` nor `espnow`.

What moves off the host:
- the radio: its contiguous DRAM block, its current peaks, and its WiFi/BLE exclusivity
- the RX buffering: a 128-message ring on the modem
- JSON classification, `find_device` filtering, and the `status_poll` auto-reply

## Layout

| Path | Board | Purpose |
|---|---|---|
| `modem/main.py` | modem | Firmware: radio bring-up first, RX ring, UART request handler |
| `modem/lib/eum_proto.py` | modem | Wire protocol (framing, CRC, constants) |
| `modem/lib/eum_classify.py` | modem | Message classification, ported from MockWand `poll()` |
| `host/lib/eum_proto.py` | host | **Byte-identical copy** of the modem's `eum_proto.py` |
| `host/lib/espnow_manager.py` | host | Drop-in `ESPNowManager` over UART |
| `host/test_link.py` | host | Bench check: broadcast, receive, counters |
| `host/test_burst.py` | host + another board | Burst / overflow test |
| `host/test_xfer.py` | host + another board | File transfer over ESP-NOW: time, throughput, loss, SHA-256, heap |
| `tests/test_proto.py` | PC | CPython tests: protocol, classification, copy check |
| `tests/test_code_xfer.py` | PC | CPython: ESP-NOW code transfer, receiver ↔ sender, lossy link |
| `tests/test_sim.py` | PC | CPython end-to-end: real modem `main.py` and host manager joined by a fake UART and a fake radio |

## Wiring (S3 ↔ S3)

| Host | Modem |
|---|---|
| GPIO43 (TX) | GPIO44 (RX) |
| GPIO44 (RX) | GPIO43 (TX) |
| GND | GND |

- **UART:** UART1 at 921600 baud. The pins and baud rate are constants at the top of `modem/main.py` and `host/lib/espnow_manager.py`. If CRC counters climb on long jumper wires, drop to 460800 on both sides.
- **Power:** give the modem its own supply (USB or its own regulator). If it shares the host's 3V3 rail, the brown-out problem comes back.
- **Pin caveat:** GPIO43/44 are the S3's default UART0 console pins. They are free on boards whose REPL runs over native USB (GPIO19/20). They are **not** free on boards whose USB port goes through a CH340/CP210x bridge wired to 43/44.

## Flashing

- **Modem:** copy `modem/main.py` to `/flash/main.py` and `modem/lib/*.py` to `/flash/lib/` on UIFlow (M5) boards. On plain MicroPython, use `/` and `/lib/`.
- **Host:** copy `host/lib/*.py` into the lib directory the same way, replacing the built-in `espnow_manager.py`. Game files run unchanged.
- **State files:** the modem keeps `no_wdt` and `last_error.txt` under `/flash` when that directory exists, and under `/` otherwise (`FS_ROOT`).
- **UIFlow pins:** check that GPIO43/44 are brought out on the board and not used by UIFlow before wiring. The pins are constants at the top of each file.
- **Before flashing,** confirm the two protocol copies match: `cmp modem/lib/eum_proto.py host/lib/eum_proto.py` (`tests/test_proto.py` also checks this).

## Protocol

```
0xA5 0x5A | type(1) | seq(1) | len(2, LE) | payload(len ≤ 1100) | crc8(1)
```
- **CRC:** CRC-8, poly 0x07, over `type..payload`.
- **Replies:** the reply type is `request | 0x80`, and `seq` is echoed back.
- **Host-driven:** the host sends one request and the modem sends exactly one reply. The modem never sends unsolicited frames.

Every reply body starts with `boot_id(1) | rx_overflow(u16) | pending(1)`:
- **`boot_id`** is random per modem boot. When it changes, the host re-activates the modem, re-adds its peers and re-pushes status.
- **`rx_overflow`** counts ring drops since the modem booted. The host prints a message whenever it increases.
- **`pending`** is the number of messages still queued on the modem.

| Request | Payload | Reply body |
|---|---|---|
| `HELLO` 0x01 | — | proto version, modem MAC(6) |
| `ACTIVATE` 0x02 | — | status, err(i16) |
| `DEACTIVATE` 0x03 | — | status, err. Stops queuing, clears ring, peers and auto-reply. The radio stays up. |
| `ADD_PEER` 0x04 / `DEL_PEER` 0x05 | mac(6) | status, err |
| `SEND` 0x06 | mac(6), flags (bit0 = sync), data ≤ 250 | status, err, acked(1) |
| `FETCH` 0x07 | max records (≤ 4) | count, then records `mac(6) rssi(i8) code(1) len(1) data` |
| `GET_RSSI` 0x08 | mac(6) | rssi (i8, 0x7F = unknown) |
| `SET_STATUS` 0x09 | battery (i8, −1 = none), auto-reply enable | status, err |
| `STATS` 0x0A | — | rx, tx, tx_fail, rx_overflow, crc_err, dup_drop, len_err, faults (u16 each) |
| `FLUSH` 0x0B | — | discarded count (u16) |
| `LAST_ERROR` 0x0C | — | reset_cause(1), previous boot's fault traceback (utf-8, ≤ 900 B) |
| `MEM` 0x0D | — | gc_free, gc_alloc, idf_free, idf_largest, idf_min_free (internal RAM), psram_free (u32 each), ring_count, ring_slots (u16) |

If a request raises on the modem, the modem sends a **`T_ERROR` reply (type 0xFF)** with the same `seq` in place of the normal reply. Its body is the failed request type(1), err(i16), and a text message. The host prints the message and the call fails.

**Send behaviour:**
- **Sync mode:** broadcasts are sent async, and unicasts are sent sync (the modem waits for the ESP-NOW ACK).
- **Retry:** the modem retries once, after 30 ms, when a send raises (for example when the TX queue is full).
- **No host-side retry:** the host never resends a `SEND` or `FETCH` after a timeout. The first attempt may already have taken effect.

## Buffering

- **Driver buffer:** the ESP-NOW driver `rxbuf` is 8 KB. The MicroPython default is 526 B, which holds about 2 messages.
- **Ring:** the modem loop moves every received message into a 128 × 260 B ring (about 33 KB, allocated once at boot). It then services one batch of UART bytes and drains the radio again. The loop sleeps 1 ms per iteration.
- **Overflow:** when the ring is full, the oldest message is dropped and counted.
- **Blocking sends:** a sync unicast blocks the modem loop until its ACK arrives. The driver buffer absorbs arrivals during that time.
- **Host side:** `poll()` fetches up to 4 messages per request. When `timeout_ms > 0`, it re-fetches every 5 ms until a message arrives or the timeout runs out.

## Fault recovery

**Modem:**
- **Request faults:** every request is handled inside a guard. An unexpected exception becomes a `T_ERROR` reply and the loop keeps running.
- **Loop faults:** the same guard wraps each loop step (radio drain, UART service, status timer).
- **Fault handling:** each fault prints its traceback on the modem's USB console, writes it to `/last_error.txt`, and increments the `faults` counter.
- **Reset on repeated faults:** more than `FAULT_LIMIT` (5) faults within `FAULT_WINDOW_MS` (10 s) calls `machine.reset()`.
- **Watchdog:** `machine.WDT(timeout=5000)` is fed once per loop pass, so a hang that raises nothing (for example a send that never returns) also resets the chip.
  - **When it arms:** only after `WDT_ARM_AFTER_MS` (180 s) of uptime **and** a first valid host request. Until then you can Ctrl-C into the REPL or run `mpremote`.
  - **Once armed:** an ESP32 watchdog cannot be turned off, so stopping the loop resets the chip within 5 s.
  - **To disable it:** create `no_wdt` on the modem, e.g. `python3 -m mpremote connect $PORT resume fs touch :/flash/no_wdt` (UIFlow; plain MicroPython uses `:/no_wdt`), then `reset`. Delete the file to re-enable it.
- **After a reset:** at boot the modem reads `/last_error.txt`, deletes it, and returns its contents through `LAST_ERROR`. Each fault is therefore reported on one boot only.

**Host:**
- **Reset detection:** a changed `boot_id` means the modem reset. The host prints the reset cause and the previous fault (`LAST_ERROR`), then restores activation, peers and status.
- **Link down:** after 3 consecutive timeouts the link is marked down, and requests fail immediately.
- **Reconnect:** while the link is down, the host tries one `HELLO` (50 ms timeout) every second. When it succeeds, the host restores state as it does after a reset.
- **Counters:** `link_stats()` adds `modem_faults`, `host_modem_errors`, `host_link_down_events`, `host_reconnects` and `host_resets_seen`.

**Lost on reset:** the modem's RX ring. How many messages were in it is not knowable.

**To explore later: EN-pin hard reset.** Wire one host GPIO to the modem's EN/RST pin so the host can hard-reset a modem that stays silent through the reconnect attempts. That covers a wedge the watchdog cannot clear, such as a stuck peripheral or a watchdog that was never started. Not implemented yet.

## Memory and transfer baseline

- **`mgr.mem_stats()`:** returns the modem's figures (via `MEM`) and the host's own. `idf_largest` is the largest contiguous free block, and it is the figure to watch: allocation failures here come from fragmentation, which `gc.mem_free()` does not show. `idf_min_free` is the lowest free level since boot. All `idf_*` figures cover internal RAM only: regions of 1 MiB or more are counted as PSRAM and reported as `psram_free`, since `esp32.idf_heap_info()` cannot filter by capability. On PSRAM boards `gc_free` is mostly PSRAM too. `test_link.py` prints `mem` every 10 s.
- **`host/test_xfer.py`:** sends a file to a receiver in 246-byte frames and checks the SHA-256.
  - **Unicast mode:** each frame waits for its ESP-NOW ACK.
  - **Broadcast mode:** async; shows raw loss under load.
  - **Report:** elapsed ms, KB/s, missing, duplicate and out-of-order frames, and heap before and after on both ends.
  - **Receiver:** any board with an `espnow_manager.py`. It writes the file to flash (`WRITE_FILE`) to match a real code pull.
  - **Receiver knobs:** `WRITE_BUF` batches flash writes into N-byte blocks. `RX_BUF` enlarges the ESP-NOW driver receive buffer on a built-in-manager receiver; the default is 526 B, about 2 frames. The result reports `write_ms`, the total time spent in flash writes.
  - **ACK ≠ delivery:** an ESP-NOW unicast ACK only means the receiver's radio got the frame. A frame can still be dropped afterwards when the driver's receive buffer is full, for example while the receiver is blocked on a flash write.
- **WiFi comparison:** not run and out of scope for now (no Dial/Box on the bench). The WiFi path it would compare against is `BroadcastDial/BDialFirmware/code_server.py` with `MockWand/code_puller.py`.

## ESP-NOW code transfer

This replaces the WiFi `code_server.py` → `code_puller.py` pull with ESP-NOW. There is no radio switch and no reset.

| Side | File | Role |
|---|---|---|
| Host | `host/code_sender.py` | `CodeSender`: answers `code_req`, sends the chunks each `code_get` asks for |
| Host | `host/code_host.py` | Bench main: serves `/flash/games/`; optional repeated remote triggers |
| Wand | `MockWandEUM/lib/espnow_code.py` | `receive()`: request, windowed fetch, verify, promote |
| Wand | `MockWandEUM/main.py` | `getcode` tap (or bench broadcast) runs `receive()`, then launches the game |

**How the transfer runs:**
- **Receiver-driven:** the wand asks for `WINDOW` (8) chunks of 245 B at a time, never more than its 4 KB ESP-NOW rxbuf and 2 KB window buffer can hold.
- **Recovery:** a window left incomplete after 400 ms is requested again from its first missing chunk. The transfer fails after 12 windows in a row with no progress.
- **Flash writes:** batched into 4 KB blocks.
- **Before promotion:** the file is checked for size, SHA-256 and `compile()`. On failure the previous copy stays in place.
- **Several wands:** the host serves up to `MAX_SESSIONS` (6) wands at once, interleaving their windows. They share the link's throughput.
  - **Busy:** a wand over the cap gets a `"busy"` offer with `retry_ms`. It waits that long plus up to as much again at random, then asks again, for at most 120 s. After that it shows the amber pull failure.
  - **Collision avoidance:** each `code_req` waits a random 0–300 ms first, so wands tapped together don't collide.
  - **Peer table:** a wand is a host peer only while it has a session (or for its one refusal reply), so the ~20-entry ESP-NOW peer table never fills.
  - **Bench hook:** `code_host.BUSY_FOR_MS` makes the host answer busy for a while after each trigger, so the retry path can be tested with one wand.

`tests/test_code_xfer.py` runs the real receiver against the real sender over a simulated link. It covers a clean transfer, 25 % loss with duplicates and reordering, refusals, no host, a file that fails to compile (old copy kept), in-transit corruption, the active-slug lookup, 8 concurrent wands against a cap of 3 (busy and retry), 25 wands in a row against the 20-peer limit, and giving up after the busy budget.

## Adding a message type

Classification now runs on the modem, so a new message type touches three places:
1. **Update** the built-in manager's `poll()` in the Bag tree.
2. **Update** `modem/lib/eum_classify.py`.
3. **Add** a code to `CODE_NAMES` in **both** copies of `eum_proto.py`, then reflash the modem.

Unknown types arrive as `("raw", decoded_json, mac)`, as they do with the built-in manager.

## Differences from the built-in manager

- **MAC:** `get_own_mac()` returns the modem's MAC, because that is the address peers see.
- **Broadcast mode in `send_raw` / `send_score`:** both send broadcasts async. The built-in version sends them sync and gets ETIMEDOUT.
- **Missing modem:** if no modem answers within 2 s, or the protocol version differs, `init()` raises `OSError`.
- **Link loss after init:** calls return `False` or `(None, None, None)` and print; they do not raise. See Fault recovery.
- **`shutdown()`:** it sends stop to peers, then `DEACTIVATE`. There is no host radio to release.
- **`self.enow`:** it is always `None`. `code_puller.py` sets it to `None`, which is harmless here.
- **`link_stats()`:** new; it returns modem and host counters.

## Tests

```
python tests/test_proto.py
python tests/test_sim.py
```

`test_sim.py` covers:
- per-request fault reply
- reset after repeated loop faults, with the fault text reported
- a hang, then link down, fail-fast, watchdog reboot, reconnect and restore
- init and MAC
- classified receive, including `find_device` filtering
- send paths
- status-poll passthrough and auto-reply
- a 100-message burst with no loss
- a 200-message burst with 72 drops reported
- `drain()`
- recovery from a corrupt frame
- recovery from a modem reset
- `shutdown()`

On hardware: run `host/test_link.py` against an ordinary MockWand or hub, then run `host/test_burst.py`.

## Not in the PoC

- an ESP32-C6 modem (it would only need the antenna select)
- the EN-pin hard reset (see Fault recovery)
- a data-ready GPIO
- OTA updates for the modem
- a WiFi/BLE coexistence test on the host
