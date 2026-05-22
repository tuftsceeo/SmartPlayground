# Branch Cleanup Plan — Wand Module Simplification

## Objectives

Clean up the wand codebase by removing currently-unused gesture recognition and direct-Splat BLE control while preserving accelerometer support, Splat Companion device code, and all working game functionality. Improvements should make the code easier to read, maintain, and debug for a mixed-experience team. This is a conservative cleanup with light DRY-up. We are not making changes that could break working functionality.

### What stays operational

- Wand programming engine (trigger → action chains, AND/THEN combinators).
- Accelerometer (`LIS2DW12`) and shake detection. The hardware initialization sequence is preserved in a defensive state for future code that may soft-reset the chip.
- All three games: Color Quest, Freeze Dance, Jump In.
- Splat Companion device code (`Splat Companion/main.py`, `Splat Companion/ble_splat.py`) for a future release.
- All Programming Station and Scoreboard functionality.

### What gets removed from the wand

- Gesture recognition pipeline (`G:` NFC tags, `gesture:<n>` triggers, `GestureEngine`).
- Direct wand-to-Splat BLE control (`SP:` triggers, `DirectSplatController`, `sp_loop`).
- Splat Companion routing from the wand (`SC:` triggers, `splat_config` ESP-NOW unicast).

---

## Preflight Verification

Before any deletion, confirm the following with grep across the wand branch. These are expected to come back empty; if any return hits, the relevant import-removal step must be added back into the modifications list.

```
grep -rn "from sp_loop" "Wand Module/"
grep -rn "from ble_splat_ctrl" "Wand Module/"
grep -rn "import sp_loop" "Wand Module/"
grep -rn "import ble_splat_ctrl" "Wand Module/"
grep -rn "run_sp_loop" "Wand Module/"
```

The expectation, based on the current state of `Wand Module/main.py`, is that none of these are imported or called. If verification passes, the archive steps below are pure removals with no remaining call sites to fix.

---

## Archive

Two destinations are used because gesture code and Splat Companion code are different concerns and should not be mixed in the archive.

### Move to `legacy/` (new top-level folder)

These are unrelated to the Splat Companion device and are archived for general historical reference.

| Source                  | Destination                  |
|-------------------------|------------------------------|
| `lib/gesture.py`        | `legacy/gesture.py`          |
| `lib/gesture_engine.py` | `legacy/gesture_engine.py`   |

After copying, delete the originals from `lib/`. Because `lib/` is deployed identically to every device, leaving stray copies behind would keep `import gesture_engine` working on the wand and continue shipping the modules to all other devices.

Update each archived file's header docstring with a one-line note that it is archived January 2026 wand-module code, originally located at `lib/`, and is not currently used in production.

### Move to `Splat Companion/` with `legacy_jan26_wand_` prefix

These are wand-side files that drove direct BLE control of Splat plushies. They are colocated with the active Splat Companion device code so anyone resurrecting Splat support has both halves in one place.

| Source                          | Destination                                              |
|---------------------------------|----------------------------------------------------------|
| `Wand Module/ble_splat_ctrl.py` | `Splat Companion/legacy_jan26_wand_ble_splat_ctrl.py`    |
| `Wand Module/sp_loop.py`        | `Splat Companion/legacy_jan26_wand_sp_loop.py`           |

Update each file's header docstring with a one-line note that it is archived January 2026 wand-side code, originally located at `Wand Module/`, and is not currently used in production.

---

## Modify: `Wand Module/main.py`

### Imports to remove

- `from gesture_engine import GestureEngine, CONFIDENCE_THRESHOLD`

Per the preflight check, `ble_splat_ctrl` and `sp_loop` are not expected to be imported here. If verification finds otherwise, also remove those import lines.

### Module-level helpers to remove

These are the actual helper names defined in `main.py`. (Note: the original plan listed `is_sp_trigger` and `parse_sp_mac`, but those live in `ble_splat_ctrl.py`. The helpers in `main.py` are named with `sc`, not `sp`.)

- `is_sc_trigger(name)` function.
- `parse_sc_mac(name)` function.
- `is_gesture_trigger(name)` function.

### Boot sequence changes

- Remove the entire `# Gesture engine (touches the same LIS2DW12 chip — soft-resets it!)` block, including the `from neopixel import NeoPixel as NP` import, the `ge_np` NeoPixel handle, the `GestureEngine` instantiation, and the `ge_ok` tracking variable.
- Remove the conditional `if ge_ok: reader.gesture_engine = ge` assignment.
- **Keep** the deferred `accel.enable_wake_int1(...)` call. The reason the call is deferred from the basic accel init block is no longer present once `GestureEngine` is gone, but the defensive ordering is cheap insurance against future code (including teacher-authored chatbot code, which can extend the wand via the `jumpin` hook) that performs a soft reset on the `LIS2DW12`. Update the explanatory comment above the deferred call to reflect this. New comment text:

