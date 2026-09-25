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
| `tests/test_proto.py` | PC | CPython tests: protocol, classification, copy check |
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

- **Modem:** copy `modem/main.py` to `/`, and `modem/lib/*.py` to `/lib/`.
- **Host:** copy `host/lib/*.py` to `/lib/`, replacing the built-in `espnow_manager.py`. Game files run unchanged.
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
| `STATS` 0x0A | — | rx, tx, tx_fail, rx_overflow, crc_err, dup_drop, len_err (u16 each) |
| `FLUSH` 0x0B | — | discarded count (u16) |

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
- **`shutdown()`:** it sends stop to peers, then `DEACTIVATE`. There is no host radio to release.
- **`self.enow`:** it is always `None`. `code_puller.py` sets it to `None`, which is harmless here.
- **`link_stats()`:** new; it returns modem and host counters.

## Tests

```
python tests/test_proto.py
python tests/test_sim.py
```

`test_sim.py` covers:
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
- a data-ready GPIO
- OTA updates for the modem
- a WiFi/BLE coexistence test on the host
