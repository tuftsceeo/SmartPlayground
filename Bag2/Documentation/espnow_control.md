# Wand ESP-NOW Teacher Control: System Comparison and Implementation Plan

## Purpose

This document does two things:

1. Documents how the two hardware iterations of the Smart Playground modules differ in how a "teacher's device" controls modes and games over ESP-NOW.
2. Lays out an implementation plan, structured for parallel Cursor subagents, to add teacher-controlled game dispatch to the wand firmware using the existing `lib/espnow_manager.py`.

The scope of the plan is the wand firmware only. Backwards compatibility with the plushie/box protocol is not a requirement. A future iteration of the webapp and hub compatible with the new wand-side protocol is out of scope for this plan.

---

## Part 1: System Comparison

### Bag1 — Plushies and Boxes

Bag1 modules (plushie, box, button, splats, controller) are passive receivers of teacher commands. They have no NFC reader and depend on the teacher's device to select the active game.

**ESP-NOW library:** `Plushie_Module/utilities/now.py`. Thin wrapper around the MicroPython `espnow` module providing `connect`, `publish`, and an IRQ-driven callback. Messages are bytes.

**Application protocol:** Line-of-JSON envelopes of the form `{"topic": "/<name>", "value": <payload>}`.

The recognized topics on the receiving side (`Plushie_Module/main.py`, callback `execute_queue`) are:

| Topic       | Value shape                | Meaning                                                              |
| ----------- | -------------------------- | -------------------------------------------------------------------- |
| `/game`     | `(N, base64_controller_mac)` | Start game `N` from the `games` tuple; `N == -1` is "stop all"     |
| `/gem`      | base64 mac                 | Carries the hidden-module MAC for the Hot/Cold game                  |
| `/ping`     | `1`                        | Liveness/RSSI probe; receiver caches RSSI                            |
| `/notify`   | `1` (or other)             | Soft poke; some games re-fire on `/notify`                           |
| `/battery`  | int                        | Reported back by modules during the Rainbow/battery game             |
| `/color`    | int                        | Module color                                                         |
| `/nfc`      | any                        | Routed from local NFC events when present                            |
| `/slide`    | any                        | Slide score traffic                                                  |
| `/reset`    | n/a (derived)              | Soft reset marker emitted by `execute_queue` on game `0` re-start   |

**Game model:** Games are `asyncio` task classes (e.g., `Notes`, `Shake`, `Jump`, `Hot_cold`, `Rainbow`, `Hibernate`, etc.) listed in `config.py`. They share a `topic`/`value`/`running` state with the main `Tool` class and a uniform `start` / `async loop` / `close` shape.

**Teacher devices in Bag1:**

