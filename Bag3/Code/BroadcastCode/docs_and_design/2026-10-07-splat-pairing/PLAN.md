# Splat-paired wands — plan

Implements [SPEC.md](SPEC.md) in `Bag3/Code/BroadcastCode/MockWand/` only. Each milestone
ends on hardware (per `Code/HARDWARE_PROTOCOL.md`: ask for ports, `resume` on every
`mpremote` call). Static check between steps: `python -m py_compile <file>`.

Hardware needed: 2-3 MockWands (u.FL antennas), 2-4 Splats, Splat cards.

## M1 — Measure before building (go/no-go)

The design depends on two unmeasured things: BLE bring-up on the wand with `main.py`'s
real import load, and wand↔wand unicast on C6.

1. Bench script `docs_and_design/2026-10-07-splat-pairing/bench_wand_ble.py`, run on a
   MockWand with `main.py` in place: replicate `main()` up to `enow.init()`, then
   `BLE().active(True)`, import the four Splat modules, connect 2 pinned Splats.
   `memprobe` at each step.
   - Pass: BLE up and 2 Splats READY; record `idf_largest` after each step.
2. Wand↔wand unicast with BLE + 2 Splats on both ends: reuse `coex_bench.py`'s ping/bulk
   phases with a MockWand as each end. Also run with BLE off and with
   `CONN_INTERVAL_US` set, to start isolating the 169-3333 ms p50.
   - Record the p50/max; this sets realistic expectations for pooled commands.
3. Write results to `RESULTS-M1.md`. **If BLE can't come up after `main.py`'s imports, stop
   and revisit §4** (e.g. move BLE ahead of module-scope imports).

## M2 — Libraries and card parsing

1. PEER-copy `splat_hub.py`, `splat_link.py`, `splat_api.py`, `lib/ble_splat.py` from
   `SplatCompanion/Companion/` into `MockWand/lib/`, unchanged, with a PEER header line.
   Add a note to `MockWand/README.md`'s lib copies section.
2. `lib/nfc_reader.py`: `parse_splat_card(text)` → `"AB:42:00:00:7E:B6"` or `None`
   (prefix `splat-`, 12 hex digits, case-insensitive). `read_command()` returns
   `("splat", mac)` style text the idle loop can route — match the existing return shape.
3. `lib/game_tags.py`: add `unpair` to `CONTROL_TAGS`.
4. CPython test for `parse_splat_card` alongside existing devtests.

## M3 — Pairing store and boot

1. `lib/pairing.py`: `load()`, `add(mac)`, `remove(mac)`, `clear()`; atomic write
   (tmp + rename, as `game_store` does). Imported only after the radio is up.
2. `main()`: after `enow.init()`, inline read of `/pairing.json`; delete it on
   `PWRON_RESET`; if non-empty, BLE up and `SplatHub(macs=...)` + `SplatGroup` before
   Stage 1. Failure paths per SPEC §4 (amber data pixel, file cleared).
3. `PAIR_CONNECT_MS` watchdog in the idle loop: drop a Splat not READY in time, error
   feedback.
4. Hardware: pair file written by hand → reset → Splat connects; power-cycle → file gone
   and BLE never imported (check the log); soft reset → file kept.

## M4 — Pair and unpair in the idle loop

1. Splat card routing in the idle loop: full / claim check (`pw_who`, 300 ms) / append +
   reset. Toggle-unpair on a held card. `unpair` card. `pw_release_all`.
2. `pw_who` responder in the idle loop.
3. Identity color (`lib/party.py`'s palette helper, or a tiny function in `leds.py`):
   Splat idle glow, wand corner pixel, pair-success flash and tone.
4. `SplatGroup.poll()` in the idle loop iteration.
5. Hardware: two wands, one Splat — A pairs; B's tap is refused fast; A taps again
   (unpair); B pairs. A third Splat on a wand holding two is refused. Power off A while
   holding → B's tap succeeds after A's silence. Idle glow survives a Splat power cycle.

## M5 — `party.py`: lobby and roster

1. `lib/party.py`: `find_or_lead(enow, slug, local_group)`, lobby loop, tie-break,
   `pw_join`/`pw_joined`/`pw_leave`/`pw_start`/`pw_end`, peer add/remove, per-sender `q`
   dedupe, `SEND_TRIES` unicast helper, heartbeat send and timeout.
2. `main.py`: after `_load_play()`, read `SPLATS_MIN`/`SPLATS_MAX`; for a party game run
   the lobby, then `_start_play()` with `net`. Extend arity handling to 8 parameters
   (6 → 7 → 8 fallback order unchanged for old games).
3. Exit handling: `stop` card and `pw_end` both end cleanly; ESP-NOW peers removed; local
   Splats return to idle glow.
4. Built-in test game `partytest.py`: lobby, then each wand's button lights the next pool
   Splat in the presser's identity color.
5. Hardware: 2 wands × 1 Splat, then 2 + 1 plain wand. Simultaneous taps (tie-break).
   Two separate groups running `partytest` at once.

## M6 — `net` API: pooled and messages

1. `net.splat(i)` proxy (`pw_cmd`), follower-side executor in `poll()`, `pw_evt` press
   forwarding, local press delivery, `net.send()`/`("msg", ...)`.
2. Dropout events: `splat_lost`/`splat_back` from `pw_hb` bitmasks, `wand_lost`/
   `wand_back`, `leader_lost`.
3. CPython simulation of `party.py` with fake ESP-NOW (lost frames, lost ACKs,
   duplicates) and fake Splats, following `SplatCompanion/test_splat_companion.py`'s
   approach.
4. Two demo games, one per model:
   - `splattag.py` (pooled): leader lights a random pool Splat; first press wins a point.
   - `relaycolor.py` (messages): a color passes wand to wand; each wand shows it on its own
     Splats.
5. Hardware: 3 wands, 4 Splats total. Log pooled-command latency (leader `splat(i).color` to
   follower BLE write) and remote press latency. Pull a follower's battery mid-game and
   check that `wand_lost` arrives; power off a Splat and check `splat_lost`/`splat_back`.
   Kill the leader and check `leader_lost`.
6. `RESULTS-M6.md` with the numbers and logs.

## M7 — Docs

1. `MockWand/README.md`: pairing, boot order change (BLE after ESP-NOW when paired), the
   `play()` contract with `net`, the new PEER copies, `unpair` tag.
2. A game-authoring section for party games (pooled and message examples), placed where wand
   game docs already live.
3. Update SPEC.md Known issues with what M1/M6 measured.

## Later (not in this plan)

- ChatBroadcast generation: SPEC §11.
- A `pw_release_all` sender in Live_Page / Box.
- Symmetric-peer games replacing the leader model.
- Port to `Bag3/Code/Wand Module/`.
- Splat Companions honoring wand pairings.
