# Adding a device to the broadcast ecosystem — surfaces to add and modify

Scope: what must be written or changed to make a new playground device a target
ChatBroadcast can generate code for and the Broadcast Box or Dial can serve.

Derived from how the Icon Display was added (`PHASE6_HANDOFF.md`). Every site below
is edited by hand; there is no device registry and none is planned. Each device gets
its own firmware tree and its own `lib/`.

Line numbers are as of this writing and will drift. Symbol names are the stable
reference.

**On the word "icon".** The icon display is the only device so far, so several generic
mechanisms carry its vocabulary in the code: `ROLE_FILES`' `icons` flag, the "icon
leg" of the pull protocol, `icon_dir=` in `code_puller.pull()`. The generic mechanism
is an **asset leg** — a role may need extra files shipped with the game file, and for
the display those files happen to be pictures. This report uses "asset leg" for the
mechanism and keeps the code's own names when naming a symbol. Everything that is
genuinely about pictures is confined to *Icon-display-only, do not copy* at the end.

---

## Naming

Three distinct identifiers, easy to conflate:

| Identifier | Example | Where it lives | Constraint |
|---|---|---|---|
| **hubtype** | `icon_display` | `hubtype.txt`, `lib/hubtype.py` `_CONFIGS` key, the v2 pull frame, `ROLE_FILES` key | `code_puller.pull(hubtype=HUB_TYPE)` sends it verbatim and `code_server._lookup()` looks it up directly — the two must be the same string |
| **role key** | `icon` | `js/chat.js` `ROLES`, `js/upload.js` `ROLE_SIGNATURES`, `data-role`, `[DEVICE: icon]` | web app only; short form, never on the wire |
| **staging suffix** | `_icon` | `ROLE_FILES[...]['suffix']` | Box/Dial filesystem only; the file lands on the device as plain `<slug>.py` |

### The designator rule

The staging suffix is the designator: it is the only thing on the Box or Dial that
says which device a given game file is for.

| Staged filename | Device |
|---|---|
| `<slug>.py` — no designator | wand |
| `<slug>_icon.py` | icon display |
| `<slug>_<new>.py` | the new device, one distinct designator each |

- **The empty suffix belongs to the wand and is not available to a new device.** It is
  `ROLE_FILES['wand']['suffix'] = ''`, and it is also what `DEFAULT_ROLE = 'wand'`
  resolves a v1 request to — a request that names no hubtype at all. Both paths reach
  the undesignated file, so nothing else may claim it.
- **`_icon` belongs to the icon display and to nothing else.** An icon game runs only
  on an icon display. Three things hold that: `ROLE_FILES` serves `<slug>_icon.py` only
  to a `icon_display` request, `ROLE_SIGNATURES.icon` requires
  `def play(nfc, panel, enow)` which no other device calls, and `_boot_scan_games()`
  skips `*_icon.py` so it never appears in the Box or Dial game menu as something
  playable in its own right.
- **Every new device declares its own distinct designator.** Reusing `_icon` would hand
  an icon-display file to hardware that cannot run it, and the pull path has no way to
  detect that: the file arrives as plain `<slug>.py` and fails at `play()` call time.

Designators are Box/Dial-side only. The device never sees one — every pulled file lands
as `<slug>.py` in `/games/`, because each device holds at most one module per slug.

---

## Surface 1 — the new device's firmware tree

New directory under `Bag3/Code/BroadcastCode/`, sibling to `MockWand/` and
`IconDisplay/`. Self-contained: it imports nothing from the other trees.

### Files to add

