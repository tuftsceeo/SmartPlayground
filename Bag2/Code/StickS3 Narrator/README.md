# StickS3 Wand Narrator

An accessibility companion: a small M5Stack StickS3, worn or clipped, that
**listens** for the ESP-NOW broadcasts already flying between the hub (or
M5Paper Remote) and the wands -- `start_game`/`stop`, plus Freeze Dance's own
Go/Freeze/Dance calls -- and **speaks** them out loud ("Freeze Dance",
"Go", "Stopped") plus shows the word in large text on its color LCD.

Built for a vision-impaired or blind student: today the only feedback a
game is running is visual (the wand's 5x5 LED matrix, or a teacher's
screen). This gives that same information as sound -- plus, for a sighted
helper glancing over, on-screen text in **landscape** (not StickS3's native
portrait), sized as large as each label allows, and colored to match
whatever the wand's own LED matrix is actually showing at that moment.

**Status: prototype, not yet bench-verified.** No StickS3 hardware was in
hand while writing this -- see the checklist at the bottom before trusting
it on a real device.

## Why this doesn't touch wand/hub firmware at all

This device only calls `enow.poll()` -- it never sends. It reuses the exact
`start_game`/`stop` ESP-NOW payloads already defined in
`../lib/espnow_manager.py` (bundled here unmodified), so it works with any
Bag2 or Bag3 wand or hub as-is. Because nothing on the wand/hub side changes,
this does **not** trigger the Bag2 verification gate in `../../../AGENTS.md`
-- but the *device itself* still needs real hardware testing (see below).

## Tier 0 vs. Tier 1 (why this only says game names + Freeze Dance calls)

- **Tier 0 (this build):** narrate `start_game` / `stop`, plus Freeze
  Dance's own Go/Freeze/Dance/Ready calls (see "Broadcast coverage" below).
  Zero wand firmware changes -- every one of these is already broadcast
  today by existing, unmodified wand/hub code; the Narrator just listens.
- **Tier 1 (not built):** narrate what's actually on the LED matrix --
  colors, shapes, correct/wrong flashes -- as games run. That needs a
  narration-event broadcast added inside each of the ~16 wand game modules
  (`Bag2/Code/Wand Module/*.py` and `Bag3/Code/Wand Module/*.py`), which is a
  hardware-agnostic game-logic change per the wand edit rule in
  `../../../AGENTS.md` -- meaning it reaches fielded Bag2 wands and needs a
  PR + real hardware verification, not something to merge from code review
  alone. Deliberately out of scope for this pass.

## Broadcast coverage

An audit of every ESP-NOW message actually broadcast-to-all in the current
(non-`old_stuff`) codebase, and what the Narrator does with each:

