# Wand Game Simulator

Browser-based Pyodide simulator that runs unmodified wand game modules against
fake MicroPython hardware. Ships as a `<wand-sim>` custom element (shadow DOM)
that composites an SVG wand illustration, a fake LED matrix, buzzer/motor
indicators, and a capability-filtered control panel around the running game.

Games: `jump`, `shake`, `shake_rainbow`, `sound`, `rainbow`, `jumpin`,
`nfc_sound`, `gestures`, `simpleicecream`, `melody`, `cooking`,
`multiicecream`.

## Run locally

From the repo root:

```bash
cd Bag3/Code/Simulator
python3 -m http.server 8000
```

Open [http://localhost:8000/index.html](http://localhost:8000/index.html).

Pyodide loads from jsDelivr (pinned version, see `PYODIDE_VERSION` in
`wand-sim.js`) — this requires outbound network access to
`cdn.jsdelivr.net`. Asset URLs resolve from `import.meta.url`, so the element
works when embedded on another origin path as long as this directory tree
is served intact.

`index.html`'s "Load file…" button reads a local `.py` file and runs it
through `wand-sim.source` instead of the dropdown's built-in games, for
testing a game under development without re-vendoring it.

## Sync vendored sources

Games and verbatim libs are copied into `vendor/` from `Bag2/Code/Wand
Module` and `Bag2/Code/lib` — a different Bag than this tool now lives in,
since Pyodide can't read the real filesystem live and `vendor/` is what it
actually imports:

```bash
python3 tools/sync_sources.py          # refresh vendor/ + MANIFEST.json
python3 tools/sync_sources.py --check  # exit 1 if vendor drifted
```

A pre-commit hook at `.githooks/pre-commit` runs `--check`. Enable with:

```bash
git config core.hooksPath Bag3/Code/Simulator/.githooks
```

(or copy the hook into `.git/hooks`).

## Tests

```bash
cd Bag3/Code/Simulator
python3 -m pytest
```

- `test_transform.py` — pure AST sync→async transform (no Pyodide).
- `test_golden_frames.py` / `test_new_games.py` / `test_capabilities.py` —
  CPython asyncio harness that loads shims + devices + transformed games and
  asserts LED frames, capabilities, and audio/motor output under scripted
  input. This is the harness to reach for when checking any of the fixes
  below without a browser.

## Accelerometer axis convention

`js/motion.js`'s `POSES` table was verified against the on-hand wand
hardware with a live per-orientation test (each of 6 poses reads
`accel.read()` and lights a distinct LED color; a real tap in each
orientation was matched against which color/axis/sign lit up). This
contradicts `ChatApp/knowledge/knowledge.py` §9's "confirmed from
calibration" note (tip up → y=+1, left side up → x=+1) on both axis
assignment and sign for the tip-up/tip-down pair — see the docstring at the
top of `motion.js` for the exact table and history of the correction.

Any game that reads `accel.read()` directly (rather than through the pose
buttons) is exercising this same convention; `simpleicecream.py`'s
Upright/Upside-down state machine, for one, checks the `x` axis.

## NFC tag feedback

None of the 12 games write to the vibration motor. The only place in the
wand codebase that does is `main.py`'s `on_scan_complete()` (a beep, then
the vibration motor) — the hub/boot loop, not a per-game file, so the
simulator (which only loads individual games) never ran it. `sim_state.py`'s
`tap_nfc()` fires the same beep-then-buzz sequence itself so every tag tap
gets it, but skips the beep if the loaded game already made its own sound in
response within a short window (`melody.py`/`cooking.py`/`nfc_sound.py` all
do) — see `_nfc_confirm_pulse()`'s docstring for the exact timing and why.

## Design notes

- **Verbatim**: `leds.py`, `buzzer.py`, `brightness.py`, `hubtype.py`,
  `game_tags.py`, `actions.py`, `battery.py` (AST-transformed sync→async).
- **Faked wholesale**: `lis2dw12`, `max17048`, `opt3002`, `pn532`,
  `nfc_reader`, `espnow_manager`.
- **Platform shims**: `machine`, `neopixel`, `time.sleep_ms` / `ticks_*`,
  `_thread`, `network`, `ubluetooth`, `micropython`.
- Stop = cancel the `play()` asyncio task; games' `try/finally: leds.off()`
  still runs.
- LED colors: incoming bytes are the wand's actual NeoPixel duty cycle
  (linear), converted through the same linear→sRGB curve
  `Stations/Icon Display Station/webapp/js/pipeline/ledcolor.js` uses before
  being set as an SVG fill, or the color renders far dimmer than the real
  LED looks.
- Every `assets/wand/WandGestures/*.svg` icon is sized 64×64 wherever it
  appears in the control panel (pose/move buttons, the shake plunger, the
  NFC tag row, the buzzer/motor indicators) — these are detailed motion
  illustrations, not simple glyphs, and read as illegible smaller.
- `<wand-sim>` attributes: `game`, `autostart`, `show-console`, `controls`,
  `source`, `muted`, `advanced` (shows the Advanced drawer + its "Show
  console" toggle; off by default, so an embedding host opts in explicitly).
  Events: `sim-ready`, `sim-frame`, `sim-print`, `sim-error` (`detail.phase`
  is `"boot"`, `"load"`, or `"run"`), `sim-stopped`.
- ChatBroadcast (`Bag3/Code/BroadcastBox/ChatBroadcast/`) embeds this
  element directly from `../../Simulator/wand-sim.js`, so both trees must be
  served from a common root (`Bag3/Code/`) rather than from ChatBroadcast's
  own directory.