```python
# Accelerometer wake-up interrupt is enabled here, separately from the basic
# accel init above, because any code that performs a soft-reset on the
# LIS2DW12 (writing 0x40 to CTRL2) will clear CTRL4_INT1, CTRL7, and
# WAKE_UP_THS. If those are configured before such a reset, the shake
# trigger will silently stop working (INT1 stays low forever).
#
# No code currently in the wand performs that reset, but teacher-authored
# code (loaded via the jumpin hook) might in the future. Keeping wake-up
# enable as a final, separate step makes future-added soft-resets safe by
# default.
```

### Event dispatch changes

In the main idle/programming loop:

- Remove the `is_sc_cmd` flag computation and the `if cmd.startswith("sc:") and len(cmd) > 3:` block that uppercases the MAC suffix.
- In the `# ── TRIGGER ──` branch, simplify the condition from `if cmd in FIXED_TRIGGERS or is_gesture_trigger(cmd) or is_sc_cmd:` to `if cmd in FIXED_TRIGGERS:`.
- Remove the inner `if is_gesture_trigger(cmd): ...` block that loads the gesture template into the engine.
- Remove all `if ge: ge.clear_loaded()` calls. These appear in at least two places (post-stop teardown and broadcast-driven reset).

In `run_event_loop()`:

- Remove the `ge_ref` parameter from the function signature.
- Update the single call site in `main()` from `run_event_loop(reader, rules, runner, accel, ge, mgr, batt)` to `run_event_loop(reader, rules, runner, accel, mgr, batt)`.
- Remove the local variables `gesture_last_fire`, `g_map`, `has_g`.
- Remove the entire `if fired is None and ge_ref and has_g and ge_ref.loaded_gestures:` block that polls motion and runs `capture_and_classify()`.
- In the startup banner loop, simplify `if not is_sc_trigger(trig) and len(rules[trig]) > 0:` to `if len(rules[trig]) > 0:`.

### `print_rules()` cleanup

Once gesture and SC handling are gone, the function reduces to a single loop over `TRIGGER_ORDER`. Remove:

- Both `for trig in sorted(rules.keys()): if is_gesture_trigger(trig): ...` blocks.
- Both `for trig in sorted(rules.keys()): if is_sc_trigger(trig): ...` blocks.
- The two trailing standalone `if is_gesture_trigger(editing) ...` and `if is_sc_trigger(editing) ...` editing-state checks.

### Docstring rewrite

Replace the module docstring with the following. Note that `jumpin` was missing from the Controls list in the original; it is now included.

```python
"""
Wand Module — NFC Multi-Trigger Event Engine
==============================================
Board: Seeed XIAO ESP32-C6
Requires hubtype.txt containing: wand

Triggers: buttondown, buttonup, shake
Actions:  playnote, notea-g, turnred/green/blue/purple/yellow/white/off,
          cat, chicken, cow, dog, pig, duck, elephant, horse, goat
Combinators: and, then
Controls: start, stop, colorquest, freezedance, jumpin
Utility: battery
"""
```

### Add: game-extension comment block

Adjacent to the `CONTROLS` set declaration, add a comment block explaining the pattern for wiring up a new game. This is the second of two places (the other is the `Wand Module/readme.md`) where this is documented. Suggested content:

```python
# ─────────────────────────────────────────────
# ADDING A NEW GAME
# ─────────────────────────────────────────────
# Each game is a separate module in this folder that exposes a single
# `play(...)` entry point. To add a new game named "yourgame":
#
#   1. Create `Wand Module/yourgame.py` exposing
#      `def play(nfc, leds, buz, accel, ...): ...` returning when the
#      "stop" NFC tag is scanned.
#   2. Add the line `from yourgame import play as play_yourgame` near
#      the existing `play_jumpin` import at the top of this file.
#   3. Add the tag name `"yourgame"` to the CONTROLS set below.
#   4. In the main control-dispatch block (search for the existing
#      `cmd == "jumpin"` branch), add a parallel branch that calls
#      `play_yourgame(...)` with the hardware refs the game needs.
#   5. The teacher prints an NFC tag whose NDEF text payload is
#      `yourgame`. Tapping it from idle enters the game; tapping the
#      `stop` tag from within the game returns to programming mode.
#
# See `jumpin.py` for the simplest possible example and
# `freeze_dance.py` for a more complete game (ESP-NOW messaging,
# accelerometer-driven state, multi-role logic).
```

---

## Modify: `lib/nfc_reader.py`

### Constants to remove