- **WebApp + hub.** The hub is an ESP32 that runs `Live_Page/WebApp/hubCode/main.py` (subclasses `controllers/controller.py`). The webapp sends line-delimited JSON commands over USB Serial; the hub translates each into `n.publish(json.dumps({'topic':'/game', 'value':(N, b64_mac)}))` via its `choose()` method. Commands are mapped by `GAME_MAP` (matched 1:1 with the plushie's `games` list).
- **Standalone controllers.** `controllers/controller.py` and `controllers/controller_ws.py` run on dedicated ESP32 devices with displays and buttons. They construct and broadcast the same `{topic, value}` messages directly to all modules.
- **Either device can also broadcast.** `/ping`, `/notify`, and game-stop (`{topic: '/game', value: -1}`) using `shutdown()` / `ping()` / `notify()` helpers.

**Receiver execution flow on a plushie:**

1. ESP-NOW IRQ enqueues `(msg, mac, rssi)` onto an in-process deque.
2. The main asyncio loop drains the queue via `pop_queue` → `execute_queue`.
3. On `/game` with `value != current_game`, the running task is awaited to completion via `stop_game`, then `start_game(value)` schedules the new asyncio task.
4. On `/game` with `value == -1`, `stop_game` runs and the module sits idle awaiting the next command.
5. All other recognized topics update `self.topic` / `self.value`, which the active game polls.

In short: Bag1 modules have **no autonomous mode selection**. The teacher's device is the source of truth for which game is active, and any teacher device on the channel can issue any command.

---

### Bag2 — Wands

Wand modules are autonomous. A child taps NFC tags directly on the wand to enter and exit games and to author trigger→action rules. The teacher's role over ESP-NOW today is restricted to broadcast utilities.

**ESP-NOW library:** `lib/espnow_manager.py`. Higher-level than `now.py`: peer management, broadcast/unicast distinction, and **typed reception**. The `poll()` method classifies incoming messages into a `msg_type` enum-by-string before returning them.

**Recognized `msg_type` values returned by `poll()`:**

| `msg_type`     | Source                  | Payload shape                                      |
| -------------- | ----------------------- | -------------------------------------------------- |
| `"stop"`       | Any device              | `["stop"]` (list) or `{"type": "stop"}` (dict)     |
| `"battery"`    | Programming Station     | `["battery"]`                                      |
| `"colors"`     | Programming Station     | `["turnred", "turnblue", ...]` (a non-stop list)   |
| `"score"`      | Wand                    | `{"type": "score", ...}`                           |
| `"splat_config"` | Wand                  | `{"type": "splat_config", "actions": [...]}`       |
| `"scan_request"` | Wand                  | `{"type": "scan_request"}`                         |
| `"raw"`        | Any (e.g., Freeze Dance) | bytes or unrecognized JSON                         |

**Application protocol:** A mix of list and dict envelopes, dispatched by shape inside `poll()`. There is no explicit `topic` field; the message type is derived structurally.

**Game model:** Games are standalone Python modules (`color_quest.py`, `freeze_dance.py`, `jumpin.py`, `cooking.py`, `melody.py`, `shake.py`, `shake_rainbow.py`, `rainbow.py`, `jump.py`, `sound.py`, `nfc_sound.py`, `simpleicecream.py`, `multiicecream.py`, `gestures.py`) each exposing `def play(nfc, leds, buz, accel, i2c, enow)`. `Wand Module/main.py` dispatches to the matching `play()` when its NFC tag is scanned. Single source of truth for the game tag names is `lib/game_tags.py` (`GAME_TAGS`, `CONTROL_TAGS`, `EXIT_TAGS`).

**Teacher devices in Bag2 today:**

- **Programming Station.** A 4-PN532 hub that broadcasts the union of whatever NFC tags are presently on its readers. Colors auto-enter Color Quest on wands; `stop` resets everything; `battery` displays battery levels. There is no "select game X" capability — game choice is performed locally on the wand by tapping a game tag.
- **No webapp/hub equivalent currently exists for the wand.** A future webapp/hub is mentioned as future work.

**Receiver execution flow on a wand (`Wand Module/main.py`):**

1. The main loop alternates between NFC polling, accelerometer wake checks, and `check_broadcast(enow, ...)`.
2. `check_broadcast` calls `enow.poll()`, returns `"stop"` when `msg_type == "stop"` (clears rules; resets to idle), and triggers a battery display when `msg_type == "battery"`. Other types are ignored at this layer.
3. NFC dispatch is an if/elif chain: `if cmd == "colorquest": play_color_quest(...)`, `elif cmd == "freezedance": play_freeze_dance(...)`, and so on for each entry in `GAME_TAGS`.
4. Each game's own `run()` independently polls `enow.poll()` and exits when `msg_type == "stop"` arrives. Games also implement fluid switching by treating any tag in `EXIT_TAGS` (= `GAME_TAGS ∪ {"stop"}` minus the game's own entry tag) as an exit condition.

In short: Bag2 wands are **autonomously controlled**. The teacher's reach is limited to a global stop, a battery-level display request, and the implicit "colors trigger Color Quest" convention.

---

### Side-by-Side Summary

