# Splat host bench (2026-11-12)

Bench files and notes for the Splat host wand role. The code is in `Bag3/Code/Wand Module/`
(`lib/splat_host.py`, `lib/pairing.py`, `lib/splatpair.py`, `lib/splat_hub.py`,
`lib/lobby_game.py`, `main.py`). Deploy problems are in
`known_issues/2026-11-12-wand-mpremote-copy-fails.md`.

## Files

| File | What |
|---|---|
| `wand_main.mpy` | `main.py` compiled with mpy-cross 1.28.0.post2 |
| `device_main.py` | The wand's `/main.py` stub (a grace sleep, then `import wand_main`) |
| `pairing.json` | Four Splats with their slots; copy to `/pairing.json` |
| `role.txt` | `splat_host`; copy to `/role.txt` |
| `host_run.log` | First run: 2 Splats connected, 2 failed with `-519` |
| `edit_*.py`, `host_new.py` | Scripts that applied the lib edits (already applied) |

## Role

`/role.txt` holds `splat_host`. It is set by the card `splathost` or by an ESP-NOW `set_role`
message, and cleared by the card `player`. Each change resets the wand. A wand that becomes a host
keeps its Splats.

## Slots and pairs

`/pairing.json` holds `splats` (the MACs the wand connects to) and `slots` (`HOST_MAX_SPLATS`
entries, each null or `[MAC, A, B]`).

- A new Splat takes its own slot if it has one, else the first missing slot (with that slot's
  pair), else the first empty slot.
- On a host, `remove()` keeps the slot, so the Splat shows as missing.
- `pick_pair`: A is `identity_name`. B is `second_name`, bumped until it differs from A and the
  pair is unused.

## Screen

There are four 2x2 corners: TL, TR, BL, BR, one per slot.

- **Corners:**
  - A paired slot shows its pair: A in the left column, B in the right.
  - A missing Splat flashes.
  - An empty slot is dim; the next one to fill breathes.
  - A re-tapped Splat pulses its corner.
- **Center cross:**
  - Off at idle.
  - Breathes yellow-green in a lobby.
  - Beats cyan in a game.
  - Fills during a hold.
- **Center pixel:** the lobby color, which is the host's identity.

## Button

- **Short press:** shows the count as a numeral for `PEEK_MS`.
- **Hold:**
  - In a lobby, starts the game after `START_HOLD_MS`; refused with no players.
  - In a game, ends it after `END_HOLD_MS`.
  - At idle, forgets every Splat after `FORGET_HOLD_MS`. One corner goes out per second, and
    releasing early keeps them.

## Connection results

| Run | Result |
|---|---|
| BLE started after imports | 2 connect; the 3rd and 4th fail with `-519` (HCI 0x07, Memory Capacity Exceeded) |
| BLE started right after ESP-NOW (`main.py`) | Found 4; the 3rd and 4th fail with `-521` (HCI 0x09, Connection Limit Exceeded) |
| Splats switched on after boot (before the rediscovery change) | Never found; dropped from `splats` after `PAIR_CONNECT_MS` |

Host-only changes:
- No drop at `PAIR_CONNECT_MS`.
- No release at `LOST_GIVE_UP_MS`.
- `SplatHub.rediscover` scans every `REDISCOVER_MS` while a Splat is missing, even with other
  Splats connected.

BENCH: `splat_link` calls `memprobe.idf_regions()` on each connect and on each Splat's first
failure. The output is grepped as `MEMIDF`.

## Bench 2026-11-12, second wand (COM8, freshly charged)

Run with `bench_diff.py` (`STEP` 0-3) and `bench_step4.py`. `/main.py` renamed to `main.py.bak`;
every library loaded from `/benchmpy` (the `lib_mpy/` builds), none from the wand's `/lib`. Hard
reset before each run. Logs: `step*_com8.log`. IDF main region given as free / largest block.

| Step | Adds | Before connect | 4 ready | Result |
|---|---|---|---|---|
| 0 | ESP-NOW, BLE, hub modules | 144588 / 143360 | 136092 / 129024 | 4 of 4 |
| 1 | every `wand_main` import, after BLE | 13588 / 13312 | 5096 / 1120 | 4 of 4 |
| 2 | `Leds()`, PN532, 110 KB GC load | 13212 / 13056 | 4712 / 1760 | 4 of 4 |
| 3 | `SplatPairing` (host), ESP-NOW poll, glow | 13232 / 13056 | 4780 / 1504 | 4 of 4 |
| 4 | the real `wand_main` (timer reset after 100 s) | — | — | 4 of 4 |

- The GC heap grows into the IDF main region in one step of about 131 KB once the imports
  outgrow it. Four connections then need about 9 KB, so they still fit.
- The first wand (COM7) failed the 3rd and 4th connects (`-519`, `-521`) on the same code.
  Differences not separated: its battery read 3.3-4.0 %; its `/lib` held stale `.py` copies;
  some of its boots were soft reboots.

## Firmware (2026-11-12)

| Wand | MicroPython | STEP 0 | Normal boot (`wand_main`, host) |
|---|---|---|---|
| COM8 | v1.28.0 (2026-04-06) | 4 of 4 | 4 of 4 (`com8_wand_boot.log`) |
| COM11 | v1.29.0 (2026-08-24) | 4 of 4 (`step0_com11.log`) | 2 of 4; then `-521`, `-519`, write failures (`com11_wand_boot.log`) |
| COM7 | v1.29.0 (2026-08-24) | not run | 2 of 4 (battery 3-4 %) |
| COM7, reflashed | v1.28.0 (2026-04-06), Seeed XIAO build | not run | 4 of 4, seen on the wand screen with the other wands off (battery 3.4 %); no log. First run with COM8 on: 1 found (`com7_v128_boot.log`) |

Same `.mpy` libraries (mpy-cross 1.28.0.post2), same `pairing.json` and `role.txt`. COM7 failed on v1.29.0 and connected 4 of 4 after reflashing to v1.28.0, at the same low
battery.

## Open

- What in v1.29.0 breaks 4 Splats in the full boot (STEP 0 still gets 4 of 4 on v1.29.0).
- Flash COM11 to v1.28.0.

- COM7 wand: rerun STEP 4 after a full charge, to separate the battery from stale `/lib` files
  and soft reboots.
- Clean install: erase and flash a wand, then copy only `/main.py`, `wand_main.mpy`,
  `hubtype.txt`, the `.mpy` libraries and the games. COM8 still holds old root files.
- Which libraries must be `.mpy`. Compiling a `.py` on the wand allocates transient GC memory,
  which can grow the heap into the IDF main region before BLE connects. Not measured per library.
- Memory after 4 Splats in the real boot. STEP 3: the IDF main region has about 1.5 KB in its
  largest block and the GC heap 16.5 KB free, with a 110 KB load standing in for `wand_main`.
  `wand_main` itself printed GC free 175696 of 271296 after imports; no probe after connecting.
- Game play with 4 Splats connected: not run. A GC heap that needs to grow has no IDF memory left
  to grow into.
- Custom games pulled to `/games/` are `.py` and compile on the wand at launch. Not measured with
  4 Splats connected.
- `pairing.json` was missing on COM8 after the STEP 4 run; cause not traced.
- `GRACE_S = 30` in `main.py` stacks with the stub's grace (about 35 s to the banner).
- Discovery took 16-23 s after the host loop started.
- Ctrl-C handler in `splat_host.run` (radios off): not tested.
