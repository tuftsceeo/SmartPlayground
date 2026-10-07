# Single-chip BLE + ESP-NOW hub on an ESP32-C6 (MockWand) — bench runbook

C6 ports of the 2026-10-06 StickS3 bench ([../2026-10-06-coex-bench/](../2026-10-06-coex-bench/), results in
[§6 of the research report](../2026-10-06-ble-espnow-concurrency-research.md)). One MockWand is the hub: it
runs BLE to the Splats and ESP-NOW to a second MockWand at the same time.

**Question.** Can one XIAO ESP32-C6 do what the StickS3 did? The airtime split is the same on both chips. The
open questions are:
- **Memory:** no PSRAM, so the GC heap, WiFi, NimBLE and the ESP-NOW ring all share one internal heap.
- **CPU:** one core instead of two.
- **Antenna path:** an RF switch that both radios use.

## What is different on the C6, and what each port does about it

| Constraint | Evidence | What the C6 scripts do |
|---|---|---|
| **Memory is the likely blocker.** WiFi init needs one large contiguous block of IDF DRAM. NimBLE and the GC heap come out of the same internal RAM. | MicroPython #18859: C6 BLE + ESP-NOW fails with `WiFi Out of Memory`. The S3's largest block fell 115 → 47 KB at `BLE().active(True)`. | Log `idf_largest` after every bring-up step. A failed bring-up logs `FAIL` with the numbers, then stops. |
| **The memory picture depends on what ran before the radio.** | MockWand after `main.py`'s imports: 77,824 B largest block before ESP-NOW (`2026-09-26-eum-bench-results.md`). Splat Companion C6 with a lean boot: 270,336 B at boot and 253,952 B after BLE (`2026-09-29-splat-hub-logs/04_*`). | Abort unless the largest block at start is at least `CLEAN_BOOT_MIN_LARGEST` (150,000). A run where `main.py` already ran answers a different question. |
| **Init order.** | #18859 failed with BLE first. The S3 bench brought ESP-NOW up first. The Splat Companion brings BLE up first. | `coex_c6_bench.py` has `ORDER = "enow_first"` or `"ble_first"`. `coex_c6_one.py` is always BLE first. |
| **Game budget.** A pulled game fails at `compile()` on a C6 wand. | Today's wand limit is 36–40 KB of source (`2026-09-30-transfer-comparison-results.md`). | Every bench phase compiles 16, 24, 32 and 36 KB of synthetic source and logs ok/FAIL. |
| **One core.** The WiFi task, NimBLE host and MicroPython all share it. The S3 has two cores. | — | Every test logs `loop stall max`, the longest gap between game-loop iterations. |
| **Antenna.** On a XIAO C6, GPIO3 = 0 enables the RF switch and GPIO14 selects external (1). The switch carries BLE as well as WiFi. Undriven, GPIO3 reads high. | `MockWand/lib/espnow_manager.py`, `SplatCompanion/Companion/boot.py`. The S3 has no switch. | `EXTERNAL_ANTENNA = True` (MockWands have u.FL antennas fitted), set as the first statement, before either radio starts. |
| **Paths.** | MockWand's flash root is `/`, not `/flash`. | Splat modules go in `/coex/`. |
| **`rxbuf` limit.** | The S3 failed between 30000 and 32768. The C6's limit is unknown. | `coex_c6_buf.py` sweeps 4096, 8192, 16384 and 30000. A `ValueError` or `MemoryError` is logged as a result, and the next size still runs. |

Everything else is unchanged from the S3 scripts: tests, frame formats, Splat load and timing.

Reused unchanged:
- **`coex_peer.py`** and **`demo_wand.py`**, both from `../2026-10-06-coex-bench/`. Both already ran on a
  MockWand (C6) as the S3's peer.
- **The Splat modules**, from `SplatCompanion/Companion/`.

## Hardware

- **Hub:** a MockWand with a u.FL antenna fitted, connected over USB.
- **Peer:** a second MockWand. It runs `coex_peer.py` for the bench and `demo_wand.py` for the demo.
- **Splats:** 4 for `coex_c6_bench.py`, `coex_c6_buf.py` and the demo; exactly 1 for `coex_c6_one.py`.
- **Distance:** 1–2 m between hub and peer, the same as the S3 run.

## Setup (once)

Read [Bag3/Code/HARDWARE_PROTOCOL.md](../../../HARDWARE_PROTOCOL.md) first. In particular: ask which board is on
which port, and pass `resume` on every `mpremote` call except a plain `reset`.

From the repo root:

```sh
HUB=/dev/cu.usbmodemXXXX     # hub MockWand -- ask, never guess
PEER=/dev/cu.usbmodemYYYY    # peer MockWand
MP="python3 -m mpremote"
SC=Bag3/Code/BroadcastCode/SplatCompanion/Companion
S3=Bag3/Code/BroadcastCode/docs_and_design/2026-10-06-coex-bench
C6=Bag3/Code/BroadcastCode/docs_and_design/2026-10-07-coex-bench-c6

# Firmware has BLE and esp32.idf_heap_info
$MP connect $HUB resume exec "import sys, bluetooth, esp32; print(sys.implementation)"

# Splat modules on the hub
$MP connect $HUB resume fs mkdir :coex
$MP connect $HUB resume fs cp $SC/splat_link.py $SC/splat_hub.py $SC/splat_api.py $SC/lib/ble_splat.py :coex/

# Disable the wand firmware on the hub so a reset gives a clean boot (boot.py only)
$MP connect $HUB resume exec "import os; os.rename('main.py', 'main_off.py')"
```

