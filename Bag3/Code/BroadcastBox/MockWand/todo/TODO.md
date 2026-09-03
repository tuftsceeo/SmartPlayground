# MockWand memory-stabilization TODO

Follow-ups from the WiFi-OOM fix (lazy game imports + radio-first
`enow.init()`, `wifi_chat_tap_debugging` branch). The core fix is
committed and hardware-validated (clean boot x5, pull x6/6 with the
actual pulled game playing correctly, idf free ~171-183KB throughout
vs. the ~12KB that caused the original crash). These are the open
items from that work.

## 1. Run `import_bench.py`'s sweep

Never run. `import_bench.py` (repo root, bench-only) has three modes —
`bench_sequential()`, `bench_isolated()` (the one that matters: cold
heap, one game per reboot, avoids the shared-dep-caching confound), and
`bench_unload_cycle()`. Running mode B on all 15 games gives real
per-game compile-time numbers (worst case suspected: `gestures.py`,
28KB source). Feeds the one still-open design decision: `_load_play()`
in `main.py` currently shows the game's `GAME_ICON` with no animation
while it compiles — decide whether a static icon is enough or a
spinner (e.g. `leds.animate_spin`) is needed, from real numbers rather
than guessing.

## 2. Run `bench_unload_cycle()`

Never run. `_unload_game()` is live (`UNLOAD_AFTER_GAME = True` in
`main.py`) and drops the finished game's module + `gc.collect()`, but
nothing has confirmed it actually reclaims memory over repeated
*different*-game cycles. Known limit: MicroPython's qstr pool is never
freed short of a reset, so each distinct game loaded in one boot leaves
a small permanent residual. `bench_unload_cycle(tag, cycles=3)` measures
this directly (delta between cycle 1 and cycle N's post-unload heap).
Run on `gestures` (largest) and `finddevice` (smallest) to see whether
the residual scales with source size.

## 3. Test the loud-failure path

`_game_load_failed()` in `main.py` (red X flash x3, two-tone beep,
`sys.print_exception` to serial, return to idle) has never actually
fired on hardware. Needs a deliberately broken pulled file (bad syntax,
or a `play()` with the wrong signature) pushed via `getcode`, tapped,
and confirmed: LEDs/beep as designed, full traceback on serial, wand
lands back at a *usable* idle rather than stuck.

## 4. Multi-game session test

Everything validated so far replayed the same pulled `jumpin.py`
repeatedly. Never tested tapping several *different* games in one boot
session (e.g. jumpin -> gestures -> cooking -> jumpin again), which is
the actual scenario item 2 above needs to be trustworthy for — a
teacher's class period cycling through many games, not one game
replayed. Watch `MEM tag=post-unload:<name>` across the sequence for
any upward drift.

## 5. Documentation

Explicitly deferred earlier ("revisit after the issue is confirmed and
the fix identified" — that condition is now met). Four separate
write-ups, not yet started:

- `Bag3/Code/BroadcastBox/design/2026-09-01-power-modes-and-fsm.md`'s
  open question "Wand RAM for dynamic import" (currently says
  "untested") — replace with the measured split-heap finding and the
  fix.
- `Bag3/Code/BroadcastBox/ChatBroadcast/knowledge/knowledge.py`'s
  gotcha #10 ("RAM is ~512KB. Avoid large allocations; call
  gc.collect() if needed.") is misleading — the real constraint is
  contiguous IDF heap vs. WiFi, not total RAM. Replace with a concrete
  budget and rules for LLM-generated game code.
- A dated bench-findings note in `Bag3/Code/BroadcastBox/`, alongside
  `REBOOT_PULL_PLAN.md` and `design/2026-09-01-wifi-handoff-diagnosis.md`
  — the two heap snapshots, the split-heap mechanism, and the
  measurement method.
- `MockWand/README.md` — note the bench-instrumentation deviations
  (`lib/memprobe.py`, `import_bench.py`, the pull-path probes, the
  `# BENCH:` markers throughout `main.py`/`code_puller.py`) so the
  fork's drift from `Bag3/Code/Wand Module/` stays legible.

---

**Out of scope for this list:** porting the fix to the fielded
`Bag3/Code/Wand Module/main.py`. Not being tracked here.