| Source | Message(s) | Narrator behavior |
|---|---|---|
| `espnow_manager.broadcast_start_game` | `{"type":"start_game","name":...}` | **Narrated** |
| `espnow_manager.broadcast_stop` | `["stop"]` | **Narrated** |
| `Wand Module/freeze_dance.py` (caller wand), `send_raw(BROADCAST_MAC, ...)` | raw bytes `b"FD_GO"`, `b"FD_FREEZE"`, `b"FD_DANCE"` (`b"FD_RESET"` is in the receive-side vocabulary but no caller path sends it as of this writing) | **Narrated** (as "Go"/"Freeze"/"Dance"/"Ready"), de-duped against the 5x repeat-send in `phrases.py`'s `FREEZE_DANCE_CALLS` + `main.py`'s `_RawDebounce` |
| `espnow_manager.broadcast_status_poll` / `broadcast_status_report` | status chatter between hub and wands | Deliberately silent -- not a player-facing event |
| `espnow_manager.broadcast_find_device` | targeted identify ping (sent as a broadcast frame, but scoped to one wand's MAC) | Deliberately silent -- for one wand, not a group event |
| `color_quest.py` → `send_scan_request` | `{"type":"scan_request"}` | Deliberately silent -- internal handshake to the Programming Station, not player-facing |
| `Stations/Programming Station/main.py` → `mgr.broadcast(commands)` | JSON list of scanned color tags, e.g. `["turnred","turnblue",...]` | **Not handled -- open question, not a silent decision.** This is genuinely broadcast-to-all and genuinely game-relevant (it's what fires Color Quest across a whole class), but narrating it means picking specific color words out of a multi-reader list, which is the same "specific in-game content" territory as the Tier 1 LED-narration work above. Flagging rather than guessing at the right phrasing. |

If new broadcast-to-all message types get added anywhere in the wand/hub
codebase later, re-run this audit (`grep -rn 'send_raw(BROADCAST_MAC\|\.broadcast('`
across `Bag2/Code` and `Bag3/Code`) rather than assuming this table still
covers everything.

## Icon colors -- matching the LED matrix, not guessing at it

`narrator_ui.py`'s on-screen color for each game/call is matched to the
**entry icon** the wand's LED matrix actually shows -- found by reading
each of the 14 `Bag2/Code/Wand Module/*.py` game modules directly (plus
Freeze Dance's Go/Freeze/Dance/Ready calls), not assumed. The real finding
worth knowing: **not every game has one.**

| Tag | Matched color | Why |
|---|---|---|
| `cooking` | Amber | Breathing amber flame icon, ready-to-scan |
| `melody` | Teal | Music-note icon, ready-to-scan |
| `simpleicecream`, `multiicecream` | White | Empty-cup fill |
| `freezedance` | White | Breathing white arrow, role-select |
| `shakerainbow` | White | Fills solid white (level 0) the instant the game starts |
| `colorquest` | Dark green | Per `Live_Page/wand_icons.html`'s "waiting between rounds" -- the only one of this table not independently confirmed by reading `color_quest.py` itself in this pass |
| `fd_go` / `fd_freeze` / `fd_dance` | Green / Red / Purple | `freeze_dance.py`'s own `STATE_GO`/`STATE_FREEZE`/`STATE_DANCE` colors |
| `fd_reset` | White | Approximation -- the real "ready" color depends on caller (amber) vs. player (yellow) role, which this device can't know; uses the white breathing-arrow color both roles' waiting states share instead of guessing a role |
| `jumpin`, `shake`, `jump`, `sound`, `nfcsound` | **No match (neutral default)** | The matrix genuinely starts **off** in these games -- it only lights up once you press the button, shake, or hold a note. There is no icon to match at the moment the game starts; matching one would be fabricating a color the wand never actually shows then. |
| `rainbow` | **No match (neutral default)** | Shows a repeating multi-color rainbow pattern, not one color |
| `gestures` | **No match (neutral default)** | Entry visual is mode-dependent (training/play); not pinned down in this pass |

"No match" isn't a bug to fix -- it's `phrases.py`'s `GAME_ICON_COLORS`
correctly reporting `None` rather than inventing a color those games don't
show. If a game's actual entry visual changes later, this table (and
`GAME_ICON_COLORS` / `FREEZE_DANCE_CALL_COLORS` in `phrases.py`) needs a
manual re-check against the code -- nothing enforces it staying in sync.

Colors are hand-copied from `../lib/leds.py`'s palette and scaled up (same
gain factor `Live_Page/wand_icons.html` uses) since that palette is
deliberately dimmed for outdoor NeoPixel visibility and would look muddy as
on-screen LCD text.

## Font size + line layout -- simulated, not guessed

Early on this picked a font size from a flat "characters × some average
glyph width" formula, which was conservative enough to leave ~20-40% of the
screen width unused on most one-word labels and never considered splitting
a two-word label across two lines for a bigger font. `assets/_simulate_text_fit.py`
replaces that guess: it renders every label the Narrator can show with the
real DejaVu Sans TTF (via Pillow) at each of the firmware's fixed bitmap
sizes (9/12/18/24/40/56/72), measures actual pixel width, and for multi-word
labels tries every line-split point to see whether stacking two lines beats
the biggest single-line fit. A 10% safety margin is baked in against the
TTF being a slightly different width than the real on-device bitmap font.

Run it (`pip install pillow`, needs `matplotlib` installed too for its
bundled DejaVu Sans TTF) to see the full table and get a fresh
`_LAYOUT_TABLE` dict to paste into `narrator_ui.py` whenever `phrases.py`'s
labels change:

```bash
python "assets/_simulate_text_fit.py"
```

Concretely, this took `Go` from 24pt to 72pt, `Freeze`/`Dance`/`Ready` from
24pt to 56pt, and every two/three-word label (`Freeze Dance`, `NFC Bell
Choir`, ...) from a cramped single line to two lines at 40pt.

`narrator_ui.py`'s `_LAYOUT_TABLE` is that script's output, pasted in
directly -- the runtime just looks up the exact rendered label text. If a
future label isn't in the table (a new game added after it was generated),
`_fallback_layout` falls back to the old rough single-line estimate rather
than crashing; re-run the simulator and paste a fresh table rather than
leaving a real label on the rough fallback long-term. If StickS3's UIFlow2
build turns out to expose `M5.Lcd.textWidth()` (a real on-device pixel
measurement, common on LovyanGFX-family displays but not confirmed here),
that would be a strictly better primary source than this pre-baked table --
worth swapping in if bench testing confirms it exists.

## Files

| File | Role |
|---|---|
| `main.py` | Boot entry: M5 init, ESP-NOW (receive-only), poll loop |
| `demo.py` | **Standalone bench demo -- no hub/wand/ESP-NOW needed at all.** See below. |
| `narrator_ui.py` | Landscape, auto-sized, color-matched text on the 240x135 color LCD |
| `phrases.py` | Game tag -> spoken label + WAV path; boot-time drift check against `game_tags.py` |
| `espnow_manager.py` | Bundled copy of `../lib/espnow_manager.py` (keep in sync) |
| `game_tags.py` | Bundled copy of `../lib/game_tags.py` (keep in sync) |
| `boot.py` | Same boilerplate as `../M5Paper Remote/boot.py` |
| `assets/_generate_phrases.py` | Dev-only: synthesizes the WAV clips via offline OS TTS |
| `assets/_simulate_text_fit.py` | Dev-only: measures real font-fit/line-splits, emits `narrator_ui.py`'s `_LAYOUT_TABLE` |
| `assets/speech/*.wav` | Generated output (gitignored candidates -- see below) -- upload to `/flash/assets/speech/` |

## Demo mode -- no hub, wand, or other hardware needed

`demo.py` is a second, self-contained entry point for exactly this
situation: you have the StickS3 and nothing else to trigger it with. It
never touches WiFi/ESP-NOW -- it just calls the same `NarratorUI` +
`phrases.py` functions `main.py` calls on a real packet, so what you see and
hear is exactly what the real thing does.

**It cycles through every game label, Freeze Dance's Go/Freeze/Dance/Ready
calls, and the "ready"/"stop" announcements, in order, forever.** Two ways
to control the pace:

- **If StickS3's two buttons expose the usual M5Unified names** (`M5.BtnA`
  = KEY1, `M5.BtnB` = KEY2 -- true on every other M5Stack device with
  buttons, but **not confirmed yet specifically on StickS3's UIFlow2
  build**): KEY1 advances to the next phrase, KEY2 replays the current one.