| Dimension                              | Bag1 (Plushie/Box)                                      | Bag2 (Wand)                                                |
| -------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------- |
| ESP-NOW library                        | `utilities/now.py` (IRQ callback)                       | `lib/espnow_manager.py` (polled, typed)                    |
| Message envelope                       | `{"topic": "/x", "value": v}`                           | Lists (`[...]`) or dicts with `"type"` field               |
| Active-game selection                  | Teacher device only                                     | Child via NFC tag (today)                                  |
| Stop control                           | `{topic:"/game", value:-1}`                             | `["stop"]` or `{"type":"stop"}`                            |
| Per-module state                       | `topic`/`value` on the `Tool`/`Plushie` instance         | None centrally — each game owns its state                  |
| Game model                             | asyncio task class with `start`/`loop`/`close`          | Standalone `play(...)` function per module                 |
| Teacher hardware in active use         | WebApp+hub, standalone controllers                      | Programming Station (NFC reader hub)                       |
| Existing teacher → wand capabilities   | n/a                                                     | Broadcast `stop`, broadcast `battery`, broadcast `colors`  |
| Missing teacher → wand capabilities    | n/a                                                     | Start a specific named game                                |
| Game-to-game switching                 | Teacher device pushes new `/game` value                 | Any tag in `EXIT_TAGS` exits; new tag enters new game      |

The functional asymmetry to close: Bag2 wands have no equivalent of Bag1's `{topic:"/game", value:N}`. That is the gap this plan fills.

---

## Part 2: Implementation Plan for Cursor Subagents

### Goal

Add ESP-NOW teacher-initiated game dispatch to the wand firmware. After this work is complete, any device that knows the wand's protocol can broadcast a single message and force every wand in range to start the named game, regardless of what the wand is currently doing (idle, programming mode, running a rule, or in another game).

### Protocol Decision

The wire format for the new message:

```json
{"type": "start_game", "name": "<game_tag>"}
```

Where `<game_tag>` is any string in `lib/game_tags.py::GAME_TAGS`. The name reuses the existing NFC tag string for the game (e.g., `"colorquest"`, `"freezedance"`, `"jumpin"`). Reusing the NFC name keeps `lib/game_tags.py` as the single source of truth for valid game identifiers.

Broadcast-only for v1. A unicast variant can be added later without affecting receivers.

### Design Decisions

The following decisions are baked into the plan:

- **Path A — explicit `msg_type`.** `espnow_manager.poll()` returns a new classification, `"start_game"`. Each game module needs a small change to recognize it as an exit condition. This costs 14 mechanical edits but keeps the runtime semantics transparent and matches the pattern documented in `GAME_AUTHORING_GUIDE.md`.
- **Force-switch.** A `start_game` received inside a running game causes that game to exit cleanly via its existing try/finally path; control returns to `main.py`, which immediately dispatches the requested game without passing through idle.
- **Dispatch table replaces if/elif chain.** `Wand Module/main.py` introduces a single `GAME_DISPATCH = {name: play_func}` dict used by both NFC dispatch and ESP-NOW dispatch. This removes a duplication and is required for the ESP-NOW path to dispatch by name.
- **Unknown game names are dropped on the wand with a log line.** No reset, no error animation; the wand stays in its current state.
- **Existing implicit conventions remain.** The Programming Station's color-list broadcast still auto-enters Color Quest. The `["battery"]` broadcast still triggers the battery display. `["stop"]` and `{"type":"stop"}` still stop everything.
- **The plan does not touch** `Bag1/`, the Programming Station, the Scoreboard, the Splat Companion, or anything under `Live_Page/`. Those continue to operate unchanged.

### Files Affected

```
lib/espnow_manager.py                          modified
Wand Module/main.py                            modified
Wand Module/color_quest.py                     modified (small)
Wand Module/freeze_dance.py                    modified (small)
Wand Module/jumpin.py                          modified (small)
Wand Module/cooking.py                         modified (small)
Wand Module/melody.py                          modified (small)
Wand Module/shake.py                           modified (small)
Wand Module/shake_rainbow.py                   modified (small)
Wand Module/rainbow.py                         modified (small)
Wand Module/jump.py                            modified (small)
Wand Module/sound.py                           modified (small)
Wand Module/nfc_sound.py                       modified (small)
Wand Module/simpleicecream.py                  modified (small)
Wand Module/multiicecream.py                   modified (small)
Wand Module/gestures.py                        modified (small)
Wand Module/GAME_AUTHORING_GUIDE.md            documentation update (small)
```

`lib/game_tags.py` is **not** modified. It is already the source of truth for valid game names and continues to be.

### Task Breakdown for Cursor Subagents