- `GESTURE_MARKER = b'G:'`
- `SC_PREFIX = "sc:"`

### `read_command()` cleanup

- Remove the entire `# ── Check for gesture tag ──` block (the `if (self.gesture_engine and sak in (0x08, 0x18) and len(ndef_data) >= 16 and ndef_data[0:2] == GESTURE_MARKER):` branch and everything inside it).
- Remove the entire `# ── Check for SC tag ──` block (the `if text and text.startswith(SC_PREFIX) and len(text) > len(SC_PREFIX):` branch).
- Remove the `self.gesture_engine` instance attribute and any initialization of it in `__init__`.

### `_find_in_raw()` cleanup

This is the brute-force raw-bytes fallback at the bottom of the recognition pipeline. It contains a dedicated SC-prefix detection block that is easy to miss when grepping for `SC_PREFIX`. Remove:

- The `# Check for SC prefix in raw data too` block, including the `sc_idx = raw_str.find(SC_PREFIX)` line and the MAC-validation logic (the 17-character extract, the colon-separated parts check, and the early return). After removal, `_find_in_raw()` consists only of the closing `for cmd in self.commands:` loop.

### Docstring rewrite

Replace the module docstring with:

```python
"""
NFC Reader — Tag scanning and command extraction
==================================================
Wraps the PN532 driver with NDEF text decoding and a raw-bytes
fallback for matching tag content against a set of known commands.

Supports two-phase reading: detect tag presence first, then read
data. This lets the caller animate during the slow read phase.

Supported tag types:
  • MIFARE Classic 1K (SAK 0x08 / 0x18)  — auth + block read (sectors 1-2)
  • NTAG / MIFARE Ultralight             — unauthenticated page read (4-19)

Usage:
    # For game code that only needs the text and UID of any tag:
    from nfc_reader import read_ndef_text
    text, uid = read_ndef_text(nfc)

    # For the main command-dispatch loop:
    from nfc_reader import NfcReader
    reader = NfcReader(nfc, commands)
    cmd, uid = reader.read_command(
        on_detect=my_start_fn,
        on_progress=my_frame_fn,
        on_complete=my_done_fn,
    )
"""
```

---

## Header / Docstring Review (All Wand Module Files)

Each file in `Wand Module/` should have its top-of-file docstring reviewed for accuracy and consistency after the changes above. The goal is to ensure no leftover references to gesture or Splat features remain anywhere a developer might read first.

| File                          | Action                                                                                 |
|-------------------------------|----------------------------------------------------------------------------------------|
| `Wand Module/main.py`         | Replace docstring per the rewrite shown above.                                         |
| `Wand Module/jumpin.py`       | Verify docstring matches current behavior (button-press LED blink). No expected changes. |
| `Wand Module/color_quest.py`  | Verify no references to gesture or Splat. No expected changes.                         |
| `Wand Module/freeze_dance.py` | Verify no references to gesture or Splat. No expected changes.                         |
| `Wand Module/target.py`       | Verify docstring is current.                                                           |
| `lib/nfc_reader.py`           | Replace docstring per the rewrite shown above.                                         |

For each "verify" entry, the developer doing the work should read the docstring against the actual code and either confirm consistency or note specific fixes inline in the PR.

---

## Update: `Wand Module/readme.md`

The readme should be updated to:

1. Remove any mention of `gesture:<n>` and `SC:<MAC>` triggers from the trigger/action tables.
2. Remove any references to the Splat Companion as a wand interaction target.
3. Confirm the Controls list includes `jumpin` alongside `start`, `stop`, `colorquest`, `freezedance`.
4. Add a new section titled "Adding a New Game" that contains a longer-form version of the comment block being added to `main.py`. Suggested structure for that section:

   - One-paragraph overview of the game module pattern (single `play()` entry point, scoped hardware references, returns on `stop` tag).
   - Numbered step-by-step list (the same five steps shown in the `main.py` comment, expanded with rationale and example signatures).
   - A short reference table of existing games (file, complexity, what hardware it uses) so a developer can pick the best template.
   - A note about the chatbot-authored teacher code path that uses `jumpin.py` as a hook, so future maintainers know not to gratuitously refactor `jumpin.py` away.

---

## Optional DRY-up Refactors

Each of the following is flagged separately. Adopt or skip each independently. None are required for the core cleanup to succeed. Recommended order is A → B → C if all three are adopted, since each builds on a cleaner starting point.

### A. `print_rules()` simplification

**Risk:** Very low.
**Value:** Medium.

