# M1 results — BLE after main.py's import load, and wand-to-wand ESP-NOW unicast on the C6

Boards: two MockWand XIAO ESP32-C6, external antennas, MicroPython 1.28.0. `/dev/cu.usbmodem1101`
is the hub in every run except `raw_A_swap` and `raw_C_swap`; `/dev/cu.usbmodem3101` is the
peer. Each run: both boards reset with `main.py` renamed to `main.py.bak` (restored afterward),
then the peer script started, then the hub script. Splats: `AB:42:00:00:20:60`,
`AB:42:00:00:6D:27` (found by `scan_splats.py`, advertising scan only). One run per
configuration except `raw_A`, which has a first run without receive draining (see Caveats).

Logs here: `bench_ble1.log`, `uni_<run>.log` (hub), `peer_<run>.log` (peer, per-ping `PEERPING`
lines). Scripts: `bench_wand_ble.py`, `coex_bench_m1.py`, `coex_peer_m1.py`, `scan_splats.py`.

## Q1: BLE and 2 Splats after main.py's imports — pass

`bench_wand_ble.py` (`bench_ble1.log`): main.py's module-scope imports, `game_store` step, main.py's
hardware objects (Leds, PowerLed, SoftI2C, Buzzer, pins), then `ESPNowManager().init()`, then BLE.

| Step | idf_largest | idf_free | gc_free |
|---|---|---|---|
| after imports [t=0.79] | 208896 | 225160 | 261616 |
| module objects [t=1.59] | 208896 | 225160 | 260256 |
| after `enow.init()` [t=3.48] | 172032 | 183440 | 220352 |
| `BLE().active(True)` [t=4.30] | 143360 | 154972 | 190400 |
| Splat modules imported [t=7.21] | 143360 | 154972 | 172832 |
| Splat 1 READY [t=10.38] | 139264 | 151684 | 157488 |
| Splat 0 READY [t=12.22] | 135168 | 148396 | 139616 |
| after 6 color writes [t=15.80] | 135168 | 148396 | 135328 |

- `enow.init()` succeeded, `BLE().active(True)` succeeded, both Splats reached READY first
  attempt (`connects=[1, 1]`, `misrouted=0`), `write_failures=0`.
- Without main.py's imports (`uni_raw_C.log`): 270336 at start [t=0.01], 172032 after ESP-NOW
  [t=0.22], 143360 after BLE [t=0.46]. After ESP-NOW the two starts match (172032); the wand
  import load had already taken 270336 → 208896 before ESP-NOW.
- SPEC §4's boot order (ESP-NOW, then BLE, then Splat modules) worked in this one run. The
  idf_largest figures in SPEC §4 (237568 / 208896 / 143360) differ from these: 172032 after
  ESP-NOW and 143360 after BLE here.
- Not exercised: NFC reader, the LED matrix running, Stage 1–4 boot, the idle loop.

## Q2: unicast send time and echo latency

Columns: `send` is the time spent inside the hub's `send()` call; `rtt` is send start to echo
pickup at the hub (the hub drains after every send). Hub send is synchronous (MAC ACK) unless
noted, the peer echoes with sync send unless noted. pm=1 is the boards' default WLAN
power-management value, pm=0 is `PM_NONE`.

| Run / condition | Gap | send p50 / p95 / max ms | rtt p50 / p95 / max ms | Bulk KB/s |
|---|---|---|---|---|
| `raw_A`, hub 1101, no BLE ever, pm=1 [t=14.85] | 20 | 18.3 / 58.9 / 91.3 | 29 / 68 / 98 | 5.4 |
| same [t=78.76] | 200 | 24.1 / 75.1 / 118.2 | 24 / 75 / 118 | |
| `raw_A`, hub send async [t=53.69] | 20 | 0.4 / 0.6 / 0.8 | 36 / 102 / 161 | |
| `raw_A`, hub send async [t=128.97] | 200 | 0.6 / 0.6 / 0.6 | 28 / 81 / 101 | |
| `raw_A`, peer echo async [t=40.02] | 20 | 19.1 / 66.1 / 170.3 | 29 / 79 / 170 | |
| `raw_A`, pm=0 [t=154.03] | 20 | 28.1 / 96.7 / 169.1 | 34 / 99 / 170 | 7.3 |
| `raw_A_swap`, hub 3101, no BLE ever [t=14.70] | 20 | 1.6 / 2.9 / 11.4 | 123 / 223 / 277 | 48.9 |
| same [t=67.05] | 200 | 1.7 / 2.1 / 3.7 | 16 / 61 / 85 | |
| `raw_A_swap`, peer echo async [t=28.32] | 20 | 1.7 / 2.3 / 4.4 | 23 / 62 / 103 | |
| `raw_A_swap`, pm=0 [t=133.53] | 20 | 1.7 / 3.0 / 5.4 | 463 / 1032 / 1092 | 50.1 |
| `mgr_A`, hub 1101, `ESPNowManager.init()` [t=15.16] | 20 | 9.6 / 62.5 / 101.5 | 26 / 80 / 109 | 8.5 |
| same [t=68.50] | 200 | 18.4 / 68.4 / 88.4 | 19 / 69 / 89 | |
| `raw_B`, peer BLE on, hub never [t=14.94] | 20 | 7.0 / 48.3 / 81.7 | 15 / 57 / 87 | 9.2 |
| same [t=39.98] | 200 | 18.4 / 58.4 / 109.0 | 19 / 59 / 109 | |
| `raw_C`, hub BLE + 2 Splats, default interval [t=19.35] | 20 | 6.7 / 39.2 / 95.9 | 13 / 49 / 224 | 8.0 |
| same [t=44.44] | 200 | 10.3 / 56.9 / 77.5 | 16 / 59 / 82 | |
| `raw_C`, 2 Splats, interval 30 ms [t=85.29] | 20 | 18.7 / 76.2 / 102.1 | 29 / 93 / 168 | 4.7 |
| same [t=110.44] | 200 | 27.8 / 112.7 / 260.0 | 30 / 113 / 261 | |
| `raw_C`, 2 Splats, interval 100 ms [t=140.59] | 20 | 10.6 / 74.1 / 139.0 | 30 / 90 / 165 | |
| same [t=165.84] | 200 | 28.5 / 104.2 / 448.0 | 29 / 109 / 449 | |
| `raw_C`, 2 Splats + peer BLE on [t=198.65] | 20 | 18.9 / 82.9 / 308.5 | 30 / 108 / 309 | 8.2 |
| same [t=223.85] | 200 | 18.2 / 58.0 / 107.6 | 19 / 59 / 108 | |
| `raw_C`, hub BLE on, no links, peer BLE on [t=245.74] | 20 | 18.9 / 58.9 / 81.0 | 29 / 69 / 105 | |
| `raw_C`, hub BLE off again, peer BLE on [t=285.94] | 20 | 19.1 / 60.6 / 106.7 | 29 / 69 / 111 | |

