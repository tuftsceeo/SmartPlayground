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

**Pull protocol (v2).** `BBoxFirmware/code_server.py`, `BroadcastDial/BDialFirmware/code_server.py`,
`MockWand/code_puller.py`, `IconDisplay/code_puller.py`. The request frame gained a
`0xFF` version sentinel carrying the hubtype; `ROLE_FILES` maps a role to a file
suffix and whether it takes the icon leg. A v1 request behaves exactly as before.

**Icon Display tree.** `IconDisplay/` — `main.py` (radio-first boot, lazy game
load, chained force-switch, loud load failure), `icon_server.py` (USB link, split
into `start`/`step`/`finish`), `icon_matrix.py`, `icon_store.py`, `lib/`, `icons/`.

**The game pair.** `MockWand/goalrace.py` and `IconDisplay/goalrace_icon.py`.
Separate programs; they share only the ESP-NOW messages named in their docstrings.

**ChatBroadcast.** Two-role support: `chat.js` `extractCodeBlocks()`, per-role
editor state in `editor.js`, role-aware validation in `upload.js`, the role rail
and icon simulator in `app.js`, the LED icon library under `js/ledicons/`, an
Icon Maker copy under `iconmaker/`, and `knowledge/icon_display.py`. The send path
pushes `<slug>.py`, `<slug>_icon.py`, every `<slug>_icons/<name>.py` and
`<slug>.tags.json` in one raw-REPL session, and **refuses to send** when the
display game names an icon the library does not have.

---

## 5. Phase 6 — the remaining work

None of this needs hardware.

### 5.1 Tell the model which icons exist

`knowledge/icon_display.py` is static and never names the library's contents, so
the model guesses icon names. The send then blocks with "asks for icons that do
not exist", which is correct but late — the teacher has to go draw one.

Inject the current icon names into the system prompt at build time.
`listIcons()` in `js/ledicons/iconLibrary.js` already returns them, and
`SYSTEM_PROMPT_BASE` in `js/app.js` is where the marker conventions live.

**Done when:** a generated display game references only names in the library, and
`tools/devtests/chatbroadcast_flow.mjs` covers the injection.

### 5.2 Exercise the whole send path host-side

`tools/devtests/chatbroadcast_flow.mjs` drives `extractCodeBlocks`,
`validateGameCode` and `pushPayload` against a fake REPL. Extend it to a realistic
two-block reply: markers, both signatures, three named icons, and assert the exact
file list and ordering `pushPayload` writes.

**Done when:** the harness fails if any file is dropped, misnamed or written in the
wrong order.

### 5.3 Role rail and editor state under a two-role game

The rail is live (`syncRoleRail()`, `selectRole()`), but the per-role editor
shard has never been driven through a full authoring cycle: generate two blocks,
switch tabs, edit each, send, start a new game, confirm nothing leaks between
roles. A DOM-level harness in the shape of `tools/devtests/icon_panel.mjs` is
enough; do not stand up a browser runner.

**Done when:** a role switch provably carries its own code, name, tags and dirty
flag, and `clearAllRoles()` leaves no residue.

### 5.4 Resolve the `goalrace_icon.py` naming question

See §7, first entry. This is a decision, not a bug — put the options to the user
rather than picking one silently.

### 5.5 Wand-consistent glyphs on the display

The display's pull mode and failure paths speak a different visual language from
the wand's: whole-panel colour fills (`fill(panel, BLUE)`, `flash(panel, RED)`)
where the wand shows glyphs. **The goal is a consistent vocabulary across the two
devices, not bit-exact compatibility** — a child should read the same meaning off
either.

Most of the machinery exists. `icon_store.scale_into()` already block-scales a
5×5 frame onto the 16×16 panel at an integer 3×, centred, and its docstring was
written for exactly this case; `icon_server.do_frame()` already uses it for 5×5
frames arriving over USB.

**Build:**

1. `IconDisplay/lib/shapes.py` — the 5×5 index tuples copied from
   `MockWand/lib/leds.py` (105 of them: digits, A–Z, symbols, faces, wifi bars,
   battery, transport). **Data only**, no LED driver. Copy from the MockWand
   tree, never from `Bag2/`.
2. A `draw_shape(panel, shape, rgb)` helper that paints a 5×5 frame from an index
   tuple and scales it in. Keep it next to the shapes, not in `main.py`.
3. A wifi-bar animation matching `leds.wifi_animate()`'s meaning: during a scan
   one bar per call (a countdown of the scan budget), during a join one bar per
   three calls.

**Then replace the display's colour fills** in `IconDisplay/main.py` so the pull
mirrors `MockWand/main.py:654-697`:

| State | Wand shows | Display should show |
|---|---|---|
| scanning / joining | blue wifi bars, animating | same, scaled |
| transfer progress | left-to-right fill, cyan on dim blue | same idea across 256 px |
| AP not up | red wifi bars | same |
| refused (no such game for this role) | orange wifi bars | same |
| transfer broke | red X | `SHAPE_X` |
| success | — (reboots) | green `SHAPE_CHECK` |
| game load failed | 3 red flashes + traceback | `SHAPE_X` in red, traceback unchanged |

Intensity stays at `IDLE_INTENSITY` / `ALERT_INTENSITY`; `MAX_INTENSITY = 0.50` is
a measured supply ceiling, not a preference.

**Done when:** `tools/devtests/boot_display.py` asserts each pull outcome lights
the glyph it should, and no path in `main.py` still calls `fill()` with a bare
status colour.

### 5.6 Cleanup

- **`ChatBroadcast/bak/`** and `9-4-known_issues.md` — stale; confirm with the user before deleting anything.
- **`Stations/Icon Display Station/icon_server.py`** — PEER of the display's copy. The `start`/`step`/`finish` split and the panel latch were **not** ported. Decide whether the station copy should follow or deliberately diverge, and say so in both docstrings.
- **`HARDWARE_PROTOCOL.md`** — check it still matches after any protocol edit. It documents v1/v2 frames, the icon leg and all four PEER files.

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

**`IconDisplay/goalrace.py` was renamed to `goalrace_icon.py`** (commit `8a51b13`,
by the user). `_icon` is the suffix the *Box* serves a display game under; on the
*device* the pull writes it as `<slug>.py`, which is what `GAME_MODULES` resolves.
So a freshly flashed display has no built-in `goalrace` — only a pulled one runs.
That is harmless on the tested path and arguably correct, but it makes the
`goalrace` entry in `GAME_MODULES` dead for a fresh flash, and `GAME_TAGS` must
stay in step or `main.py` prints `[ERR] GAME_MODULES keys do not match`. The
devtests model the pull by copying `*_icon.py` to `<slug>.py` when they stage a
fake flash. **Ask the user** which they want: the device tree carrying device
names, or the Box's staging names.

**No card reader on the display.** `has_nfc` is `False` in `IconDisplay/lib/hubtype.py`.
The code is written as though one is fitted. Until it is, the *only* way to start a
game on the display is a pull, triggered from the REPL:
`import pull_flag, machine; pull_flag.set_pending('goalrace'); machine.reset()`.
A temporary `{"cmd":"start_game"}` in `icon_server.py` (~8 lines) would make bench
iteration much faster; it was offered and not yet taken up.

**The display never sees a `stop`.** `send_stop_all_peers()` is unicast to paired
peers, and goal messages are broadcasts, so the two devices never pair. The display
stays in a game until it is reset. Not a defect in this demo; it will matter when a
teacher needs to end a round.

**Four hand-duplicated PEER files.** `code_server.py` ×2 (Box, Dial),
`code_puller.py` ×2 (MockWand, IconDisplay), plus `icon_server.py` (display,
station) and `json_link.py`. Each carries a `PEER:` comment. A fix in one is not a
fix in the others — this has already bitten once, when the Dial's `code_server.py`
was missed.

**Display brightness is pinned at the `x0.05` floor.** `LOG_LUX_MIN = log10(500)`
means any ordinary indoor light clamps to minimum. Noticed on the bench, not
investigated, out of scope here.

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
python3 Bag3/Code/BroadcastBox/tools/devtests/boot_display.py    # display boot order + game dispatch
python3 Bag3/Code/BroadcastBox/tools/devtests/usb_link.py        # icon server + panel latch
python3 Bag3/Code/BroadcastBox/tools/devtests/goalrace_pair.py   # the pair, one fake radio between them
node    Bag3/Code/BroadcastBox/tools/devtests/chatbroadcast_flow.mjs
node    Bag3/Code/BroadcastBox/tools/devtests/icon_panel.mjs
cd Bag3/Code/Simulator && python3 -m pytest && python3 tools/sync_sources.py --check
cd Bag3/Code/BroadcastBox/ChatBroadcast && node tools/check_tags.mjs
```

`check_tags.mjs` going red is a regression to report, never a test to edit — the
tag checklist must not change for any existing game.

The devtests run device modules under stubs in `tools/devtests/stubs/`
(`machine`, `neopixel`, `network`, `espnow`, `select`, `memprobe`). They exercise
no radio, panel, card reader or serial port. Passing means the code compiles and
the protocol, boot order, dispatch and static derivations still agree — not that
it works.

---

## 9. Handing back for hardware

When phase 6 is implemented and §8 is green, the user runs one test:

1. Open ChatBroadcast against the Box or Dial and ask for a two-device game.
2. Read the send checklist **before** anything reaches flash.
3. Send; then pull on the wand by tapping `getcode:<slug>`, and on the display
   with the REPL trigger in §7.
4. Play a round.

Report what each step should print, so a deviation is recognisable without
guessing.
