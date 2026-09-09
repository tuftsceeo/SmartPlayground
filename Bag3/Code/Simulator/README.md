# Wand Game Simulator

Browser-based Pyodide simulator that runs unmodified wand game modules against
fake MicroPython hardware. Ships as a `<wand-sim>` custom element (shadow DOM)
laying out the wand — drawn in CSS, with a live 5x5 LED matrix, speaker and
button — on a tilt/press pad, beside a capability-filtered control panel, with
four pop-ups available over the whole panel.

The panel follows the "Wand Simulator v4", "Wand v4" and "Wand Sim Overlays"
design artboards in
`Bag3/Code/BroadcastBox/docs_and_design/simlution v4/`.

Games: `jump`, `shake`, `shake_rainbow`, `sound`, `rainbow`, `jumpin`,
`nfc_sound`, `gestures`, `simpleicecream`, `melody`, `cooking`,
`multiicecream`, `freeze_dance`.

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

`buzzer.py` is the one exception: it's hand-mirrored from
`Bag3/BroadcastBox/MockWand/lib/buzzer.py`, not synced from Bag2, so it's
not in `sync_sources.py`'s `VERBATIM_LIBS` and `--check` doesn't touch it.
If MockWand's `buzzer.py` changes, copy it into `vendor/lib/buzzer.py` by
hand and re-run `sync_sources.py`.

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
orientation was matched against which color/axis/sign lit up).
`ChatApp/knowledge/knowledge.py` §9 documented a different (wrong) table
before this — corrected there too, to match — see the docstring at the top
of `motion.js` for the exact table and history of the correction.

Every game exercises this same convention, since the pad is the only way to
change orientation and it reports these vectors; `simpleicecream.py`'s
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

## ESP-NOW is one-sided

There is no second wand, so the radio is two halves that don't meet.

**Outgoing.** `py/devices/espnow_manager.py` reports every send through
`sim_state.emit_enow_sent()`, which the panel shows under "Sent by this
wand" and the element re-emits as `sim-enow-sent`. Showing the message *is*
the output — nothing receives it. `send_raw` is spelled out on the fake
manager rather than left to its `__getattr__` no-op because
`freeze_dance.py` drives the whole game through it.

**Incoming.** The advanced block's "Heard from the caller" buttons queue
messages via `sim_state.enqueue_enow()` as if a peer had sent them. A game
reading a raw payload needs real bytes (`freeze_dance.py` compares against
`MSG_GO = b"FD_GO"`), so `wand-sim.js` builds a hex-escaped Python bytes
literal rather than passing a JS string. The vocabulary per game is
`RADIO_BY_GAME` in `js/controls.js`; every game also gets `stop` and
`start_game`, the two the hub broadcasts.

`emit_log` and `emit_error` are deliberately separate channels. A send is
routine traffic and must not reach the error channel — while they shared
one callback, a Freeze Dance caller's every broadcast surfaced in the host
as a crash (and, once the panel grew pop-ups, as "Can't simulate").
`tests/test_espnow_channels.py` guards that.

## Freeze Dance roles

`freeze_dance.py` picks its role from the `caller` and `player` NFC tags, so
they appear in the tag popover like any other tag — no special affordance.
It is the one vendored game that names its tag set `GAME_COMMANDS` rather
than the `COMMANDS` that `Wand Module/main.py` documents;
`get_capabilities()` reads either, or the game would offer no tags at all
and its role-select step would be unreachable. The naming divergence is in
the Bag trees, not here, and has been left alone.

## Design notes

- **Verbatim**: `leds.py`, `brightness.py`, `hubtype.py`, `game_tags.py`,
  `actions.py`, `battery.py` (AST-transformed sync→async), synced from
  Bag2. `buzzer.py` is verbatim too, hand-mirrored from MockWand: see
  "Sync vendored sources" above.
- **Faked wholesale**: `lis2dw12`, `max17048`, `opt3002`, `pn532`,
  `nfc_reader`, `espnow_manager`.
- **Platform shims**: `machine`, `neopixel`, `time.sleep_ms` / `ticks_*`,
  `_thread`, `network`, `ubluetooth`, `micropython`.
- Stop = cancel the `play()` asyncio task; games' `try/finally: leds.off()`
  still runs.
- LED colors: incoming bytes are the wand's actual NeoPixel duty cycle
  (linear), converted through the same linear→sRGB curve
  `Stations/Icon Display Station/webapp/js/pipeline/ledcolor.js` uses before
  being set as a CSS color, or the color renders far dimmer than the real
  LED looks.
- The wand is built in CSS by `js/renderer.js`, which also owns the wand's
  own stylesheet (`WAND_STYLE`, concatenated into the shadow root's `<style>`
  by `wand-sim.js`). `assets/wand/WAND_FRONT.svg` and
  `assets/wand/WandGestures/*.svg` are no longer rendered — an earlier pass
  inlined the SVG and drove its named layers — but are left in place; the
  design system under `docs_and_design/` copies from them.
- Buzzer and motor state show on the wand itself (the speaker cone takes the
  note's color and emits a ring per note; the motor raises a "BUZZ" badge and
  a repeating burst of agitrons), not on separate indicator chips. The raw
  Hz / on-off readout lives in the advanced block.
- No per-game "how to play" text: the panel's readers are mostly
  pre-readers, so `_TEACHER_TABLE` carries only the button kind and motion
  vocabulary that drive which controls are shown.
- Icons are inline SVG in `js/icons.js`, copied from
  `ChatBroadcast/js/icons.js` rather than imported — ChatBroadcast depends on
  this directory, so the dependency must not run both ways.
- The pad feeds free-form tilt (`js/motion.js`'s `setPadTilt`) while the
  pointer moves, then snaps to the named pose its position reads as once the
  pointer settles, so an orientation-reading game sees the exact gravity
  vector from the `POSES` table rather than an in-between one. The pad's four
  edge labels fix that mapping — see `setPadTilt`'s docstring.
- Gesture animations run for the duration `fireMove()` reports, not a fixed
  design value, so the wand stops moving when the accelerometer does.
- `<wand-sim>` attributes: `game`, `autostart`, `show-console`, `controls`,
  `source`, `muted`, `advanced` (shows the axis readout, the custom tag /
  radio message drawer, the hardware dials and the log; off by default, so an
  embedding host opts in explicitly), `log-lines` (default 2).
  Events: `sim-ready`, `sim-frame`, `sim-print`, `sim-error` (`detail.phase`
  is `"boot"`, `"load"`, or `"run"`), `sim-stopped`, `sim-overlay-action`
  (`detail` is `{ kind, action }`), `sim-enow-sent` (`detail` is
  `{ kind, data, mac }`).
- Pop-ups: `showOverlay(kind, opts)` / `hideOverlay()`, where `kind` is
  `"game-over"`, `"cant-simulate"`, `"welcome"` or `"new-code"` (a
  bottom-anchored banner; the rest are centred cards over a scrim). `opts`
  can override `title`, `message` and `buttons`. Every button dispatches
  `sim-overlay-action` and closes the pop-up. `"cant-simulate"` is the one
  the element raises by itself, on a boot or load failure; the host triggers
  the others. `index.html` has a button per kind for exercising them.
- The panel lays out in two panes above 420px of its own width and one below
  it, and shrinks the wand below 300px (container queries in
  `js/controls.js`). Its design width is 500px.
- ChatBroadcast (`Bag3/Code/BroadcastBox/ChatBroadcast/`) embeds this
  element directly from `../../Simulator/wand-sim.js`, so both trees must be
  served from a common root (`Bag3/Code/`) rather than from ChatBroadcast's
  own directory.
