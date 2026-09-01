# Known issue: silent reboots while on USB

Opened 2026-09-01. Unresolved. This is a hypothesis document for testing, not a
fix — nothing here has been implemented.

## Symptom

The box resets at random intervals of roughly 30 seconds to 2 minutes while
plugged into a computer over USB. It appears stable on battery.

At the time of the resets the box is idle-but-armed: SoftAP up, screen on,
heartbeat presumably running, no tag being written, no sounds playing. The
reset produces **no output at all** — no traceback, no error, and no boot
banner on the same serial session.

It ran for hours on USB the previous night (2026-08-31) with sound effects,
NFC writes, and the AP all working.

## The constraint that shapes everything below

`main.py` wraps the whole program in `except Exception` and prints a JSON
`fatal` with a traceback. **Any Python-level bug would therefore produce
output.** Silence means the reset is happening below Python: a brownout, a
watchdog, or a native crash.

Two corollaries:

- A plain bug in our own `.py` files is a poor fit for the evidence.
- The absence of a message is partly an artifact: this board's USB is native
  CDC, so the serial port *is* the chip. A reset drops the USB device and
  re-enumerates it, so any panic message and the reboot banner go into a port
  the host has already lost. Live serial cannot observe this failure.

## Ruled out

**A bad merge.** `BBoxFirmware/` at HEAD is byte-identical to `cfed7a4`, the
last commit of the session where the box worked. The merge at HEAD
(`9a0391c`) touched only Icon Display Station art and webapp files — 22 files,
none under `BroadcastBox/`. Every individual fix was verified still present:
the `bbox_ui.begin()` ordering, `setTextSize(1)`, `paint_error` at font 12,
the NFC retry counter, `existing_text` / `write_text`, the 30 ms write settle,
and `AP_CHANNEL = 1`.

**The code delta since the stable run.** The only commit after the box was
last known-good is `cfed7a4`, containing exactly two things:

- `card_writer.py` write verification and settle delays — runs *only* during a
  tag write, and nothing was writing during the reboots.
- `code_server.py` `ap.config(channel=1)` — see H3; likely inert.

## Steady-state power profile (confirmed by code, not yet by measurement)

Commit `19a2093` introduced auto-arm: `run()` calls `_try_arm()`
unconditionally, so whenever `payload.py` exists on flash the box raises the
AP and begins polling the PN532 at boot, with no human action.

`_poll_nfc()` returns immediately unless `_armed_write` is true, so **auto-arm
is the single flag gating both always-on loads**. With
`pump(idle_ms=20, drain_ms=40)` and `sleep_ms(1)` per iteration,
`detect_tag(timeout=80)` runs on the order of ten times a second, which is an
effectively continuous RF field.

`ap.config(pm=0)` disables AP power save so the radio never dozes. This is
pre-existing, inherited from `BBoxPrototype/s3_sender.py`.

`bbox_ui.SPEAKER_VOLUME` is 190, immediately below the ~191 threshold the
comment above it warns about for brownout.

## Auto-arm is an amplifier, not the trigger

Auto-arm cannot be the cause: it was already live during the stable hours. The
serial log from 18:03 on 2026-08-31 shows `{"type": "armed",
"ssid": "SP-FILEPUSH"}` arriving straight after `hello` with no arm command.

What it does explain is the *pattern* rather than the onset. It lowers the
margin, and it makes any single reset self-perpetuating: every reboot
re-enters maximum draw — AP plus NFC polling plus screen — within about five
seconds of boot, right after the boot grace. A one-off marginal event becomes
a repeating 30 s–2 min cycle. Before auto-arm, a reset landed the box in a
low-draw idle state where it would sit stably.

## Hypotheses

### H1 — Brownout from charge current stacked on the always-on load

The USB port supplies a fixed budget. On USB the charger runs *in addition to*
the system load; on battery there is no charge current, and a LiPo sources
current spikes far better than a current-limited port. Charge current is
highest when the cell is depleted and tapers to near zero when full.

This is the only hypothesis that explains "same code, stable for hours, fails
today" without invoking a code change: last night the battery finished full,
so charge current was negligible; today it starts depleted and draws maximum.
It also accounts for the warmth noticed while charging.

Predicts: `machine.reset_cause()` reports `BROWNOUT_RESET` or `PWRON_RESET`.

### H2 — Watchdog reset from a SoftI2C stall on the PN532

`_init_nfc()` uses `machine.SoftI2C`, which is bit-banged in C with no
clock-stretch timeout. A PN532 that wedges and holds SCL low can stall that
loop indefinitely. Auto-arm is what makes this path run continuously from
boot instead of only once a teacher arms the box.

This is the only *software* path identified that can reset the board with no
Python traceback, which is why it survives the constraint above. It fits both
the randomness and the silence. The PN532 had a documented `ETIMEDOUT` storm
during the previous session, so the bus is known to misbehave on this unit.

Predicts: `machine.reset_cause()` reports `WDT_RESET`.

### H3 — `ap.config(channel=1)` (weak)

The only always-active line in `cfed7a4`, and therefore possibly running for
the first time today. Channel 1 is already the ESP32 AP default, so this
likely changes nothing on air, and no mechanism connecting it to a reset has
been identified. Noted only because it is the sole idle-path delta.

Caution: last night's `ch=1` scan result is **not** evidence this file was
flashed, since channel 1 would be reported either way.

## Discriminating tests

1. **Read the reset cause.** One boot separates H1 from H2 outright:
   `BROWNOUT_RESET` / `PWRON_RESET` means the rail collapsed and it is power;
   `WDT_RESET` means the main loop stalled and it is the I2C path. Because USB
   CDC drops on reset, this has to be persisted to flash (or read on the next
   boot) rather than watched live.
2. **Sample battery voltage in the heartbeat.** A sag across the last
   heartbeats before a reset supports H1; a flat rail right up to the reset
   argues against it.
3. **Charge the box fully with the firmware not running, then run on USB.** If
   it survives, charge current is confirmed and H1 stands.
4. **Change the cable and use a wall charger or powered hub** rather than a
   laptop port. Costs nothing and removes a common variable.
5. **Boot with the payload absent** so `_try_arm()` declines. That leaves the
   AP down and NFC polling disabled. If the resets stop, the always-on load is
   implicated; if they continue, both H1 and H2 weaken sharply.
6. **Disconnect the Grove PN532** and run armed. Isolates H2 from H1 by
   removing the I2C path while keeping the AP up.

## Reader swap (2026-09-01, untested)

Reader chip changed from PN532 to WS1850S (same I2C pins, sda=9/scl=10;
addr moved 0x24 → 0x28 — see `card_writer.py` / `bbox_server.py`). Datasheet
draw drops from a ~150 mA read/write burst (PN532) to a ~30 mA burst
(WS1850S), and the SoftAP's own power spikes are the other named factor in
H1. This is a hardware change aimed at H1, not a fix that's been verified
against the failure: reset frequency on USB has not yet been re-measured
with the WS1850S installed. Tests 1–4 above (reset_cause, battery sampling,
full-charge-then-run, alternate cable/charger) still need to be run to
confirm whether resets stop, and H2 (SoftI2C stall) is a separate
hypothesis this swap does not address at all — WS1850S is still driven over
`machine.SoftI2C` with no clock-stretch timeout.

## Open question

Nothing in the code changed between the stable hours and the failure except
`cfed7a4`, whose contents cannot plausibly affect the idle path. If this is
software, the mechanism was already present and something crossed a threshold
— battery state of charge, temperature, or a degraded PN532 or USB supply.
Test 5 is the cheapest way to find out whether the always-on load is involved
at all.
