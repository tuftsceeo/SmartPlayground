# Wand Game Simulator

Browser-based Pyodide simulator that runs unmodified wand game modules against
fake MicroPython hardware. Ships as a `<wand-sim>` custom element (shadow DOM)
laying out the wand — drawn in CSS, with a live 5x5 LED matrix, speaker and
button — on a tilt/press pad, beside a capability-filtered control panel, with
four pop-ups available over the whole panel.

The panel follows the "Wand Simulator v4", "Wand v4" and "Wand Sim Overlays"
design artboards in
`Bag3/Code/BroadcastCode/BroadcastBox/docs_and_design/simlution v4/`.

Games: `jump`, `shake`, `shake_rainbow`, `sound`, `rainbow`, `jumpin`,
`nfc_sound`, `gestures`, `simpleicecream`, `melody`, `cooking`,
`multiicecream`, `freeze_dance`, `goalrace`, `color_quest`, `finddevice`,
and the lobby games `lobbytest`, `splattag` and `relaycolor`
(`target.py` is vendored beside them for `color_quest`).

## `<sim-room>`

`sim-room.js` wraps `<wand-sim>` (unchanged) with output panels on one
virtual ESP-NOW bus (`js/bus.js`) and clock (`js/clock.js`). `index.html`
uses it. The wand runs the real `espnow_manager.py` over a bus-backed
`espnow` shim (`py/shims/espnow.py`), so dicts go out as JSON and are
classified as on the device; each device gets its own MAC through
`network.WLAN().config('mac')`.

Panels appear from the loaded game's capabilities (`get_capabilities()`:
`lobby_game`, `local_splats`, `splats_min`, `splats_max`, `uses_display`,
`has_display_file`). New panels register with `SimRoom.registerPanel(id,
{slot, title, wants, create, update, hide})`.

The room re-dispatches `<wand-sim>`'s events and passes through its
`autostart`, `profile`, `start()`, `stop()`, `restart()`, `showOverlay()`
and `hideOverlay()`, so a host can use it in place of `<wand-sim>`;
ChatBroadcast's preview and example detail view do. It also emits
`room-radio` (`detail` is `{ text, type }`, one line per lobby game `pw_*` frame
on the bus), and each icon display's prints arrive as `display-print`
(`detail` is `{ text, mac }`, composed, bubbling).

The simulator draws no log, console, serial or radio text. Every such line
leaves as an event (`sim-log`, `sim-error`, `display-print`, `room-radio`,
`sim-enow-sent`) for the host to show; ChatBroadcast shows them in its
Developer mode footer, and `index.html` in a `<pre>` under the room.