Tasks are organized in two phases. Phase 1 tasks must complete before Phase 2 begins. Phase 2 tasks are mutually independent and can run in parallel.

---

#### Phase 1 — Foundation (sequential)

##### Task F1: Extend `lib/espnow_manager.py`

**File:** `Bag2/Code/lib/espnow_manager.py`

**Changes:**

1. Update the module docstring's `msg_type` enumeration to include `"start_game"`.
2. Inside `poll()`, in the dict-handling branch, before the fallthrough to `"raw"`, add a case for `mt == "start_game"`. Validate that `data.get("name")` is a non-empty string; if it is, return `("start_game", data, mac_str)`. If the name is missing or not a string, return `("raw", data, mac_str)` so existing raw handling can still see it.
3. Add sender helpers near `send_stop_to` / `broadcast_stop`:
   - `send_start_game(self, mac_str, name)` — unicast equivalent.
   - `broadcast_start_game(self, name)` — broadcast equivalent. Wraps `self.broadcast({"type": "start_game", "name": name})`.
4. Update the convenience-senders section comment header if appropriate.

**Out of scope:** Do not add a pending-request cache field or `pop_pending_start_game()`. Path A keeps this stateless.

**Definition of done:**

- The file imports cleanly under MicroPython (no `f-strings`, no Python-3.9+ syntax — match existing style).
- A manual REPL test on any device: `mgr.broadcast_start_game("colorquest")` sent from one device, and `mgr.poll(1000)` on another returns `("start_game", {"type":"start_game","name":"colorquest"}, mac_str)`.
- Existing message types are unaffected (regression check via Programming Station broadcasting `["stop"]` and `["battery"]`).

##### Task F2: Refactor `Wand Module/main.py` dispatch and ESP-NOW handling

**File:** `Bag2/Code/Wand Module/main.py`

**Changes:**

1. Introduce a `GAME_DISPATCH` dict near the top of the file (after the `from gestures import play as play_gestures` block):

   ```python
   GAME_DISPATCH = {
       "colorquest":     play_color_quest,
       "freezedance":    play_freeze_dance,
       "jumpin":         play_jumpin,
       "cooking":        play_cooking,
       "melody":         play_melody,
       "shake":          play_shake,
       "shakerainbow":   play_shake_rainbow,
       "rainbow":        play_rainbow,
       "jump":           play_jump,
       "sound":          play_sound,
       "nfcsound":       play_nfc_sound,
       "simpleicecream": play_simpleicecream,
       "multiicecream":  play_multiicecream,
       "gestures":       play_gestures,
   }
   ```

   Add a sanity check immediately after the dict (still at module load time): assert `set(GAME_DISPATCH.keys()) == GAME_TAGS`. If the assertion fails on boot, print a clear error and continue. (This catches drift between `GAME_TAGS` and the dispatch table.)

2. Replace the existing if/elif game-dispatch chain in the main loop with a single lookup:

   ```python
   if cmd in GAME_DISPATCH:
       _launch_game(cmd, nfc, leds, buz, accel, i2c, enow)
       # ...post-game state cleanup as before
       continue
   ```

   Define `_launch_game(name, nfc, leds, buz, accel, i2c, enow)` as a helper. After invoking `GAME_DISPATCH[name](...)`, the helper inspects `enow` for a pending start-game request *(see step 3)* and, if one is present, loops to dispatch it. This is how force-switch chains across multiple games without bouncing through idle.

3. Modify `check_broadcast(enow, batt_ref, leds_ref, buz_ref)` to recognize the new `msg_type`:

   ```python
   if msg_type == "start_game":
       name = data.get("name") if isinstance(data, dict) else None
       if name in GAME_DISPATCH:
           return ("start_game", name)
       print("  ESP-NOW: ignoring unknown start_game name: %r" % name)
       return None
   ```

   The return type of `check_broadcast` becomes `Optional[Union[str, Tuple[str, str]]]`. Callers that expect a string (`== "stop"`, `== "battery"`) keep working unchanged. New callers can `if isinstance(result, tuple) and result[0] == "start_game": ...`.

