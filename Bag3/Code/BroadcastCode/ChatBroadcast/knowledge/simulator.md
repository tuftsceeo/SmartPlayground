# Simulator notes (sent for the rest of a chat once it reports a simulator problem)

The practice window runs the game in Pyodide (CPython 3.12) in the browser, not MicroPython.

## How a game is loaded

- `runtime.py load_game` reads the code and `transform.py transform_and_compile` rewrites it: every
  ordinary `def` becomes `async def`, and calls inside become awaited. Lambdas, generator
  expressions, default arguments and module-level comprehensions are left alone. Imports and loops
  are not changed.
- `time.sleep_ms`, `sleep` and `sleep_us` become real-time async sleeps.
- Line numbers in errors match the code as written. Pasted code is reported as `custom.py`.
- A loop that runs more than 2 s without sleeping is stopped with
  `SimTimeout: game loop ran >2.0s without sleeping — likely a busy loop`. On the wand the same loop
  freezes the device, so add a `time.sleep_ms(...)` in the loop.

## What is simulated

- **Wand `play()` arguments:** nfc (a fake reader), leds, buz, accel, i2c, enow and batt. The real
  library code for leds, the buzzer, actions, battery, espnow_manager, lobby_game, game_tags, pairing and
  splat_api runs unchanged.
- **Icon Display:** runs in its own Python, with display_tags, icon_store, shapes and
  espnow_manager, on a simulated 16x16 matrix. It is called as `play(None, panel, enow)`.
- **Not provided:** any module outside these. Importing one fails at load with
  `ModuleNotFoundError`. That is a real problem, because the device does not have the module either.

## Inputs the teacher can give

- **Tap a tag:** a chip for each entry in the game's `COMMANDS` / `GAME_COMMANDS`. The tag is held
  under the reader for 600 ms with a short confirm beep.
- **Unknown tags:** the simulator passes any tapped text to the game, while the real reader returns
  `None` for text outside `commands`. The simulator also gives no low beep for unknown tags.
- **Movement:** Shake (with a strength slider), Jump and Spin buttons, a tilt pad, and the button
  (press and hold).
- **Splats:** click a drawn Splat (a press of at least 250 ms).

## Timing

Sleeps take real time. `ticks_ms` starts at about 60 s of uptime. The code itself runs at browser
speed, so heavy work that is fine here may be slow on the wand.

## Several devices

`[GAME_SETTINGS]` sets the number of wands (1–4) and of Splats per wand (0–2). Extra wands start as
"?" and boot only when clicked. All wands and the Icon Display share one simulated ESP-NOW channel.
Lobby games run the real leader/follower code.

The simulator does not have:
- Splat cards;
- `/pairing.json`;
- the `pw_who` checks;
- the 30 s connect deadline.

## The error you receive

The simulator's text arrives inside an `<error>` block after the request.

- **Load failure (syntax, import):** the full traceback. Ignore the wrapper frames
  (`_pyodide/_base.py eval_code_async`, `<exec>`, `runtime.py load_game`, `transform.py`) and
  read the `custom.py` lines.
- **Crash while running:** the last traceback line, followed by the recent simulator log, which
  holds the full traceback. Ignore its `runtime.py` frames (`_runner`, `_run_play`).
- **A game whose `play()` returns:** no error. The preview shows a "Game ended" banner.

## Simulator passes, device fails

| Passes in the simulator | On the wand |
|---|---|
| CPython-only syntax or library calls | Fails on MicroPython |
| Type annotations, `typing`, `dataclasses` | Not available |
| Large lists and strings, deep recursion | Out of memory |
| Code over 32000 bytes | Refused at send time |
| `play()` with the wrong parameters (the simulator retries without `batt`) | TypeError, or refused at send time |
| Unknown tag text reaching the game | The reader returns `None` |
| (fails in the simulator) A helper `def` called inside a `lambda` or generator expression, e.g. `sorted(x, key=lambda v: score(v))` or `any(f(i) for i in r)` | Works. In the simulator the helper returns a coroutine: `sorted` raises `TypeError: '<' not supported between instances of 'coroutine'…`, `any`/`all` are wrongly true. The game is fine on the wand; to make it run in both, compute the values in a plain `for` loop first |
| Heavy work between sleeps | Slow or laggy |
| BLE and radio timing | Real delays and dropped messages |

## How to answer a simulator problem

- **A game bug:** fix it, and reply with the full file as usual.
- **A simulator limit (the code is fine on the wand):** say so in one short sentence, leave the
  code unchanged, and suggest sending the game to the wand.
- **Keep it short for teachers:** say what went wrong in plain words. Don't mention Pyodide or the
  Python version.
- **Device-only risks** from the table above: warn about them only when the code actually risks
  one.