| File | Contents | Source to copy from |
|---|---|---|
| `hubtype.txt` | one line, the hubtype string | `IconDisplay/hubtype.txt` |
| `boot.py` | must not drive any output device | `MockWand/boot.py` (PEER) |
| `main.py` | new — see the required structure below | shape of `IconDisplay/main.py` |
| `code_puller.py` | `REQ_V2`, `_write_request()`, `pull(..., hubtype=, icon_dir=)` — `icon_dir` is where the asset leg lands; pass `None` for a role with no assets | `MockWand/code_puller.py` (PEER) |
| `pull_flag.py` | `PATH`, `MAX_ATTEMPTS`, `set_pending`/`bump`/`budget_left`/`requested_slug`/`clear` | `MockWand/pull_flag.py` (PEER; MockWand's and IconDisplay's are byte-identical) |
| `games/` | empty directory, the pull destination | — |
| `lib/hubtype.py` | `_CONFIGS["<hubtype>"]` entry: pins, LED count, capability flags | `IconDisplay/lib/hubtype.py` (PEER ×4, already divergent) |
| `lib/espnow_manager.py` | `ESPNowManager` | `MockWand/lib/espnow_manager.py` (PEER) |
| `lib/game_store.py` | `GAMES_DIR='/games'`, `is_valid_slug`, `slugs`, `exists`, `set_last_pulled`/`take_last_pulled` | `MockWand/lib/game_store.py` (PEER) |
| `lib/<device>_tags.py` | `GAME_TAGS`, `CONTROL_TAGS = {"stop","getcode"}`, `EXIT_TAGS`, `exit_tags_excluding()` | `IconDisplay/lib/display_tags.py` — a separate table per device, deliberately not shared |
| `lib/memprobe.py` | `probe()`, `frag()` | PEER |
| `README.md` | layout, the `play()` contract, an **Unverified** section | `IconDisplay/README.md` |
| `manifest.js` | local path → `/flash/...` for the web installer | `BBoxFirmware/manifest.js` |

Optional NFC leg, only when a reader is fitted:

| File | Chip |
|---|---|
| `lib/nfc_reader.py` (PEER) + `lib/nfc_ws1850s.py` + `lib/ws1850s.py` | WS1850S @ 0x28 — `IconDisplay/lib/` |
| `lib/nfc_reader.py` (PEER) + `lib/pn532.py` | PN532 @ 0x24 — `MockWand/lib/` |

`nfc_reader.py` is one shared file across both chips; `nfc_ws1850s.py` is a shim
presenting the four PN532 methods it calls. Do not fork the reader logic.

### `main.py` — required elements

| Element | Reference | Rule |
|---|---|---|
| Module docstring | `IconDisplay/main.py` | States the exact `play()` signature this device calls |
| `GAME_MODULES` | `IconDisplay/main.py:82` | tag → module basename. Built-ins only |
| Boot-time dispatch check | `IconDisplay/main.py:86-88` | `set(GAME_MODULES) != GAME_TAGS` prints `[ERR]`. Nothing else keeps the two in step |
| `_load_play()`, `_launch_game()` | `IconDisplay/main.py:286` | Lazy import, force-switch chaining on an in-game `start_game` |
| `_start_play()` | `MockWand/main.py:457-484` | Reads `__code__.co_argcount` and calls the matching arity. Added after a pulled 6-arg `play()` raised `TypeError` and took the main loop with it |
| `_game_load_failed()` | `IconDisplay/main.py` | Loud: visible failure signal plus `sys.print_exception()`. Never silent |
| `_run_pull_mode()` | `IconDisplay/main.py` | Six outcomes (scanning, AP not up, refused, transfer broken, budget spent, success), each with its own feedback |
| `_emit()` + identity | `MockWand/main.py:169`, identity at `:933` | NDJSON, one object per line: `identity` once after boot, `heartbeat` every 5 s in the idle loop only, `game_start`/`game_end` around a launch, `error` on load failure. This is the only thing that makes the board recognisable on a direct USB connect |
| `main()` ordering | below | Load-bearing |
| Idle loop | `IconDisplay/main.py:615` | Poll `enow` every iteration; handle `start_game`, `stop`, game tags, and `getcode:<slug>`. An unknown game over ESP-NOW is ignored, not an error — games are optional skills |

### `main()` ordering rules

