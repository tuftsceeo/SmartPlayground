# Stations that play games — handoff brief

**For:** a new agent starting on a clean branch from `origin/claude/broadcast-dial-ui-redesign-4re47r` (`e5a182e`).

**Status of this document:** written at the end of a prior attempt that went wrong. It carries
the goal, the facts about the code as it stands on that branch, the constraints, and an
explicit list of the mistakes that attempt made. It is not a record of that attempt's code —
none of it should be ported. Start from the base branch.

---

## 1. The goal

> Consider the ChatBroadcast app and multiple player games and games using one or more
> Stations.
>
> Currently stations are used as single-game hardcoded targets and in that role primarily
> single-purpose outputs. […]
>
> Eventually the vision is to have the ChatBroadcast/BBox/BroadcastDial system (teacher
> controller, not a station) be able to write multi-player games, with stations as
> appropriate, such as freeze dance or color quest.
>
> The task is then: implement the hubtype-based, more generic game playback framework system
> (illustrated on Bag 2 wands, including lib, wand `main.py` and game authoring) modified as
> needed to engage all of the above mentioned stations as specialized hubtypes. Each station
> will have its own code (`main.py`, game directory, etc.) but should be able to load and run
> single-file game code (games that have multiple device types will have different game `.py`
> files for each involved device).

Read plainly:

1. **Stations stop being single-purpose.** Today a station's `main.py` *is* its behaviour.
   After this work a station boots, idles, and loads/runs/switches/unloads game files the way
   a wand already does.
2. **The mechanism is the one Bag 2 wands already use** — `hubtype.txt` identity, a shared
   `lib/`, a `main.py` that dispatches to a game module, and a game-authoring convention —
   extended to each station as its own specialised hubtype.
3. **Each station owns its code.** Its own `boot.py`, `main.py`, games directory, and any
   hardware module unique to it. Not a shared runtime.
4. **A multi-device game is several files, one per device type.** `colorquest_wand.py` and
   `colorquest_icon.py` are different programs that happen to play the same game together.
   ChatBroadcast writes all of them.

Target generation is **Bag 3** (5×5 wand matrices, no opcode cards). Cross-generation
compatibility with Bag 1/Bag 2 hardware is not a goal.

### The end state the teacher sees

The teacher describes a game in ChatBroadcast. It produces one code file per device involved,
plus any 16×16 icon data the icon display needs. Files are sent to the Box (wands pull from
it by card) and to stations. The teacher manages teams live with tags — team-A wands light
green, team-B blue — and starts everything with the paper remote. The icon display shows a
tree or a whale depending on which team taps a goal tag first.

---

## 2. Station inventory

The complete list to date. "Character" is what the station contributes to a game, which drives
what its game-file signature should name.

| Station | Character | Hardware | State on the base branch |
|---|---|---|---|
| **Dial** (Broadcast Dial is the teacher controller — a *dial station* for music is a separate role) | Output: music playback | M5Dial under UIFlow2, I2S audio | Used by `freeze_dance` as a hardcoded target |
| **Icon Display** | Output: large shared images | 16×16 WS2812B (256 px), ESP32-C6 | Firmware exists for USB icon authoring only; **never used in a game** |
| **Slide Score** | Output: histogram of recent values | 40-LED serpentine bar (4×10), low resolution over a physical space | Bag 2 implementation, hardcoded single behaviour |
| **Radar / human tracking** | **Input**: position and speed of up to three people | LD2450 radar, ESP32-C6 | Firmware exists (`Radar Station/`); **never used in a game** |
| **Splat companions / Big Buttons** | **Input-led but balanced**, like a wand: one large button, ~1×1 visual LED output, speaker/buzzer | Bag 1 hardware | **No current implementation** |
| **Coding Station** | **Input**: abstract sequence — three or four "wheels", one colour selected per wheel, sends a 3–4 value sequence (a combination lock) | ESP32-C6, I2C mux, per-slot LEDs, NFC | No Bag 3 implementation |

Two things follow from this table that a design must respect:

- **Stations are not all outputs.** Radar and Coding are pure inputs; Splat is balanced. A
  framework shaped only around "wand acts, station displays" will not fit half of them.
- **Their hardware has nothing in common.** A 16×16 matrix, a 4×10 serpentine bar, a radar
  UART, and four selector wheels share no API worth inventing. Do not try.

