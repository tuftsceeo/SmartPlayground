# Broadcast demo — phase 6 handoff

For an agent continuing this work **without hardware access**. Everything below
is host-verifiable. Do not ask for a device test until the phase 6 implementation
is complete and the checks in *Verification* pass.

Branch: `claude/document-review-plan-c0zf2i`.

---

## 1. What this is

A teacher describes a game in ChatBroadcast and gets two code files — one for
MockWand, one for the Icon Display — plus the named 16×16 icons that game uses.
All of it goes to the Broadcast Box (or Dial) over USB. Each device pulls its own
file, then the two play together over ESP-NOW.

The demo game is `goalrace`: wands join a team and race to tap a goal tag; the
display shows the winning team's icon.

---

## 2. Standing constraints

These are the user's rules, not preferences. Breaking one is a defect.

| Rule | Detail |
|---|---|
| **Bag 2 is read-only** | `Bag2/` may not be modified for any reason |
| **Bag 3 wand is untouched** | `Bag3/Code/Wand Module/`. "Wand" here always means **MockWand** |
| **Station originals stay** | `Bag3/Code/Stations/` keeps its copies; the Broadcast tree got copies |
| **`hubtype` defaults to wand** | Correct 99% of the time; do not make it raise |
| **Games are optional skills** | A device boots regardless of which games are present. A tag for a game this device lacks gives a warning tone, never a load failure |
| **No boot grace periods** | All are zero. `kbd_intr()` is never disabled, so Ctrl-C always works and a countdown buys nothing |
| **No opcodes** | `opcodes.py` was a stale NFC direction. MockWand declares tag sets in `lib/game_tags.py`; the display in `lib/display_tags.py` |
| **Errors surface loudly** | Never degrade silently. A missing icon raises; a failed load flashes red and prints the traceback |
| **Device code style** | MicroPython: `%` formatting only, no f-strings, no type annotations |

---

## 3. Hardware results

All five phases below ran on real devices. **Every one passed.**

| Phase | What it proved | Evidence |
|---|---|---|
| **1. Display boot** | Radio-first ordering holds; no `[ERR]`, no countdown | Clean boot log, ESP-NOW active |
| **2. Wand pull** | v2 request frame, file promotion, auto-reset into the game | `[XFER] OK ... promoted` |
| **3. Editor over USB** | The display answers the Icon Maker web app on the same panel `main.py` owns | Browser connected and drew |
| **4. Display pull** | Role-aware resolve **and** the icon leg | `requested 'goalrace' as 'icon_display'`, 4438-byte game, `icon leg: 3 file(s)`, auto-launch |
| **5. Pair play** | The two halves play one game over ESP-NOW | Wand joins a team, taps goal; display shows tree/whale |

Measured heap on the display with radio, panel and game all resident: **213 KB GC
free, 183 KB IDF free**. The radio-first boot order is what buys that; do not
reorder `main()`.

Two hardware problems were found and fixed during these runs:

- **Arity crash.** A pulled 6-argument `play()` raised `TypeError` and took the
  main loop with it. `_start_play()` in `MockWand/main.py` now inspects
  `co_argcount` and calls the older shape; `upload.js` makes `batt` optional.
- **Panel reverted to idle.** The idle breath reclaimed the panel ~3 s after the
  last editor frame. Ownership is now latched (see §6).

---

## 4. What is implemented

**Pull protocol (v2).** `BBoxFirmware/code_server.py`, `Bag3/Code/BroadcastDial/BDialFirmware/code_server.py`
(a sibling tree of `BroadcastBox/`, not under it),
`MockWand/code_puller.py`, `IconDisplay/code_puller.py`. The request frame gained a
`0xFF` version sentinel carrying the hubtype; `ROLE_FILES` maps a role to a file
suffix and whether it takes the icon leg. A v1 request behaves exactly as before.

**Icon Display tree.** `IconDisplay/` — `main.py` (radio-first boot, lazy game
load, chained force-switch, loud load failure, wand-consistent glyphs), `icon_server.py`
(USB link, split into `start`/`step`/`finish`, a bench `start_game` command),
`icon_matrix.py`, `icon_store.py`, `lib/` (including `shapes.py`), `icons/`.

