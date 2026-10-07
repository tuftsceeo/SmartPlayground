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
## A4. Boot integration — not done
## A5. Pair and unpair in the idle loop — not done
## A6. `party.py` — not done
## A7. Games — not done
## A8. Docs — not done
