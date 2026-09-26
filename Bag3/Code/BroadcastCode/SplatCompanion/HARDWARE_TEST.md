# Hardware test prompt: Splat Companion

Paste the block below into a local agent session on the machine with the boards attached.

---

You are testing `Bag3/Code/BroadcastCode/SplatCompanion/` on branch `splat-espnow`. Read these first:
- `Bag3/Code/HARDWARE_PROTOCOL.md`
- `SplatCompanion/README.md`
- `../EspnowModem/README.md`

**Rules:**
- **Ask** which board is on which port, and confirm nothing else holds the ports.
- **Pass** `resume` on every `mpremote` call.
- **Write** only under `/flash/` on a UIFlow modem board. The XIAO C6 companion, a C6 modem, and the MockWand use `/` and `/lib/`.
- **Leave** physical steps to the user, including any card taps. Give numbered steps, then wait for "go".
- **Report** what the logs show; only the user can confirm what the Splat did, or read a card result off a screen.

**Hardware:**
- XIAO ESP32-C6 companion, with a PN532 wired as on the wand (I2C 0x24) and a MAX17048 gauge
- a modem board (M5StickS3 or a second XIAO C6) running `../EspnowModem/modem/main.py`, with its own USB power
- one stock Splat
- one MockWand (Bag3, built-in `espnow_manager.py`) to run `bench_wand.py`
- a Broadcast Box or Dial with a game staged as `<slug>_splat.py` (for step 5)
- NFC cards: one printed `splatwhack`, one printed `stop`, one printed `getcode:<slug>` naming the staged game
- UART wiring (ask the user to confirm it): companion D0 (GPIO0, TX) → modem RX, companion D1 (GPIO1, RX) ← modem TX, GND–GND (see README "Wiring" for the exact modem-side pin per board)

**Steps:**
1. **Flash** the companion as in README "Deploying". Check the modem's firmware matches the branch (`cmp` a copy of `lib/eum_proto.py` read back against the repo's).
2. **Capture** the companion boot for 60 s with `tools/serial_monitor.py`. Expect, in order:
   - `[hubtype] splat_companion`
   - a battery line (or `[WARN] Battery:` if the gauge isn't wired)
   - `PN532 firmware ... -- NFC ready` (or an I2C scan dump if it isn't)
   - `ESPNow(EUM): active (MAC: ...)` (note this MAC)
   - a `{"type": "identity", ...}` JSON line
   - `SplatLink: ready, Splat <MAC>`

   Ask the user whether the Splat flashed green once. Report any `[ERR]`, `Traceback`, or `gap_scan failed`.
3. **Bridge test.** Set `COMPANION_MAC` in `bench_wand.py` to the MAC from step 2. Run it on the MockWand with `mpremote connect $WAND_PORT resume run bench_wand.py`, capturing the companion log in the background. The user, per phase:
   - config: press and release the Splat 3 times, including one very short tap; report light and sound on each press, and whether they stop on release
   - cmd: report whether the Splat shows yellow + dog, then purple + a note, then goes off
   - stop: press once; report that nothing lights or sounds

   From the logs, report `[bench] DONE` counts (expect presses == releases) and `splat_event` arrival times against the companion's press lines.
4. **Card dispatch.** With the bridge idle:
   - Tap the `splatwhack` card. Expect a `game_start` JSON line, then the companion's own prompts (a splat color) with the user pressing on cue; report the printed score line and whether it matches what the user actually hit.
   - While the game is running, tell the user to press the Splat once with no prompt showing (a miss) and once during a prompt (a hit); report both outcomes.
   - Tap the `stop` card (or send ESP-NOW stop from `bench_wand.py`). Expect a `game_end` line and the bridge's status LEDs to return.
5. **Pull.** With a `<slug>_splat.py` staged on the Box/Dial, tap the `getcode:<slug>` card. Expect: LEDs go blue, the companion resets, then either the pulled game auto-launches (report its `game_start` line) or a pull-failure color per README's status-LED table. Report which.
6. **Concurrency.** With the companion idle and running the bridge, the user switches the Splat off. Rerun `bench_wand.py` phase 1 (config) while the Splat is off, then the user switches it back on.
   - Expect: `Companion: splat_config ...` logged while BLE shows not ready, then `SplatLink: ready`, then presses after reconnect play the config.
   - Report how long the reconnect took.
7. **Modem link.** The user pulls the modem's TX wire for about 5 s, then replaces it. Expect the companion LEDs to go red, then recover, with `link restored` in the log. Presses during the outage should still light the Splat. Report the `splat_event` lines after recovery.
8. **Switch polling off.** Set `SWITCH_POLL_MS = 0` in `companion.py`, redeploy, and repeat step 3's config phase. Report whether presses still arrive.
9. **Probe.** Set `DEBUG_PROBE = True` in `main.py`, redeploy, and capture 2 min of idle plus a few presses and one game session. Report:
   - `max_step_gap_ms`
   - `host_idf_largest` and `gc_free`
   - `modem_crc_err`, `host_timeouts`, `relay_failures`, `player_fail`
   - the `writes=/errors=` counts

   Then set `DEBUG_PROBE` back to `False`.

**Report:**
- a table per step (expected / seen / evidence line)
- every `[ERR]` / `[WARN]` line, with a count
- open questions for the user, including:
  - Do the note pitches sound right?
  - Did a chain with notes still react to the Splat button?
  - Was the pull's antenna behaviour (README's UNVERIFIED note) a problem -- did the join take noticeably longer or fail on a first attempt?