**The game pair.** `MockWand/goalrace.py` and `IconDisplay/goalrace.py`. Separate
programs; they share only the ESP-NOW messages named in their docstrings. The
`_icon` suffix (`IconDisplay/goalrace.py` was `goalrace_icon.py` through phase 5)
lives only in the Box/Dial staging tree (`BroadcastDial/BDialFirmware/games/`) —
see §5.4, resolved.

**ChatBroadcast.** Two-role support: `chat.js` `extractCodeBlocks()`, per-role
editor state in `editor.js`, role-aware validation in `upload.js`, the role rail
and icon simulator in `app.js`, the LED icon library under `js/ledicons/`, an
Icon Maker copy under `iconmaker/`, and `knowledge/icon_display.py`. The send path
pushes `<slug>.py`, `<slug>_icon.py`, every `<slug>_icons/<name>.py` and
`<slug>.tags.json` in one raw-REPL session, and **refuses to send** when the
display game names an icon the library does not have.

---

## 5. Phase 6 — done

All of §5.1–§5.8 below is implemented and covered by the host suite in §8.
None of it needed hardware; §9 is still the hardware hand-back.

### 5.1 Tell the model which icons exist -- done

`ChatApp.getSystemPrompt()` in `js/app.js` appends `listIcons()` (from
`js/ledicons/iconLibrary.js`) to the system prompt as "ICONS CURRENTLY
AVAILABLE ON THE ICON DISPLAY", so the model is told the library's current
contents at send time rather than guessing and failing the send-time check
late. `tools/devtests/chatbroadcast_flow.mjs` reads `app.js`'s source (it
cannot import the module itself -- see §5.2) and confirms the prompt is
built from `listIcons()` rather than a hardcoded copy.

### 5.2 Exercise the whole send path host-side -- done

`tools/devtests/chatbroadcast_flow.mjs` drives `extractCodeBlocks`,
`validateGameCode` and `pushPayload` against a fake REPL with a realistic
two-block reply (both signatures, three named icons) and asserts the exact
file list and ordering `pushPayload` writes: `<slug>.py`, `<slug>.tags.json`,
`<slug>_icon.py`, then every `<slug>_icons/<name>.py`, one raw-REPL session,
one soft reset, reset last.

### 5.3 Role rail and editor state under a two-role game -- done

`tools/devtests/role_state.mjs` drives `js/editor.js`'s per-role state
(`getCode`/`setCode`/`setActiveRole`/`saveVersion`/`clearAllRoles`) through a
full cycle: two blocks land, switching tabs carries each role's own code, an
edit on the active tab never leaks into the other, version history is
per-role, and `clearAllRoles()` empties every role's code, history and
tab-rail membership. `editor.js` imports CodeMirror from four `esm.sh` URLs
at module scope; a `node:module` loader hook
(`tools/devtests/stubs/cm_loader.mjs`) redirects those to a bare local stub
so the module imports under plain Node with no network access.

App.js's `syncRoleRail()`/`selectRole()` and the per-game dirty/name/tags
state stay untested here: `app.js` pulls in `auth.js`, `router.js` and other
DOM-touching modules the loader-hook trick cannot paper over the way a
handful of CodeMirror exports can.

### 5.4 The `goalrace_icon.py` naming question -- resolved

The device tree carries device names; the `_icon` suffix lives only in the
Box/Dial staging tree. `IconDisplay/goalrace_icon.py` is now
`IconDisplay/goalrace.py`, matching `MockWand/goalrace.py`.
`BroadcastDial/BDialFirmware/games/goalrace_icon.py` (the staging copy the
Box/Dial serve from under `ROLE_FILES`) is unchanged. The `_stage_pulled_games()`
shim that used to rename `<slug>_icon.py` to `<slug>.py` for the devtests is
gone from `boot_display.py`, `usb_link.py` and `goalrace_pair.py` — they
flash the tree verbatim now, which is what a real device has.

