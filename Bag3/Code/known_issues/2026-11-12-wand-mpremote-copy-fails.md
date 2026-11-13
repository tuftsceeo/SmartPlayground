---
title: mpremote copies to a running Splat host wand fail
date: 2026-11-12
status: open
devices: [Wand (Mock Wand), ESP32-C6]
components: [mpremote deploy, main.py boot grace, Splat host loop]
code:
  - Bag3/Code/Wand Module/main.py
  - Bag3/Code/Wand Module/lib/splat_host.py
  - Bag3/Code/HARDWARE_PROTOCOL.md
open:
  - Confirm that GRACE_S = 30 lets mpremote (not only Thonny) break in after a reset.
  - Decide whether GRACE_S stays non-zero on bench wands only.
keywords: [mpremote, raw repl, could not enter raw repl, timeout, COM7, GRACE_S, Thonny, port in use, deploy]
---

# mpremote copies to a running Splat host wand fail

## Symptom

During the Splat host bench (2026-11-12) every `mpremote` copy to the wand on COM7 failed. Thonny
could still stop the same program with Ctrl-C.

| Attempt | Result |
|---|---|
| `resume fs cp` while the host loop was running | Timed out (rc=124), no output |
| `reset`, then `resume fs cp` straight away | `could not enter raw repl` |
| Same steps, with a `serial_monitor.py` capture left running | Port held; a leftover capture process had to be killed |
| Same steps, with Thonny open | `failed to access COM7 (it may be in use by another program)` |
| `reset`, wait 30 s, then `resume fs cp` | Hung with no output; stopped by hand |

## Causes

- **No boot grace.** `main.py` had `GRACE_S = 0`. `main()` takes the board straight away, and the
  radio (ESP-NOW, then BLE on a host) comes up first. A copy sent just after a reset arrives
  during that bring-up. A copy sent later arrives during the host loop.
- **mpremote breaks in less reliably than Thonny.** Thonny keeps sending Ctrl-C until the REPL
  answers. mpremote's raw-REPL entry sends a few and gives up, so a busy loop that only
  occasionally reads serial misses them. (This is the likely cause; it was not instrumented.)
- **The host loop slept 1 ms per pass.** That leaves little idle time to service USB serial.
  `splat_host.run` now sleeps `HOST_IDLE_SLEEP_MS` (20 ms).
- **One process per port.** Leftover background captures and Thonny each held COM7, and
  `mpremote` then reported the port as in use.
- **Retrying blind.** Repeating the same command after a failure wasted time. The protocol says to
  find out why a call failed before retrying.

## Mitigation

- **The wand's `/main.py` stub waits 30 s before importing `wand_main` (critical).** The stub on
  the wand is saved as `Bag3/Code/Experiments/SplatHostBench/device_main.py`; copy it to
  `/main.py`:

      import time
      print("30 second grace")
      time.sleep(30)

      import wand_main

  Copy, interrupt or run tests only during this window; start test scripts no earlier than 30 s
  after a boot.

- `main.py` `GRACE_S = 30`: after any reset there is a 30 s window to press Ctrl-C before `main()`
  starts. Copy during that window.
- Until the new build is on the wand, stop it in Thonny with Ctrl-C (or copy with Thonny), then
  close Thonny before running `mpremote`.
- Before opening the port, check that no `serial_monitor.py` or `mpremote` process holds it.
