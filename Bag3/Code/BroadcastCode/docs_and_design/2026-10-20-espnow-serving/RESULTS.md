# ESP-NOW serving: results

## Phase 1: S3 radio feasibility (2026-10-20)

Bench: `tools/devtests/espnow_serve.py` on the board, one MockWandEUM wand held close,
one 36 KB file (`speed36`), run with `mpremote resume run`. CPython tests:
`EspnowModem/tests/test_espnow_serve.py` (9, passing).

**Verdict:** the Dial passes the gate. The Box is unresolved: its failures match the known
USB charge-current brownout and were all run with a depleted battery.

| Board | 1. `import espnow`, `active(True)` | 2. Field off | 3. Field on | 4. UI up first, then radio |
|---|---|---|---|---|
| Dial (StampS3A) | pass | pass, 4.1 s | pass, 5.4 s | pass, 9.3 s |
| Box (StickS3) | pass | pass, 3.3 s | USB dropped twice | 1 pass (4.0 s), 1 drop; repeat below |

All Dial runs: 0 send failures, no BROWNOUT. Dial step 4 at 9.3 s against 4.1 s for step 2 is
not explained and has not been repeated.

### Box step 4 repeat (field off, UI built first, 5 runs)

| Run | Result | Reset cause logged |
|---|---|---|
| 1 | `host timeout`, wand silent (invalid run) | none |
| 2 | stalled at chunk 86/151, board restarted | PWRON (1) |
| 3 | pass, 4.2 s, 151 frames, 0 send failures | none |
| 4 | stalled at chunk 21/151, board restarted | PWRON (1) |
| 5 | restarted 2 s after `radio_up`, before any frame | PWRON (1) |

- Every restart was PWRON (1). No WDT (3) or SOFT (5) was seen.
- Run 5 restarted with the radio up and nothing transferring, so transfer load is not
  required to trigger it.
- VBUS read 5.1-5.4 V and the battery 3.4-3.7 V (about a quarter to a half charge) in every
  run. The 500 ms samples cannot show a dip shorter than the interval.
- Run 1's wand was silent. The loop waited 12 s after the wand reset; the wand's boot to
  "Boot complete" took about 6 s plus its game-list print.
- This build's `machine` has `PWRON_RESET`, `HARD_RESET`, `WDT_RESET`, `DEEPSLEEP_RESET` and
  `SOFT_RESET` (1, 2, 3, 4, 5) and no `BROWNOUT_RESET`. The brownout signature is believed,
  not verified, to read as PWRON.

### Reading the Box result

The Box's reset problem under radio load on USB is documented in
`git show 42dd9d4:Bag3/Code/BroadcastBox/BBoxFirmware/known_issue.md` (H1: charge current
for the battery stacked on the radio load, expected to read `BROWNOUT` or `PWRON`) and
`docs_and_design/old/2026-09-01-wifi-handoff-diagnosis.md`. It was resolved by making the Box
modal (the AP and the NFC RF field are never on together, `a406712`) with no further issues
reported.

The step 4 bench was already modal: field off, no reader object built. Only the radio,
display and speaker were on, the same load as SERVE. H1 says charge current is highest when
the battery is depleted, and every run here started with a depleted battery. The Box result is
therefore a depleted-battery result, not yet a ruling on ESP-NOW. Step 3 (field on plus radio)
breaks the modal rule by design, so its drops add nothing.

### Open before the Box gate closes

1. Charge the Box to about 4.1 V or more with the radio off, then repeat step 4 five times.
   Pass criterion: 5 of 5 with no PWRON. Allow 20 s after the wand's reset before starting.
2. If it still drops on a full battery, run it from a wall charger or powered hub, then on
   battery only. The bench writes `/flash/bench_trace.txt` and `/flash/resetlog.txt`, so a
   run with USB unplugged can be read back afterward.
3. Control: run the shipped SERVE (SoftAP) for the same duration on the same battery state.
   If it also resets, ESP-NOW is no worse than the shipped firmware on this power path.

### Bench state left on the boards

- Dial (3101) and Box (1101) were last run by `mpremote run`, which stops the firmware; a
  plain `reset` restores their screens.
- The wand on 101 runs the MockWandEUM tree. `tools/deploy.py ... --type wand` restores the
  stock tree.
- `main.py` on the Box now logs the reset cause with its raw number to `/flash/resetlog.txt`
  first thing on every boot (`reset_log.LOG_ENABLED = True`).
