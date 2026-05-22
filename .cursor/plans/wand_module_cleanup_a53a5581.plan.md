---
name: Wand Module Cleanup
overview: Remove unused gesture recognition and direct-Splat BLE control from the wand codebase, archive the code for historical reference, and update documentation. This is a conservative cleanup preserving all working functionality.
todos:
    - id: archive-gesture
      content: Create legacy/ folder and move gesture.py + gesture_engine.py with archive headers
      status: completed
    - id: archive-splat
      content: Move ble_splat_ctrl.py + sp_loop.py to Splat Companion/ with legacy_ prefix and archive headers
      status: completed
    - id: modify-main
      content: Remove gesture/SC code from Wand Module/main.py (imports, helpers, boot sequence, event loop, print_rules)
      status: completed
    - id: modify-nfc
      content: Remove gesture/SC code from lib/nfc_reader.py (constants, gesture_engine attribute, detection blocks)
      status: completed
    - id: update-docstrings
      content: Update docstrings in main.py and nfc_reader.py per plan specifications
      status: completed
    - id: update-readme
      content: Update Wand Module/readme.md - remove gesture/SC, add jumpin, add 'Adding a New Game' section
      status: completed
    - id: optional-dryup
      content: "Optional: Apply print_rules simplification and boot sequence extraction refactors"
      status: completed
    - id: verify
      content: Run verification grep commands and confirm no active gesture/splat references remain
      status: completed
isProject: false
---

# Wand Module Simplification — Branch Cleanup

## Summary

Remove unused gesture recognition (`G:` tags, `GestureEngine`) and direct-Splat BLE control (`SP:` triggers, `SC:` triggers) from the wand while preserving accelerometer support, Splat Companion device code, and all three games.

**Path Note**: All paths are under `Bag2/Code/` (e.g., `Bag2/Code/Wand Module/main.py`).

---

## Phase 1: Preflight Verification (Confirmed)

Verified via grep — no imports of `sp_loop` or `ble_splat_ctrl` exist in `Wand Module/main.py`. Safe to proceed with pure removals.

---

## Phase 2: Archive Files

### Create `Bag2/Code/legacy/` folder and move gesture files:

| Source                            | Destination                          |
| --------------------------------- | ------------------------------------ |
| `Bag2/Code/lib/gesture.py`        | `Bag2/Code/legacy/gesture.py`        |
| `Bag2/Code/lib/gesture_engine.py` | `Bag2/Code/legacy/gesture_engine.py` |

Add archive header noting: _"Archived January 2026 wand-module code, originally at lib/, not currently used in production."_

### Move wand-side Splat files to Splat Companion folder:

| Source                                    | Destination                                                     |
| ----------------------------------------- | --------------------------------------------------------------- |
| `Bag2/Code/Wand Module/ble_splat_ctrl.py` | `Bag2/Code/Splat Companion/legacy_jan26_wand_ble_splat_ctrl.py` |
| `Bag2/Code/Wand Module/sp_loop.py`        | `Bag2/Code/Splat Companion/legacy_jan26_wand_sp_loop.py`        |

Add archive header noting: _"Archived January 2026 wand-side code, originally at Wand Module/, not currently used in production."_

---

## Phase 3: Modify `Bag2/Code/Wand Module/main.py`

### 3.1 Remove imports (line 24):

```python
from gesture_engine import GestureEngine, CONFIDENCE_THRESHOLD
```

### 3.2 Remove helper functions (lines 79-88):

- `is_sc_trigger(name)`
- `parse_sc_mac(name)`
- `is_gesture_trigger(name)`

### 3.3 Remove gesture engine boot sequence (lines 340-362):

- The `# Gesture engine` block with `GestureEngine` instantiation
- The `if ge_ok: reader.gesture_engine = ge` assignment
- Keep the deferred `accel.enable_wake_int1()` call but update its comment

### 3.4 Update `run_event_loop()`:

- Remove `ge_ref` parameter from signature (line 188)
- Update call site (line 565) to remove `ge` argument
- Remove gesture-related variables: `gesture_last_fire`, `g_map`, `has_g`
- Remove gesture polling block (lines 229-238)
- Simplify startup banner condition (line 205)

### 3.5 Simplify idle/programming loop:

- Remove `is_sc_cmd` handling (lines 500-503)
- Simplify trigger condition from `if cmd in FIXED_TRIGGERS or is_gesture_trigger(cmd) or is_sc_cmd:` to `if cmd in FIXED_TRIGGERS:` (line 586)
- Remove inner gesture loading block (lines 588-593)
- Remove all `if ge: ge.clear_loaded()` calls (lines 401, 464, 548, 568)

### 3.6 Simplify `print_rules()`:

- Remove gesture trigger loops (lines 127-138)
- Remove SC trigger loops (lines 140-150)

### 3.7 Update docstring:

Replace module docstring with version listing: `buttondown`, `buttonup`, `shake` triggers only; add `jumpin` to Controls list.

### 3.8 Add game-extension comment block:

Adjacent to `CONTROLS` set, add documentation for adding new games.

---

## Phase 4: Modify `Bag2/Code/lib/nfc_reader.py`

### 4.1 Remove constants (lines 51-52):

```python
GESTURE_MARKER = b'G:'
SC_PREFIX = "sc:"
```

### 4.2 Remove `gesture_engine` attribute (line 163)

### 4.3 Remove gesture tag block in `read_command()` (lines 213-229)

### 4.4 Remove SC tag block in `read_command()` (lines 234-240)

### 4.5 Remove SC prefix detection in `_find_in_raw()` (lines 312-323)

### 4.6 Update docstring:

Remove gesture and SC references from module docstring.

---

## Phase 5: Update `Bag2/Code/Wand Module/readme.md`

- Remove `gesture:<n>` and `SC:<MAC>` from trigger tables
- Add `jumpin` to Controls list
- Add "Adding a New Game" section with step-by-step instructions
- Reference `jumpin.py` as the simplest game template

---

## Phase 6: Header/Docstring Review

Verify these files have no leftover gesture/Splat references in docstrings:

- `Bag2/Code/Wand Module/jumpin.py`
- `Bag2/Code/Wand Module/color_quest.py`
- `Bag2/Code/Wand Module/freeze_dance.py`
- `Bag2/Code/Wand Module/target.py`

---

## Phase 7: Optional DRY-up Refactors

**A. `print_rules()` simplification** (Recommended) — After removals, collapse to single `TRIGGER_ORDER` loop.

**B. Boot sequence extraction** (Recommended) — Extract init steps into `_init_brightness()`, `_init_battery()`, `_init_nfc()`, `_init_accel()` helpers.

**C. Scan-feedback callback grouping** (Optional) — Group `on_tag_detect`, `on_scan_progress`, `on_scan_complete` into a `ScanFeedback` class.

**D. Tag-command dispatch** (NOT recommended this pass) — Defer dispatch table refactor.

---

## Phase 8: Verification

After cleanup, verify:

1. `import main` succeeds on wand
2. `grep -rn "gesture" "Wand Module/" "lib/"` returns no active code hits
3. `grep -rn "splat" "Wand Module/" "lib/"` returns no active code hits
4. `grep -rn "GestureEngine|CONFIDENCE_THRESHOLD|GESTURE_MARKER|SC_PREFIX"` returns no hits
5. All three games (`colorquest`, `freezedance`, `jumpin`) work
6. `buttondown`, `buttonup`, `shake` triggers work
7. `battery` utility works
8. Programming Station broadcast `stop` resets wand

---

## Files Changed Summary

| Action       | File                                                                                    |
| ------------ | --------------------------------------------------------------------------------------- |
| Create       | `Bag2/Code/legacy/` folder                                                              |
| Move+Archive | `lib/gesture.py` → `legacy/gesture.py`                                                  |
| Move+Archive | `lib/gesture_engine.py` → `legacy/gesture_engine.py`                                    |
| Move+Archive | `Wand Module/ble_splat_ctrl.py` → `Splat Companion/legacy_jan26_wand_ble_splat_ctrl.py` |
| Move+Archive | `Wand Module/sp_loop.py` → `Splat Companion/legacy_jan26_wand_sp_loop.py`               |
| Modify       | `Bag2/Code/Wand Module/main.py`                                                         |
| Modify       | `Bag2/Code/lib/nfc_reader.py`                                                           |
| Modify       | `Bag2/Code/Wand Module/readme.md`                                                       |

## No Changes (Preserved)

- `Wand Module/jumpin.py`, `color_quest.py`, `freeze_dance.py`, `target.py`
- `Splat Companion/main.py`, `ble_splat.py`
- `Stations/` (both)
- `lib/espnow_manager.py` (keeps `send_splat_config()` for future Splat Companion)
