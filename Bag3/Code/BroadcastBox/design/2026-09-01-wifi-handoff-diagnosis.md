# WiFi-handoff diagnosis — 2026-09-01

## Problem

`MockWand/code_puller.pull()` was timing out joining the Broadcast Box's
`SP-FILEPUSH` SoftAP, where `BBoxPrototype/c6_receiver.pull()` (a simpler,
known-good prototype with no ESP-NOW involvement) succeeded on the same
hardware pair. The AP was visible in the wand's scan at usable RSSI, so the
failure was between scan and IP, not radio/antenna/AP-never-came-up.

## Method

Rather than building the full two-prototype 2×2 bench rig originally
proposed, we static-diffed the known-good and suspect sender code, found one
live suspect, and confirmed/killed it with the minimum possible live
measurement before escalating. See
`Bag3/Code/BroadcastBox/BBoxFirmware/code_server.py`,
`Bag3/Code/BroadcastBox/BBoxPrototype/s3_sender.py`,
`Bag3/Code/BroadcastBox/BBoxFirmware/probe_stick.py`, and
`Bag3/Code/BroadcastBox/MockWand/code_puller.py`.

## H1 — channel-config drops authmode (DEAD)

`code_server._start_ap()` has one substantive addition over
`s3_sender._start_ap()` / `probe_stick.py`: a second `ap.config(channel=1)`
call after the call that sets `essid`/`password`/`authmode`, with failures
silently swallowed:

```python
try:
    ap.config(channel=AP_CHANNEL)
except (ValueError, OSError):
    pass
```

MicroPython's `config()` does read-modify-write on the whole AP config
struct, so a second call could in principle drop the authmode field and
leave the AP beaconing open — still fully visible to a scan, matching the
observed symptom, while a station offering WPA2 credentials fails to
associate.

**Confirmed dead, independently, from both ends:**
- Box-side readback (temporary diagnostic print added to `_start_ap()`,
  reverted after use): `[AP] readback authmode=4 channel=1`.
- Wand-side scan (`code_puller.pull(verbose=True)`, already wired at
  `MockWand/main.py:627-628`, no code change needed): `found SP-FILEPUSH on
  ch=1 rssi=-34 sec=4` and, on the failure-path full scan, `SP-FILEPUSH
  ch=1 rssi=-31 sec=4 <-- wanted`.

`4` is `network.AUTH_WPA_WPA2_PSK`'s actual value on this port — the
requested authmode, intact, on both sides. The AP is not going open.

## H2 — ESP-NOW → STA radio handoff (CONFIRMED)