The peer keeps its normal firmware. `resume run` interrupts its `main.py`, and the peer scripts reconfigure
ESP-NOW themselves.

## Each run

**Hard reset the hub before every run.** A run leaves the radios up and the heap fragmented.

```sh
mkdir -p $C6/logs
$MP connect $HUB reset
sleep 3
$MP connect $PEER resume run $S3/coex_peer.py > $C6/logs/<name>_peer.log &    # stop it after the run
$MP connect $HUB resume run $C6/<script>.py | tee $C6/logs/<name>.log
```

Keep `resume` on the hub's `run`. Without it, mpremote soft-resets first. A soft reset may not give back heap
that boot already split off; the Dial's fragmentation survived one.

### Run order (about 50 minutes; the person is needed only at the start and for the last ~15)

Unattended runs come first. One person step at the start: switch on 4 Splats. After that, a person is needed
only for the hands-on block at the end.

| # | Script | Splats | Person | Length | What it answers |
|---|---|---|---|---|---|
| 1 | `coex_c6_bench.py`, `ORDER = "enow_first"` | 4 | none | ~12 min | Does BLE start **after** ESP-NOW (the S3 order)? This run also gives the no-BLE baseline the S3 run never reached. ESP-NOW at 1, 2 and 4 Splats, compile budget, 5 min soak. |
| 2 | `coex_c6_bench.py`, `ORDER = "ble_first"`, `SOAK_S = 0` | 4 | none | ~8 min | Does ESP-NOW start **after** BLE (the #18859 order)? The same tests with that order. |
| 3 | `coex_c6_buf.py`, `RUN_BUTTONS = False` | 4 | none | ~8 min | `rxbuf` capacity and limit on a C6. |
| 4 | `coex_c6_buf.py`, `RUN_BUFFER = False` | 4 | presses in two 30 s phases | ~2 min | Splat press latency, quiet vs loaded. |
| 5 | `demo_c6_hub.py`, with `demo_wand.py` on the peer | 4 | plays | 3–5 min | End-to-end play. The hub logs memory and loop stall every 60 s. |
| 6 | `coex_c6_one.py` | 1 (switch 3 off) | presses, ~10 per 30 s phase | ~3 min | BLE alone vs BLE + ESP-NOW latency, one Splat. Skip it if run 2 failed at ESP-NOW bring-up: it uses the same order and would fail after phase A. |

To change `ORDER`, `SOAK_S`, `RUN_BUFFER` or `RUN_BUTTONS`, edit the local file before `run`, then revert it.
mpremote passes no arguments.

If the hub stops at `FAIL: largest free IDF block is below CLEAN_BOOT_MIN_LARGEST`:
1. **Check** that `main.py` is renamed, and that the run used a hard reset and `resume`.
2. **Read** the `MEM start` line.
3. **Lower** the threshold or set it to 0 only if that number is still clearly above the MockWand-with-main.py
   figure (77,824 B).

### Restore the hub afterwards

```sh
$MP connect $HUB resume exec "import os; os.rename('main_off.py', 'main.py')"
$MP connect $HUB resume fs rm -r :coex      # optional
$MP connect $HUB reset
```

## Reading the results

`grep -E '^\[.*\] (RESULT|MEM|FAIL|SPLATS)' logs/*.log` collects the lines that matter.

| Outcome | Meaning |
|---|---|
| `FAIL: ESP-NOW bring-up ... WiFi Out of Memory` | That order does not fit. Keep the `MEM ... FAILED` line: its `idf_largest` is the number to compare with #18859's ~22 KB. |
| `FAIL: BLE().active(True)` | NimBLE could not get its memory after ESP-NOW. |
| `compile N B: FAIL` with BLE up, `ok` in the `no-ble` phase | BLE costs the game budget that much. Today's wand ceiling is 36–40 KB. |
| `loop stall max` far above the S3's figures | Single-core contention. The S3's worst IRQ-to-loop was 88 ms under load. |
| `rxbuf=... FAILED ValueError` | The C6's ring limit sits below that size. |

Pass criteria from the research report (§6, "Against the proposed pass criteria"):
- **Disconnects:** zero Splat disconnects.
- **Unicast:** at least 99% delivered.
- **Bulk:** at least 8 KB/s.
- **Memory:** `idf_largest` at least 40 KB with everything up.

For a C6 hub that will load games, add: **a 36 KB compile passes with 4 Splats connected.**

### S3 numbers to compare against (4 Splats)

- Unicast ping: 300/300.
- Broadcast wand→hub: 84.7%.
- Bulk: 32.2 KB/s.
- Ping RTT p50 / p95: 39 / 104 ms.
- `idf_largest` with BLE up: 47,104 B.

## Limits of this bench

- **A lean script is the best case.** A hub running real firmware imports more before the radio and has less
  contiguous memory.
- **The compile probe uses synthetic source.** Each size is held whole in RAM and then compiled, which is how
  a pulled game is checked. Real game bytecode may cost more or less.
- **Two radios on two MockWands, 1–2 m apart.** The test covers neither range nor more than one wand.
