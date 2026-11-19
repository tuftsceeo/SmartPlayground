# Multi-controller bench, 2026-11-18

Raw logs and host scripts behind the "Bench results" section of
`../2026-11-18-stress-test-debrief.md`. Host-side only; nothing here runs on a device.

## Hardware

**Controllers.**

| Label | Board | `host_id` | Port |
|---|---|---|---|
| dialA | Broadcast Dial | 5094 | `usbmodem3101` |
| dialB | Broadcast Dial | 004c | `usbmodem101` |
| box | Broadcast Box | cd64 | `usbmodem1101` |

The controllers were in use from T1 onward. The single-Dial runs used dialA only.

**Devices answering.** 17 in all: 16 wands and 1 IconDisplay.

**USB wand logs.** `wand101.log` and `wand1101.log` cover the single-Dial runs only. Their
monitor starts at host time 1795030600.05.

## Files

| Run | Script | Log | Analysis |
|---|---|---|---|
| Single Dial, first 8 baseline scans | `scan_timing.py` | `baseline.jsonl` | printed |
| Single Dial: baseline, storms, Find, Rescan spam | `runner.py` | `run.jsonl` | `analyze.py` → `analysis_run1.txt` |
| Single Dial: threshold storms, random polls | `runner2.py` | `run2.jsonl` | `analysis_run2.txt` |
| T1, three controllers scanning | `multi.py` | `t1.jsonl` | `analyze_multi.py` → `analysis_t1.txt` |
| T2: sends, scans, Finds | `t2.py` + `t2cfg.json` | `t2.jsonl` | `analyze_t2.py` |
| Find control (k1/k2/k3) | `t2.py` + `t3cfg.json` | `t3ctl.jsonl` | inline in the debrief |

**Log format.** Every log line is JSON:
- `ta`: absolute host time
- `ph`: phase
- `c`: controller label
- then one of `sent`, `rx`, `scan_start` or `readerr`

**Box dropout.** The Box dropped off USB 51 s into `k3_finds_real` (`readerr`). Afterwards
it re-enumerated but was silent: see `box_check.log`.
