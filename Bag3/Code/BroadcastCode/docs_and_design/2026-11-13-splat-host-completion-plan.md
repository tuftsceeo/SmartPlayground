# Plan: Splat host wand prototype draft for bench testing

## Context

Branch `wand-splat-update` is a prototype branch. The user bench-tests it on hardware; the main branches are protected. The goal is a working **draft** to run on hardware next week, on **MicroPython v1.28.0**. Fixing v1.29 is out of scope.

The work is a draft. Problems found on the bench get debugged then. There is no test suite yet, and building one waits until a prototype exists to instrument.

- **Checks:** syntax only. Run `python -m py_compile` on each changed `.py` file and `node --check` on each changed `.js` / `.mjs` file.
- **Stale:** the existing devtests (`BroadcastCode/tools/devtests/`), Simulator tests and older docs predate the game-mode split and slot policy. Don't fix or run them as gates. If one is touched along the way and fails, note it in "Stale tests" below and move on.
- **Background:** the earlier state is summarised in `2026-11-13-splat-host-status-overview.md` (same folder).

## User decisions (2026-11-13)

1. **Splat ownership.** Every Splat belongs either to a Splat host wand (`splat_host` role, up to 4) or to a solo wand acting as a peripheral host (1–2). Splats are never shared between wands over ESP-NOW.
2. **Game modes.**
   - **Solo wand (type 2):** one player with 1–2 Splats on that wand. No lobby. Declares `SPLATS_LOCAL` and takes `splats=None`.
   - **Splat host game (type 9):** any lobby with Splats, 3 or more Splats, or several players sharing Splats. Declares `SPLAT_HOST = True`, `SPLATS_MIN` (1..4), optional `SPLATS_MAX`, optional `PLAYERS_MIN`, and takes `net=None`.
   - **Plain lobby:** a lobby with no Splats. Declares `PLAYERS_MIN` alone and takes `net=None`. The first wand to tap leads. A `SPLATS_MIN` declared without `SPLAT_HOST` is an error.
   - **Removed:** the pooled lobby path (`_PoolSplat`, `net.owner`, `pw_cmd`/`pw_evt`) and the `splattag`/`relaycolor`/`lobbytest` games and tags.
3. **Slot policy (host).**
   - A missing Splat stays paired and keeps being searched for.
   - A newly tapped Splat takes the first empty slot.
   - If no slot is empty, it replaces the first missing slot and takes over that slot's pair colors.
   - It is refused only when all 4 slots are connected.
   - A replaced Splat can then be claimed by another wand.
   - If two wands claim one Splat, the first to connect wins, and the Splat shows as missing on the other.
   - Forget all is a long hold with a countdown.
4. **`boot.py`.** Light the 25 wand pixels immediately for power-on feedback, before the radio comes up. No `memprobe`. Add a one-line exception to the radio-first rule in AGENTS.md.
5. **`splat_api.py`.** `Wand Module/lib/splat_api.py` is the source of truth. SplatCompanion moves to `Experiments/` as stale, with a README that points to its pairing-management code.
6. **Firmware.** Hosts require v1.28.0. On v1.29 the wand still works as a normal wand, but the host role is flagged. Watch memory on the bench.

## Workstreams

Only `Bag3/Code/Wand Module/` changes on the wand side. No Bag1 or Bag2 edits.

### W1: Firmware draft (done by the lead agent)
0. **Game-mode split.** Bring the type 2 / pooled-removal changes from `Experiments/SplatAuthoringRows/wand/` into `Wand Module/`. Make `PLAYERS_MIN` the plain-lobby gate. Update the README sections. In ChatBroadcast, add `splatGameCheck.js` with the decision 2 rules, apply `readers.patch` and `wiring.patch`, and add one paragraph to the knowledge files covering solo vs host vs plain lobby. Leave station mode (`splat_host.py` `_station_cmd`) for W6.
1. **Slot policy.** Change `lib/pairing.py` / `lib/splatpair.py` to: own slot, then first empty, then replace the first missing (live link state) and keep its colors, else refuse.
2. **`boot.py`** and the AGENTS.md exception, as in decision 4.
3. **Feedback.** Pass the motor into `SplatPairing`.
   - On pair: success tune plus a buzz.
   - On refuse: falling tone plus a double buzz. The 0-player start refusal gets the same.
4. **v1.29 flag.** At host start, if not v1.28, print one `[WARN]` line from a lazily imported module and show an error pattern. Note it in `known_issues/2026-11-12-splat-host-v129-firmware.md`.
5. **Small fixes.** Cache `pair_of`. Make `_on_ready` show the pair glow, not the identity color.
6. Run the syntax check and commit.

### W2: SplatCompanion to Experiments
Move it with `git mv` and add a README. Update the AGENTS.md references. Drop the Companion comparisons from `test_wand_copies.py`.

### W3: Flash bundle
Regenerate `flash_bundle/` from the current Wand Module. It must include `lib/splat_host.py` and the new `boot.py`.

### W4: Hardware bench (the user runs it, or an agent does with the user's OK under `HARDWARE_PROTOCOL.md`)
- Host boot with 4 Splats.
- Each case of the slot policy, including the two-wand claim.
- A host lobby with 2 player wands and a `host_*` game.
- A solo wand with 2 local Splats.
- Memory: largest free block, IDF and heap, at each step. Flag anything under about 8 KB.

Debug what turns up, then record the v1.28 numbers in the known-issue note.

### Later (after a working draft)
- Simulator vendor resync and UI.
- A test suite built on the instrumented prototype.
- Station mode.
- The SplatAuthoringRows game-design handoff (`game_design/HANDOFF.md`).

Open design questions there go to the user.

## Stale tests (noted, not fixed)
- `devtests/boot_wand_lobby_game.py`: the `lead` scenario hangs in the lobby (`SimError` at 60 s). It hangs the same way at HEAD.
- `devtests/boot_wand_idle.py` and `boot_wand_pairing.py`: they test the old drop/unpair behaviour.
- `devtests/test_wand_copies.py`: it compares against the SplatCompanion copies.
- `ChatBroadcast/tools/splat_game_check_test.mjs`: 15 cases fail. They expect the fork's old rule that SPLATS_MIN alone means a plain lobby; the checker now requires PLAYERS_MIN alone. Their knowledge-example case needs updating too.
- Simulator pytest: 6 failures, and 5 vendor files have drifted.
- `check_tags.mjs` fails on `nfc_sound`, and `sync_icons --station` reports `ready.py` drift. Both are outside this work.

## Process
- Commit each workstream on `wand-splat-update` with the attribution line.
- No push or PR until the user says so.