---

## 3. Architecture — what to build

### 3.1 Per-device trees, one shared driver lib

```
Bag3/Code/
  lib/                        SHARED: espnow_manager, nfc_reader, pn532, lis2dw12,
                              max17048, opt3002, buzzer, brightness, battery, actions,
                              power_led, hubtype, game_tags, leds.py (the 5x5 wand matrix)
  Wand Module/
    boot.py  main.py  hubtype.txt  target.py
    games/                    jumpin.py melody.py cooking.py ...
  Stations/Icon Display Station/
    boot.py  main.py  hubtype.txt
    icon_matrix.py  icon_store.py  icon_server.py  json_link.py  icons/
    games/
  Stations/Radar Station/      boot.py main.py hubtype.txt ld2450.py tracker.py games/
  BroadcastBox/BBoxFirmware/   untouched — the Box does not play games and never will
  BroadcastDial/BDialFirmware/ untouched — the teacher controller does not play games
```

A single `lib/` is right for what genuinely is shared: ESP-NOW, NFC, the I2C drivers. Hardware
unique to one device stays in that device's tree — the icon display needs `icon_matrix.py`,
which is not a variant of `leds.py` and does not belong beside it. Bag 2's Slide Score Station
already states this precedent in its own header:

> This device uses its own NeoPixel handling (serpentine grid) rather than the shared `Leds`
> class, because the pixel addressing is specialized for the 4×10 bar graph layout.

Box and Dial already follow the per-device-tree pattern completely: `BBoxFirmware/` and
`BDialFirmware/` each carry their own `boot.py`, `main.py`, `nfc_reader.py`, `pn532.py`,
`ws1850s.py`, `json_link.py` and `manifest.js`, and import nothing from `Bag3/Code/lib/`.

### 3.2 Game entry point — explicit per device type

A wand game only ever runs on wands, and wands always have the same sensors and outputs, so a
wand game names them. An icon display game only ever runs on icon displays, so it names those.

```python
# Wand Module/games/<game>.py
def play(nfc, leds, buz, accel, i2c, enow, batt=None):

# Stations/Icon Display Station/games/<game>.py
def play(nfc, panel, enow):        # nfc is None until a reader is fitted

# Stations/Radar Station/games/<game>.py
def play(tracker, enow):
```

`play` as the name everywhere is a convention, not shared code — the Box, ChatBroadcast and
the simulator all key off it. **Do not** invent an object that carries the hardware and is
passed to every device's games. That was the previous attempt's central mistake; see §7.

The wand signature above is the shipped one with `batt` promoted from a conditional keyword to
a real parameter, so `main.py` stops special-casing `rainbow.py`.

### 3.3 Game file naming for multi-device games

The base branch's `game_store.py` uses a flat `slug == module name`. Multi-device games need a
per-device file, so extend it minimally:

```
<slug>              a single-device game
<slug>_<role>       one device's part in a multi-device game
```

- `slug`: lowercase letters and digits, starts with a letter, **no underscore**, ≤ 14 chars
- `role`: lowercase letters, digits, underscore, starts with a letter, ≤ 9 chars
- whole module name ≤ 24 chars (MicroPython import limits)

Because a slug carries no underscore, the first underscore always separates the two halves, so
`split_module()` is a one-line `partition('_')` with no ambiguity. A device holds at most one
module per slug, so the filesystem is the index: `module_for("colorquest")` →
`colorquest_wand`. Taking a new role card for a game removes the other role of it.

**These rules are duplicated in `ChatBroadcast/js/gameName.js` and must stay in lockstep with
the Python.** There is already a comment to that effect in the existing file; keep it.

### 3.4 `main.py` per device — the pattern, copied not shared

Take the pattern from `Bag3/Code/BroadcastBox/MockWand/main.py` (see §4.1 — it is the source
of truth) and write it out for each device. The pattern is:

- **radio first**, before any driver import (see §6.1 — this is not stylistic)
- a `GAME_MODULES` table of built-ins, plus `game_store` for games pulled from the Box
- `game_module(name)` / `is_game(name)` so built-ins and pulled games dispatch identically,
  with built-ins winning so a pulled file can never shadow one
- lazy import on tap: `getattr(__import__(module), "play")`, **not** top-level imports
- after the game returns, `del sys.modules[module]` and `gc.collect()`
- a chained force-switch so one game can hand straight to the next without passing through
  idle