- **Icon displays:** devices of their own beside the wand, each with its
  own MAC (`02:00:00:00:0d:01` up), up to 4. One starts as a placeholder;
  a click wakes it, and each boots its own Pyodide running
  `py/icon_host.py` (IconDisplay/main.py's idle loop, without `main()`),
  drawn with iconmaker's `renderPreview`. A game with a display file
  (`vendor/display/games/<game>.py`, or the `displaySource` property)
  wakes every display, adding one if there are none, and the room unicasts
  `start_game` to each; a game without one takes away the display it added
  and sends `stop` to the rest. Advanced mode adds and takes away displays,
  and "See all wands" shows them too; simple mode shows them only while
  the game uses them.
  `renderPreview` is imported from
  `../BroadcastCode/ChatBroadcast/iconmaker/`, so serve `Bag3/Code/` (from
  `Simulator/` alone the panel falls back to plain squares and warns).

- **Splats:** for a lobby game (`SPLATS_MIN`), the wand's Splats are drawn
  under the wand in its pad, one per paired Splat (the `wand_splats`
  setting; none, none drawn); a click on one presses it. See "Lobby games"
  below.
- **Advanced mode only** (the `advanced` attribute): a "Splats on this wand"
  card (count and "in reach" boxes) for a lobby game, and, for a lobby game
  or any game whose `wands` setting is more than 1, a bar saying how many
  other wands are playing, with "+ Add a wand" and "See all N wands", which
  opens every wand side by side.

Not simulated: heap and fragmentation, compile size, radio timing and BLE
pacing.

### Settings

`<sim-room>`'s `settings` property carries what the game code does not:
`{ wand_splats, wands }`. `wand_splats` (0–2, default 1) is how many Splats
each wand starts a newly loaded game with; `wands` (1–4, default 1) is how
many wands the game is for. ChatBroadcast reads them from the chat model's
`[GAME_SETTINGS: {...}]` marker and hides it from the chat. Set them before
`source`. The wand firmware reads neither; a game learns its Splats from
`net.local.count`.

## Lobby games

A game that declares `SPLATS_MIN` runs as `MockWand/main.py` runs it: the
wand builds its `splatpair.SplatPairing`, `lobby_game.enter()` finds a lobby or
opens one, and `play()` gets the `lobby_game.Net` as its eighth argument
(`runtime._run_lobby`). All of it is the vendored code: `lobby_game.py`,
`pwire.py`, `splatpair.py`, `pairing.py` and `splat_api.py`.

What stands in for what:

- **BLE:** `py/shims/splat_hub.py` replaces `splat_hub.py`,
  `splat_link.py` and `ble_splat.py`. Its links are ready unless unplugged
  (the "in reach" boxes, advanced mode), so `splat_api.SplatGroup`, the pairing glow and
  `net`'s ready mask (`splat_lost` / `splat_back`) run unchanged. Writes
  (color, sound, note, off) are drawn on the Splats; a click on one is a
  button press on the Splat, held at least 250 ms.
- **Pairing:** the wand holds `wand_splats` Splats (`runtime.set_game_splats`),
  set when a different game or setting loads. The advanced card's −/+
  changes it until then (and restarts the game). MACs are
  `5A:00:<wand's last two bytes>:00:<i>`.
  There are no Splat cards, `/pairing.json`, `pw_who` claim checks or the
  30 s connect deadline.
- **Other wands:** a game has none unless `wands` is more than 1 or
  "+ Add a wand" adds one (advanced mode). Each starts as a placeholder (an
  outline wand with "?" on its screen) that runs nothing and is not on the
  radio. Clicking it starts another `<wand-sim>` running the same game, on
  the room's bus and clock with its own MAC (`02:00:00:00:0A:02` on) and
  Splats, so every wand runs the vendored `lobby_game.py` and the game's own
  `play()`. A game that is not a lobby game gets other wands only from
  `wands`; they run its `play()` on the same bus, with no Splats. Each
  boots its own Pyodide. New code reaches the running ones; a game for a
  different number of wands, or one that neither is a lobby game nor sets
  `wands` above 1, starts over.
- **Protocol peers:** `js/peers.js` virtual peers speak `lobby_game.py`'s `pw_*`
  frames (find, lobby, join, start, heartbeat with the ready mask, pooled
  `pw_cmd`, `pw_evt`, `pw_msg`, leave, end, `q` dedupe) and run no game
  code. `js/headless.js` and the tests use them; the room does not. Where a
  game needs the other wands to act, a short script in `js/peers.js`
  (`GAME_SCRIPTS`) plays their part: `lobbytest`'s follower button and
  leader lighting, `relaycolor`'s token passing.

In a room the wand's ticks mirror the room clock
(`time_patch.set_clock_anchor`, re-synced every second by `js/pyboot.js`
`attachWand`) rather than calling into JS on every `ticks_ms()`.

Pyodide loads with WebAssembly's JSPI hidden (`js/pyboot.js`
`loadPyodideNoJspi`), the path it takes under Node. With JSPI, Pyodide
0.27.0 on Chrome 152 stops with a fatal "function signature mismatch" or
"invalid address in funcref table" after about a minute of lobby game play.

## Headless runs

`tools/sim_run.mjs` runs a lobby game in Pyodide under Node, with no
browser (`js/headless.js`): the same wand, peers and Splats on a bus and a
clock running 4x real time.

```bash
node Bag3/Code/Simulator/tools/sim_run.mjs --game splattag --seconds 20
node Bag3/Code/Simulator/tools/sim_run.mjs --file my_game.py --verbose
```

Three scenarios: **lead** (the wand leads, follower peers fill the lobby to
`SPLATS_MIN`, the wand's button starts it, random Splat and button presses
for `--seconds`, then the stop card), **follow** (a leader peer runs the
game with the wand in it, then ends it) and **lost** (the leader goes
silent). It reports exceptions, and an unhandled `end` or `leader_lost` when
`play()` does not return after the leader ends the game or goes silent;
exit 1 on either. `ChatBroadcast/tools/prompt_eval.mjs` runs every generated
lobby game through it (`simRun`), and `prompt_eval.mjs --self-test-sim`
checks that on a good and two broken games.