- **If those objects don't exist on this firmware**, `demo.py` catches that
  at startup, prints which mode it picked, and falls back to auto-advancing
  every 3.5s -- so the demo still runs even if that guess is wrong.

Run it without disturbing `main.py`:

```python
import demo
demo.main()
```

(from the device's REPL, after uploading `demo.py` alongside the other
files) -- or copy it over `main.py` temporarily to have it run at boot.

This needs the WAV clips generated first (see "Generating the spoken
clips" below) -- without them it'll still advance and show text, but log
"no WAV for &lt;tag&gt;" instead of playing sound.

## Generating the spoken clips

WAV files are **not** committed pre-built. Generate them locally:

```bash
pip install pyttsx3
python "assets/_generate_phrases.py"
```

This uses your OS's own offline TTS voice (SAPI5 on Windows, `NSSpeechSynthesizer`
on macOS, `espeak` on Linux) -- no cloud account, no network call -- and
resamples to mono 16-bit PCM @ 16000 Hz, the format `M5.Speaker.playWavFile()`
expects driving StickS3's ES8311 codec. Re-run it whenever `phrases.py`'s
`GAME_LABELS` / `SPECIAL_LABELS` change.

Multi-word labels are synthesized **one word at a time** and spliced back
together with an explicit `WORD_PAUSE_MS` (350ms by default) of real
silence -- asking the TTS engine for the whole phrase in one call runs the
words together with no real gap (SAPI5 turned "Shake Fill" into something
like "Shakeville"). If it still sounds too clipped or too slow once you
hear it on the actual device, adjust `WORD_PAUSE_MS` at the top of
`_generate_phrases.py` and re-run.

Regular human speech was chosen over on-device synthesis after ruling out
two alternatives:

