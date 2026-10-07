# Part A progress

Branch `wands_with_splats-partA`, from `wands_with_splats`. Plan: [PLAN.md](PLAN.md). Design: [SPEC.md](SPEC.md).
Resume rule: read this file and `git log`, continue from the first unfinished step.

## Baseline (before A1)

Run from `Bag3/Code/BroadcastCode/`.

| Check | Result |
|---|---|
| `tools/devtests/compile_check.sh` | pass |
| `tools/devtests/boot_splat.py` | pass |
| `tools/devtests/boot_display.py` | fails: `code_puller` has no attribute `DEBUG_PULL` (IconDisplay tree) |
| `tools/devtests/game_menu_scan.py` | fails: `No module named 'bbox_server'` |
| `tools/devtests/wire_test.py`, `host_id_check.py` | pass |
| `tools/devtests/wire_contract.py` | exits with no output |
| `SplatCompanion/Companion/test_splat_companion.py` | aborts at `test_copies_match`: `SplatCompanion/lib/espnow_manager.py` differs from `EspnowModem/host/lib/espnow_manager.py` |

None of these are touched by Part A. The `espnow_manager.py` divergence is flagged here, not reconciled.

## Decisions that SPEC.md and PLAN.md did not settle

- **Test location.** New tests live in `tools/devtests/`, not `MockWand/`. `tools/deploy.py` uploads every
  `.py` under `MockWand/` except `tools/` and `README.md`, so a test file in `MockWand/` would be flashed
  onto the wand. PLAN names `MockWand/test_party.py`; the equivalent is `tools/devtests/test_party.py`.
- **A1 wand-side copy check.** `SplatCompanion/Companion/test_splat_companion.py` is outside the allowed
  tree and aborts at baseline, so the four-copy check is `tools/devtests/test_wand_copies.py`.

## UNVERIFIED on hardware

(accumulated per step below)

## A1. Libraries — done

- Files: `MockWand/lib/{splat_hub,splat_link,splat_api,ble_splat}.py` (byte copies), `MockWand/README.md`
  (PEER copies note), `tools/devtests/test_wand_copies.py`.
- Test: `python3 tools/devtests/test_wand_copies.py`.

## A2. Card parsing and the `unpair` tag — done

- Files: `MockWand/lib/nfc_reader.py` (`parse_splat_card`, `read_command` accepts a Splat card),
  `MockWand/lib/game_tags.py` (`unpair` in `CONTROL_TAGS`), `tools/devtests/test_wand_cards.py`.
- Test: `python3 tools/devtests/test_wand_cards.py`.
- Decision: `nfc_reader.py` and `game_tags.py` are imported at `main.py` module scope, ahead of
  `enow.init()`. The new function has no docstring, print or module constant, and the explanation is a `#`
  comment, so the only added allocation is one small function object plus the `"unpair"` string.
  Part B's `memprobe` run should confirm `idf_largest` after imports is unchanged within noise.
- Decision: `read_command()` returns the lowercase decoded text (`splat-ab42...`), as it does for every card;
  `parse_splat_card` is case-insensitive.
- `unpair` is not in `EXIT_TAGS`, so a running game ignores it; the idle loop acts on it in A5.
- UNVERIFIED on hardware: a real NDEF read of a `splat-` card. The test feeds a synthetic NTAG page image
  through `read_command()`.
## A3. Pairing store — done

- Files: `MockWand/lib/pairing.py` (`load`, `add`, `remove`, `clear`, `holds`, `exists`, `MAX_SPLATS = 2`,
  `PATH = "/pairing.json"`), `tools/devtests/test_wand_pairing_store.py`.
- Test: `python3 tools/devtests/test_wand_pairing_store.py`.
- Decisions:
  - `add()` raises `ValueError` for a malformed MAC or a full list, and is a no-op for a MAC already held.
    `remove()` of the last entry deletes the file. Callers pass the stored form (uppercase, colons).
  - A corrupt file prints `[WARN]` and reads empty; `load()` drops invalid and duplicate entries and caps at
    `MAX_SPLATS`.
  - A write or rename `OSError` propagates after the temp file is removed; the previous file stays. Callers
    (A5) report it with error feedback.