Pyodide comes from its npm package: `PYODIDE_DIR`, or fetched once with
`npm pack` into the OS temp dir.

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

Games and verbatim libs are copied into `vendor/` from
`Bag3/Code/BroadcastCode/MockWand` and its `lib/`, since Pyodide can't read
the real filesystem live and `vendor/` is what it actually imports:

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
- `test_radio.py` / `test_icon_host.py` — the radio stack and capabilities,
  and the display host running IconDisplay's goalrace.
- `test_lobby_game.py` — lobby games on the wand: lobby, start, pooled
  commands, Splat presses and the ready mask, against hand-written peer
  frames.
- `node --test tests/js/*.test.mjs` — bus, clock and payload helpers, and
  the virtual peers against each other (`peers.test.mjs`).
- `node tools/sim_run.mjs --game lobbytest` — a lobby game end to end,
  headless (see "Headless runs").
- `node tools/room_smoke.mjs` — Playwright: goalrace in `<sim-room>`, an
  icon display is added and reacts to `goal`. Serves `Bag3/Code/`; Pyodide
  is answered from a local copy of its npm package (see the script header).
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

## ESP-NOW

The wand runs the vendored `vendor/lib/espnow_manager.py` (transformed like
the other libs) over `py/shims/espnow.py`. Without a bus (plain
`<wand-sim>`) the radio is two halves that don't meet; inside `<sim-room>`
both halves go over the room's bus.

**Outgoing.** Every frame goes through `sim_state.radio_send()`, which
reports it through `sim_state.emit_enow_sent()` (kind `broadcast` or
`send`; the element emits it as `sim-enow-sent`) and, when a host set `sim_state.set_radio_tx()`,
hands it to the bus. Unicast needs the peer added first, as on the device.

**Incoming.** The advanced block's "Heard from the caller" buttons call
`sim_state.enqueue_enow()`, which encodes the message as the hub would send
it (`sim_state.encode_panel_message()`: a word `w` becomes `{"type": w}`,
`start_game` carries the loaded game's name, JSON text goes out as is, a
`raw` message keeps its bytes) and delivers it from `PANEL_MAC`, over the
bus when there is one. A game reading a raw payload needs real bytes
(`freeze_dance.py` compares against `MSG_GO = b"FD_GO"`), so `wand-sim.js`
builds a hex-escaped Python bytes literal rather than passing a JS string.
The vocabulary per game is `RADIO_BY_GAME` in `js/controls.js`.

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
  `actions.py`, `battery.py`, `buzzer.py` (AST-transformed sync→async),
  synced from MockWand/lib.
- **Verbatim, transformed**: `espnow_manager.py` (from MockWand/lib).
- **Faked wholesale**: `lis2dw12`, `max17048`, `opt3002`, `pn532`,
  `nfc_reader`.
- **Platform shims**: `machine`, `neopixel`, `time.sleep_ms` / `ticks_*`,
  `_thread`, `network`, `espnow`, `ubluetooth`, `micropython`.
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
  vector from the `POSES` table rather than an in-between one. The mapping is
  in `setPadTilt`'s docstring.
- Gesture animations run for the duration `fireMove()` reports, not a fixed
  design value, so the wand stops moving when the accelerometer does.
- `<wand-sim>` attributes: `game`, `autostart`, `controls`,
  `source`, `muted`, `advanced` (shows the axis readout, the custom tag /
  radio message drawer and the hardware dials; off by default, so an
  embedding host opts in explicitly).
  Property `pyodide` (after `sim-ready`).
  Events: `sim-ready`, `sim-loaded` (`detail.capabilities`), `sim-frame`, `sim-print`, `sim-log` (`detail.text`, one console line), `sim-error` (`detail.phase`
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
- ChatBroadcast (`Bag3/Code/BroadcastCode/BroadcastBox/ChatBroadcast/`) embeds this
  element directly from `../../Simulator/wand-sim.js`, so both trees must be
  served from a common root (`Bag3/Code/`) rather than from ChatBroadcast's
  own directory.
