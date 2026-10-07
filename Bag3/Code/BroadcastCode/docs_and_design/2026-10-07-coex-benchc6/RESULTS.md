# C6 coexistence bench results — BLE (Splats) + ESP-NOW on one XIAO ESP32-C6

Hub: MockWand XIAO ESP32-C6 (`/dev/cu.usbmodem1101`), external antenna. Peer: second MockWand
running `coex_peer.py`, external antenna. 2 Splats on hand (S3 bench used 4). MicroPython
1.28.0. Each hub script was run after a plain reset with `main.py` renamed to `main.py.bak`
(radio unclaimed, `idf_largest=270336` at start). Compared against `../2026-10-06-coex-bench/`
(StickS3 hub). One run per test; no repeats.

Logs here: `bench1.log`, `buf1.log`, `btn1_crash.log`, `btn2.log`, `one1.log`.

## Result

BLE and ESP-NOW ran together with 1 and 2 Splats. No Splat dropped (`drops=[0, 0]`) and no write
failed in any run. Button response matches the S3. ESP-NOW unicast on this C6 pair is much
slower than on the S3 regardless of BLE, and 2-Splat loaded broadcast receive is lower.

## Bench (`coex_bench.py`, `bench1.log`)

Differences from the S3 run: Splat counts 1 and 2 (S3: 1, 2, 4); soak 60 s (S3: 300 s).

| Phase | Ping acked | Ping rtt p50 / max | Send ms p50 | Bcast rx | Bcast tx | Bulk KB/s |
|---|---|---|---|---|---|---|
| splats=1 [t=11.47–30.14] | 300/300 | 3333 / 6589 ms | 19.5 | 93.3% | 100% | 12.1 |
| splats=2 [t=43.13–62.82] | 300/300 | 169 / 1116 ms | 8.2 | 96.0% | 100% | 8.9 |
| ble-idle [t=132.94–152.11] | 300/300 | 1127 / 4564 ms | 12.4 | 100% | 100% | 10.4 |
| ble-off [t=160.25–179.04] | 300/300 | 3015 / 6571 ms | 19.6 | 100% | 100% | 11.4 |
| S3 splats=1 (`bench1.log`) | 300/300 | 25 / 151 ms | 1.9 | 98.3% | 100% | 43.6 |
| S3 splats=2 | 300/300 | 25 / 92 ms | 1.9 | 93.3% | 100% | 39.4 |

- Soak, 2 Splats, 60 s [t=62.86–123.46]: 600/600 pings acked, 600/600 echoed, both Splats
  connected, no drops. The S3 log stops at the 269 s soak report, so it has no S3 soak
  result line or S3 ble-idle/ble-off rows.
- With BLE off (ble-off row) send time is still 19.6 ms and bulk 11.4 KB/s, so the slow
  ESP-NOW path is not caused by BLE. Cause not found.
- Every unicast was ACKed first try (`bulk first-try=151 retried=0 failed=0` in all phases).
- Heap (`idf_largest`): 270336 start [t=0.00], 237568 after ESP-NOW [t=0.24], 208896 after BLE
  [t=0.48], 143360 after Splat modules [t=1.89], 135168 at splats=2 [t=62.86]. S3: 47104
  after BLE [`bench1.log` t=0.33].

## Receive buffer (`coex_buf.py`, `buf1.log`), 2 Splats

Frames held in a back-to-back burst while the loop is blocked: 62 at `rxbuf=16384` [t=32.21],
114 at 30000 [t=58.29]. Identical to the S3 (62, 114; S3 `buf2.log`). `rxbuf=30000` allocated.

Stall sweep (250-byte frames every 20 ms, 100 sent):

| Stall | rxbuf=16384 | rxbuf=30000 |
|---|---|---|
| 0–100 ms | 99–100% | 99–100% |
| 200 ms | 100% | 84% |
| 500 ms | 100% | 100% |
| 1000 ms | 80% [t=29.37] | 79% [t=55.47] |

`rx_dropped=+0` in every row, so the losses at 1000 ms (and the 84% at 200 ms) occur outside
the driver receive buffer. Cause not found. S3 rows used 4 Splats and varied 65–97% with no
clear trend with stall.

## Buttons (`coex_buf.py`, `btn2.log`), 2 Splats

| | Quiet [t=36.52] | Loaded [t=67.38] | S3 quiet / loaded (4 Splats, `btn1.log`) |
|---|---|---|---|
| Presses per Splat | [13, 17] | [21, 24] | [5,5,10,6] / [5,5,3,7] |
| IRQ-to-loop p50 / p95 / max | 1 / 2 / 3 ms | 1 / 4 / 41 ms | 2 / 15 / 17 and 3 / 88 / 88 ms |
| Write-to-notify p50 / p95 | 35.0 / 98.7 ms | 43.3 / 134.1 ms | 42.2 / 143.2 and 39.5 / 144.2 ms |
| ESP-NOW bcast received | — | 85.4% (1281/1500) | — / 98.0% |

`btn1_crash.log`: the first loaded phase stopped with `MemoryError` allocating 6508 bytes in
the receive callback (`seen` was a `set` of up to 1500 ints; the C6 has no PSRAM). The quiet
phase of that run: presses [18, 31], IRQ-to-loop p50 1 ms [t=35.66]. `coex_buf.py` and
`coex_one.py` now count frames in a bitmap; `btn2.log` is from that version.

## One Splat (`coex_one.py`, `one1.log`)

| Phase | Presses | IRQ-to-loop p50 / max | IRQ-to-red-write p50 / max | Write-to-notify p50 / p95 |
|---|---|---|---|---|
| A BLE only [t=33.98] | 14 | 1 / 2 ms | 2 / 10 ms | 131.1 / 142.9 ms |
| B ESP-NOW idle [t=66.23] | 25 | 2 / 3 ms | 4 / 44 ms | 33.5 / 88.5 ms |
| C ESP-NOW loaded [t=97.08] | 30 | 1 / 10 ms | 2 / 53 ms | 30.4 / 109.7 ms |
| S3 A / B / C (`one1.log`) | 39 / 35 / 47 | 1/9, 1/23, 1/7 ms | 2/53, 2/72, 3/50 ms | 111.7/147.1, 41.6/128.5, 16.0/94.0 ms |

Loaded phase C: broadcasts received 1496/1500 (99.7%), pings ACKed 300/300 (S3: 96.6%,
300/300). The 1-Splat loaded receive (99.7%) is higher than the 2-Splat loaded receive
(85.4%, `btn2.log`); the two runs differ in Splat count and in who pressed what, so the
cause is not isolated.

## Caveats

- **Press counts are unreliable.** Every button run logged more presses than the ~5–10
  requested (13–31 per Splat, 14–30 in `coex_one`). The tester's own counts were not
  recorded. The count may include contact bounce, so latency percentiles are over events
  that may not each be a real press.
- 2 Splats versus the S3's 4; 60 s soak versus 300 s; single runs. S3 button/loaded rows
  are not like-for-like with the C6's.
- The demo (`demo_hub.py` / `demo_wand.py`) was not run.
- Both wands still have `main.py` renamed to `main.py.bak`.