- UNVERIFIED on hardware: `os.rename` over an existing file on the C6's littlefs (`game_store.py` and
  `pull_flag.py` rely on the same behavior).
## A4. Boot integration — done

- Files: `MockWand/main.py` (`_PAIRING_PATH`, `_pair_ctl`, `_read_pairing()`, `_boot_pairing()`, the call after
  `enow.init()` and before Stage 1, `_pair_ctl.poll()` at the top of the idle loop's `try`),
  `MockWand/lib/splatpair.py` (`SplatPairing`: hub + group, `poll()`, `PAIR_CONNECT_MS`, `release()`),
  `MockWand/lib/pairing.py` (`valid()` made public), test infrastructure `tools/devtests/wandsim.py`,
  `tools/devtests/stubs/ubluetooth.py`, `stubs/micropython.py`, additive changes to `stubs/machine.py`
  (`reset_cause`, `PWRON_RESET` etc., `PWM`) and `stubs/network.py` (`WLAN.config("mac")`),
  `tools/devtests/boot_wand_pairing.py`.
- Tests: `python3 tools/devtests/boot_wand_pairing.py`. It boots the real `main.py` under the stubs on a virtual
  clock and asserts: no `ubluetooth` or Splat-module import on an unpaired boot; the call order `enow.init`,
  `BLE.active`, Stage 1; the file kept on soft, hard and watchdog resets and deleted on a power-on reset;
  `BLE().active` raising boots unpaired with the file deleted and amber in stage 0's data row; a corrupt file
  boots unpaired; a Splat that never connects is dropped after `PAIR_CONNECT_MS` with error feedback.
- `wandsim.py` is the shared harness for A5 and A6: virtual-time cooperative threads (one per wand,
  `time.sleep_ms` yields), a fake ESP-NOW bus with frame loss, lost ACKs and duplicates, fake BLE Splats.
- Decisions:
  - New `main.py` code is two small functions and two module globals; there is no docstring, print or import at
    module scope. The whole of `main.py` is still compiled ahead of `enow.init()`, so its bytecode grows by
    roughly these functions. Part B's `memprobe` figures (`idf_largest` after imports) are the check.
  - Any failure in the pairing boot path (file read, `BLE().active(True)`, imports, hub construction) boots
    unpaired, deletes the file, shows amber at stage 0 data cell 2 (the cell left of the ESP-NOW cell), prints
    the traceback and emits `{"type":"error","where":"pairing"}`.
  - A Splat that has not connected once (`link.connects == 0`) `PAIR_CONNECT_MS` after the hub is built is
    dropped. `SplatPairing.release()` removes the unit from `hub.links`, `hub.pinned`, `group.units` and
    `macs`, so unit indexes stay equal to tap order; the hub is not rebuilt. With no units left,
    `hub` and `group` are `None` and BLE stays active.
  - `SplatPairing.poll()` takes up to 8 group events per call and discards them (no press wiring at idle).
  - Non-party games do not poll the Splat links. A paired wand's Splats may disconnect during a long non-party
    game and reconnect through `SplatLink` afterwards.
- UNVERIFIED on hardware: `machine.reset_cause()` / `PWRON_RESET` behavior on the C6 (USB power, battery,
  `machine.reset()`, watchdog); `BLE().active(True)` raising on a real board; `idf_largest` and
  `connects` timing with `main.py`'s import load, NFC and the matrix running; whether a Splat stays connected
  through a non-party game with no keepalive; `os.remove` / `os.stat` of `/pairing.json` on littlefs.
- Pre-existing test status: unchanged (see Baseline).
## A5. Pair and unpair in the idle loop — done

- Files: `MockWand/lib/splatpair.py` (full controller: `on_card`, `claimed_elsewhere`, `on_msg`, `release`,
  `release_all`, identity palette, glow, `mark`, `after_game`, feedback), `MockWand/lib/pwire.py` (`send_acked`,
  `ensure_peer`, `Dedupe`, `SEND_TRIES`), `MockWand/main.py` (card routing, `_pair_card`, `_StartGameCapture`
  and `check_broadcast` hand `pw_` messages to the controller, `_launch_game` wrapper over `_run_games`,
  `show_idle` corner pixel, paired idle timing), `tools/devtests/wandboot.py` (shared boot harness, scripted NFC
  reader), `tools/devtests/boot_wand_idle.py`; `boot_wand_pairing.py` now uses `wandboot.py`.
- Tests: `python3 tools/devtests/boot_wand_idle.py` (real `main.py` idle loop, scripted cards, other simulated wands
  on the fake bus that do or do not answer `pw_who`).
  Cases: unpaired tap with no answer calls `machine.reset()` once and writes the file; a holder's `pw_held` refuses
  with no reset and no write; a holder slower than `CLAIM_WAIT_MS` is not heard; a full wand refuses without
  broadcasting; a held card releases that Splat only; the last held card leaves an unpaired wand with BLE still
  active; the `unpair` card releases everything; `pw_release_all` in idle; `pw_who` answered for held MACs only and
  never by an unpaired wand; identity glow, success flash and tone, corner pixel; reconnect refreshes the glow
  without a second flash; in-game `pw_who` consumed and `pw_release_all` ending the game as a `stop`;
  `_launch_game` restoring the idle Splat state.
- Decisions:
  - Identity palette is the six non-off `splat_api.COLOR_RGB` names (SPEC allows 6-8). Wand colors for the names:
    red, green, blue, purple -> `MAGENTA` (leds `PURPLE` reads as blue), yellow -> `AMBER`, white. Corner pixel is 4.
  - Idle glow is `COLOR_RGB[identity]` scaled by `GLOW_SCALE` (0.15), written with `link.setLEDsON`, because
    `SplatAPI.color()` has no brightness.
  - Paired-wand idle timing: NFC detect timeout 100 ms (`PAIRED_DETECT_MS`) and idle sleep 20 ms
    (`PAIRED_IDLE_SLEEP_MS`) instead of 250 ms / 200 ms. The unmodified idle iteration is about 450 ms, longer than
    `CLAIM_WAIT_MS` (300), so a holder would miss most claim checks. Unpaired wands are unchanged.
  - The `pw_who` responder adds the asker as a peer for the unicast reply and removes it afterwards unless it was
    already a peer. The reply uses `pwire.send_acked` (`SEND_TRIES`).
  - `pw_who` and `pw_release_all` are handled in `check_broadcast` (idle, sleeping, programming run mode) and in
    `_StartGameCapture.poll` (any running game). In a game, `pw_who` is hidden from the game and `pw_release_all`
    is returned as `stop` after releasing, which is how SPEC's "handled as a game exit" is implemented.
  - The claim check consumes other messages during its 300 ms window; `pw_who` from others is answered, anything
    else (for example a `stop` broadcast in that window) is dropped.
  - A claim check with ESP-NOW down is refused (error feedback): it cannot be made.
  - `pw_find` is not answered in the idle loop. The lobby loop (A6) answers it; a wand in the idle loop has no
    open lobby.
  - The first READY of each Splat in a boot flashes the identity color and plays the success tone, including after
    a reset that was not a new pairing.
  - A write failure from `pairing.add()` gives error feedback and no reset.
- UNVERIFIED on hardware: claim-check latency with the real idle loop; the 100 ms NFC detect timeout's effect on card
  reads; `show_idle` and the corner pixel next to the idle ring; flash, tone and glow appearance on wand and Splat;
  palette distinctness on the matrix and a Splat; `unpair` and `splat-` cards read from real NDEF; peer add/remove
  of an asker while ESP-NOW is busy.
## A6. `party.py` — done

- Files: `MockWand/lib/party.py` (`enter`, `Net`, `run_lobby`, lobby display, `_PoolSplat`), `MockWand/lib/pwire.py`
  (A5), `MockWand/lib/splatpair.py` (`poll()` returns the Splat events), `MockWand/main.py` (`_splat_limits`,
  `_enter_party`, `_run_games` lobby flow with `net.close()` in a `finally`, `_start_play` with 8 parameters and
  the 8, 7, 6 fallback), `tools/devtests/test_party.py`, `tools/devtests/boot_wand_party.py`,
  `tools/devtests/wandboot.py` (game files, fake button, MAC wiring), `tools/devtests/wandsim.py`.
- Tests:
  - `python3 tools/devtests/test_party.py`: simulated wands on a fake ESP-NOW bus with fake BLE Splats. Cases: join,
    lobby count and display, button start at SPLATS_MIN, auto-start at SPLATS_MAX, full lobby refused, plain wand
    counting 0, simultaneous leaders (lowest MAC wins), a follower of a yielding leader re-finding, two groups on the
    same slug with different ids and no cross-talk, stop card on a follower and on the leader, pooled commands to the
    owner, remote and local presses, `splat_lost` / `splat_back` (follower's and leader's own), `wand_lost` /
    `wand_back`, `leader_lost` once, a follower returning from `play()` giving `wand_lost` at once, a lost ACK
    resent with the same `q` and applied once, duplicated frames, `SEND_TRIES` exhaustion, a join surviving lost
    frames, 25% frame and ACK loss, ESP-NOW `stop` / `start_game`, a leader that never answers a join, another game's
    lobby not joined, a leader holding enough Splats starting alone.
  - `python3 tools/devtests/boot_wand_party.py`: the real `main.py` leading and following a party game; 6/7/8
    parameter `play()`; invalid `SPLATS_*` declarations as load failures; `net.close()` after a game that raises;
    a lobby cancelled by ESP-NOW stop; a `SPLATS_MIN` game whose `play()` has no `net` parameter.
- Decisions the SPEC did not settle:
  - Identity color in `net.wands` is the palette name (`"turngreen"`), usable directly in `splat(i).color()`.
  - `pw_joined` carries `first` (this wand's first pool index) and `wands` (the roster so far); the final roster is
    in `pw_start`. Followers do not use the interim roster.
  - Followers send `pw_hb` from joining on, and the leader removes a lobby follower silent for `WAND_LOST_MS`.
  - A leader answers `pw_find` for its slug with an immediate broadcast `pw_lobby`, in addition to the 1 s one.
  - Pool order is join order, each wand's Splats contiguous in local order; the leader's come first.
  - `pw_end` carries an optional `r`: `"yield"` (the lobby's leader joined a lower-MAC lobby; followers look again),
    `"full"` (the join would exceed SPLATS_MAX). `enter()` re-finds up to `REFIND_MAX` (2) times after a yield or a
    join that went unanswered, and leads if no lobby answers.
  - A wand that receives a `pw_join` for a lobby it no longer leads answers `pw_end` with `r: "yield"`.
  - `net.poll()` returns `("end",)` repeatedly once the game has ended, and also on an ESP-NOW `stop`,
    `start_game` or `pw_release_all` (SPEC lists `end` for followers only; the leader gets it too). A `pw_end`
    that arrives in the same loop pass as `pw_start` gives `("end",)` from the first `poll()`.
  - `net.send()` refuses a body over `MSG_MAX_BYTES` (200) with `ValueError`; ESP-NOW's frame limit is 250.
  - `pw_leave` during a game gives the leader `wand_lost` at once.
  - `splat_lost` / `splat_back` for a follower's Splat come from the `l` bitmask in its `pw_hb`, so they can lag by
    up to `HEARTBEAT_MS`; the baseline is "all READY", so a Splat not READY at game start is reported lost.
  - A party game whose `play()` has no `net` parameter still goes through its lobby and then runs without `net`.
  - `pw_start` that cannot be delivered to a follower (3 tries) is not retried; that follower sees no game and the
    leader reports it `wand_lost` after `WAND_LOST_MS`.
  - Lobby feedback on `enter()` returning `None`: neutral stop tone for the wand's own stop card or an ESP-NOW stop,
    red X and reject tone otherwise.
  - Test harness: `/games` at the filesystem root was created once by the first version of `wandboot.py` (an empty
    directory in the sandbox, not in the repo); the harness now keeps those paths in its temp directory.
- UNVERIFIED on hardware: everything about ESP-NOW latency and the slow-send board (`pw_cmd` round trips, lobby
  timing with `FIND_WAIT_MS` 500, `JOIN_WAIT_MS` 1000), BLE and ESP-NOW coexistence on one C6 radio while a
  party game runs, `WAND_LOST_MS` against real packet loss, peer table use with 20 peers, `read_ndef_text`
  stop-card reads in the lobby loop every 8 iterations (`LOBBY_NFC_MS` 40), lobby display legibility, Splat write
  pacing (50 ms per command) inside `net.poll()` at game rate.
## A7. Games — not done
## A8. Docs — not done