One defect this surfaced, also fixed: `_boot_scan_games()` on both the Box
and the Dial enrolled a `*_icon.py` staging file as a playable game in its
own right (`BDialFirmware/games/index.json` carried a phantom "Goalrace
Icon" entry), and a newly-sent one could become the active game by mtime.
Both boot scans now skip `*_icon.py`; covered by
`tools/devtests/game_menu_scan.py`.

### 5.5 Wand-consistent glyphs on the display -- done

`IconDisplay/lib/shapes.py` carries the 105 `SHAPE_*` tuples (and
`WIFI_FRAMES`) copied verbatim from `MockWand/lib/leds.py`'s "5x5 GRID
SHAPES" section, plus `draw_shape()` and `wifi_animate()` built on
`icon_store.scale_into()`'s existing integer 3x centred scale.

`main.py`'s pull mode and load-failure paths now match the table this
section used to propose exactly: scanning/joining animates `SHAPE_WIFI_2`
in blue (`code_puller.pull()`'s `on_status`/`on_progress` callbacks are
wired up now — they never were before), AP-not-up is `SHAPE_WIFI_2` in red,
refused is `SHAPE_WIFI_2` in amber, a broken transfer or a spent attempt
budget is `SHAPE_X` in red, success is a steady `SHAPE_CHECK` in green
before the reset, and a game load failure is `SHAPE_X` in red with
`sys.print_exception()` unchanged. The pull-flag-write-failure and
unknown-game-tag paths in the idle loop also moved off bare colour, onto
`SHAPE_X` and `SHAPE_QUESTION` respectively. `show_idle()`'s breath and the
transfer progress bar stay whole-panel colour — neither has a wand
equivalent to mirror. `flash()` (whole-panel blink) is gone; every caller
now uses `flash_glyph()`.

`tools/devtests/boot_display.py` spies on `shapes.draw_shape()` (the glyph
is transient — `flash_glyph()` clears the panel again before four of the
six pull outcomes return, so reading final pixels would miss it) and
asserts the exact shape and colour every outcome asks for, plus both
game-load failure paths. `tools/devtests/usb_link.py` covers the new
`start_game` bench command (§5.6).

Intensity: see §5.7, below — it changed from the values this section
originally proposed.

### 5.6 The `{"cmd":"start_game"}` bench command -- done

`icon_server.py`'s `do_start_game()` takes `{"cmd":"start_game","name":"<slug>"}`,
validated against an `is_game` callable `main.py` injects at construction
(avoiding a circular import). An unknown or uninstalled slug is refused
loudly with a structured error reply — a deliberate difference from the
ESP-NOW `start_game` path, which silently ignores a game this display
does not have. A valid request releases the panel and queues
`pending_start_game`, which `main.py`'s idle loop consumes the same way it
consumes an ESP-NOW `start_game` message. Not part of the wire protocol in
`HARDWARE_PROTOCOL.md` — a bench affordance only. This replaces the REPL
incantation (`import pull_flag, machine; pull_flag.set_pending('goalrace');
machine.reset()`) as the way to start a display game on the bench.

### 5.7 Display brightness -- set to 0.15 across the board, for now

`IDLE_INTENSITY`/`ALERT_INTENSITY` (`main.py`) and `READY_INTENSITY`/
`WINNER_INTENSITY` (`goalrace.py`, and its Box/Dial staging copy) are all
`0.15` — a single conservative value, per the user, pending a sparse-glyph
current-draw measurement on the bench. `MAX_INTENSITY` (0.50) is unchanged;
it is the measured supply ceiling, not a preference.

The bench data behind that ceiling does exist, contrary to what an earlier
draft of this handoff implied about the display: `Stations/Icon Display
Station/readme.md` and `voltage_test.py`, measured 2026-08-25 — 112 lit
pixels safe at 50% white on the 5V path, 128 fails (driver board rated
5V/3A); 192 on 12V; a full 256 on a non-white rainbow ramp. It is bench data
for the station's driver board, not this tree (nothing in `IconDisplay/` has
run on hardware — see its README's Unverified section), and glyph content
(a scaled 5x5 frame lights at most ~150 of 256 px, usually far fewer) sits
well inside that envelope even before this drop. **Correction to an earlier
version of this section:** it attributed `LOG_LUX_MIN` and an "x0.05 indoor
floor" to the display. Those are wand-only
(`MockWand/lib/brightness.py`) — the display has no light sensor at all
(`has_nfc` is the only capability flag `lib/hubtype.py` even has for this
device that varies; there is no light-sensor flag, and no ambient-light code
anywhere in this tree). Fixed a related stale pointer in the station's
`readme.md`: the `INTENSITY` constant it named in `main.py` no longer exists
there (`main.py` was rewritten to boot `IconServer`); it survives as
`DEFAULT_INTENSITY` in `icon_matrix.py`.

### 5.8 Cleanup

- **`ChatBroadcast/bak/`** and **`9-4-known_issues.md`** — kept, per the
  user, with a header marking each clearly outdated.
- **`Stations/Icon Display Station/icon_server.py`** — ported. It now
  carries `_drew()`/`owns_panel()`/`release_panel()` and the `start`/`step`/
  `finish` split, matching the display's copy. Two divergences are
  deliberate and recorded in both docstrings: the station still builds its
  own `Matrix` (it is the only NeoPixel owner on that device, unlike the
  display), and `do_start_game`/`is_game` are display-only — the station has
  nothing to launch.
- **`HARDWARE_PROTOCOL.md`** — re-checked; it already stated the `_icon`
  suffix is Box/Dial-staging-only and the destination name is always plain
  `<slug>.py`, which is what §5.4 made the repo tree agree with. No changes
  needed.

---

## 6. The panel-ownership latch

Worth understanding before touching `IconDisplay/main.py` or `icon_server.py`.

The editor and the idle animation write the same 256 pixels. Ownership is
**latched** by the first editor draw (`_drew()`), and released only by
`release_panel()` — which `main.py` calls on a card tap, an ESP-NOW `start_game`,
or a `stop`. `USB_QUIET_MS` (5 minutes) is a backstop, not the normal release:
**the USB link has no disconnect event**, so a long silence is the only available
stand-in for "the browser closed the port". A `clear` command keeps the latch,
because a deliberate blank is still the editor's picture.

This has passed host tests but **has not run on hardware** — a game owns the loop,
so phase 5 never stepped the USB server.

---

## 7. Known issues and open decisions

**The display's card reader is wired but has never read a tag.** It is a
WS1850S at `0x28` — the same chip as the Broadcast Box, on the wand's I2C pins —
so `has_nfc` is now `True` and `lib/nfc_ws1850s.py` presents it to
`nfc_reader.py` as the four PN532 methods that file calls. The PN532 driver is
gone from this tree. Covered host-side by `tools/devtests/nfc_display.py`
(19 checks against a fake chip holding a real NDEF card image), **unproven on
hardware**: the address, the Crypto1 clearing and the tap-to-launch path all
want a bench run. `main.py` scans the bus at boot and prints what it found, so
a wrong address reads off the boot log rather than presenting as a display that
silently ignores cards.

**The display can also be started on the bench without a card**, via
`icon_server.py`'s `start_game` command (§5.6). The REPL incantation
(`import pull_flag, machine; pull_flag.set_pending('goalrace');
machine.reset()`) still works too — that path pulls a fresh copy from the
Box first, where `start_game` just launches what is already on flash.

**The display never sees a `stop`.** `send_stop_all_peers()` is unicast to paired
peers, and goal messages are broadcasts, so the two devices never pair. The display
stays in a game until it is reset. Not a defect in this demo; it will matter when a
teacher needs to end a round.

**`_icon` is a reserved slug suffix on the Box and the Dial.** `_boot_scan_games()`
skips any `*_icon.py` so a display game's staging copy never enters the game menu,
which means a game slug ending in `_icon` would lose its wand file from the menu.
Documented in `HARDWARE_PROTOCOL.md`; **nothing enforces it at send time** —
ChatBroadcast will happily push such a slug. A name check in the send path is the
obvious fix if it ever bites.

**Hand-duplicated PEER files.** `code_server.py` ×2 (Box, Dial),
`code_puller.py` ×2 (MockWand, IconDisplay), `icon_server.py` ×2 (display,
station — kept in sync as of phase 6, see §5.8), and `json_link.py`, plus
several less-visible ones (`ws1850s.py`, `card_writer.py`, `stats_log.py`,
`reset_log.py`, `boot.py`, `bbox_ui.py`/`dial_ui.py`,
`ledColor.js`/`ledcolor.js`) and the new `shapes.py` (§5.5, PEER of
`MockWand/lib/leds.py`'s shape data, drift tolerated for now — see §5.5).
Each carries a `PEER:` comment. A fix in one is not a fix in the others —
this has already bitten once, when the Dial's `code_server.py` was missed.
Per the user: comments for now, real deduplication is a later refactor once
the MVP is proven.

**`iconmaker/js/device/` was kept**, contrary to the original plan, because it is
what drives the display's USB editor link. Drop it only if that direct link is
abandoned.

**Not re-checked:** whether the Radar or other station trees hold further
undiscovered PEER files.

---

## 8. Verification without hardware

From the repo root:

```
bash Bag3/Code/BroadcastBox/tools/devtests/compile_check.sh    # py_compile over Bag3/Code
python3 Bag3/Code/BroadcastBox/tools/devtests/wire_test.py       # Box pull protocol, both ends
python3 Bag3/Code/BroadcastBox/tools/devtests/wire_test_dial.py  # Dial pull protocol
python3 Bag3/Code/BroadcastBox/tools/devtests/boot_display.py    # display boot order + game dispatch + pull-mode glyphs
python3 Bag3/Code/BroadcastBox/tools/devtests/usb_link.py        # icon server + panel latch + start_game
python3 Bag3/Code/BroadcastBox/tools/devtests/goalrace_pair.py   # the pair, one fake radio between them
python3 Bag3/Code/BroadcastBox/tools/devtests/nfc_display.py     # the display's WS1850S shim + tag decode
python3 Bag3/Code/BroadcastBox/tools/devtests/game_menu_scan.py  # Box/Dial boot scan never enrolls a *_icon.py staging file
node    Bag3/Code/BroadcastBox/tools/devtests/chatbroadcast_flow.mjs
node    Bag3/Code/BroadcastBox/tools/devtests/icon_panel.mjs
node    Bag3/Code/BroadcastBox/tools/devtests/role_state.mjs     # per-role editor state, a full authoring cycle
cd Bag3/Code/Simulator && python3 -m pytest && python3 tools/sync_sources.py --check
cd Bag3/Code/BroadcastBox/ChatBroadcast && node tools/check_tags.mjs
```

`check_tags.mjs` going red is a regression to report, never a test to edit — the
tag checklist must not change for any existing game.

The devtests run device modules under stubs in `tools/devtests/stubs/`
(`machine`, `neopixel`, `network`, `espnow`, `select`, `memprobe`, and, added in
phase 6, `M5`/`m5ui`/`lvgl` for `game_menu_scan.py` and a `node:module` loader
hook for `role_state.mjs`'s CodeMirror imports). They exercise no radio, panel,
card reader or serial port. Passing means the code compiles and the protocol,
boot order, dispatch and static derivations still agree — not that it works.

---

## 9. Handing back for hardware

When phase 6 is implemented and §8 is green, the user runs one test:

1. Open ChatBroadcast against the Box or Dial and ask for a two-device game.
2. Read the send checklist **before** anything reaches flash.
3. Send; then pull on the wand by tapping `getcode:<slug>`. On the display,
   pull the file onto flash the same way a real tap eventually will, once a
   reader is fitted: `import pull_flag, machine;
   pull_flag.set_pending('<slug>'); machine.reset()` at the REPL. The pull
   auto-launches on that reset; to relaunch it later without another pull,
   use the `start_game` USB command instead (§5.6).
4. Play a round.

Report what each step should print, so a deviation is recognisable without
guessing.
