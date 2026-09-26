# Hardware test prompt: Splat Companion (EUM)

Paste the block below into a local agent session on the machine with the boards attached.

---

You are testing `Bag3/Code/BroadcastCode/EspnowModem/SplatCompanionEUM/` on branch `splat-espnow`. Read these first:
- `Bag3/Code/HARDWARE_PROTOCOL.md`
- `SplatCompanionEUM/README.md`
- `EspnowModem/README.md`

**Rules:**
- **Ask** which board is on which port, and confirm nothing else holds the ports.
- **Pass** `resume` on every `mpremote` call.
- **Write** only under `/flash/` on the UIFlow modem. The XIAO C6 and the MockWand use `/` and `/lib/`.
- **Leave** physical steps to the user. Give numbered steps, then wait for "go".
- **Report** what the logs show; only the user can confirm what the Splat did.

**Hardware:**
- XIAO ESP32-C6 companion
- M5StickS3 running the EUM modem firmware from `EspnowModem/modem/`, with its own USB power
- one stock Splat
- one MockWand (Bag3, built-in `espnow_manager.py`) to run `bench_wand.py`
- UART wiring (ask the user to confirm it): C6 D0 (GPIO0) → modem GPIO44, C6 D1 (GPIO1) ← modem GPIO43, GND–GND

**Steps:**
1. **Flash** the companion as in README "Deploying". Check the modem's `/flash/main.py` and `/flash/lib/eum_proto.py` match the branch (`cmp` a copy read back with `fs cp :/flash/lib/eum_proto.py /tmp/`).
2. **Capture** the companion boot for 60 s with `tools/serial_monitor.py`. Expect, in order:
   - `[hubtype] splat_companion`
   - `ESPNow(EUM): active (MAC: ...)` (note this MAC)
   - `SplatLink: ready, Splat <MAC>`

   Ask the user whether the Splat flashed green once. Report any `[ERR]`, `Traceback` or `gap_scan failed`.
3. **Set** `COMPANION_MAC` in `bench_wand.py` to the MAC from step 2. Run it on the MockWand with `mpremote connect $WAND_PORT resume run bench_wand.py`, while capturing the companion log in the background. The user, per phase:
   - config: press and release the Splat 3 times, including one very short tap; report light and sound on each press, and whether they stop on release
   - cmd: report whether the Splat shows yellow + dog, then purple + a note, then goes off
   - stop: press once; report that nothing lights or sounds

   From the logs, report:
   - `[bench] DONE` counts; expect presses == releases
   - `splat_event` arrival times against the companion's press lines
4. **Test concurrency.** With the companion running, the user switches the Splat off. Rerun `bench_wand.py` phase 1 while the Splat is off, then the user switches it back on.
   - Expect in the companion log: `Companion: splat_config ...` while BLE shows not ready, then `SplatLink: ready`.
   - Presses after the reconnect should play the config.
   - Report how long the reconnect took.
5. **Test the modem link.** The user pulls the modem's TX wire for about 5 s, then replaces it. Expect the companion LEDs to go red, then back to the previous state, and `link restored` in the log. Presses during the outage should still light the Splat. Report the `splat_event` lines after recovery.
6. **Try switch polling off.** Set `SWITCH_POLL_MS = 0` in `companion.py`, redeploy, and repeat the step 3 config phase. Report whether presses still arrive.
7. **Probe.** Set `DEBUG_PROBE = True` in `splat_companion.py`, redeploy, and capture 2 min of idle plus a few presses. Report:
   - `max_step_gap_ms`
   - `host_idf_largest` and `gc_free`
   - `modem_crc_err`, `host_timeouts`, `relay_failures`, `player_fail`
   - the `writes=/errors=` counts

   Then set both constants back.

**Report:**
- a table per step (expected / seen / evidence line)
- every `[ERR]` / `[WARN]` line, with a count
- open questions for the user, including:
  - Do the note pitches sound right?
  - Did a chain with notes still react to the Splat button?
