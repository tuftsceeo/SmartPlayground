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
## A5. Pair and unpair in the idle loop — not done
## A6. `party.py` — not done
## A7. Games — not done
## A8. Docs — not done
