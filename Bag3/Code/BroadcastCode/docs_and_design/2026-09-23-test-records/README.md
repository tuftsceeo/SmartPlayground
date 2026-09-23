# 2026-09-23 test records

Raw serial captures backing `../2026-09-23-debug-handoff-multihost-pull.md`
("Update 6" section onward). Renamed `.log` -> `.txt` on copy so they are not
swept by the repo's `*.log` gitignore rule.

- `sticky_state_t2/` -- T2 (STICKY-STATE) run against Dial 2 (`tilt_tones`,
  host `004c`). `cycle_*.txt` are individual wand-side pull attempts;
  `cycle_1_kept.txt`/`cycle_1_r2.txt`/`cycle_2_r2.txt`/`cycle_3_r2.txt` are
  cycles preserved across a mid-run restart (see the handoff doc for why).
  `dial2_continuous_run1.txt`/`run2.txt` are Dial 2's own serve-side log,
  captured continuously in parallel with the wand-side cycles -- run1 is
  the first ~900s window (expired before the T4 soft-reset test), run2
  starts after that reset.
- `one_vs_two_t5/` -- T5 (one Dial vs two, wand-driven) against Dial 1
  (`apple_button`, host `5094`). `phaseA_*` = only Dial 1 armed,
  `phaseB_*` = both Dials armed.
- `stats_log/` -- raw `/flash/stats.log` pulls from both Dials (T1),
  200/30 lines respectively (each file's own on-device trim cap).

Produced with `tools/devtests/sticky_state_bench.sh` and
`tools/devtests/one_vs_two_bench.sh`.
