# Splat host wand: predictable pairing and screen (Bag3 only)

## Context
The Splat host role is built and committed on `wand-splat-update` (12d09ff, 76f6a4b, 45b02d9). Its screen and pairing behavior are still ad hoc:
- `lib/splat_host.py` `_draw` lights single corner pixels.
- The lobby replaces everything with a numeral (`lib/lobby_game.py` `_draw_lobby`, host branch).
- The host still takes tilt input.

The host is a teacher-operated device that only pairs Splats and hosts lobbies. This round makes its behavior predictable, following the user's UX spec and their answers:
- The center cross lights to show state.
- The player count is a peek on a short press.
- Color pairs are built now, with a provisional palette.

Bag2 is not touched. Only the Bag3 `Wand Module` tree and the Simulator change.

**Checked against the latest merge.** `wand-splat-update` is now at `b38da54` (a merge of `simple-mode-corrections`). On top of 45b02d9 it adds only `6174b1b` "add emulated nfc tag":
- `bboxDeviceLink.js`
- `boxFirmwareInstaller.js`
- `tools/deploy_bak.py`
- `docs/HARDWARE_SOFTWARE_INVENTORY.md`

None of these files is in this plan, so there are no conflicts. Work starts from `b38da54`.

## Screen (5x5)
- **Corners:** four 2x2 blocks, one per Splat slot. Pixels are (0,1,5,6), (3,4,8,9), (15,16,20,21) and (18,19,23,24). They fill in the order TL, TR, BL, BR.
- **Center cross (row 2, column 2):**
  - idle: off;
  - lobby open: yellow-green breathing;
  - playing: cyan heartbeat;
  - start/end hold: a progress fill along the cross.
- **Center pixel (12):** the lobby color, while a lobby is open.
- **Corner states:**
  - empty: dim, with only the next open slot breathing;
  - paired: the left column of the block in color A and the right column in color B;
  - missing: the pair flashes on and off;
  - just tapped: a short bright pulse.

## Splat color pairs (reverse of the wand→Splat identity code)
- **Reuse** `splatpair.py`'s `PALETTE`, `WAND_RGB` and its `identity_name`/`second_name` scheme (MAC bytes modulo the palette size), applied to the **Splat's** MAC instead of the wand's.
- **Rules:**
  - the two halves must differ (if they match, bump the second);
  - no pair may repeat one already on this host (bump the second until it is unique).
- **On the Splat:** the pair shows as `left` = A and `right` = B, using the new light parts (76f6a4b), as its idle glow.
- **Stored:** the logical names go in the host's pairing record, so a pair survives reboots unchanged.
- **Provisional:** a Splat shows only the six `COLOR_RGB` names, so the spec's 12-color palette with reserved colors does not fit. This round uses the six, giving 30 ordered pairs. It is marked for the palette bench test in the known-issue note.

## Interactions (`lib/splat_host.py`)
- **Pair: tap a Splat's tag.**
  - A new Splat first fills a *missing* corner and takes that corner's pair; otherwise it takes the next empty corner.
  - A fifth Splat is refused.
  - Re-tapping a paired Splat pulses its corner and the Splat itself (identify).
- **Feedback on every tap:** light, sound and buzz together.
  - Success: a rising chirp and one buzz.
  - Refusal: a falling tone and a double buzz.
  - Reuse the `buz` helpers already in `splatpair.py` or `buzzer.py` where they exist.
- **Game tag tap:** opens a lobby, and Splats can still be paired in the lobby. This is the existing `launch` path.
- **Short press:** peeks the lobby count as a numeral (the existing `SHAPE_n`) for about 4 s, then returns to the corners. This replaces the persistent numeral in `_draw_lobby`'s host branch.
- **Hold:**
  - **In the lobby:** start, with the cross filling. Starting with 0 players is refused.
  - **While playing:** end. The hold is longer than the start hold.
  - **At idle:** forget all Splats. The corners go out one per second over about 4 s, and releasing early keeps them.
- **Teacher commands:** `start_game` and `stop` are accepted as now. There is no end-of-game animation.
- **Boot:** stored pairs show solid for about 1 s, then any Splat not seen flashes as missing. A missing Splat does not block the start.
- **No tilt:** the host ignores the accelerometer in its idle loop and lobby. Host games already get `net` and don't need it.

## Player wands
- In a host lobby, a player wand shows one pixel per joined wand (not a digit) plus the lobby color pixel matching the host's center pixel.
- This goes in `_wait_for_host` / the follower draw in `lib/lobby_game.py`.
- The lobby color comes from the host's MAC and travels in `pw_lobby` as a new field `c`.

## Simulator
- **The host card's wand** is drawn right side up and compact, with no tilt or shake controls and no accelerometer readout. This needs a renderer option on `<wand-sim>` for a host. Check `js/renderer.js` and `wand-sim.js` for an existing way to hide the controls.
- **Pairing slots** (`js/panels/splatController.js`) show each Splat's pair colors and the missing state. A slot's "forget" maps to the idle hold.
- **The two issues found earlier:**
  - In a host game, game wands default to 0 Splats even without settings (`sim-room.js` `gameSplats` should use `caps.splat_host`).
  - Wand-owned Splat cards render oversized in the dialog.
- Vendor sync: `tools/sync_sources.py`, then `--check`.

## Files
- `Wand Module/lib/splat_host.py`: draw, pairs, button, boot.
- `lib/lobby_game.py`: the host draw and peek, the player draw, `pw_lobby` `c`.
- `lib/splatpair.py`: pair helpers and the left/right glow.
- `lib/pairing.py`: stored pair names.
- Simulator: `py/runtime.py`, `js/panels/wands.js`, `js/panels/splatController.js`, `sim-room.js`, `js/renderer.js`/`wand-sim.js`.
- The `known_issues` note, item 3.

## Constraints
- Nothing new is imported ahead of the radio: `splat_host` stays a lazy import after bring-up.
- f-strings stay as they are, and there are no type annotations.
- Every serial-I/O loop keeps its unconditional `time.sleep_ms(1)`.

## Verification
- Run `python -m py_compile` on every changed `.py`.
- Extend `BroadcastCode/tools/devtests/test_splat_host.py` to cover:
  - the corner pixels;
  - pair uniqueness and the bump rule;
  - missing-slot reuse;
  - fifth-Splat refusal;
  - the peek timeout;
  - the hold thresholds;
  - refusal with 0 players.
- Run Simulator `pytest tests/test_splat_host.py`, `node --test tests/js/*.test.mjs` and `sync_sources.py --check`.
- In the browser:
  - add a host and pair 4 slots, checking the corners and pairs;
  - check that the Splats show their left/right pair;
  - unpair one, check it shows missing, re-pair it and check it fills that slot;
  - check the lobby cross and the peek;
  - hold to start, with the player wand's dots;
  - hold to end.
- Hardware only with the user's OK, under `HARDWARE_PROTOCOL.md`: the 4-Splat BLE question and the palette bench test.