The real failure trace (NFC-triggered `pull()`, ESP-NOW active beforehand
per the wand's normal boot sequence in `MockWand/main.py`) showed:

```
status seen while joining: STAT_CONNECTING (1001), STAT_WRONG_PASSWORD (202)
...
[XFER] join attempt 1/2 failed, status=STAT_CONNECTING (1001)
...
[XFER] join attempt 2/2 failed, status=STAT_CONNECTING (1001)
```

A transient `STAT_WRONG_PASSWORD` immediately followed by permanently stuck
`STAT_CONNECTING` (auto-reconnect silently retrying and never resolving) is
not "connect() never attempted" — it's the driver reaching the 4-way
handshake, having it fail in a way ESP-IDF's status heuristic classifies as
a bad credential, then retrying forever. Since both sides confirm the actual
password matches (`pwd_len: 11` on the wand, same hardcoded `playground1` on
both), "wrong password" is the wrong read of that status; a handshake-layer
failure — a stale security/crypto context left over from ESP-NOW — is the
right read.

### Isolating test (cold vs. warm), same wand + same Box + same code

`MockWand/main.py` unconditionally calls `ESPNowManager().init()` early in
`main()` (line ~417-418), before any NFC-triggered join is possible in
normal operation — so a "cold" (ESP-NOW-never-touched) trial requires
bypassing the normal boot path:

1. `mpremote fs mv :main.py :main.py.bak` — main.py won't auto-run.
2. `mpremote reset` — boots to a bare REPL, radio genuinely untouched.
3. `mpremote exec "import code_puller; print('COLD_RESULT',
   code_puller.pull(verbose=True))"` — runs the exact same join path with a
   pristine radio.
4. `mpremote fs mv :main.py.bak :main.py` + reset — restore normal
   operation.

**Cold result — clean success, first try:**

```
  found SP-FILEPUSH on ch=1 rssi=-44 sec=4
  status seen while joining: STAT_CONNECTING (1001)
  joined SP-FILEPUSH, ip=192.168.4.2
[XFER] connected to 192.168.4.1:8266
[XFER] receiving jumpin.py, 4627 bytes expected
[XFER] OK: jumpin.py promoted, 4627 bytes
COLD_RESULT True
```

No `STAT_WRONG_PASSWORD`, no stuck `STAT_CONNECTING` — joins and transfers
on the first attempt.

**Warm** (today's real path — ESP-NOW init → run → teardown → join)
reliably reproduces the `STAT_WRONG_PASSWORD`-then-stuck-`STAT_CONNECTING`
signature, both join attempts, on repeated real NFC-triggered trials.

Same wand, same Box, same `code_puller.pull()` code, one variable (whether
ESP-NOW ever ran before the join). This is a clean confirmation: the
ESP-NOW→STA handoff itself corrupts the radio's association/handshake
state, not a config problem, and it's a known category of ESP32 WiFi/ESP-NOW
coexistence bug rather than anything specific to this codebase's config
values.

### Next suspect, not yet isolated

`MockWand/lib/espnow_manager.py`'s `shutdown()` only calls
`self.enow.active(False)` (the ESP-NOW protocol object) — it never calls
`sta.active(False)`. The STA-level reset is instead handled separately, and
later, in `code_puller._reset_sta()` (disconnect/active(False)/active(True)
cycle) and `code_puller._shutdown_espnow()` (reach-through
`raw.active(False)` fallback). The corrupted handshake state most likely
survives in that gap — either the ESP-NOW driver's crypto/PHY state isn't
fully cleared by `enow.active(False)` alone, or the STA active-cycle that
follows isn't sufficient to reset it. Narrower instrumentation around
`_shutdown_espnow()` / `_reset_sta()` (rather than new hardware prototypes)
is the recommended next step to pin down exactly which teardown step leaves
the radio in the bad state.

## Unrelated issue found during this session — Box power instability

While testing, the Box (M5Stack StickS3) began resetting repeatedly
(~1s–19s uptime, irregular interval) whenever connected to any USB port —
stable indefinitely on battery alone. Confirmed:
- Not caused by a code change (reproduced on an unmodified `code_server.py`
  after reverting a diagnostic print).
- Not a specific cable or port (reproduced across multiple cables/ports,
  and with the Mac itself on AC power).
- Every crash cycle showed **clean output up to the last line, then the USB
  device vanished with no traceback, no panic, and no brownout-detector
  message** — consistent with a hard power-rail collapse severe enough to
  kill the USB transmitter mid-stream, not a Python exception.
- Crashes only occurred after the SoftAP armed and started running (one
  cycle survived 23s of "up" time through 3 heartbeats before dying);
  timing was irregular, consistent with WiFi-TX-triggered current spikes
  rather than a fixed watchdog timer.
- Correlated with the wand also drawing charge current on the same host at
  one point, though it also reproduced with the wand disconnected.

Working hypothesis: PMIC charge-current arbitration vs. WiFi TX current
spikes on the StickS3's own power path (a known-ish failure class on
M5Stack boards with an AXP-family PMIC), not the incoming USB supply
quality. Not yet root-caused or fixed — noted here so it isn't confused
with the WiFi-handoff investigation, and because it blocked serial
monitoring (`screen` dies when the device node disappears) until a
reconnect-on-drop logger was used instead.

## Files touched

- `BBoxFirmware/code_server.py` — temporary diagnostic readback print added
  and reverted; no net change on disk.
- No other production files modified. `MockWand/code_puller.py` on the
  wand's flash was reflashed with the current (already-reverted, no debug
  instrumentation) repo version during this session.

## Status / next steps

1. H1 dead, H2 confirmed — do not pursue the channel-config line further.
2. Instrument `espnow_manager.shutdown()` / `code_puller._reset_sta()` /
   `_shutdown_espnow()` directly to find exactly which step fails to clear
   the ESP-NOW-era handshake/crypto state, rather than building new
   hardware prototypes.
3. Box USB-power instability is a separate, unresolved issue — needs its
   own investigation (M5.Power / charge-current API, or accept as a
   hardware limitation and always test on battery).
