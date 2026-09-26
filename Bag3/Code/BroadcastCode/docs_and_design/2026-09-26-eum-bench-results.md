# 2026-09-26 — ESP-NOW UART modem (EUM) bench results

Hardware results for `EspnowModem/` on branch `claude/espnow-uart-modem-poc-3tx37r`.
The runs were made by a local agent following `Bag3/Code/HARDWARE_PROTOCOL.md`;
the numbers below are copied from its reports. Raw serial captures were not
committed.

**Hardware**
- **Modem and host:** two M5StickS3 boards, stock UIFlow2 firmware, wired over UART1 (GPIO43/44) at 921600 baud.
- **Receiver:** a MockWand (Seeed XIAO ESP32-C6, no PSRAM).
- **Other traffic:** a paper remote (5C:01:3B:0D:BE:94) was also in range.

## Link and recovery (commits up to `d47732d`)

| Test | Result |
|---|---|
| Host → modem → wand broadcast, 2 min | `tx ok=True` every second; real start_game/status_poll/stop received from the paper remote; all error counters 0 |
| Modem power-off/on (twice) | link down after 3 timeouts → link restored → state restored → broadcasts resume; `host_resets_seen` incremented |
| UART wire pull/replug, TX then RX, no power loss (twice) | same recovery sequence; `host_resets_seen` stayed 0 (reconnect correctly told apart from a modem reset) |
| Host unicast `send_start_game` / `send_stop_to` to a real wand | both ACKed; wand visibly started and stopped the game |
| Burst, 100 broadcasts (`test_burst.py`) | 96/100 in order, 0 modem ring drops; the 4 lost equal one timed-out FETCH (`FETCH_MAX` = 4) |

**Findings:**
- **Write paths:** `/no_wdt` and `/last_error.txt` could not be written at the filesystem root on UIFlow2 (ENODEV). Both were moved under `/flash`.
- **Ctrl-C:** `mpremote` sends Ctrl-C, and the modem's `except Exception` guards let it through, so the program drops to the REPL. This is intentional, so the modem stays stoppable.

## Memory (commit `34bb487`)

- **What the figures cover:** the IDF heap figures now count internal RAM only. Earlier figures of ~8 MB were PSRAM.
- **MockWandEUM boot (C6):** largest free IDF block 77,824 B at `pre-enow`, 41,984 B at `post-enow` (with the 4 KB ESP-NOW rxbuf). No "WiFi Out of Memory".
- **During transfers:** the wand's largest free IDF block stayed at 40,960 B before and after every transfer.

## Raw ESP-NOW file push (`test_xfer.py`, commit `bfda95c`)

Setup: host+modem sender, stock MockWand receiver (default 526 B rxbuf, one
flash write per chunk), sending a 56,926 B file in 246 B frames.

| Mode | Throughput | Frames received | Notes |
|---|---|---|---|
| Unicast, sync (3 runs) | ~16 KB/s | 183–193 / 232 | 0 send failures: frames ACKed by the radio were then dropped in the receiver's full rxbuf |
| Broadcast, async (3 runs) | ~22.6 KB/s | 156–167 / 232 | loss expected |

This result led to the receiver-driven windowed protocol below.

## ESP-NOW code transfer (`code_sender.py` → `MockWandEUM/lib/espnow_code.py`, commit `b764134`)

Setup: 8-chunk windows of 245 B, 4 KB rxbuf, batched 4 KB flash writes, and
size, SHA-256 and `compile()` checks before promotion.

| File | Size | Runs OK | Total ms | Body ms | Body KB/s | Frames | Dup | Launched |
|---|---|---|---|---|---|---|---|---|
| jumptest (`jump.py`) | 5,654 B | 3/3 | 1400–1678 | 587–947 | 5.8–9.4 | 24 | 0 | yes |
| gesttest (`gestures.py`, largest built-in) | 27,870 B | 3/3 | 3688–4347 | 2581–2755 | 9.9–10.5 | 114 | 0 | yes |
| bigtest (MockWand `main.py`) | 56,926 B | 0/4 | 5467–6957 | 5182–6702 | 8.3–10.7 | 233 | 0 | no |

- **Clean data path:** every transfer arrived byte-exact, with no re-requests needed.
- **bigtest rejection:** bigtest was rejected before promotion with `too large to compile here (56926 B source, 152384 B gc free): memory allocation failed, allocating 41216 bytes`. That block is larger than the wand's 40,960 B largest free block, so the game could not have been imported either. The previous copy stayed in place.
- **gesttest margin:** gesttest's lowest `min_gc_free` was 41,552 B, close to that ceiling. About 28 KB of source is the practical per-game limit on this wand while its firmware is running.
- **Link health:** `modem_crc_err`, `modem_faults`, `host_timeouts` and `host_resets_seen` were all 0 across these runs.

**Harness gap:** a successful transfer launches the game, which holds the
wand's loop, so the next remote trigger timed out. During the session this
was worked around by broadcasting stop between runs. `code_host.py` now does
this itself (`STOP_LEAD_MS`).

## Not measured

- **WiFi comparison:** no WiFi `code_server.py` / `code_puller.py` baseline; no Dial or Box was available.
- **Watchdog:** the watchdog firing on a real hang (only power-cycle and wire-pull recovery were tested).
- **Boot banner:** the modem's boot banner was never captured; `mpremote reset` re-enumerates USB before it prints.