4. In the idle main loop, after the `result = check_broadcast(...)` call, add a branch:

   ```python
   elif isinstance(result, tuple) and result[0] == "start_game":
       _, name = result
       # Same teardown as a "stop":
       enow.send_stop_all_peers(); enow.clear_peers()
       rules = {}; editing = None; pending_combinator = None
       buz.stop()
       _launch_game(name, nfc, leds, buz, accel, i2c, enow)
       last_activity_ms = time.ticks_ms()
       idle_frame = 0
       show_idle(last_soc, 0)
   ```

5. In `run_event_loop()` (programming-mode runtime), do the same recognition. When `check_broadcast` returns `("start_game", name)`, the function returns a value (or sets a sentinel via closure) so that `main()` can dispatch the requested game after the run loop exits.

6. Update the file-top docstring's `Controls:` list with a one-line note that `start_game` may also be received over ESP-NOW.

**Definition of done:**

- All 14 NFC-tap entry paths still dispatch the same game functions they did before.
- A `start_game` broadcast received while idle starts the requested game.
- A `start_game` broadcast received while running a rule clears rules, exits the run loop, and starts the requested game.
- A `start_game` broadcast with an unknown name is logged and ignored; the wand stays in its current state.
- The `GAME_DISPATCH` keys assertion succeeds against `GAME_TAGS`.
- Existing `stop` and `battery` behaviors are unaffected.

---

#### Phase 2 — Per-game updates (parallel, 14 subagents)

Each subagent receives the same instruction template and one file. These can all run concurrently after Phase 1 lands.

##### Task P-{game}: Update game module to recognize `start_game` as an exit

**Files (one per subagent):**

- `Bag2/Code/Wand Module/color_quest.py`
- `Bag2/Code/Wand Module/freeze_dance.py`
- `Bag2/Code/Wand Module/jumpin.py`
- `Bag2/Code/Wand Module/cooking.py`
- `Bag2/Code/Wand Module/melody.py`
- `Bag2/Code/Wand Module/shake.py`
- `Bag2/Code/Wand Module/shake_rainbow.py`
- `Bag2/Code/Wand Module/rainbow.py`
- `Bag2/Code/Wand Module/jump.py`
- `Bag2/Code/Wand Module/sound.py`
- `Bag2/Code/Wand Module/nfc_sound.py`
- `Bag2/Code/Wand Module/simpleicecream.py`
- `Bag2/Code/Wand Module/multiicecream.py`
- `Bag2/Code/Wand Module/gestures.py`

**Instruction template (identical for each):**

> Locate every call site in this file that consumes the return of `enow.poll()` (search for `enow.poll`). For each site that exits the game on `msg_type == "stop"`, extend the check to also exit on `msg_type == "start_game"`. Use a tuple-`in` test for readability:
>
> ```python
> msg_type, _, _ = self.enow.poll()    # or `enow.poll()` if no `self`
> if msg_type in ("stop", "start_game"):
>     return
> ```
>
> Do not consume or validate the `data` payload — the manager has already classified the message, and `Wand Module/main.py` will read the pending request via its own `check_broadcast` path after this `play()` function returns. Your only job is to exit the run loop cleanly.
>
> Preserve the existing try/finally cleanup in `play()` so LEDs, buzzer, and motor are turned off on the way out. Do not add any new state, parameters, or returns. The game's exit path remains identical to today's stop path.
>
> If this file contains more than one `enow.poll()` call (e.g., a pre-game wait loop and a main run loop), apply the change at every site that currently treats `"stop"` as an exit.
>
> Constraints:
> - MicroPython compatibility — no f-strings, no walrus operators, no `match` statements.
> - Do not modify game logic, sound, animation, button handling, or NFC handling.
> - Do not modify `play()`'s function signature.

**Definition of done (per file):**

- A `grep -n 'enow.poll' <file>` shows that every poll call followed by a stop-exit now also exits on `"start_game"`.
- The file still imports cleanly and runs in standalone test mode (i.e., `def main():` at the bottom of the module still works if invoked directly).
- The game's NFC-driven entry, exit, and gameplay are visibly unchanged on hardware.

##### Task P-doc: Documentation update

**File:** `Bag2/Code/Wand Module/GAME_AUTHORING_GUIDE.md`