- **Espressif ESP-SR TTS** -- real on-device synthesis, but Chinese-language
  only and ESP-IDF/C only; this repo has no build step and is 100%
  MicroPython, so there's no way to embed it without breaking that.
- **Talkie (LPC/TMS5220 "robot voice")** -- fun retro aesthetic, but it's an
  AVR 168/328 timer/PWM library with no ESP32 or MicroPython port, and a
  synthesized robotic voice is less intelligible than real speech -- the
  wrong tradeoff for an accessibility tool specifically. (Worth revisiting
  for a *non-accessibility* feature later, e.g. a fun voice on the teacher
  lanyard's shake-to-randomize flourish.)

## Uploading to the device

No Flasher manifest exists for this device yet (there isn't one for Bag3
wand hardware either -- see `../../../Live_Page/AGENTS.md`). Use MicroPico's
manual-connect upload:

1. Flash UIFlow2 MicroPython onto the StickS3 (via
   [M5Burner](https://docs.m5stack.com/en/quick_start/m5burner)) if not
   already done.
2. Copy `main.py`, `narrator_ui.py`, `phrases.py`, `espnow_manager.py`,
   `game_tags.py`, `boot.py` to the device root.
3. Copy `assets/speech/*.wav` to `/flash/assets/speech/` on the device.
4. Reboot.

## WiFi channel

Same as every other device in this system: no explicit channel is set, so
it matches whatever channel the wands/hub are using by default. If it never
hears anything, confirm a wand or hub is active and broadcasting nearby
before assuming the device is broken.

## Bench verification checklist (not yet run)

1. **Boot** -- "Listening..." shows on screen; "Narrator ready" plays once.
2. **Orientation** -- text reads right-side-up in landscape, matching
   however the device ends up worn/clipped. If it's upside-down or
   mirrored, flip `ROTATION` between `1` and `3` in `narrator_ui.py`.
3. **Text fit** -- spot-check a single word ("Go" at 72pt), a two-line
   split ("Freeze Dance" at 40pt over two lines), and the longest three-word
   labels ("NFC Bell Choir", "Multi Ice Cream") -- all per `_LAYOUT_TABLE` in
   `narrator_ui.py` -- and confirm none clip off the screen edges, and that
   text is vertically centered rather than pushed toward the bottom with a
   gap above it (that exact symptom showed up once already on real
   hardware -- see "Positioning" above for the root cause and why it's now
   plain `setCursor()`+`print()` instead of `setTextDatum()`/`drawString()`).
   This remains the single biggest risk in this file: `_LAYOUT_TABLE`'s
   sizes and pixel widths are measured against a TTF approximation of the
   real bitmap font (see "Font size + line layout" above), not the actual
   on-device rasterizer.
4. **Icon colors** -- trigger `cooking`, `melody`, `simpleicecream`, and a
   Freeze Dance Go/Freeze/Dance call; confirm the background color visibly
   matches that game's LED matrix (see "Icon colors" above). Also confirm
   `jumpin`/`shake`/`jump`/`sound`/`nfcsound`/`rainbow`/`gestures` render in
   the neutral blue -- that's correct, not a missing case.
5. **Volume safety** -- StickS3's own docs warn that on battery power (USB
   unplugged), speaker volume above ~75% can brown-out and reboot the
   device. `SPEAKER_VOLUME = 190` (~74%) in `main.py` is chosen with that
   margin in mind, but has not been confirmed on real hardware -- verify
   before raising it.
6. **Game announce** -- triggering any game from the hub/M5Paper Remote
   updates the screen and speaks the game's name within ~1s.
7. **Freeze Dance calls** -- with Freeze Dance running as caller, pressing/
   releasing the caller's button (or a shake) announces "Go"/"Freeze"/
   "Dance" exactly once per call, not five times.
8. **Stop announce** -- broadcasting stop shows "Listening..." and plays
   "Stopped".
9. **Silence on unrelated traffic** -- `status_poll`/`status_report`/
   `scan_request` packets (e.g. from a teacher checking wand battery, or
   Color Quest requesting a station scan) produce no screen change and no
   audio.
10. **Missing WAV** -- deleting one clip logs a caught exception, not a
    crash, and the screen still updates.
11. **Range** -- audible/legible at a few meters, matching the double-send
    reliability the rest of this system assumes.