1. **`pull_flag.is_pending()` is the first statement.** Nothing before it may import
   `espnow_manager`, or any other radio-claiming module. A SoftAP join only succeeds
   on a radio ESP-NOW has never touched this boot; MicroPython exposes no
   `esp_wifi_deinit()` to clear it from Python. `pull_flag.py`'s docstring records the
   measurement (cold: transfers first try; warm: 3/3 real taps failed).
2. **A `getcode` tap queues and resets — it never pulls in place.**
   `set_pending(slug)` then `machine.reset()`.
3. **The attempt budget is spent before each attempt** (`pull_flag.bump()`), so a
   crash mid-pull cannot boot-loop.
4. **Radio before large allocations.** `enow.init()` precedes anything that takes tens
   of KB. `esp_wifi_init()`/`esp_wifi_start()` need contiguous internal IDF heap that
   MicroPython's GC heap is carved out of; building the panel first produced
   `OSError: WiFi Out of Memory`. A device with no large buffer may reorder, but must
   `memprobe.probe()` around each radio stage to confirm on first bench run.
5. **No boot grace periods.** All are zero; `kbd_intr()` is never disabled.
6. **A failed capability degrades, it does not block.** A missing card reader costs
   card taps and nothing else. `main.py` scans the I2C bus and prints every address
   found when `nfc_addr` is not among them, so a wrong address reads off the boot log.

### On-device layout rules

- `/lib` for libraries, flash root for `main.py` and built-in games, `/games/<slug>.py`
  for pulled games. `main.py` appends `/games` to `sys.path`.
- **Pulled games must never land in the root.** Root precedes `/games` on the path and
  a stale root copy would shadow the new one.
- A slug is a MicroPython module name: lowercase, leading letter, `[a-z0-9_]`, ≤16
  chars. Enforced in three places that must agree — `ChatBroadcast/js/gameName.js`
  (`slugify`/`isValidSlug` + reserved list), `lib/nfc_reader.py` (`is_valid_slug`),
  `lib/game_store.py`.

---

## Surface 2 — Broadcast Box and Dial

Four files, two PEER pairs. **A fix in one is not a fix in the other.** This has
already caused a defect once, when the Dial's `code_server.py` was missed.

| File | Symbol | Change |
|---|---|---|
| `BroadcastBox/BBoxFirmware/code_server.py:84` | `ROLE_FILES` | Add `'<hubtype>': {'suffix': '_xxx', 'icons': <bool>}` — `icons` is the asset-leg flag, `False` for a role that ships only its game file |
| `BroadcastDial/BDialFirmware/code_server.py:84` | `ROLE_FILES` | Identical entry |
| `BroadcastBox/BBoxFirmware/bbox_server.py:676` | `_boot_scan_games()` | Add the new suffix to `name.endswith('_icon.py')` |
| `BroadcastDial/BDialFirmware/bdial_server.py:668` | `_boot_scan_games()` | Identical change |

### Rules

- **A hubtype absent from `ROLE_FILES` is refused, not guessed at.** `_lookup()`
  returns `None`, the device gets an explicit zero-size reply, treats it as terminal,
  clears its flag and does not spend a retry. Handing a device a file written for
  different hardware is worse than telling it there is nothing for it.
- **`DEFAULT_ROLE = 'wand'` is untouched.** It is what a v1 request, which names no
  hubtype, gets. The `0xFF` sentinel is what lets one socket serve an un-updated wand
  and a hubtype-aware device.
- **Every staging suffix must be added to both `_boot_scan_games()` copies.** A
  staging file that is not skipped enrols as a playable game in its own right and, being
  newest by mtime, can become the active game. This produced a phantom "Goalrace Icon"
  entry in `BDialFirmware/games/index.json`.
- **Each new suffix becomes a reserved slug ending.** A game slug ending in `_icon`
  loses its wand file from the menu. Nothing enforces this at send time; ChatBroadcast
  will push such a slug. With more than one reserved suffix, a check in
  `gameName.js`'s reserved list is the fix.