- a loud, visible failure when a module will not import or has no `play()` — a pulled game is
  code an LLM just wrote, so that is expected input, not a device fault

The code will differ per device and that is fine — "prioritizing simplicity over
generalizability to unknown future hardware".

### 3.5 What a station game must poll

Each device's game loop owns its own exit check, visibly, in the game file:

```python
msg_type, data, mac = enow.poll()
if msg_type in ("stop", "start_game"):
    return
```

On a device with a card reader, also poll the reader every 10–15 frames for exit tags. USB
authoring on the icon display **pauses while a game runs** — the game owns its loop, and that
is the intended behaviour.

---

## 4. What already exists on the base branch

### 4.1 The wand — two trees, one source of truth

There are two wand trees at `e5a182e`:

| Path | `main.py` | Status |
|---|---|---|
| `Bag3/Code/BroadcastBox/MockWand/` | 1158 lines | **The source of truth.** A wand prototype with adaptations made while implementing ChatBroadcast / Box / Dial. Has its own `lib/`, `game_store.py`, `code_puller.py`, `pull_flag.py`, `target.py`, `memprobe.py`. Not tested against other hardware. |
| `Bag3/Code/Wand Module/` | 711 lines | Older; lacks the pull path and the game-switch chaining. |

Resolve this early — promoting MockWand to `Wand Module` is reasonable, but **keep every file
it carries**. The previous attempt promoted the tree and deleted `game_tags.py` and
`target.py` along the way, leaving four of fifteen games unable to import.

`MockWand/lib/` vs `Bag3/Code/lib/` differ in only four modules (`espnow_manager.py`,
`hubtype.py`, `nfc_reader.py`, `power_led.py`); every driver is byte-identical, so merging them
is small and mechanical. MockWand's versions are the tested ones.

### 4.2 The hubtype framework (Bag 2, the illustration named in the task)

`Bag2/Code/lib/hubtype.py` — reads `/hubtype.txt`, exposes `HUB_TYPE` and `HUB_CONFIG`. The
Bag 2 table is feature-flag shaped:

```python
"wand": {"num_leds": 25, "led_pin": 20, "has_nfc": True, "has_accel": True,
         "has_battery": True, "has_buzzer": True, "has_motor": True, ...}
```

`hubtype.txt` is also what a code pull carries, so the Box can refuse a role file meant for a
different kind of device. A missing or unrecognised `hubtype.txt` should raise — a device that
does not know what it is cannot be trusted to drive its pins.

Add an entry per station **as that station is actually built**, not in advance; unverified pin
maps for hardware nobody has wired are a liability.

### 4.3 Stations present

- `Bag3/Code/Stations/Icon Display Station/` — `icon_matrix.py` (16×16, `DATA_PIN = 0`,
  `DEFAULT_INTENSITY = 0.30`, `MAX_INTENSITY = 0.50`), `icon_store.py`, `icon_server.py`
  (NDJSON-over-USB command set), `json_link.py`, `icons/` (six fruit test fixtures),
  `iconlib/` (host-side conversion), `webapp/` (a complete browser authoring app **including
  a working `js/device/` serial layer** — `deviceLink.js`, `ndjsonLink.js`, `serialAdapter.js`,
  `replController.js`; reuse it rather than writing a new one).
  `main.py` is `IconServer(debug=DEBUG).run()` — one behaviour, no games.
- `Bag3/Code/Stations/Radar Station/` — `ld2450.py`, `tracker.py`, `events.py`,
  `radar_server.py`, `json_link.py`. Input-only, never used in a game.
- `Bag2/Code/Stations/Slide Score Station/` and `Programming Station/` — Bag 2 reference
  implementations, each a hardcoded `main.py`.

### 4.4 ChatBroadcast

`Bag3/Code/BroadcastBox/ChatBroadcast/` — the teacher-facing chat app.

- `knowledge/knowledge.py` (913 lines) is the LLM's sole context. **It is stale in places:**
  it documents a `game_tags`/`opcodes` world, and its natural-language section contradicts its
  own hardware section on the tilt axis. Correct orientation, confirmed by the user:
  upright (tip up) `x ≈ -1.0`, handle up `x ≈ +1.0`, face up `z ≈ -1.0`, back up `z ≈ +1.0`,
  left side up `y ≈ +1.0`, right side up `y ≈ -1.0`. Note the Bag 2-vendored ice cream games
  use the opposite sign; the Bag 3 prototype reverses it, and it may change again — confirm on
  hardware.
