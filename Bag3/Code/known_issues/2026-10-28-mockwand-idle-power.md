---
title: MockWand idle and sleep battery drain
date: 2026-10-28
status: partly fixed (NFC power-down, matrix off, dimmed power LED); radio and CPU still always on
devices: [MockWand (XIAO ESP32-C6, Bag3)]
components: [PN532, ESP-NOW, ESP32-C6 CPU, WS2812 matrix, power LED (GPIO 2), LIS2DW12, OPT3002, MAX17048]
code:
  - Bag3/Code/BroadcastCode/MockWand/main.py
  - Bag3/Code/BroadcastCode/MockWand/lib/pn532.py
  - Bag3/Code/BroadcastCode/MockWand/lib/power_led.py
  - Bag3/Code/BroadcastCode/MockWand/lib/brightness.py
  - Bag3/Code/BroadcastCode/MockWand/lib/hubtype.py
open:
  - No current measurement before or after the changes
  - ESP-NOW receiver on continuously in idle and sleep
  - CPU never sleeps; the sleep loop polls at full clock every 100 ms
  - No inactivity sleep inside games
  - PN532 field stays on during the 30 s awake idle before sleep
  - LIS2DW12 runs at 100 Hz high-performance
  - A wand whose accelerometer fails at boot never sleeps
  - NeoPixel standby current; whether the board can switch matrix power is unknown
  - Power LED and matrix brightness not checked outdoors
  - Deploy does not ask which diffuser a wand has
keywords: [battery, power, current, idle, sleep, NFC sleep, PN532, PowerDown, RF field, ESP-NOW, lightsleep, power LED, PWM, brightness, diffuser, OPT3002, LIS2DW12, MockWand, wand]
---

# MockWand idle and sleep battery drain

The wand enters "NFC sleep" after 30 s with no tag and no activity (`NFC_SLEEP_MS`), and only
when the accelerometer came up at boot. Movement (accelerometer magnitude > 1.4 g) or the
button wakes it.

## Fixed (commit a413c39, Chat_to_Tap_Doggle)

| Change | Where | Evidence |
|---|---|---|
| PN532 powered down while asleep. `power_down()` sends an ACK frame to abort the pending InListPassiveTarget (its RF field stays on until a tag appears), then PowerDown with I2C-only wake. Every sleep exit (movement, button, ESP-NOW stop/start/battery, Dial code push) calls `_nfc_wake()`, which retries `begin()` 3 times. | `lib/pn532.py`, `main.py` | 3101: PowerDown acknowledged with a search pending; woke on first `begin()`; two movement wakes then a card read (`getcode:faulttest`) in the serial log |
| Matrix off while asleep (was a dim blue dot rewritten every 100 ms). | `main.py` | User confirmed dark |
| OPT3002 shut down after the boot light reading. Games that calibrate leave it in continuous mode. | `main.py` `_boot()` | Clean boot log |
| Power LED on PWM, about 3% indoors, blip every 4 s while asleep. | `lib/power_led.py` | User confirmed brightness and blink |
| Battery state of charge re-read every 60 s in idle and sleep (`SOC_REFRESH_MS`); previously only at boot and on wake. | `main.py` | Not observed |

No current was measured; the savings are expected, not shown.

## Power LED states

PWM starts after radio bring-up and light calibration (`pled.start()` in `main()`); before that
GPIO 2 is a plain output held on. Full scale follows `brightness.MULTIPLIER` with the diffuser
gain removed: `LED_FLOOR` (0.03) at `MIN_MULT` up to 1.0 at `MAX_MULT`. It is re-read on
`idle()` and `asleep()`, so a game's recalibration reaches the LED when the wand returns to idle.
Patterns step from `Timer(0)` every 100 ms.

| State | Pattern |
|---|---|
| Ready (idle) | 80% of full, solid |
| Asleep | 50% blip every 4 s |
| Battery ≤ 20% | double blip every 2 s (idle and asleep) |
| Battery ≤ 10% | 2.5 Hz blink |
| Game running | off |
| Code pull | flicker per received chunk |
| Boot failure | long-short |

Boot failure only shows on a debug boot with a fatal NFC error. A fast boot resets on that error,
and an import failure before `main()` leaves the LED solid from `pled.on()`.

## Diffuser

`hubtype.py` wand config has `"diffuser": "black"` (default) or `"white"` (older builds).
Black scales `MIN_MULT` and `MAX_MULT` by 1.2 (`brightness.DIFFUSER_GAIN`), giving 0.06 indoors
and 0.60 in sunlight. 3101 booted at 286 lux to x0.06.

## Not implemented

Larger savings:

1. **ESP-NOW receiver always on**, likely the largest remaining draw (roughly 70-80 mA on the C6,
   not measured). It must keep receiving: find and status poll reach the wand over ESP-NOW. No
   transmit is needed while idle or asleep. Options, cheapest first:
   - `machine.freq(80_000_000)` while asleep; the receiver stays fully on.
   - Duty-cycle with `machine.lightsleep()` (~1 s) between receive windows. The Box/Dial would
     have to repeat find and status poll for longer than one sleep period.
   - ESP-IDF connectionless power save (`esp_now_set_wake_window`,
     `esp_wifi_connectionless_module_set_wake_interval`). Not exposed in MicroPython; needs a
     custom firmware build.
2. **CPU never sleeps.** The sleep loop reads the accelerometer over I2C every 100 ms. INT1 wake
   is already armed (`enable_wake_int1`) and could wake a `lightsleep`; this depends on the radio
   decision above.
3. **Inactivity sleep in games.** Proposed: no motion or input for 10 minutes during a game puts
   the wand to sleep. Games run their own loops, so this needs a shared hook every game calls.

Smaller:

4. PN532 field during the 30 s awake idle. RFConfiguration MaxRetries (`0x32`, item `0x05`) could
   end each search so the field drops between polls. Untested.
5. LIS2DW12 at 100 Hz high-performance (`odr_mode=0x54`). A low-power mode would draw less; the
   wake threshold would need re-checking.
6. Sleep requires `accel_ok`. The button alone could wake a wand without an accelerometer.
7. NeoPixel standby current. Whether the board can switch matrix power is unknown; ask before
   assuming.
8. Matrix brightness is set at boot and game start only. Periodic re-calibration in idle was
   considered and declined.
9. Outdoor tuning of `MAX_MULT`, and a diffuser question at deploy time.
