# WiFi pull speed — 2026-09-30

One Broadcast Dial serving one MockWand.

## Setup

| Item | Value |
|---|---|
| Firmware | `Chat_to_Tap_Doggle` at `f91fc34`, verified by read-back |
| Dial | `broadcast_dial`, host_id `5094` (`SP-FILEPUSH-5094`) |
| Wand | MockWand (ESP32-C6), external antenna |
| Diagnostics | `DEBUG_SERVE = True`, `DEBUG_PULL = True`, on-device only |
| Test files | `tools/devtests/make_speed_games.py`: `speed05/10/20/40.py`, exactly 5120 / 10240 / 20480 / 40960 B |
| Trigger | scripted: `pull_flag.set_pending(slug, '5094')`, then `mpremote reset` |
| Runs | 1 trial, then 5 pulls per size. The `tilt_tones` control was not run. |

## Measures

| Field | From | To |
|---|---|---|
| `join_s` | wand `# pull mode: attempt` | wand `joined` |
| `body_ms` | wand `# DBG body done ... ms=` (first body read to last byte) | |
| `verify_s` | wand `# DBG body done` | wand `[XFER] OK: ... promoted` (sha256, `compile()`, rename) |
| `total_s` | wand `# pull mode: attempt` | wand `[XFER] OK` |
| `dial_age_ms` | Dial `# DBG finish ... age_ms=` (accept to finish) | |

## Results

Median [min–max] of 5.

| Size | Passed | join_s | body_ms | verify_s | total_s | dial_age_ms |
|---|---|---|---|---|---|---|
| 5120 B | 5/5 | 7.06 [6.95–7.15] | 841 [804–939] | 0.35 [0.27–0.43] | 8.82 [8.32–9.05] | 1424 [1219–1526] |
| 10240 B | 5/5 | 6.96 [6.76–7.37] | 1101 [1074–1291] | 0.33 [0.24–0.92] | 8.61 [8.55–9.52] | 1695 [1478–2153] |
| 20480 B | 5/5 | 6.99 [6.85–7.08] | 2142 [2013–2251] | 0.46 [0.28–0.59] | 9.94 [9.55–10.32] | 2837 [2606–2987] |
| 40960 B | 1/5 | 7.32 [7.13–7.40] | 4050 [3965–4070] | 0.47 (1 pass) | 12.14 (1 pass) | 4515 [4419–4747] |

- **Transfer rate: 10.8 KB/s.** This is a linear fit of `body_ms` against size (19 pulls, R² 0.994), with an intercept of ~0.3 s.
- **Join: ~7 s per pull, independent of size.** In a 5 KB pull, the time before the first body byte breaks down as:

  | Step | Time |
  |---|---|
  | Import `code_puller` | ~1.1 s |
  | Radio reset + scan | ~2.5 s |
  | Connect | ~1.7 s |
  | Request to header | ~0.35 s |

- **Verify is 0.3–0.5 s** and grows little with size.
- **`dial_age_ms` exceeds `body_ms` by 0.4–0.7 s.** The difference covers the request, the header and the ack.

## 40 KB

| Run | Result |
|---|---|
| 1 | OK |
| 2 | `compile()` MemoryError, allocating 41216 bytes |
| 3 | `compile()` MemoryError, allocating 39168 bytes |
| 4 | `compile()` MemoryError, allocating 41216 bytes |
| 5 | Dial `finish ok=False`; wand log truncated when the bench stopped |

- **Runs 2–4 transferred every byte:** `sent=40960/40960 blocked=0` on the Dial, `body done 40960/40960` on the wand.
- **The wand kept the previous game each time:** it rejected the `.part` file, then booted normally.
- **20480 B is the largest size tested that passed 5/5.** Nothing between 20 and 40 KB was tested.

## Dial IDF heap

| Point | idf_free | idf_largest |
|---|---|---|
| Armed | 29216 | 20480 |
| Idle, after the trial pull | 28500 | 16384 |
| At each `DBG finish` | 25696–26120 | 11264–16384 |
| Idle, after the last pull | 28192 | 16384 |

No `serve_guard` reboot or warning. The guard samples total `idf_free` only while the Dial is idle (no clients, no stations).

## Example lines

Wand, `speed05` run 1:

```
# pull mode: attempt 1/1 for 'speed05' on host '5094'
# code_puller rev phase0-2026-09-04
  found SP-FILEPUSH-5094 on ch=1 rssi=-38
# DBG joined SP-FILEPUSH-5094 ... after 9 ticks
[XFER] receiving /games/speed05.py, 5120 bytes expected
# DBG body done 5120/5120 assoc=True ms=804
[XFER] OK: /games/speed05.py promoted, 5120 bytes
```

Wand and Dial, `speed40` run 2:

```
# DBG body done 40960/40960 assoc=True ms=3965
[XFER] rejected: /games/speed40.py.part does not compile: memory allocation failed, allocating 41216 bytes
# pull failed mid-transfer -- resetting to retry (1/1 spent)

# DBG finish ok=False state=ack sent=40960/40960 age_ms=4513 sel=85 blocked=0 clients=0 stations=1 idf_free=25900 idf_largest=14848
```

Raw serial captures were not committed.
