---
title: A Splat host wand drops a code_push that arrives during a game
date: 2026-11-17
status: fixed in code 2026-11-17 (3c897264); not re-run on hardware
devices: [Wand]
components: [Wand Module/main.py, Wand Module/lib/splat_host.py]
code:
  - Bag3/Code/Wand Module/main.py
  - Bag3/Code/Wand Module/lib/splat_host.py
open:
  - Push during a running game on a splat_host wand ends the game but never pulls
  - Not checked for a player wand (the bench wand was in the splat_host role)
keywords: [code_push, distribute, splat_host, _pending_push, _StartGameCapture, host, timeout]
related:
  - Bag3/Code/known_issues/2026-11-15-box-fleet-port.md
  - Bag3/STRESS_TEST_UNATTENDED_2026-11-16.md
---

# Splat host wand drops a mid-game code_push

**What the log shows (2026-11-16, 23:58-23:59, Box `51c0` -> wand `A0:F2:62:85:CB:FC`, role
`splat_host`, 4 Splats paired but not switched on):**

1. `fleet.distribute stresshost` pulled and started the host game (`MEMSPAN tag=import:stresshost`).
2. 40 s later `fleet.distribute stresse`: the Box logged `dist_progress why "pushed"`; the wand logged
   `MEM tag=post-game:stresshost` one second later (the game ended), and then nothing: no
   `# getcode` line. The Box reported `dist_progress ok false why "timeout"` after 30 s.
3. The wand kept answering `status_poll`; `g` still listed `stresshost`, not `stresse`.

**From reading the code (not tested):** during a game, `main._StartGameCapture.poll()` turns a
`code_push` into `_queue_push(data)` plus `"stop"`. Only `main.py`'s idle loop reads
`_pending_push`. A `splat_host` wand never reaches that loop: it runs `splat_host.run()` /
`_loop()`, which handles a `code_push` it receives directly (`splat_host.py:272`) but never
looks at `main._pending_push`. So the push that ended the game is lost.

A push to a splat_host wand that is *not* in a game pulls normally (five of five in the same run).

Fix direction (not done): have `splat_host._loop` take a queued push after `launch()` returns,
e.g. via a getter passed in like `get_ctl`.

## 2026-11-19: outcome

`splat_host.py` now wraps launch and pull (`_then_push`) so a push queued in `main._pending_push` is pulled after the game ends (commit `3c897264`). Not re-run on hardware.
