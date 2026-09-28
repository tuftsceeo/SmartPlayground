# NFC-DEP bench: test results

Measurements from two Mock Wands (PN532 firmware 1.6, IC 0x32), wand A as target (`dep_sender.py`),
wand B as initiator (`dep_receiver.py`). Run 2026-09-26 to 2026-09-28. Raw serial output is in
`logs/`. Every value below is copied from those logs; file names are given per row.

## Conditions
- **Bus:** `machine.SoftI2C`, SDA 22 / SCL 23; frequency as set by `I2C_FREQ` and printed in each log.
- **Frame and chunk:** CHUNK=240 data bytes per request; the reply is 244 bytes (4-byte offset + data).
- **Timeout:** `TIMEOUT_CODE` = 0x0B in every run (printed in each `RESULT` line).
- **Spacing:** wands touching in all runs. Steps 5 (distance) and 6 (lift) were not run.
- **Code revision:**
  - `*_gb_*` logs print module REV `2026-09-28b`.
  - Earlier logs predate the REV line; their revisions are as reported by the operator.
  - Those earlier runs used `mpremote resume run` without evicting cached modules, so a
    `pn532_dep.py` change could lag until a reset. Each `RESULT` line prints the timeout code
    actually in effect.

## Transfer results

Medians across the passing runs. `rtt` is the receiver's per-chunk InDataExchange time. `wait` and
`read` are its split into ready-wait and I2C read. `tg_set` and `tg_get` are the sender's per-request
TgSetData and TgGetData phases.

| I2C | Baud | Payload | Code rev | Runs ok | xfer_ms | B/s | rtt ms | wait ms | read ms | tg_set ms | tg_get ms | Logs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 kHz | 106 | 1 KB | pre-a3f6143 | 5 of 6 started | 1199–1219 | 840–854 | 231 | 194 | 32.5 | 138 | 90 | `*_smoke`, `*_linktime` |
| 100 kHz | 106 | 7 KB | a3f6143 | 6/6 | 7044 | 1000 | 231.6 | 194.5 | 32.5 | 138.9 | 90.8 | `*_headline_100k_fixed`, `*_headline_100k_retry` |
| 400 kHz | 106 | 7 KB | pre-0de5723 | 6 of 8 started | 5117 | 1377 | 168.7 | 153.5 | 12.1 | 114.2 | 52.9 | `*_headline_400k`, `*_headline_400k_retry`, `*_headline_400k_fixed` |
| 400 kHz | 106 | 7 KB | 0de5723 | 2/3 | 4779, 4941 | 1474, 1426 | 158.3 | 143.0 | 12.1 | 114.1 | 42.5 | `*_headline_400k_refix` |
| 400 kHz | 212 | 7 KB | 0de5723 | 3/3 | 4409 | 1598 | 145.4 | 130.0 | 12.1 | 102.0 | 41.9 | `*_baud212_400k` |
| 400 kHz | 424 | 7 KB | 0de5723 | 3/3 | 4176 | 1687 | 138.1 | 122.7 | 12.1 | 95.0 | 41.8 | `*_baud424_400k` |
| 400 kHz | 424 | 1 KB | 4a5d986, general bytes off | 1/1 | 699 | 1464 | 138.8 | 123.6 | 12.1 | 95.6 | 39.6 | `*_gb_off_400k_424` |
| 400 kHz | 424 | 1 KB | 4a5d986, general bytes on | 1/1 | 703 | 1456 | 138.3 | 122.9 | 12.1 | 95.6 | 39.7 | `*_gb_on_400k_424` |

The 7 KB payload is `dep_jumpin.bin` (7048 bytes) and the 1 KB payload is `dep_kb1.bin` (1024 bytes).

The "N of M started" rows count runs that were started, including ones cut short when the script
exited early: `B_linktime` after 4 of its 5 runs, `B_headline_400k` after 2 of its 3.

`B_headline_100k.log` contains no `RESULT` line. It ends in `DepError: InRelease status 0x01 (timeout)`.

## Link setup
- **poll_ms** (receiver polling start to link up):
  - 54–56 at 100 kHz / 106 kbps (11 runs);
  - 47–49 at 400 kHz, 106 and 424 kbps;
  - 48, 647 and 1145 at 400 kHz / 212 kbps (`B_baud212_400k`).
- **Empty links:** `A_baud212_400k` logs two links (1 and 4) that were released after 9–10 ms
  with no requests (`ops {}`).
- **ATR_RES from the target:** `aa99887766554433221100000009` followed by PPt, with TO=0x09.

## Frame size (ATR PP byte)

| General bytes | Initiator PPi (from `A_*` log) | Target PPt (from `B_*` log) | Logs |
|---|---|---|---|
| none | `0x00` → LR=0, 64-byte frames | `0x01` → LR=0, 64-byte frames | `*_gb_off_400k_424` |
| LLCP `46666d010110` | `0x02` → LR=0, G=1 | `0x03` → LR=0, G=1 | `*_gb_on_400k_424` |

In the ATR_REQ captured in `A_trace_400k_1kb`, PPi = `0x00`.

## Sender TgSetData phase timing (TRACE on)

Phase times in ms, from single commands with the reply length shown.

| Log | I2C | Baud | Reply bytes | write | ack | wait | read |
|---|---|---|---|---|---|---|---|
| `A_trace_400k_1kb` (runs at 100 kHz, despite its name) | 100 kHz | 106 | 244 | 32.5 | 2.7 | 97.8 | 5.5 |
| `A_trace_400k_1kb` | 100 kHz | 106 | 68 | 10.2 | 1.5 | 31.6 | 5.5 |
| `A_trace_400k_1kb` | 100 kHz | 106 | 2 | 1.9 | 1.5 | 7.1 | 5.5 |
| `A_gb_off_400k_424`, `A_gb_on_400k_424` | 400 kHz | 424 | 244 | 12.2–12.5 | 1.8–1.9 | 78.6–78.9 | 2.1–2.2 |
| same | 400 kHz | 424 | 68 | 4.0 | 1.8 | 25.6 | 2.1–2.6 |
| same | 400 kHz | 424 | 2 | 0.9 | 1.8 | 6.2 | 2.1 |

- **Response read:** a full 255-byte response frame takes 32.5 ms at the 100 kHz setting and
  12.1 ms at 400 kHz (receiver `read_us`).

## Failures

| Log | Run | Receiver line | Sender line |
|---|---|---|---|
| `B_headline_400k_fixed` | 3 | `ready timeout after 1000 ms` in op `D`, after 7048 bytes (sha256 already verified) | `link 3 done+released in 6127 ms` |
| `B_headline_400k_retry` | 2 | `ready timeout after 1000 ms` in op `C`, 6960 of 7048 bytes, 29 chunks | `link 2 FAILED after 6031 ms: ready timeout after 1000 ms` |
| `B_headline_400k_refix` | 2 | `ready timeout after 1000 ms` in op `C`, 2880 of 7048 bytes, 12 chunks | `link 2 FAILED after 2996 ms: ready timeout after 1000 ms` |
| `B_linktime` | 5 | `DepError: InRelease status 0x13 (DEP bad frame format)` after the transfer | — |
| `B_headline_100k` | 1 | `DepError: InRelease status 0x01 (timeout)` | — |

- **Release errors:** the two `InRelease` errors occurred before commit a3f6143, which changed
  release handling. No `InRelease` error appears in later logs.
- **Failure totals:** all three mid-transfer or `D` failures were at 400 kHz / 106 kbps. None
  occurred in the 212 or 424 kbps runs (6 runs) or the 100 kHz / 106 kbps 7 KB runs (6 runs).