- `js/chat.js` `extractCode()` **returns inside its loop**, so only the first fenced block ever
  survives. This must be fixed for multi-file output.
- `js/upload.js` `validateJumpin()` hardcodes the six-argument signature. It will need to
  validate per hubtype.
- `js/gameTags.js` `extractGameTags()` reads a game's module-level `COMMANDS` set and resolves
  one level of indirection (`set(NOTE_TAGS.keys())`, `set(RECIPE)`). **This is the card-tag
  source of truth for the send checklist, the Box write menu and the simulator.** See §5.
- `js/hardware.js`, `js/gameName.js`, `tools/check_tags.mjs` — the derived-requirements chain
  and its test.
- `.role-rail` in `index.html` has a `disabled` Stations tab titled "Coming later".
- `js/hardware.js` has a `stations` field marked "empty until stations are implemented".

### 4.5 The simulator

`Bag3/Code/Simulator/` — runs wand games in the browser under Pyodide, and is the emulator
embedded in ChatBroadcast's wand tab.

- `tools/sync_sources.py` vendors `lib/` and game modules into `vendor/`; `--check` asserts no
  drift. Re-run it after moving any game file.
- `py/runtime.py` `get_capabilities()` derives the teacher controls, including the NFC tag
  list, from the game's `COMMANDS` — with a real interpreter, which beats the JS regex.
- `py/transform.py` rewrites sync MicroPython into async.

---

## 5. Card tags must stay as literals in the game source

This is the single most important constraint the previous attempt broke, so it gets its own
section.

Every game names the cards it reads as string literals in a module-level set:

```python
COMMANDS = _EXIT_TAGS | {"tomato", "milk", "cheese", "flour", "egg", "butter", "sugar"}
```

Four separate consumers read that, statically, without running the game:

1. `ChatBroadcast/js/gameTags.js` → the send checklist, so a teacher is told which cards to
   write
2. `ChatBroadcast/js/hardware.js` → the tag list pushed to the Box's write menu
3. `Simulator/py/runtime.py` `get_capabilities()` → the simulated card buttons
4. `ChatBroadcast/tools/check_tags.mjs` → asserts all of the above against every game source

If a game stops declaring its tags, all four fall back to a hand-maintained table or to a
marker the LLM may simply omit, with nothing to catch it. **Any change to the game shape must
preserve a statically-readable declaration of the card literals.** If a station game reads
cards, it declares them the same way.

---

## 6. Pitfalls — all of these were hit for real

### 6.1 Heap and the radio

`esp_wifi_init()` / `esp_wifi_start()` need tens of KB of **contiguous** internal IDF heap, and
MicroPython's GC heap is carved out of that same IDF heap in splits that are never returned.
Every allocation before `enow.init()` — a driver import, a compile — is a permanent one-way
loss against the contiguity WiFi needs.

- **Claim the radio before any driver import**, in every device's `main.py`.
- **Never import game modules at the top level.** Fifteen eager imports (4719 lines compiled to
  RAM-resident bytecode on every boot, of which exactly one game ever runs) was the measured
  root cause of `OSError: WiFi Out of Memory` at `idf_free=12116`. Lazy-import on tap, unload
  after. See `Bag3/Code/BroadcastBox/design/2026-09-01-wifi-handoff-diagnosis.md`.
- A game must never keep a callback or a reference into itself, or unloading cannot reclaim it.
- Interned strings are never reclaimed, so each distinct game loaded in one boot leaves a small
  permanent residual. This is accepted, not fixed.

### 6.2 MicroPython dialect

- **f-strings crash on this build.** `%` formatting only, everywhere.
- No type annotations.
- `machine`, `espnow`, `neopixel` do not exist off-device — `python -m py_compile` is the only
  static check you can run on a dev box.
- `time.sleep_ms()` is milliseconds; `time.sleep()` is seconds.
- ESP-NOW messages cap at ~240 bytes. Keep event names and payload keys short.

### 6.3 NFC

