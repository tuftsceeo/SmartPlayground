# Reboot-bracketed code pull — validation + implementation plan

**Status:** Phase 0 not yet run. Everything in Phase 1 is gated on it.

---

## Serial port etiquette — applies to every step

**Before opening any serial port — `screen` or `mpremote`, either board — stop,
tell the user which port is needed and why, and wait for explicit confirmation
that they have closed anything holding it.** The user connects to these devices
to verify results and will not always have released the port. No exceptions,
including "just a quick read".

Known ports (confirm, don't assume):
- Wand (Xiao ESP32-C6, vanilla MicroPython v1.27): `/dev/cu.usbmodem101`
- Box (M5Stack StickS3, UIFlow2): `/dev/cu.usbmodem3101`

**StickS3 / UIFlow2 constraints:** boots in **>20 s**, and **every `mpremote`
command resets the board**. Use `mpremote` on the S3 for file transfer only;
read output with `screen`. The C6 is vanilla MicroPython and iterates fast —
`mpremote` is fine there.

---

## Context — what is already established

The wand cannot join the Box's `SP-FILEPUSH` SoftAP after ESP-NOW has been
running. Root cause is isolated:

| Finding | Evidence |
|---|---|
| **Cold radio joins and transfers perfectly** | `COLD_RESULT True` — clean join, `ip=192.168.4.2`, `jumpin.py` 4627 bytes received and promoted, first try |
| **Warm radio (ESP-NOW → shutdown → join) fails reproducibly** | `STAT_WRONG_PASSWORD (202)` then stuck `STAT_CONNECTING (1001)` for the full 15 s, both attempts, every NFC-triggered trial |
| Credentials are fine | Both sides hardcode `playground1`; wand confirms `pwd_len: 11` |
| AP config is fine | Box readback `authmode=4`; wand scan `SP-FILEPUSH ch=1 rssi=-44 sec=4` |

**Ruled out — do not re-explore:**
- `code_server.py`'s extra `ap.config(channel=1)` call (confirmed intact from both ends)
- Antenna GPIO 3/14 toggle, the `sta.active(False)`/`active(True)` cycle, the
  pre-join `scan()`, connect-by-BSSID — **all four ran identically in the cold
  (passing) and warm (failing) trials**, so none of them is the differentiator
- Brownout, heap exhaustion, "AP never came up" — a successful scan disproves all three

The only remaining difference between pass and fail is whether
`espnow.ESPNow()` was constructed, activated and torn down beforehand.

### Why a reboot should fix it

MicroPython's `network` module exposes `active(False)` → `esp_wifi_stop()`, but
**not** `esp_wifi_deinit()`. The `WRONG_PASSWORD`-then-stuck signature points at
the 4-way handshake's crypto context, which plausibly lives below `stop()`. If
so, no sequence of MicroPython calls can clear it — but a full chip reset will.

And the round trip was never required: `main.py` already calls
`machine.reset()` after a successful pull, so the wand returns to ESP-NOW via
the reboot. Only ESP-NOW → WiFi **within one boot** has to be avoided.

---

## Phase 0 — the validation test (~15 minutes, gates everything else)

**The question:** does `machine.reset()` clear whatever ESP-NOW leaves behind?

High prior — a hard reset reinitialises the WiFi driver from scratch — but
unverified. The existing cold test was a *power cycle with `main.py` disabled*,
which is **not** the same path as a `machine.reset()` following real ESP-NOW
use. Phase 1 is worthless if this assumption is wrong, so test it first.

### Setup

1. Confirm the port is free (see etiquette above).
2. **Re-flash `code_puller.py` from the current repo working tree.** The device
   is known to be carrying an older instrumented copy with `[DBG…]`
   hypothesis-tagged lines that no longer exist in git. Add a version print at
   import (e.g. `print("# code_puller rev", REV)`) so the running code is
   identifiable from now on. Do not skip this — the old copy has unknown extra
   `sleep_ms()`/print calls near the radio calls, and this is a timing-sensitive
   failure.
3. Disable auto-boot so `main.py` does not initialise ESP-NOW behind the test:
   rename `main.py` → `main_real.py` on the wand. **Restore it when done.**

### Three conditions, 3 trials each

Run all three **in the same session**, interleaved. Condition B is the control:
without it, a passing C proves nothing, because it would not be established
that the failure even reproduces today.

**A — cold (baseline, expect PASS)**
```bash
python3 -m mpremote connect /dev/cu.usbmodem101 exec \
  "import code_puller; print('A_COLD', code_puller.pull(verbose=True))"
```

**B — warm, no reset (control, expect FAIL)**
```bash
python3 -m mpremote connect /dev/cu.usbmodem101 exec \
  "import sys; sys.path.append('/lib'); from espnow_manager import ESPNowManager; import time; \
   e=ESPNowManager(); e.init(); \
   [ (e.broadcast(['turnred']), time.sleep_ms(200)) for _ in range(25) ]; \
   e.shutdown(); \
   import code_puller; print('B_WARM_NORESET', code_puller.pull(verbose=True, enow=e))"
```

**C — warm + hard reset (the actual question)**
```bash
# Step 1 — dirty the radio, then hard reset. mpremote WILL lose the connection
# here; that is expected, not an error.
python3 -m mpremote connect /dev/cu.usbmodem101 exec \
  "import sys; sys.path.append('/lib'); from espnow_manager import ESPNowManager; import time, machine; \
   e=ESPNowManager(); e.init(); \
   [ (e.broadcast(['turnred']), time.sleep_ms(200)) for _ in range(25) ]; \
   machine.reset()"

# Step 2 — wait ~3 s for reboot, then join on the post-reset radio.
python3 -m mpremote connect /dev/cu.usbmodem101 exec \
  "import code_puller; print('C_WARM_RESET', code_puller.pull(verbose=True))"
```

Note C step 2 passes no `enow`, so `_shutdown_espnow()` is skipped — exactly the
production pull-mode path. Capture the full `status seen while joining:` line
for every trial; that is the discriminating output.

### Reading the result

| A | B | C | Meaning |
|---|---|---|---|
| PASS | FAIL | **PASS** | **Assumption confirmed — proceed to Phase 1.** |
| PASS | FAIL | FAIL | Corruption survives a chip reset. Surprising and important. Stop, report, reconsider — this would favour the ESP-NOW-transport route. |
| PASS | PASS | PASS | Failure did not reproduce today. Do not proceed on this data; investigate what differs (Box state, RF environment, the re-flash). |
| FAIL | — | — | Cold path is not reliable. Phase 1's reliability *is* the cold path's reliability, so this must be understood first. |

Record every trial. Intermittency is the whole reason for n=3.

---

## Phase 1 — implementation (only if Phase 0 shows PASS / FAIL / PASS)

### The state machine

```
boot
 └─ leds / buzzer init (no radio)
 └─ /pullpending on flash?
      ├─ yes → PULL MODE (radio is cold — never touched by ESP-NOW this boot)
      │        attempts >= MAX_ATTEMPTS?
      │          yes → clear flag, show error, fall through to normal boot
      │          no  → increment + write flag, short grace, code_puller.pull()
      │                 success → clear flag, show ✓, machine.reset()
      │                 failure → machine.reset()   (retry, bounded by counter)
      │
      └─ no  → NORMAL BOOT: ESP-NOW init, games, NFC idle loop
                 tap "getcode" → write /pullpending, beep, machine.reset()
```

The wand never changes radio mode within a boot. Every WiFi join happens on a
cold radio.

### Design decisions

- **`machine.reset()`, never `machine.soft_reset()`.** A soft reset does not
  reinitialise the radio and would defeat the entire mechanism.
- **Counter is written *before* the attempt**, so a hard crash mid-pull still
  counts against the budget and cannot boot-loop.
- **`MAX_ATTEMPTS = 2.`** Each failed pull currently costs ~40 s
  (`JOIN_ATTEMPTS = 2` × `CONNECT_TIMEOUT_S = 15` plus scans). Three retries
  would leave a wand dead-looking for two minutes in a classroom.
- **Consider tuning the pull-mode timeouts.** A cold radio joined fast in
  testing; if it has not associated in ~8 s something is wrong and waiting 15 s
  twice adds nothing. Worth a pass once Phase 0 data shows typical cold join
  times.
- **Keep a short (1–2 s) Ctrl-C grace in pull mode.** The existing 5 s grace is
  too slow to sit through on every pull, but removing it entirely means a wedged
  pull loop cannot be rescued over USB.
- **Flag file at flash root** (`/pullpending`) — MockWand deploys to the root,
  not `/flash`. Write, flush, close before resetting.
- **No Box-side changes.** `BBoxFirmware/` is untouched by this work.

### Files

**New**
- `MockWand/pull_flag.py` — `is_pending()`, `set_pending()`, `bump_attempts()`,
  `clear()`. ~30 lines; keeps `main.py` readable and makes the logic testable in
  isolation.

**Modified**
- `MockWand/main.py`
  - flag check immediately after LED/buzzer init, **before** `ESPNowManager()`
    (currently constructed around line 417)
  - `getcode` handler (currently around line 603) becomes: write flag, beep,
    `machine.reset()`. The inline `code_puller.pull()` call and its
    `_pull_progress` LED closure move into pull mode.
- `MockWand/code_puller.py` — version/rev print at import; optional cold-path
  timeout tuning.

**Unchanged:** everything in `BBoxFirmware/`, `ChatBroadcast/`, `BBoxPrototype/`.

---

## Phase 2 — verification

1. **Happy path, real hardware:** tap the `getcode` card → wand reboots → pulls
   → reboots → new game runs. End to end, no USB attached.
2. **Retry path:** power the Box's AP down, tap `getcode`. Wand attempts
   `MAX_ATTEMPTS` times, then boots normally with a visible error indication.
   **No boot loop.**
3. **Rescue path:** Ctrl-C during the pull-mode grace window reaches the REPL.
4. **Repeat trials:** 5 consecutive successful pulls. Phase 0's pass rate is the
   ceiling here; if cold was 3/3 but production is 3/5, the difference is
   something Phase 1 introduced.
5. Confirm `main_real.py` was renamed back to `main.py` and the wand boots
   normally from cold power.

---

## Deferred — not part of this work

- **ESP-NOW file transport (v2).** Chunked transfer over ESP-NOW would remove
  the radio transition architecturally and enable broadcast-to-all-wands, which
  is a real classroom win. ~1–3 days, and needs new ESP-NOW firmware on the Box
  (`bbox_server.py` is AP + TCP only today). This plan does not block it — the
  transport swaps out and the reboot bracket drops away, with no rework to card
  writing, the Box UI, or the app.
- **Hunting a MicroPython radio-config sequence.** Likely impossible at the
  Python level given `esp_wifi_deinit()` is not exposed. Reboot makes it moot.
- **Two Box bugs found while reading, unrelated to the join:**
  `CodeServer.poll()` serves the whole file synchronously inside one call (up to
  30 s, stalling the Box's serial link, heartbeat, NFC and UI); and its
  `'serving'` branch is unreachable, so `paint_receiving()` never fires — do not
  read the Box LCD as evidence of transfer state.
