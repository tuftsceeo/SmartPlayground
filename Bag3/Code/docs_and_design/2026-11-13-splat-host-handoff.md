# Handoff: Splat host wand, screen, pairing and testing (2026-11-13)

Bag3 only. Bag2 is not touched. Branch `wand-splat-update` (not pushed). These two files are
written in the shared working folder, which is checked out on `ccr-e1ed35ff-24apiv`; they are not
committed on any branch.

## Read first

- `AGENTS.md`, `Bag3/AGENTS.md`, `Bag3/Code/HARDWARE_PROTOCOL.md`.
- The plan: `2026-11-12-splat-host-screen-pairing-plan.md` (this folder; copied from
  `C:\Users\Jennifer\.claude\plans\swift-sparking-dolphin.md`, which is outside the repo and was
  never committed).
- `Bag3/Code/known_issues/2026-11-11-simple-mode-large-changes.md` item 3.
- `Bag3/Code/known_issues/2026-11-12-splat-host-v129-firmware.md`.
- `Bag3/Code/Experiments/SplatHostBench/HANDOFF.md` and `README.md` (memory bench, another session).

## State of `wand-splat-update`

| Commit | What |
|---|---|
| `9d1a8b8` | `main.py` starts ESP-NOW before any other import; `espnow_manager.init()` keeps an active ESP-NOW; bench scripts `utilities/bench_host_pairs.py`, `utilities/bench_ble_conns.py`; `tools/deploy.py` uses `sys.executable`; known-issue note item 3 results. |
| `d9855f74` "splat test work" | Plan firmware: `splat_host.py` (2x2 corners, breathing next slot, missing flash, peek, forget hold), `splatpair.py` pair helpers, `pairing.py` slot reuse, `lobby_game.py` `pw_lobby` `c`, `test_splat_host.py` extended, vendor copies synced. |
| `e534aef2`, `3cb1c884`, `d24fcc05` | 4-Splat memory bench (`Experiments/SplatHostBench/`): 4 of 4 on v1.28.0, 2 of 4 on v1.29.0 in the full boot. |

`.claude/skills/bag3-hardware-protocol/SKILL.md` has an uncommitted user edit; leave it.

## Plan progress

Done in code (not checked against every plan line; review the diff of `d9855f74` against the plan):

- Corner blocks, empty/next/missing/paired drawing, peek (`PEEK_MS` 4000), forget hold
  (`FORGET_HOLD_MS` 4000).
- Pair per Splat MAC, unique on the host; slot reuse (own, then first missing, then first empty).
- Lobby color travels as `pw_lobby` `c`; player wands read it into `lobby_c`.

Not done or not confirmed:

- Simulator: host card without tilt controls; slots showing pair colors and missing state
  (`js/panels/splatController.js` shows plain paired/empty); oversized wand-owned Splat cards.
- `sim-room.js` `gameSplats`: returns 0 when `hostSplats` is set, else 1; it does not read
  `caps.splat_host`, so a host game without settings still gives game wands 1 Splat. Check.
- Player-wand dots (one per joined wand) not confirmed.
- `node --test`, `pytest`, `tools/sync_sources.py --check`: not run after `d9855f74` by this session.
- Browser verification with screenshots: not done.
- `flash_bundle` `wand_main.mpy` not regenerated.

## Hardware findings

- Left (LEDs 0–6) and right (7–13) are the Splat's left and right halves. All 30 ordered pairs of
  the six `PALETTE` colors at `GLOW_SCALE` 0.5 were read as distinct.
- Splat count is limited by IDF heap state, not a connection cap: `-519` (HCI 0x07) on a fragmented
  heap; 4 of 4 with ESP-NOW then BLE first, precompiled libraries, after a hard reset. The other
  session's bench shows the full boot gets 2 of 4 on v1.29.0; open in the v1.29.0 note.
- After `9d1a8b8` on COM7 (v1.29.0): boot OK, largest IDF block 163840 after imports, Dial code push
  OK. A host boot with 4 paired Splats has not been run.

## Bench setup (Windows)

- COM7 wand, MAC A0:F2:62:85:CB:FC, u.FL antenna (GPIO14 = 1). `/main.py` is a 17-byte stub;
  `wand_main.mpy` and `lib` from `9d1a8b8` are on it; host games are not in `/games`.
- Splats (no NFC tags): `AB:42:00:00:64:3F`, `62:2F`, `80:B4`, `B2:16`. Bench scripts pin them by
  MAC. Power-cycle Splats between runs; they keep a stale paired state.
- `python -m mpremote` (never `python3`). Routine update: reset, one `resume cp`, reset. Do not use
  `deploy.py` except on a new or very stale device.
- Every port command gets a 10 s limit, checked at once; small copies take seconds. If one runs
  out, find the cause (what holds the port, board state), tell the user, and ask before any
  physical step. One step at a time; batch once it works. Hardware only with the user's OK.

## Testing to do

1. `python -m py_compile` on changed `.py`; `pytest Bag3/Code/tools/devtests/test_splat_host.py`;
   Simulator `node --test`; `python Bag3/Code/Simulator/tools/sync_sources.py --check`.
2. Finish the Simulator items above, then browser-check: host card, slots with pairs and missing,
   lobby, peek, start/end/forget holds, player wand dots. Screenshots.
3. Hardware (with OK): copy the `d9855f74` libs to COM7, set `role.txt` = `splat_host`, pair 4
   Splats, boot. Record connected count and the MEM lines; check corners, pair glow on each Splat,
   missing flash, peek, holds, and a 5th Splat refused.
4. Update the known-issue notes with results.