- **`icons: <bool>` is the asset-leg flag.** `False` means the transfer ends at the
  game file's ack. `True` means a second leg follows: a 1-byte file count, then that
  many files from `icons_dir_for(slug)`, capped at `MAX_ICONS = 64`. The flag, the
  directory helper and the cap are named for the display because it is the only role
  using them; the mechanism is "this role needs extra files with its game". A new
  device that needs none sets `False` and touches nothing else. A new device that needs
  its own assets is the point at which these three names should be generalised —
  reusing `icons_dir_for()` for something that is not a picture is worse than renaming
  it.

### Known gaps a new role inherits

- `do_games_delete()` (`bbox_server.py:480`, `bdial_server.py:472`) removes only
  `<slug>.py` and `<slug>.tags.json`. A staging file under a role suffix, and any asset
  directory, are left on flash.
- `do_games_clear()` removes `*.py` and `*.tags.json` at the top of `GAMES_DIR`. Asset
  subdirectories survive.

Concretely today that means `<slug>_icon.py` and `<slug>_icons/` are orphaned by both.
Any new role with a suffix or an asset directory is orphaned the same way.

### Wire protocol — no change needed

```
v1:  device -> box :  len(1) | slug                        (len 0 = "serve active")
v2:  device -> box :  0xFF | len(1) | slug | len(1) | hubtype

     box -> device :  size(4B BE) | sha256(32B) | name_len(1B) | name
     box -> device :  file body, 512B chunks
     device -> box :  2-byte ack, b'OK' or b'NO'
```

v2 already carries the hubtype. A new role is a `ROLE_FILES` entry, not a protocol
revision. Any actual protocol change must be mirrored in all four files in one commit.

### Dial card-write menu

`dial_ui.py` reads `<slug>.tags.json`, pushed alongside the game. No change for a new
role unless it introduces its own tag family.

---

## Surface 3 — the ChatBroadcast web app

### Files to modify

| File | Symbol | Change | Generic today? |
|---|---|---|---|
| `js/chat.js:63` | `ROLES` | Add the role key, in tab order | — |
| `js/chat.js:5` | `KNOWLEDGE_FILES` | Add `knowledge/<device>.py` | — |
| `js/chat.js:85` | `roleBefore()` | None. The regex `/\[DEVICE:\s*([a-z_]+)\s*\]/gi` accepts any lowercase word; `ROLES` is the only gate | yes |
| `js/chat.js:100` | `extractCodeBlocks()` | None | yes |
| `js/upload.js:12` | `ROLE_SIGNATURES` | Required `play()` parameter names, in order | — |
| `js/upload.js:27` | `OPTIONAL_PARAMS` | Params the role's `play()` may omit and still run | — |
| `js/app.js:~75` | `SYSTEM_PROMPT_BASE` | The required-signature line and the `[DEVICE: <role>]` marker | — |
| `js/app.js:265` | `syncRoleRail()` | `hasDisplay = have.has('icon')` gates both tab groups' visibility and the Icon Maker button; the tooltip is a `role === 'wand' ? 'Wands' : 'Icon display'` ternary. Both assume exactly two roles | **no** |
| `js/app.js:540` | `selectRole()` | None | yes |
| `js/app.js:1695` | `updatePreview()` | `showingIcon = getActiveRole() === 'icon' && …` is a two-way switch between `#preview-panel` and `#icon-sim-panel`. A third role needs its own branch | **no** |
| `js/app.js:1725` | `syncPreviewEmpty()` | `isIcon = getActiveRole() === 'icon'` drives the placeholder glyph and caption | **no** |
| `js/app.js:2157-2186` | `confirmSend()` | The `extraFiles` block. Generically: validate the role's code, refuse the send if an asset it names is missing, then queue `<slug><suffix>.py` and any asset files. Today every step is written for one role — `getCode('icon')`, `validateGameCode(iconCode,'icon')`, `missingIconsIn()`, the literal `` `/flash/games/${slug}_icon.py` `` | **no** |
| `index.html:172-181`, `:240-248` | `.device-tab[data-role]` | Two buttons per role — preview toolbar and code drawer. They are two views of one editor role and always move together | — |
| `js/editor.js` | `roleState` | None. Built from `ROLES`, so per-role code, history and tab membership come free | yes |
| `js/hardware.js:29,96` | `buildHardwareReqs()` `stations` | Populate when the role has code, so the send-confirm overlay states the device is needed. Always `[]` today | — |
| `css/app.css:551` | `.device-tab` | None expected; confirm the rail does not overflow past two tabs | — |