Every unicast in these runs was ACKed (`acked` equals `sent`; bulk `retried=0 failed=0`);
echoes back 297–300 of 300 in the rows above.

What the logs show:
- **Slow sync send tracks the sending board.** With 1101 as hub, send p50 is 6.7–28.5 ms in
  every row. With 3101 as hub (`raw_A_swap`), send p50 is 1.6–1.7 ms and bulk is 49–50 KB/s.
  3101's own echo sends in `raw_A` (peer log) are 1.7–2 ms: 272 of 300 echoes took 1–2 ms
  (`peer_raw_A.log`). In `raw_A_swap`, 1101 as the echoing peer makes rtt 123 ms p50 at a 20 ms gap.
- **Send time on 1101 moves in steps of about 10 ms** (a 5 ms-bucket histogram of the 20 ms-gap
  `raw_A` hub send times has populations at 0–5, 15, 25, 35, 55, 65 ms).
- **No variable tested removes it on 1101.** BLE never activated (`raw_A`), BLE on the peer
  (`raw_B`), BLE on the hub with and without Splats (`raw_C`), fixed 30 and 100 ms connection
  intervals, 20 and 200 ms gaps, async echo, `PM_NONE` all leave send p50 between 6.7 and 28.5 ms.
  Async hub send returns in 0.4–0.6 ms with echo rtt 28–36 ms p50.
- **Run-to-run spread on 1101 is large.** Sync send p50 at a 20 ms gap with no BLE: 18.3 ms
  (`raw_A`), 9.6 (`mgr_A`), 7.0 (`raw_B`, peer BLE on); with BLE + 2 Splats at default interval 6.7
  ms (`raw_C`). Those lower values do not line up with BLE being on.
- **`espnow_manager` setup** (default rxbuf, no channel config) vs raw setup: send p50 9.6 vs
  18.3 ms at 20 ms gap on 1101, 18.4 vs 24.1 at 200 ms; bulk 8.5 vs 5.4 KB/s. Single runs.
- The demo's 2 ms hub→wand sends (`coex-benchc6/demo_hub.log`) were in a session whose port names
  may not map to these boards; which board sent them is not known. Cause not found.
- **Cause of the slow send on 1101: not found.** Not isolated: the two boards' hardware
  (antenna, module, firmware images), each board's `/lib` copies, and USB power.

## Swapped hub with Splats (`raw_C_swap`, hub 3101)

`SplatHub` on 3101 logged "no Splat found for unit 0/1" for every discovery from t≈2 to the
end of the run (`uni_raw_C_swap.log`), with both Splats switched on and advertising to 1101's scan a few
minutes earlier. `connects=[0, 0]` throughout. The run was stopped at t≈405 s. Its rows
(`s0`, BLE active, no links) are send p50 1.7 ms, bulk 13–14 KB/s, but rtt p50 777–4531 ms
with 204/300 echoes back at 20 ms gap, because the 1101 peer's echo sends are slow. Why 3101 found
no Splat is not known: not tested whether the Splats were still connected from the earlier
run, and not tested with 3101's antenna setting.

## Caveats

- First `raw_A` run (`uni_raw_A_nodrain.log`) did not read the receive buffer between sends
  when `send()` took longer than the gap; its rtt p50 of 1062–2953 ms is pickup delay at the hub.
  `coex_bench.py` has the same loop, so the coex-benchc6 rtt figures (169–3333 ms) include it.
  The send-call times in that log (19.5 ms p50) match the drained rerun. `coex_bench_m1.py`
  drains after every send.
- The hub's echo arrival time is the pickup time in `irecv`, not the radio arrival time.
- Single runs; only two Splats, so no Splats on the peer, no 1-Splat-per-wand case, no 4 Splats.
- `bench_wand_ble.py` is compiled on the wand ahead of its imports; main.py itself is not
  loaded, and boot.py's memprobe import is present as in a normal boot.
- No NFC, LED animation or game code ran. Splat colors/sounds were not observed.
- `scan_splats.py` read MACs from advertising; it did not connect.
