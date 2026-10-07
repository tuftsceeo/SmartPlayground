# coex-benchc6 — BLE (Splats) + ESP-NOW on one XIAO ESP32-C6

The `2026-10-06-coex-bench` tests, run with a XIAO ESP32-C6 (MockWand board) as the
single-chip hub in place of the StickS3. Test logic, constants, phases and `RESULT`
line formats match the S3 scripts, so logs compare line for line.

| File | Runs on | Differs from the S3 copy |
|---|---|---|
| `coex_bench.py` | C6 hub | antenna select; `/coex` path |
| `coex_buf.py` | C6 hub | same |
| `coex_one.py` | C6 hub | same |
| `demo_hub.py` | C6 hub | same |
| `coex_peer.py`, `demo_wand.py` | second board (MockWand) | none (byte-identical) |

## Antenna

Both bench wands have u.FL antennas fitted, so each hub script has `EXTERNAL_ANTENNA = True`
and the peer uses `espnow_manager`'s setting (also `True`). The S3 hub used its own antenna.

## Splat count

Two Splats are on hand, so the hub scripts use 2 where the S3 run used 4 (`SPLAT_COUNTS`
`(1, 2)`, `connect(2)`, `SPLATS = 2`). The S3 four-Splat rows have no C6 counterpart; compare
the 1- and 2-Splat rows.

## Setup

Per `Code/HARDWARE_PROTOCOL.md`: ask for the ports, and pass `resume` on every `mpremote` call.

```bash
HUB=/dev/cu.usbmodemXXXX ; PEER=/dev/cu.usbmodemYYYY
# Hub: Splat libs into /coex (ble_splat comes from SplatCompanion/Companion/lib)
python3 -m mpremote connect $HUB resume fs mkdir :/coex
C=../../SplatCompanion/Companion
python3 -m mpremote connect $HUB resume \
  fs cp $C/splat_link.py :/coex/splat_link.py + fs cp $C/splat_hub.py :/coex/splat_hub.py + \
  fs cp $C/splat_api.py :/coex/splat_api.py + fs cp $C/lib/ble_splat.py :/coex/ble_splat.py
```

Reset the hub (`mpremote connect $HUB reset`) before each run so the radio claims its
memory first; a previous run's heap state invalidates the result.

## Runs

```bash
python3 -m mpremote connect $PEER resume run coex_peer.py      # leave running
python3 -m mpremote connect $HUB  resume run coex_bench.py     # unattended, ~7 min
python3 -m mpremote connect $HUB  resume run coex_buf.py       # 4 Splats; buttons need a person
python3 -m mpremote connect $HUB  resume run coex_one.py       # 1 Splat; needs a person
python3 -m mpremote connect $PEER resume run demo_wand.py      # with demo_hub.py on the hub
```

Static check only: `python -m py_compile <file>`.

## Compare against

`../2026-10-06-coex-bench/*.log`: `bench1.log`, `buf1.log`/`buf2.log`, `btn1.log`, `one1.log`,
`demo_*.log`. The `MEM` lines (`idf_largest` after ESP-NOW and after BLE) are the
C6 DRAM headroom figures; the C6 has no PSRAM.
