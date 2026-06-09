# Color Quest — Documentation vs. Code Issues

This document records mismatches between written documentation and actual wand firmware behavior for Color Quest and related ESP-NOW color broadcasts. It is a reference for teachers, firmware authors, and doc maintainers.

---

## 1. Color broadcast does not auto-enter Color Quest from idle

### What some docs claim

- [espnow_control.md](espnow_control.md) (Bag1/Bag2 comparison and Appendix A) states that a Programming Station color-list broadcast enters Color Quest on wands.
- [Programming Station readme](../Code/Stations/Programming%20Station/readme.md) says wand modules "receive the sequence" when the station broadcasts.

### Actual behavior

[`main.py`](../Code/Wand%20Module/main.py) `check_broadcast()` handles only:

- `stop` — clears rules and returns to idle
- `battery` — shows battery level on LEDs
- `start_game` — force-dispatches a named game (after Part 2 implementation)

It does **not** handle `msg_type == "colors"`. A color-list broadcast such as `["turnred", "turnblue", "turngreen"]` sent while the wand is idle is **ignored**.

### Real entry flow today

1. Child (or teacher via NFC) taps a `colorquest` tag on the wand.
2. `main.py` calls `play_color_quest()`.
3. Inside [`color_quest.py`](../Code/Wand%20Module/color_quest.py), `wait_for_commands()` polls ESP-NOW and accepts a `colors` message as the hunt sequence.
4. The game loop (`run_game`) can also accept mid-game `colors` broadcasts for a new sequence.

Color Quest only consumes `colors` messages **while the game module is already running**.

### Implication for teacher control

After wand firmware supports `start_game`:

- Use `broadcast_start_game("colorquest")` to force every wand into Color Quest from idle, run mode, or another game.
- A raw color-list broadcast alone is **not** sufficient to start Color Quest from idle.
- Typical teacher workflow: (1) `broadcast_start_game("colorquest")`, then (2) press the Programming Station button to broadcast the color sequence — or have the child use the `color_quest_scan` / rescan NFC flow documented in `color_quest.py`.

---

## 2. Stale paths in COLOR_QUEST_README.md

[`COLOR_QUEST_README.md`](COLOR_QUEST_README.md) references:

| Stated path | Actual location |
|-------------|-----------------|
| `station_test/main.py` | [`Stations/Programming Station/main.py`](../Code/Stations/Programming%20Station/main.py) |
| `slide_score_display.py` | [`Stations/Slide Score Station/main.py`](../Code/Stations/Slide%20Score%20Station/main.py) |

The system diagram and device table in COLOR_QUEST_README should be updated in a separate doc pass.

---

## 3. Where `colors` messages are consumed

| Device | When `colors` is handled |
|--------|--------------------------|
| Wand (`color_quest.py`) | Only while Color Quest `play()` is active (`wait_for_commands`, `run_game`, `_post_win_wait`) |
| Slide Score Station | Any time — treats `colors` as a new-game reset signal |
| Wand idle (`main.py`) | Never |

The Programming Station broadcasts `colors` to all listeners. The scoreboard reacts immediately; wands react only if already inside Color Quest.

---

## 4. Interaction with `start_game` dispatch

Wire format (wand firmware):

```json
{"type": "start_game", "name": "colorquest"}
```

After broadcast:

- Wand exits current state (idle, programming, run loop, or another game).
- `play_color_quest()` runs and blocks in `wait_for_commands()` until a sequence arrives.
- Options for the sequence: Programming Station button broadcast, `scan_request` / rescan tag flow, or button-triggered random quest (standalone test path).

`start_game` does not embed a color sequence. It only selects the game module.

---

## 5. Recommended doc corrections (reference — not applied here)

These are suggested follow-up edits for other files; this issues doc does not modify them.

- **espnow_control.md** Appendix A: change the color-list row to "Enters Color Quest **once the game is active**" (or "after `colorquest` NFC tap or `start_game` dispatch").
- **espnow_control.md** verification table: row "Wand idle → color list broadcast" should expect **stays idle**, not enters Color Quest.
- **COLOR_QUEST_README.md**: update file paths and diagram to `Stations/Programming Station/` and `Stations/Slide Score Station/`.
- **Programming Station readme**: clarify that wands receive the sequence only when already in Color Quest (unless `start_game` was sent first).

No firmware change is required to add idle `colors` → Color Quest auto-entry unless that behavior is explicitly requested later.
