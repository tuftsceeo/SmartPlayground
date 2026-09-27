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
- one MockWand (Bag3, built-in `espnow_manager.py`) to broadcast `start_game` and `stop` from its REPL (step 4)
- a Broadcast Box or Dial with a game staged as `<slug>_splat.py` (for step 5)
- NFC cards: one printed `splatwhack`, one printed `stop`, one printed `getcode:<slug>` naming the staged game
- UART wiring (ask the user to confirm it): companion D0 (GPIO0, TX) → modem RX, companion D1 (GPIO1, RX) ← modem TX, GND–GND (see README "Wiring" for the exact modem-side pin per board)

**Steps:**
1. **Flash** the companion as in README "Deploying". Check the modem's firmware matches the branch (`cmp` a copy of `lib/eum_proto.py` read back against the repo's).
2. **Capture** the companion boot for 60 s with `tools/serial_monitor.py`. Expect, in order:
   - `[hubtype] splat_companion`
   - a battery line (or `[WARN] Battery:` if the gauge isn't wired)
   - `PN532 firmware ... -- NFC ready` (or a `[WARN] PN532 not at 0x24; I2C devices found: [...]` line if it isn't)
   - `ESPNow(EUM): active (MAC: ...)`
   - a `{"type": "identity", ...}` JSON line
   - `SplatLink: ready, Splat <MAC>` then `Companion: Splat <MAC> ready`

   Report any `[ERR]`, `Traceback`, or `gap_scan failed`.
3. **Idle station.** With no game running, the user presses the Splat 3 times, including one very short tap. Expect: nothing lights or sounds on the Splat, the status strip stays cyan (breathing), and nothing is logged except heartbeats. Report anything the Splat did.
4. **Card dispatch.**
   - Tap the `splatwhack` card. Expect a `game_start` JSON line, then the companion's own prompts (a splat color) with the user pressing on cue; report the printed score line and whether it matches what the user actually hit.
   - While the game is running, tell the user to press the Splat once with no prompt showing (a miss) and once during a prompt (a hit); report both outcomes.
   - Broadcast `{"type": "stop"}` from the MockWand REPL. Expect a `game_end` line, the Splat going dark, and the cyan status LEDs to return.
   - With the companion idle, broadcast `{"type": "start_game", "name": "nosuchgame"}` from the MockWand REPL. Expect `ignoring unknown start_game name 'nosuchgame'` and no game. Then broadcast `{"type": "start_game", "name": "splatwhack"}`. Expect `ESP-NOW start_game: splatwhack` and a `game_start` line; stop it again with `{"type": "stop"}`.
   - **Cards during a game.** Start `splatwhack` with its card and remove the card, then tap the `stop` card. Expect `STOP tag during splatwhack`, a `game_end` line and the Splat going dark.
   - Start it again, leave the `splatwhack` card on the reader for 5 s. Expect no restart and no `tag tapped again` spam beyond one line per re-tap.
   - Start it again and tap the `getcode:<slug>` card. Expect the pull flow of step 5.
   - Report whether prompts or presses felt delayed while no card was on the reader (each in-game check can hold the game for up to 30 ms).
5. **Pull.** With a `<slug>_splat.py` staged on the Box/Dial, tap the `getcode:<slug>` card. Expect: LEDs go blue, the companion resets, then either the pulled game auto-launches (report its `game_start` line) or a pull-failure color per README's status-LED table. Report which.
6. **Reconnect.** With the companion idle, the user switches the Splat off, waits 10 s, then switches it back on. Expect `Companion: Splat link down`, blue status LEDs, then `SplatLink: ready` and cyan again. Report how long the reconnect took.
7. **Modem link.** The user pulls the modem's TX wire for about 5 s, then replaces it. Expect the companion LEDs to go red, then recover, with `link restored` in the log. Then broadcast `{"type": "start_game", "name": "splatwhack"}` and confirm the game starts.
8. **Probe.** Set `DEBUG_PROBE = True` in `main.py`, redeploy, and capture 2 min of idle plus a few presses and one game session. Report:
   - `max_step_gap_ms`
   - `host_idf_largest` and `gc_free`
   - `modem_crc_err`, `host_timeouts`, `splat_fail`
   - the `writes=/errors=` counts

   Then set `DEBUG_PROBE` back to `False`.

9. **Multiple Splats (only if 2+ Splats are available).** Set `"max_splats": 2` in `lib/hubtype.py`, redeploy, and switch both Splats on.
   - Expect `Splats configured: 2`, then `Companion: Splat 0 (...) ready` and `Splat 1 (...) ready` with two different MACs; status pixels 0 and 1 cyan, pixel 2 off.
   - Tap `splatwhack`: both Splats should show each prompt. The user presses each Splat once; report both hits.
   - Switch one Splat off for 10 s, then on. Expect only its pixel to go blue, the other Splat to keep working, and a reconnect to the same MAC.
   - With 4 Splats, repeat with `"max_splats": 4` and report `max_step_gap_ms` from step 8's probe during a game (each color change writes to all four).
   - Set `max_splats` back to `1`.

**Report:**
- a table per step (expected / seen / evidence line)
- every `[ERR]` / `[WARN]` line, with a count
- open questions for the user, including:
  - Do the note pitches sound right?
  - Was the pull's antenna behaviour (README's UNVERIFIED note) a problem -- did the join take noticeably longer or fail on a first attempt?
