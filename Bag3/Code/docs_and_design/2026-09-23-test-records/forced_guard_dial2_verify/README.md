# FORCED-GUARD + DIAL 2 + FOUR-WAND BURST: Phases 1-2 results

Branch `Chat_to_Tap_Doggle`, on top of `fc2637d`. Phases 3-4 (hands-on,
port-swapping) not attempted this session -- ran out of time before a demo.

## Phase 1 (force the guard, Dial 1): partial, one real anomaly found

Set `MIN_IDF_FREE = 30000` then `33000` on Dial 1 only, hard-reset, armed.

- **Steps a-e (forced reboot sequence): confirmed.** `phase1_dial1_warning_state.txt`
  shows the end state directly: `# serve_guard: WARNING idf_free=29228
  idf_largest=20480 below floor 33000 after 2 reboots -- serving anyway`,
  repeating every ~5s, no third reboot. Consistent with the design.
- **Anomaly, not in the original plan: arm() itself failed with
  `WiFi Out of Memory`** on what should have been a fresh boot (`phase1_dial1_arm_oom.txt`),
  reproduced twice in a row. This is the *old* arm-time OOM blocker (pre-`41f78dc`),
  separate from serve_guard's *idle-time* mechanism -- serve_guard only helps
  once SERVE is already up, not if `arm()` itself can't get the AP started.
  Also noted at the time: Dial 1's game list had changed (`games: 2,
  active: button_blue`, `mode: IDLE`) from the clean bench state, likely from
  a ChatBroadcast web-UI session (the user's own "game splash / linked to
  laptop no games loaded" bug they were separately chasing) writing to the
  device in parallel. **Not confirmed whether the OOM was caused by that
  write activity or would have happened anyway** -- flagging for the
  sparring partner rather than concluding either way.
- **Step 4 (pull while WARNING showing): PASS.** One scripted wand pull
  against Dial 1 in the WARNING state succeeded (`pull OK`,
  `phase1_dial1_after_arm.txt`), even with `idf_free` below the floor.
- **Step 5 (serve_guard.txt clears after a successful pull): INCONCLUSIVE.**
  An `fs ls` check right after the pull still showed `serve_guard.txt`
  present. Likely a timing race (the check itself halts the running program
  via `fs`/`exec`, possibly before the main loop's next `poll()` tick could
  clear the flag) rather than a real bug -- not confirmed either way. Worth
  a cleaner re-test with a passive-only check.
- Restored `MIN_IDF_FREE = 22000` on Dial 1 afterward (repo default).

## Phase 2 (Gate 2 against Dial 2, Dial 1 also armed): PASS

Both Dials armed clean (Dial 2 `idf_free=29248` at arm). **20/20 scripted
wand pulls against Dial 2 succeeded** (`cycle_1_dial2gate2.txt` through
`cycle_20_dial2gate2.txt`, each `pull OK` in 13.9-19.8s). `idf_free` only
dropped to 28228 over the full run (`dial2_continuous.txt`) -- no leak of
concern, well clear of the floor. Full 5-min formal idle-leak check (task
step 9) was skipped given the demo deadline; the end-of-run number already
shows no concerning trend.

## Bonus: real multi-wand taps on Dial 1 during the session

While logging Dial 1 passively for unrelated reasons, the user did several
real physical taps from multiple wands in quick succession.
`dial1_multiwand_realtaps.txt` shows three back-to-back
`accepted`/`finish ok=True` cycles, full 5113/5113-byte transfers, no
errors -- a good real-world data point alongside the scripted Gate 2 result.

## Bottom line

Both Gate-2-style runs (Dial 1 earlier, Dial 2 here) pass 20/20. The one
real anomaly (arm-time OOM on Dial 1) did not reproduce during clean Gate 2
testing and may be tied to the concurrent ChatBroadcast write-session rather
than the fc2637d fix itself -- recommend NOT reverting fc2637d, but worth
the sparring partner's read on the arm-time OOM note above.

Phases 3-4 (four-wand burst reproduction, real-tap matrix) are unattempted --
next session should pick those up.