Update the "Critical Rules" section and the new-game checklist:

- Rule 1 currently reads: *"Exit tags and ESP-NOW stop in each run iteration."* Extend to: *"Exit tags, ESP-NOW stop, and ESP-NOW start_game in each run iteration."*
- Add a checklist item: *"Exits on `msg_type in ('stop', 'start_game')` in every `enow.poll()` site."*

This task can run in parallel with the per-game updates.

---

### Verification Plan

After all tasks complete, verify with the following manual checks. Each can be performed by a developer with two wand-class ESP32-C6 boards on a bench (one acts as the teacher device by running a short snippet that calls `ESPNowManager.broadcast_start_game`).

| Scenario                                                                                | Expected outcome                                                  |
| --------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Wand idle. Broadcast `start_game name="colorquest"`.                                    | Wand enters Color Quest.                                          |
| Wand in Color Quest. Broadcast `start_game name="freezedance"`.                         | Color Quest exits cleanly; Freeze Dance starts immediately.       |
| Wand in Freeze Dance (player role). Broadcast `start_game name="jumpin"`.               | Freeze Dance exits; Jumpin starts.                                |
| Wand mid-edit (rules built, not yet running). Broadcast `start_game name="cooking"`.    | Rules cleared; Cooking starts.                                    |
| Wand in run mode (rule looping). Broadcast `start_game name="melody"`.                  | Run loop exits; rules cleared; Melody starts.                     |
| Wand idle. Broadcast `start_game name="nonsense"`.                                      | Wand logs and remains idle.                                       |
| Wand idle. Broadcast `["stop"]`.                                                        | No change (already idle); existing behavior intact.               |
| Wand idle. Broadcast `["battery"]`.                                                     | Battery display triggers; existing behavior intact.               |
| Wand idle. Broadcast `["turnred", "turnblue"]`.                                         | Wand enters Color Quest (existing implicit convention intact).    |
| Tap any game NFC tag.                                                                   | Game starts; no regression from dispatch refactor.                |

### Risks and Open Questions

- **Race between in-game NFC poll and ESP-NOW poll.** If a game polls NFC and ESP-NOW in the same tick, a near-simultaneous `start_game` and `stop` NFC tag both exit the game; the order is non-deterministic but both lead to a defined state (idle vs. new game). Either is acceptable; no action.
- **Multiple `start_game` messages in a single window.** Path A is stateless — the game exits on the first one it sees, and `main.py`'s `check_broadcast` is called immediately afterward, so the second one (if still in the inbox) wins. This is the desired "last write wins" behavior.
- **Programming Station future work.** When the Programming Station gains a "set game" tag, its `main.py` will call `enow.broadcast_start_game(name)`. No wand-side change is needed at that point.
- **Future "status game".** Reserved for a later pass. Will likely be implemented as a regular game module (e.g., `status.py`) that responds to a unicast `status_request` ESP-NOW message with a `status_report` reply, paired with a battery-style visual. Not in this plan.

---

## Appendix A: Quick Reference — Existing Wand ESP-NOW Behaviors (Preserved)

| Trigger                                  | Effect on wand                                          |
| ---------------------------------------- | ------------------------------------------------------- |
| `["stop"]` or `{"type":"stop"}`          | Clears state, returns to idle                           |
| `["battery"]`                            | Shows battery level on LEDs                             |
| `["turnred", ...]` (color list, no stop) | Enters Color Quest                                      |
| `{"type":"score", ...}`                  | (Scoreboard-bound; no wand action)                      |
| `{"type":"splat_config", ...}`           | (Splat Companion-bound; no wand action)                 |
| `{"type":"scan_request"}`                | (Programming Station-bound; no wand action)             |

## Appendix B: Quick Reference — New Wand ESP-NOW Behavior

| Trigger                                                | Effect on wand                                                      |
| ------------------------------------------------------ | ------------------------------------------------------------------- |
| `{"type":"start_game", "name":"<game_tag>"}` (broadcast) | Force-switches to the named game. Idle, run mode, and other games all exit cleanly first. |
| Same message with unknown `name`                       | Logged; ignored. Wand stays in current state.                       |