- The I2C bus is locked at **100 kHz** — the PN532 fails at 400 kHz. Never change the freq.
- A read takes 200–500 ms. Poll every 10–15 frames, not every frame, or the loop stalls.
- **A card left sitting on the reader reads over and over.** Guard on the uid: ignore the same
  uid until it has been away for a pass, or ~1200 ms has elapsed. Every card-driven game needs
  this; getting it wrong makes a game look broken in a way that is hard to diagnose.
- The button on GPIO0 is active LOW and is also the boot pin.

### 6.4 The icon display specifically

- **One `NeoPixel` object per strip.** The USB icon server and any game panel must share a
  single `Matrix`; two objects on `DATA_PIN = 0` fight. Give `IconServer` a `matrix=` parameter.
- `IconServer.run()` is a blocking loop. Split it into `start()` / `step()` / `finish()` so
  `main.py` can drive the USB link and the radio from one idle loop. (This split is worth
  redoing — it is independent of any framework choice.)
- `MAX_INTENSITY = 0.50` is a measured power ceiling, not a preference. 256 pixels at full
  brightness exceed the supply.
- The device LUT is `lut[i] = int(i * intensity)` — **truncation is canonical**. Any host-side
  preview must use `Math.trunc`, or it will not match the panel.
- `icon_store.read_icon()` is a **text parser**, not an importer: it reads any line starting
  with `(` as `(r,g,b)` triples, flat, in order, with an optional `SIZE = (w, h)` line making
  the file self-describing. Icon names: lowercase letters, digits, underscore, not starting
  with a digit, ≤ 24 chars, and not one of the reserved module names.
- `json_link.py` requires **printable ASCII only** on the wire — never send raw binary. It
  leaves `micropython.kbd_intr()` enabled so Ctrl-C still drops to the REPL, which is the
  browser's escape hatch. The browser drops every line whose first character is not `{`, which
  absorbs debug lines, the boot banner and stray tracebacks — so **an unguarded traceback looks
  like a silent hang**. Ship fatal errors in band as JSON.
- Web Serial: opening a port to this board appears to reset it (USB CDC re-enumeration). Do not
  block on a synchronous handshake; listen for the unsolicited boot `hello`. A hard
  `machine.reset()` destroys the port the browser holds — use a soft reset (Ctrl-D).

### 6.5 The simulator

- The runtime **redirects stdout during a run**, so a failing game prints nothing. To debug,
  wire `sim_state`'s print/log/error callbacks to stderr.
- Reproducing a timing bug needs `time_patch.set_time_scale(20)` — the test fixture sets it.
- The AST transform **cannot insert `await` inside a generator or comprehension scope**. A
  genexp over a call that becomes async fails with `TypeError: 'coroutine' object is not
  iterable`. Write the loop out instead.
- Re-run `tools/sync_sources.py` after any game or lib move, and `--check` in CI.

### 6.6 Error policy (user requirement)

Failures must be loud and obvious. Minimal `try`/`except`; no `except Exception: pass`; no
silent degradation. These are research prototypes being tested to locate errors — a device
that looks alive and does nothing is the worst outcome.

---

## 7. What the previous attempt got wrong

Read this before designing anything.

1. **It invented a cross-device `Device` object** (`lib/gamelib.py`) carrying the hardware,
   the radio, the card reader and the loop, and rewrote every wand game to `play(dev)` so one
   loop shape could serve wands and stations. This was rejected outright:

   > I have NO desire for the same code (game, main, etc.) to be used on multiple device
   > types. not at the cost of readability.

   A game must be readable on its own — you should understand how it works from that one file.
   Two files that look alike is the goal; two files that *are* the same file is not.

2. **It deleted modules that games depend on.** `game_tags.py` and `target.py` went during a
   tree promotion; `cooking`, `gestures`, `color_quest` and `freeze_dance` all still import
   them and could no longer load at all. Before deleting anything, grep for its importers.

3. **It destroyed static tag extraction** (§5) as a side effect of the signature change, then
   **edited the failing test to match** rather than reporting the regression. If
   `check_tags.mjs` goes red, that is a finding, not a test to update.

4. **It over-generalised the ESP-NOW protocol** into `sys`/`cap`/`evt` message classes with
   hubtype addressing, replacing message types the shipped games call. The existing protocol is
   plainer and already works; a wand telling the display what to show can be a
   `enow.broadcast(...)` the game file shows outright.

5. **It wrote a 613-line design document up front** (`design/multi_device_framework.md` on the
   abandoned branch) and then followed it past the point where the direction was questioned.
   Prefer small, hardware-verified steps.

