# Splat Echo freeze investigation, 2026-09-30 and 2026-10-01

Branch `claude/bag3-companion-onboarding-review-nrv66u`, starting from `bf37b81`. The hub was a XIAO ESP32-C6 on `usbmodem3101`, with its EUM modem and four Splats (`max_splats` 4 on the board). The wands were two Bag3 MockWands: `usbmodem101` (`A0:F2:62:87:B4:30`) and `usbmodem1101` (`A0:F2:62:87:92:CC`). The modem MAC is `A0:F2:62:85:A9:9C`. The captures are in [2026-09-30-splatecho-logs/](2026-09-30-splatecho-logs/), with GC and port-retry lines removed.

Symptom: wands stop responding to tilt and button mid-game, most often after a slow turn.

## Instrumentation

Both halves of `splatecho.py` keep a 150-line log. The log is printed, and written to `/echo_log.txt` at start, on exit and after 10/20/40… s with no event; the previous game's log becomes `/echo_log_prev.txt`. Every message from the hub carries a count, `q`, so a wand log shows gaps. The wand logs the ESP-NOW driver's `stats()` counters, including `rx_dropped`. The hub logs modem `link_stats()` and per-Splat link state. These lines are marked `DIAGNOSTIC` in the code.

## Runs

| # | Build | Result | Evidence |
|---|---|---|---|
| 01 | broadcast | Stuck at the first add. Test artifact. | The modem ring held 64 `echo_hello`s from before the hub restarted. The hub assigned player 0 from one of them, then wand 1101 was reset while `echo_turn` q=1 and `echo_add_now` q=2 were sent. After rejoining, 1101 got `echo_you` and nothing else (`last_q=None`). No Splat connected: the hub `machine.reset()` left them connected, not advertising. |
| 02 | broadcast | **Freeze reproduced by play.** | The hub sent `echo_add_now` q=14 to player 0 and waited. Wand 101 never received it (`state=waiting`, 12 `BUTTON pressed outside add` lines). Wand 101 received hub q 1,2,4–8,10,12,13 (missed 3,9,11,14). Wand 1101 missed 3 and 9. `rx_dropped` stayed at 13 on 101 from the join onward and at 0 on 1101. Modem `rx_overflow` and `tx_fail` did not change during the game. No exception, reset or Splat drop. |
| 03 | broadcast, 100 ms gap after each Splat BLE write | Stuck at the first add. | Wand 101 missed q=1 (sent after the gap) and q=2; wand 1101 received both. |
| 04 | link test, no game | Broadcast loss measured. | See the table below. |
| 05 | unicast, length-keyed add | No deadlock in about 10 min of play. | 119 sends to players. 117 were ACKed by both wands on the first try, 1 needed a second try, and 1 went unACKed by wand 1101 after 3 tries (an `echo_add_now` resend; the next resend reached it). Wand-side duplicates: 0. Splat link drops and write failures: 0. |

| 06 | `acfffe4` (unicast, add id, UI cues) | No deadlock in about 7 min of play. | 23 steps were added, each following a wand press; there was 1 `RESEND echo_add`. Of 228 sends to players, 4 went unACKed after 3 tries, all to `…B4:30`, and that wand never received those 4. The two `echo_add_now`s among them were recovered by the 1 s resend; the two `echo_turn`s are not resent. Splat link drops and write failures: 0. 28 Splat presses were ignored: 22 in add, 4 in playback, 2 in result. User report: on a few failed rounds not every Splat lit, and some Splat sounds were late or missing. |
| 07 | link test, modem on the onboard antenna | No loss. | See "Antenna" below. |
| 08 | hub BLE scan per antenna setting | Hub BLE signal depends on the antenna switch. | See "Antenna" below. |

### 04: link test

The hub broadcast 300 numbered packets 20 ms apart, through the modem, in each condition ([04_link_test_hub_tx.py](2026-09-30-splatecho-logs/04_link_test_hub_tx.py) and [04_link_test_wand_rx.py](2026-09-30-splatecho-logs/04_link_test_wand_rx.py)). The modem reported 0 send failures.

