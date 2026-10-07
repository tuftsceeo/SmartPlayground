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

## A2. Card parsing and the `unpair` tag — not done
## A3. Pairing store — not done
## A4. Boot integration — not done
## A5. Pair and unpair in the idle loop — not done
## A6. `party.py` — not done
## A7. Games — not done
## A8. Docs — not done