After the gesture and SC removals, `print_rules()` becomes a single iteration over `TRIGGER_ORDER` plus the trailing "empty" check. The function can be tightened from roughly thirty lines to ten or so by removing the now-dead `for trig in sorted(rules.keys()):` scaffolding and the dual standalone editing-state branches. Most of this happens automatically when the SC/gesture blocks are deleted; the remaining cleanup is collapsing whitespace and verifying the empty-rules and editing-state paths still print the correct output. Recommended.

### B. Boot sequence extraction

**Risk:** Low.
**Value:** High for readability.

The current `main()` function in `Wand Module/main.py` mixes hardware initialization, sensor calibration, peripheral setup, and the idle/programming loop in one long body. Extract the boot steps into named helper functions. Suggested split:

- `_init_brightness(i2c)` — wraps the OPT3002 light sensor calibration block.
- `_init_battery(i2c, leds)` — wraps the MAX17048 read and `leds.boot_battery(...)` call. Returns `(batt, last_soc)`.
- `_init_nfc(i2c)` — wraps the PN532 begin/print and the `NfcReader` construction. Returns `(nfc, reader)`.
- `_init_accel(i2c)` — wraps the basic `LIS2DW12` init and returns `(accel, accel_ok)`. The deferred `enable_wake_int1` call stays in `main()` so the future-proof comment block stays adjacent to the line it justifies.

Each helper has a single responsibility, returns the handles `main()` needs, and prints its own status line. The `main()` body shrinks to a short, readable sequence of named init calls followed by the existing idle/programming loop. Recommended.

### C. Scan-feedback callback grouping

**Risk:** Low.
**Value:** Low to medium.

The three module-level callback functions `on_tag_detect`, `on_scan_progress`, and `on_scan_complete` are tightly coupled (they all act on `leds`, `buz`, and `motor`) and currently float as bare functions. Grouping them into a small class `ScanFeedback` whose constructor takes `(leds, buz, motor)` and whose methods are `on_detect`, `on_progress`, `on_complete` would consolidate the visual/haptic feedback policy in one named place. `read_with_feedback(reader)` would become a one-line method on that class. Optional; recommended only if the team wants more class-based structure as a stylistic goal.

### D. Tag-command dispatch (NOT recommended for this pass)

The large if/elif chain in the idle/programming loop that classifies a scanned `cmd` into utility / control / combinator / trigger / action could be refactored into a dispatch table mapping command categories to handler methods. This would be a larger structural change with non-trivial test surface, and a single bug in the new dispatch table would silently break programming. Listed here for completeness; recommend deferring until a future cleanup pass that has time for thorough on-device testing.

---

## No Change (Reaffirmed)

| File                          | Reason                                                                                       |
|-------------------------------|----------------------------------------------------------------------------------------------|
| `Wand Module/jumpin.py`       | Teacher-extensible game hook. Docstring review only.                                         |
| `Wand Module/color_quest.py`  | Unaffected. Imports only `read_ndef_text`, `_decode_ndef_text`, `COMMON_KEYS` from `nfc_reader`. |
| `Wand Module/freeze_dance.py` | Unaffected. Same import surface as `color_quest.py`.                                         |
| `Wand Module/target.py`       | Scoreboard MAC config. Unaffected.                                                           |
| `Splat Companion/main.py`     | Active device code preserved for future release.                                             |
| `Splat Companion/ble_splat.py`| Active device code preserved for future release.                                             |
| `Stations/` (both)            | Unaffected.                                                                                  |
| `lib/espnow_manager.py`       | Keeps `send_splat_config()` and the `splat_config` message classification, so the Splat Companion device continues to work in future releases. |

---

## Verification After Cleanup

The following should all be true on the cleaned branch. Each is a fast check.

1. `import main` succeeds on the wand under MicroPython without `ImportError`.
2. `grep -rn "gesture" "Wand Module/" "lib/"` returns no hits in active code (only the rewritten docstrings and any preserved comments should reference history, if at all).
3. `grep -rn "splat" "Wand Module/" "lib/"` returns no hits in active code.
4. `grep -rn "SC:" "Wand Module/" "lib/"` returns no hits in active code.
5. `grep -rn "GestureEngine\|CONFIDENCE_THRESHOLD\|GESTURE_MARKER\|SC_PREFIX" "Wand Module/" "lib/"` returns no hits.
6. Tapping a `buttondown` trigger tag, an action tag, and the `start` tag still cycles the wand into running mode and fires the action on button press.
7. Tapping the `shake` trigger and shaking the wand still fires the configured action chain (validates the accel wake-up survived the cleanup).
8. Tapping `colorquest`, `freezedance`, and `jumpin` tags each enters the corresponding game; tapping `stop` inside each game returns to programming mode.
9. The `battery` tag still shows battery level from idle and from running modes.
10. The Programming Station's `stop` broadcast still resets the wand from idle, programming, and running modes.