| Condition | Wand 101 missed | Wand 1101 missed |
|---|---|---|
| a: Splats disconnected | 6 | 16 |
| b: 4 Splats; a color write to all 4 before every 5th packet | 14 | 16 |
| c: 4 Splats connected and polled | 8 | 32 |

- RSSI at the wands was −65 to −74 dBm.
- `rx_dropped` was 0 on both wands, so the losses happened before the receive buffer.
- Condition b is not separated from a and c by this data.

### Antenna (07, 08)

Neither the hub nor the modem board has a u.FL antenna fitted; the wands do.

- **Modem:** the modem firmware had `MODEM_EXTERNAL_ANTENNA = True`.
  - With it set to `False`, the link test lost 0 of 300 packets per condition per wand, against 6–32 in run 04.
  - RSSI at the wands went from −65 to −74 dBm to −22 to −28 dBm.
- **Hub:** nothing on the hub drove GPIO3/14 before `main.py` brought BLE up (GPIO3 read 1). Splat advertisement RSSI at the hub:

| GPIO3 / GPIO14 | RSSI (dBm), 4 Splats |
|---|---|
| undriven (3 reads 1) / 0 | −76 to −87 |
| 0 / 0 (onboard) | −61 to −67 |
| 0 / 1 (external, nothing fitted) | −86 to −98 |
| 0 / 0, set in `boot.py` | −61 to −69 |

## Conclusions from the evidence

- The freeze in run 02 is the add-phase wait. The hub waited for `echo_add` with no timeout, and the wand never received `echo_add_now`.
- The lost messages were broadcasts that did not arrive at the wand. The wands were not blocked or dropping them: the receive buffer drop count did not change during the game. Broadcast loss in run 04 was 2–10% per wand, with the modem transmitting on its external antenna path and nothing fitted. With the onboard antenna selected, loss in run 07 was 0.
- The hub's BLE link to the Splats ran 12–20 dB below the onboard-antenna level until `boot.py` selected the antenna. Run 06's missing Splat lights and sounds happened at that level; whether they recur with the onboard antenna has not been tested.
- Run 02 ruled out, for that freeze: Splat presses not registering, Splat link drops, a hub exception, a wand reset, and loss at the hub or modem.

## Changes in `acfffe4`

- **Hub game** (`SplatCompanion/Companion/splatecho.py`):
  - After joining, every message goes by unicast to each player and is retried up to `SEND_TRIES` times until ACKed.
  - The add request has a per-request id (`"add"`) and is resent every `ADD_RESEND_MS`. An `echo_add` with another id is ignored.
  - There is an `ADD_PAUSE_MS` pause after a step is added.
  - `echo_repeat_now` is sent before a repeat.
- **Hub ESP-NOW library** (`SplatCompanion/Companion/lib/espnow_manager.py`): `last_acked` records whether the last unicast was ACKed (reply `body[3]`). `send_to()` still returns the modem status.
- **Wand game** (`MockWand/splatecho.py`):
  - `echo_add` goes by unicast to the hub, retried until ACKed. A repeat of an answered `"add"` id resends the same step.
  - Hub messages whose `q` equals the last one are dropped as duplicates.
  - The wand turns green on `echo_repeat_now`.
  - The round's winner gets a rainbow and `buz.celebrate()`; the player who missed gets red and `buz.error()`.

## Antenna changes

- `SplatCompanion/ESPNowModem/main.py`: `MODEM_EXTERNAL_ANTENNA = False`.
- `SplatCompanion/Companion/boot.py` sets GPIO3 = 0, then GPIO14 = 0 (onboard) before `main.py` runs.
- `SplatCompanion/Companion/code_puller.py`: the `EXTERNAL_ANTENNA` fallback is `False`.

## Not verified on hardware

- Run 05 used a build that keyed the add handshake on pattern length. That length repeats after a round resets the pattern, so a new request matched an old answer. In run 05, wand 101 logged 22 `RESEND echo_add`s. The hub log shows `ADDED unit 0 after ~1.7 s, pattern [0]` repeatedly, with the player not choosing.
- The per-request id replaced that, and in run 06 every add followed a wand press. `echo_repeat_now`, the rainbow and tunes, and `ADD_PAUSE_MS` ran in run 06.
- Play with both onboard-antenna changes in place has not been run.