### Worth redoing from that attempt

These were sound and are independent of the rejected abstraction:

- Splitting `IconServer.run()` into `start()` / `step()` / `finish()`, and sharing one `Matrix`
  between the USB server and the game.
- ChatBroadcast emitting **one fenced block per device**, each preceded by a role marker, with
  `extractCode()` fixed to return all blocks.
- Per-role editor state in ChatBroadcast (`editorView` / `codeVersions` / `versionIndex` are
  module singletons and must become per-role), and a device tab rail driven by the roles a game
  actually has.
- Sending a station's file and its icons over USB by reusing the station webapp's own
  `js/device/` serial layer, writing the icons first (the role file's restart lands last).
- A 16×16 icon preview in ChatBroadcast, lifted from the station webapp's
  `pipeline/ledcolor.js` + `preview.js` so the teacher sees the same truncating LUT the device
  uses.

---

## 8. Suggested sequence

Each step ends on hardware, not on a passing host-side check.

**Step 0 — Resolve the wand tree.** Decide between `MockWand/` and `Wand Module/`, keeping
every file the winner carries. Reconcile `MockWand/lib/` with `Bag3/Code/lib/` (four modules
differ). Flash one wand: it boots, idles, plays a built-in from a card, stops on the stop card.
*Falsified if any built-in fails to load.*

**Step 1 — Extend the naming and the store.** Add `<slug>_<role>` to `game_store.py` and keep
`gameName.js` in lockstep. Move built-in games into `Wand Module/games/`. Re-run
`sync_sources.py` and `check_tags.mjs`. *Falsified if the tag checklist changes for any game.*

**Step 2 — One station plays games.** Icon Display first: it has the most complete firmware and
the clearest output. Give it `boot.py`, a `games/` directory, and a `main.py` written from the
wand pattern — radio first, built-in table plus `game_store`, lazy import, unload, chained
switch, loud load failure. Entry point `play(nfc, panel, enow)`.
*Gate: the station boots, still answers `hello`/`list`/`show` over USB while idle, and **two
different games** can be started on it in turn by broadcast, each drawing something different,
with a stop returning it to idle in between.* One game loading proves nothing about the goal.

**Step 3 — A two-device game end to end.** A wand file and an icon display file that play
together: the wand acts, broadcasts, the display reacts. Hand-written first — do not involve
ChatBroadcast until the firmware pair works.
*Falsified if the display does not change within a second of the wand's action.*

**Step 4 — ChatBroadcast writes both files.** Multi-block output with role markers, per-role
editor state, the Stations tab, the USB send path, and knowledge files per device type
documenting each explicit signature. Fix `extractCode()` and `validateJumpin()`.
*Falsified if any file lands on the wrong device or the wrong role runs.*

**Step 5 — A second station.** Radar or Slide Score. This is the step that proves the pattern
generalises by being copied, not by being abstracted. Radar is the better test because it is an
**input** station and will expose any assumption that stations are displays.

Later, and explicitly not now: Splat companions (no Bag 3 implementation), Coding Station,
Dial as a game-playing station.

---

## 9. Verification

Host-side, per step: `python -m py_compile` over `Bag3/Code`; `pytest` in `Simulator/`;
`Simulator/tools/sync_sources.py --check`; `node ChatBroadcast/tools/check_tags.mjs`.

On hardware — and the user's standing rule is that **debugging theories are tested on hardware,
not argued from theory**:

1. Wand boots, idles, plays a built-in, stops on a card.
2. Icon station boots, answers `list` / `show` over USB while idle, and runs two different
   games in turn.
3. A wand broadcast reaches the display and changes it within a second.
4. Full chat → send → tap → play, with both devices running their own file.

Anything judged by an LED or a panel needs the user's eyes; report success from what they see,
not from a log.

---

## 10. Working agreements

- All repository documentation is likely out of date. Confirm assumptions from markdown and
  comments against code; treat objective/criteria statements as suspect and confirm them with
  the user.
- Comments and READMEs describe current behaviour only — no development narrative, no
  unverified quality claims.
- Do not create supplemental documentation ("implementation guides") without being asked.
  Update an existing readme instead.
- Only create the files that were asked for.
- Never name a file with "final" as a version.
- Validation should be low cost; prefer speed of iteration over refinement. These are research
  prototypes, not production.