### Direct USB connection — only if the device connects without the Box

| File | Symbol |
|---|---|
| `js/device/bboxDeviceLink.js:32` | `EXPECTED_DEVICES`, `deviceShortName()`, `deviceProductName()` |
| `js/device/wandDeviceLink.js:30` | the model: `EXPECTED_DEVICE`, `FORWARDED_EVENTS`, `verifyIsWand()` reading `/hubtype.txt` and refusing a mismatch |
| `js/device/wandGameInstaller.js` | the model: raw-REPL write to `/games/<slug>.py`, `set_last_pulled()`, exit raw REPL, Ctrl-D |
| `index.html:339` | connect-overlay picker entry |

### Knowledge file

`knowledge/<device>.py`, one per device type — there is no shared game API to
document. Follow `knowledge/icon_display.py`:

- A `CRITICAL CONTRACT` block first: the exact signature to copy, and a
  FORBIDDEN-signatures list naming the other devices' signatures explicitly.
- What each argument is, whether it is already built, and what must never be
  constructed inside a game.
- Arguments that can be `None` and the guard required.
- The hardware that does **not** exist on this device.
- The ESP-NOW messages it exchanges with the other half of a pair.
- MicroPython rules: `%` formatting, no f-strings, no type annotations,
  `time.sleep_ms()` is milliseconds.

`getSystemPrompt()` (`js/app.js:~245`) appends a live inventory of whatever assets the
device currently holds, so the model is told what exists at send time instead of
guessing and failing the send-time check. The display appends `listIcons()`. A role
with no assets appends nothing; a role with its own appends its own list, read from
the live source rather than hardcoded in the prompt.

### Preview

Only the wand has a Pyodide simulator (`Bag3/Code/Simulator/`). The display has a
static preview (`js/ledicons/iconPanel.js` `mountIconPanel()`). A device with no visual
output gets an explicit "no preview" branch in `updatePreview()` and
`syncPreviewEmpty()`, not a third simulator.

---

## Icon-display-only, do not copy

These exist for one device. They are not part of adding a device, and a new tree that
copies them is carrying dead weight.

