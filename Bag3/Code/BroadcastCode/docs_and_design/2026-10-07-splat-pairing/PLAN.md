# Splat-paired wands — plan

Implements [SPEC.md](SPEC.md) in `Bag3/Code/BroadcastCode/MockWand/` only.

Part A is software only and can be done without hardware access. Part B is one hardware
session that verifies Part A; nothing in Part A waits on it. Part C is deferred work.

## Status

- **M1 (measure before building): done.** [RESULTS-M1.md](RESULTS-M1.md). BLE plus 2 Splats
  came up after `main.py`'s import load (one run). Slow ACKed unicast follows board
  `usbmodem1101`, cause not found. Neither result blocks Part A.

## Rules for Part A

- No serial ports and no `mpremote`. Verification is `python -m py_compile`, CPython tests
  and the boot stubs in `tools/devtests/`.
- Anything only hardware can confirm is marked `UNVERIFIED on hardware` in code comments or
  the README, and gets an entry in Part B.
- Constants whose values hardware will set (`CLAIM_WAIT_MS`, `FIND_WAIT_MS`,
  `PAIR_CONNECT_MS`, `WAND_LOST_MS`, `SEND_TRIES`, the identity palette) are module-level
  constants with the SPEC values, so tuning them doesn't touch logic.
- AGENTS.md: nothing new at `main.py` module scope ahead of `enow.init()`. New modules
  (`pairing`, `party`, Splat libs) are imported inside `main()` after the radio is up.
- Each step ends with `tools/devtests/compile_check.sh` (or `py_compile` on every touched
  file) passing.

## Part A — software

### A1. Libraries

1. Copy `splat_hub.py`, `splat_link.py`, `splat_api.py` and `lib/ble_splat.py` from
   `SplatCompanion/Companion/` into `MockWand/lib/`, byte for byte. No header edits:
   `ble_splat.py` is checked as an exact copy by `test_splat_companion.py`'s
   `test_copies_match`. Record them as PEER copies in `MockWand/README.md`'s lib section.
2. Extend `test_copies_match` (or add an equivalent wand-side check) to cover the four
   MockWand copies.

### A2. Card parsing and the `unpair` tag

1. `lib/nfc_reader.py`: `parse_splat_card(text)` returns `"AB:42:00:00:7E:B6"` or `None`
   (prefix `splat-`, exactly 12 hex digits, case-insensitive). `read_command()` returns
   the raw card text for a valid Splat card, so the idle loop routes it. Follow the
   existing return shape.
2. `lib/game_tags.py`: add `unpair` to `CONTROL_TAGS`.
3. CPython tests for `parse_splat_card`: valid, mixed case, 11 and 13 digits, non-hex,
   colons, missing prefix, `splat-` with a `:slug` or `@id` suffix.

### A3. Pairing store

1. `lib/pairing.py`: `load()`, `add(mac)`, `remove(mac)`, `clear()`, `MAX_SPLATS = 2`.
   Atomic write (tmp + rename, as `game_store.py` does). Corrupt or missing file → empty.
2. CPython tests against a temp directory: add to full, duplicate add, remove absent,
   corrupt JSON, rename failure leaves the old file.

### A4. Boot integration

1. `main()`, after `enow.init()` and before Stage 1: inline read of `/pairing.json`; delete
   it on `machine.reset_cause() == machine.PWRON_RESET`; if non-empty, `BLE().active(True)`,
   import the Splat libs, build `SplatHub(macs=...)` and one `SplatGroup`. Failure paths
   per SPEC §4 (amber data pixel, file cleared, boot continues).
2. `PAIR_CONNECT_MS` check in the idle loop: drop a Splat not READY in time, with error
   feedback.
3. Boot stub test (new `tools/devtests/boot_wand_pairing.py`, modeled on `boot_splat.py`
   and `stubs/`): unpaired boot never imports `ubluetooth`; paired boot after a soft reset
   builds the hub; power-on reset clears the file; `BLE().active` raising boots unpaired;
   ordering (BLE after `enow.init()`, before Stage 1) asserted from the stub call log.

### A5. Pair and unpair in the idle loop

1. Splat card routing: full → refuse; claim check (`pw_who`, `CLAIM_WAIT_MS`) → refuse on
   `pw_held`; else `pairing.add()` + `machine.reset()`. Held card → disconnect + remove,
   no reset. `unpair` card and `pw_release_all` → disconnect all + clear, no reset.