| Thing | Where |
|---|---|
| Named 16×16 picture files, 768 duty bytes each | `IconDisplay/icons/*.py`, `icon_store.py` |
| `Matrix` — serpentine addressing, intensity LUT, `MAX_INTENSITY = 0.50` | `IconDisplay/icon_matrix.py` |
| USB icon-authoring server and its panel-ownership latch | `IconDisplay/icon_server.py` (PEER of the station's copy) |
| Icon Maker web app, and the `#btn-icon-maker` visibility rule | `ChatBroadcast/iconmaker/`, `js/app.js` `syncRoleRail()` |
| Browser icon library and the generated defaults | `ChatBroadcast/js/ledicons/`, `tools/sync_icons.py` |
| `missingIconsIn()` / `iconNamesIn()` / `iconFileText()` send-time checks | `ChatBroadcast/js/app.js`, `js/ledicons/iconLibrary.js` |
| `#icon-sim-panel` and `mountIconPanel()` | `ChatBroadcast/js/ledicons/iconPanel.js` |
| `shapes.py` — 5×5 glyphs scaled 3× onto the panel | `IconDisplay/lib/shapes.py` |
| `icon_panel.mjs`, `sync_icons.py --check` | devtests |

What **is** generic, and what a new device inherits: the asset leg itself
(`ROLE_FILES`' flag, the 1-byte count, `icon_dir=`), the rule that the send is refused
when generated code names an asset that does not exist, and the rule that the model is
told the asset inventory at prompt time. A device with no assets uses none of it.

---

## Surface 4 — host devtests

`Bag3/Code/BroadcastCode/tools/devtests/`. (`PHASE6_HANDOFF.md` §8 gives these as
`BroadcastBox/tools/devtests/`; that path does not exist. `sync_icons.py` and
`check_tags.mjs` are under `ChatBroadcast/tools/`.)

| Test | Change for a new role |
|---|---|
| `compile_check.sh` | `py_compile` over `Bag3/Code`; picks the tree up automatically — confirm its glob reaches it |
| `wire_contract.py` → `wire_test.py`, `wire_test_dial.py` | New role cases: the v2 request resolves `<slug><suffix>.py`, takes or skips the asset leg, and an unknown hubtype is still refused. Run against Box and Dial |
| `game_menu_scan.py` | Assert the boot scan skips the new suffix on both |
| `boot_<device>.py` (new) | Model on `boot_display.py`: nothing radio-claiming imported before `_run_pull_mode()`; boot order; dispatch and force-switch chain; each pull-mode outcome's feedback; loud load failure |
| `chatbroadcast_flow.mjs` | Extend to an N-block reply; assert the exact file list and ordering `pushPayload` writes, one raw-REPL session, one soft reset, reset last |
| `role_state.mjs` | Extend to an N-role cycle |
| `tools/devtests/stubs/` | Add a stub for any new module the tree imports (`machine`, `neopixel`, `network`, `espnow`, `select`, `memprobe`, `M5`/`m5ui`/`lvgl` exist; `bluetooth` does not) |

Passing means the code compiles and the protocol, boot order, dispatch and static
derivations agree. It does not mean the device works — no radio, panel, card reader or
serial port is exercised.

### Full suite

```
bash     Bag3/Code/BroadcastCode/tools/devtests/compile_check.sh
python3  Bag3/Code/BroadcastCode/tools/devtests/wire_test.py
python3  Bag3/Code/BroadcastCode/tools/devtests/wire_test_dial.py
python3  Bag3/Code/BroadcastCode/tools/devtests/boot_display.py
python3  Bag3/Code/BroadcastCode/tools/devtests/usb_link.py
python3  Bag3/Code/BroadcastCode/tools/devtests/goalrace_pair.py
python3  Bag3/Code/BroadcastCode/tools/devtests/nfc_display.py
python3  Bag3/Code/BroadcastCode/tools/devtests/game_menu_scan.py
node     Bag3/Code/BroadcastCode/tools/devtests/chatbroadcast_flow.mjs
node     Bag3/Code/BroadcastCode/tools/devtests/icon_panel.mjs
node     Bag3/Code/BroadcastCode/tools/devtests/role_state.mjs
python3  Bag3/Code/BroadcastCode/ChatBroadcast/tools/sync_icons.py --check
cd Bag3/Code/Simulator && python3 -m pytest && python3 tools/sync_sources.py --check
cd Bag3/Code/BroadcastCode/ChatBroadcast && node tools/check_tags.mjs
```

`check_tags.mjs` going red is a regression to report, not a test to edit — the tag
checklist must not change for any existing game.

---

## Surface 5 — documentation

| File | Change |
|---|---|
| `Bag3/AGENTS.md` | Add the tree to the broadcast-devices table (tree, device identity, hardware) |
| `Bag3/Code/HARDWARE_PROTOCOL.md` | The reserved staging-suffix list |
| `BroadcastBox/README.md` | The `ROLE_FILES` paragraph |
| `<Device>/README.md` | Layout, `play()` contract, the **Unverified** section |
| `docs_and_design/` | A phase handoff recording what ran on hardware and what did not |

---

## PEER file inventory

Hand-duplicated copies, each carrying a `PEER:` comment. Adding a device grows this
list. Per the user: comments for now, deduplication is a later refactor once the MVP is
proven.

| File | Copies |
|---|---|
| `code_server.py` | BroadcastBox, BroadcastDial |
| `code_puller.py` | MockWand, IconDisplay |
| `pull_flag.py` | MockWand, IconDisplay (byte-identical) |
| `game_store.py` | MockWand/lib, IconDisplay/lib (byte-identical) |
| `espnow_manager.py` | MockWand/lib, IconDisplay/lib, Bag2/Code/lib, Bag3/Code/lib, hubCode2, M5Paper Remote, StickS3 Narrator, Simulator |
| `hubtype.py` | MockWand/lib, IconDisplay/lib, Bag3/Code/lib, Bag2/Code/lib — **divergent in content**, not only comments |
| `icon_server.py` | IconDisplay, Stations/Icon Display Station |
| `json_link.py` | Box, Dial, IconDisplay, both Bag3 stations |
| `nfc_reader.py`, `ws1850s.py` | Box, IconDisplay/lib, Bag3/Code/lib |
| `shapes.py` | IconDisplay/lib, PEER of `MockWand/lib/leds.py`'s shape data (drift tolerated) |
| `boot.py`, `card_writer.py`, `stats_log.py`, `reset_log.py` | Box, Dial |
| `bbox_ui.py` / `dial_ui.py` | deliberately different renderers, shared tokens |
| `ledColor.js` / `ledcolor.js` | ChatBroadcast, iconmaker |

Tag vocabulary is duplicated separately with nothing enforcing consistency:
`Bag2/Code/lib/game_tags.py`, `Bag3/Code/lib/game_tags.py`,
`MockWand/lib/game_tags.py`, `IconDisplay/lib/display_tags.py`,
`Live_Page/WebApp2/hubCode2/game_tags.py`,
`Live_Page/WebApp2/js/utils/commands.json`, `Live_Page/wand_icons.html`,
`Simulator/vendor/lib/game_tags.py`.

---

## Rules summary

1. Each device gets its own tree and its own `lib/`. No shared device abstraction.
2. hubtype string, `_CONFIGS` key and `ROLE_FILES` key are the same string.
3. Every new device declares its own distinct staging designator. No designator is the
   wand's; `_icon` is the icon display's. Neither is available to a new device.
4. Add the role to `ROLE_FILES` in **both** `code_server.py` copies in one commit.
5. Add the staging suffix to **both** `_boot_scan_games()` copies in the same commit.
6. Each staging suffix becomes a reserved slug ending.
7. A device with no assets sets `icons: False` and uses none of the asset leg. Do not
   copy the icon library, the panel, the Icon Maker or their devtests into a tree that
   has no pictures.
8. `pull_flag.is_pending()` is `main()`'s first statement; nothing radio-claiming is
   imported before it.
9. A `getcode` tap queues a pull and resets; it never pulls in place.
10. Radio comes up before any large allocation, unless `memprobe` proves otherwise on
   hardware.
11. Errors surface loudly. No `try/except: pass`, no silent degradation. A missing
    capability costs that capability and nothing else.
12. Device code is MicroPython: `%` formatting, no f-strings, no type annotations, no
    `typing`/`dataclasses`/`pathlib`/`logging`. Any loop doing serial I/O sleeps
    `1 ms` unconditionally every iteration. (The repo-root `AGENTS.md` says the
    opposite — "f-strings are used throughout, don't fix them". Flagged, not
    reconciled: no device tree under `Bag3/Code/` or `Bag2/Code/Wand Module/` contains
    an f-string, and both `PHASE6_HANDOFF.md` and `knowledge/icon_display.py` state
    that f-strings crash this MicroPython build.)
13. Games are optional skills. A tag for a game this device lacks gives a warning, not
    a load failure.
14. One knowledge file per device type, naming the other devices' signatures as
    forbidden.
15. `<slug><suffix>.py` is a Box/Dial staging name only. On the device the file is
    always plain `<slug>.py`.
16. Fixing one PEER copy fixes only that copy. Say which tree was touched.