2. `pw_who` responder in the idle loop.
3. Identity color: palette helper keyed on own MAC, using color names from `splat_api`'s
   `COLOR_RGB` so the wand and the Splat show the same name. Splat idle glow, wand corner
   pixel, pair-success flash and tone.
4. `SplatGroup.poll()` every idle-loop iteration.
5. Boot stub or CPython tests: each card case above, with a fake ESP-NOW that does or
   doesn't answer `pw_who`; reset is called only on a successful add.

### A6. `party.py`: lobby, roster, `net`

1. `lib/party.py`: `find_or_lead()`, lobby, lower-MAC tie-break, join/leave/start/end,
   peer add/remove, unicast with `SEND_TRIES` and per-sender `q` dedupe, heartbeats and
   timeouts, `net` members and events per SPEC §7, pooled `splat(i)` proxy and follower
   executor, `send()`/`msg`.
2. `main.py`: read `SPLATS_MIN`/`SPLATS_MAX` after `_load_play()`; run the lobby for party
   games; extend `_start_play()` arity handling to 8 parameters (6 and 7 still work).
3. CPython simulation (`MockWand/test_party.py`, following `test_splat_companion.py`):
   several simulated wands on a fake ESP-NOW bus with frame loss, lost ACKs and duplicates,
   plus fake Splats. Cases: join, lobby count, start at min and auto-start at max,
   simultaneous leaders, two groups same slug, stop on leader and on follower, pooled
   command delivery, remote press, `splat_lost`/`back`, `wand_lost`/`back`, `leader_lost`,
   duplicate `q` dropped.

### A7. Games

1. `partytest.py`: each wand's button lights the next pool Splat in the presser's identity
   color.
2. `splattag.py` (pooled) and `relaycolor.py` (messages), per the old M6.
3. Each runs in the A6 simulation for a scripted session.

### A8. Docs

1. `MockWand/README.md`: pairing, boot-order change, the 8-parameter `play()` contract,
   PEER copies, `unpair` tag, `UNVERIFIED on hardware` list.
2. Party-game authoring section with one example per model.
3. Note in `coex-benchc6/RESULTS.md` that its rtt figures are inflated by the undrained
   bench loop (see RESULTS-M1.md caveats). Ask before editing; it's a committed results doc.

## Part B — hardware session

Per `Code/HARDWARE_PROTOCOL.md`: ask for ports, `resume` on every `mpremote` call, physical
steps for the person. Needs 2–3 MockWands, 2–4 Splats, Splat cards printed with
`splat-<MAC>`, an `unpair` card and a `partytest` card. Results go in `RESULTS-PartB.md`.

### B0. Prerequisites (do first)

1. Power-cycle both Splats; run `scan_splats.py` on 3101. Explains or rules out
   `raw_C_swap`'s "no Splat found". If 3101 still finds none, stop: pairing assumes any
   wand can see a free Splat.
2. Compare 1101 and 3101: firmware build (`os.uname()`), `/lib` file hashes, antenna pin
   state, USB cable/port swap. Rerun `coex_bench_m1.py`'s ping on whichever change moves
   the send time.

### B1. Boot and store (A3–A4)

Hand-written `/pairing.json` → reset → Splat connects; power-cycle → file gone, no
`ubluetooth` in the log; soft reset → kept; a MAC that isn't present → dropped after
`PAIR_CONNECT_MS`. `memprobe` figures against RESULTS-M1, now with NFC and Stages 1–4.

### B2. Pairing (A5)

Two wands, one Splat: A pairs; B refused fast; A taps again (unpair); B pairs. Third Splat
on a full wand refused. A powered off while holding → B pairs. Idle glow returns after a
Splat power cycle. Card reads use real cards (the NDEF path).

### B3. Lobby (A6)

2 wands × 1 Splat; then plus a plain wand. Simultaneous taps. Two groups running
`partytest` at once. Stop on leader and on follower.

### B4. `net` and games (A6–A7)

3 wands, 4 Splats if available. Pooled-command and remote-press latency, with 1101 in the
group and without. Dropouts: pull a follower's power, power off a Splat, kill the leader.
Play `splattag` and `relaycolor`.

### B5. Update docs

SPEC §10 and README `UNVERIFIED` list from B0–B4; retune constants if needed.

## Part C — later

- ChatBroadcast generation: SPEC §11.
- A `pw_release_all` sender in Live_Page / Box.
- Symmetric-peer games replacing the leader model.
- Port to `Bag3/Code/Wand Module/`.
- Splat Companions honoring wand pairings.
