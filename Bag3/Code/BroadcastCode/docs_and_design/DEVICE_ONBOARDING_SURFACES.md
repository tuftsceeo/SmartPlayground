# Adding a device to the broadcast ecosystem — surfaces to add and modify

Scope: what must be written or changed to make a new playground device a target
ChatBroadcast can generate code for and the Broadcast Box or Dial can serve.

**The wand is the baseline.** `MockWand/` is the default case in every sense that
matters here: it is what an undesignated game file is for, what `DEFAULT_ROLE`
resolves to, what a request naming no hubtype gets, and the tree a new device is
copied from. A new device is described by how it *deviates* from the wand, and each
deviation has exactly one place it must be declared.

Every site below is edited by hand. There is no device registry and none is planned —
each device gets its own tree and its own `lib/`.

Line numbers are as of this writing and will drift. Symbol names are the stable
reference.

---

## What a new device inherits unchanged

Copy these from `MockWand/` and do not redesign them. They are the same on every
device and carry measured reasons.

| Concern | Files |
|---|---|
| Pull across a reset | `code_puller.py`, `pull_flag.py` |
| Games on flash | `lib/game_store.py` |
| Radio | `lib/espnow_manager.py` |
| Device config | `lib/hubtype.py` |
| Heap instrumentation | `lib/memprobe.py` |
| Boot | `boot.py` |

All are PEER copies: a fix in one is not a fix in the others.

### Rules that come with them

1. **`pull_flag.is_pending()` is `main()`'s first statement.** Nothing before it may
   import `espnow_manager` or any other radio-claiming module. A SoftAP join only
   succeeds on a radio ESP-NOW has never touched this boot, and MicroPython exposes no
   `esp_wifi_deinit()` to clear it from Python. `pull_flag.py`'s docstring records the
   measurement: cold, transfers first try; warm, 3/3 real taps failed.
2. **A `getcode:<slug>` tap queues and resets — it never pulls in place.**
   `set_pending(slug)` then `machine.reset()`.
3. **The attempt budget is spent before each attempt** (`pull_flag.bump()`), so a crash
   mid-pull cannot boot-loop.
4. **Only a broken transfer retries.** `noap`, `nojoin`, `norequest` and success all
   clear the flag — a second boot would scan the same air, join the same AP and ask for
   the same missing game.
5. **Radio before any large allocation.** `esp_wifi_init()`/`esp_wifi_start()` need
   contiguous internal IDF heap that MicroPython's GC heap is carved out of. A device
   whose allocations are small may reorder, but must `memprobe.probe()` around each
   radio stage to confirm on the first bench run.
6. **No boot grace periods.** All are zero; `kbd_intr()` is never disabled, so Ctrl-C
   always reaches the REPL.
7. **Pulled games live in `/games/<slug>.py`, never the flash root.** `main.py` appends
   `/games` to `sys.path`; root precedes it, so a stale root copy would shadow a freshly
   pulled one.
8. **Slugs are MicroPython module names** — lowercase, leading letter, `[a-z0-9_]`, ≤16
   chars. Enforced in three places that must agree: `ChatBroadcast/js/gameName.js`
   (`slugify`/`isValidSlug` and its reserved list), `lib/nfc_reader.py`
   (`is_valid_slug`), `lib/game_store.py`.
9. **Errors surface loudly.** No `try/except: pass`, no silent degradation. A missing
   capability costs that capability and nothing else — a device with no card reader
   still boots, still pulls, still plays.
10. **Games are optional skills.** A tag for a game this device lacks gives a warning,
    never a load failure.

---

## Where a device declares how it deviates

Six axes. Everything else follows the wand.

| Axis | Declared in | Wand's value |
|---|---|---|
| **Identity** | `hubtype.txt`, one line | `wand` |
| **Hardware** | `lib/hubtype.py` `_CONFIGS["<hubtype>"]` — pins, LED count, capability flags | the `wand` entry |
| **Designator** | `ROLE_FILES[...]['suffix']` on Box and Dial | `''` — no designator |
| **Game signature** | `main.py`'s `play()` call, mirrored in `js/upload.js` `ROLE_SIGNATURES` | `play(nfc, leds, buz, accel, i2c, enow, batt=None)` |
| **Tag vocabulary** | `lib/<device>_tags.py` | `lib/game_tags.py` |
| **Extra files with a game** | `ROLE_FILES[...]['icons']` | `False` — game file only |

A device that needs none of the last axis sets `False` and touches nothing further.

### The designator rule

The staging suffix is the designator: on the Box or Dial it is the only thing that says
which device a given game file is for.

- **No designator is the wand's.** `ROLE_FILES['wand']['suffix'] = ''`, and it is also
  what `DEFAULT_ROLE = 'wand'` resolves a v1 request to — a request naming no hubtype
  at all. Both paths reach the undesignated file, so nothing else may claim it.
- **Every other device declares its own, distinct.** Reusing another device's
  designator hands it a file written for different hardware, and the pull path cannot
  detect that: the file arrives as plain `<slug>.py` and fails at `play()` call time.
- **Each designator becomes a reserved slug ending.** A game slug ending in an existing
  designator loses its wand file from the Box and Dial menu. Nothing enforces this at
  send time; ChatBroadcast will push such a slug. A check in `gameName.js`'s reserved
  list is the fix.

Designators are Box/Dial-side only. The device never sees one — every pulled file lands
as `<slug>.py`, because each device holds at most one module per slug.

---

## Surface 1 — the new device's firmware tree

New directory under `Bag3/Code/BroadcastCode/`, sibling to `MockWand/`. Self-contained:
it imports nothing from the other trees.

### Files

| File | Contents | From |
|---|---|---|
| `hubtype.txt` | one line, the hubtype string | — |
| `boot.py` | must not drive any output device | `MockWand/boot.py` (PEER) |
| `main.py` | new — see below | shape of `MockWand/main.py` |
| `code_puller.py` | `REQ_V2`, `_write_request()`, `pull(...)` | `MockWand/code_puller.py` (PEER) |
| `pull_flag.py` | `PATH`, `MAX_ATTEMPTS`, `set_pending`/`bump`/`budget_left`/`requested_slug`/`clear` | `MockWand/pull_flag.py` (PEER) |
| `lib/hubtype.py` | the `_CONFIGS` entry for this device | `MockWand/lib/hubtype.py` (PEER ×4, already divergent in content) |
| `lib/espnow_manager.py` | `ESPNowManager` | `MockWand/lib/espnow_manager.py` (PEER) |
| `lib/game_store.py` | `GAMES_DIR='/games'`, `is_valid_slug`, `slugs`, `exists`, `set_last_pulled`/`take_last_pulled` | `MockWand/lib/game_store.py` (PEER) |
| `lib/memprobe.py` | `probe()`, `frag()` | `MockWand/lib/memprobe.py` (PEER) |
| `lib/<device>_tags.py` | `GAME_TAGS`, `CONTROL_TAGS = {"stop","getcode"}`, `EXIT_TAGS`, `exit_tags_excluding()` | shape of `MockWand/lib/game_tags.py` — a separate table per device, deliberately not shared |
| `README.md` | layout, the `play()` contract, an **Unverified** section | — |

Plus whatever drivers this device's hardware needs. `/games/` is created on the device
by `game_store`, not committed.

Card reader, only when one is fitted:

| Chip | Files |
|---|---|
| PN532 @ 0x24 | `lib/nfc_reader.py` (PEER) + `lib/pn532.py` |
| WS1850S @ 0x28 | `lib/nfc_reader.py` (PEER) + `lib/nfc_ws1850s.py` + `lib/ws1850s.py` |

`nfc_reader.py` is one shared file across both chips — `nfc_ws1850s.py` is a shim
presenting the four PN532 methods it calls. Do not fork the reader logic. `main.py`
scans the I2C bus at boot and prints every address found when `nfc_addr` is not among
them, so a wrong address reads off the boot log instead of presenting as a device that
silently ignores taps.

### `main.py` — required elements

All present in `MockWand/main.py`.

| Element | Reference | Rule |
|---|---|---|
| Module docstring | `:1` | States the exact `play()` signature this device calls |
| `GAME_MODULES` | `:75` | tag → module basename, built-ins only |
| Boot-time dispatch check | `:97` | Mismatch against the tag table prints `[ERR]`. Nothing else keeps the two in step |
| `_emit()`, `identity` | `:169`, `:933` | NDJSON, one object per line: `identity` once after boot, `heartbeat` every 5 s in the idle loop only, `game_start`/`game_end` around a launch, `error` on load failure. The only thing that makes the board recognisable on a direct USB connect |
| `_load_play()`, `_unload_game()`, `_launch_game()` | `:375`, `:394`, `:487` | Lazy import, force-switch chaining on an in-game `start_game` |
| `_start_play()` | `:457` | Tolerates an older, shorter `play()`. Reads `__code__.co_argcount` and makes the right call first time; where the port does not expose it, the full call is tried and an arity `TypeError` falls back. A parameter added after games were written and pulled would otherwise make every earlier game dead on the device |
| `_game_load_failed()` | `:416` | Loud: visible failure signal plus `sys.print_exception()` |
| `_run_pull_mode()`, `_pull_status()`, `_pull_progress()`, `_pull_fail()` | `:705`, `:672`, `:691`, `:660` | The five terminal outcomes and the in-progress feedback |
| `run_event_loop()` | `:569` | Poll `enow` every iteration; handle `start_game`, `stop`, game tags, `getcode:<slug>`. An unknown game over ESP-NOW is ignored, not an error |
| `main()` | `:798` | Ordering per the inherited rules above |

---

## Surface 2 — Broadcast Box and Dial

Four files, two PEER pairs. **A fix in one is not a fix in the other.** Editing the
Box's copy and not the Dial's leaves the device working on one and refused on the other.

| File | Symbol | Change |
|---|---|---|
| `BroadcastBox/BBoxFirmware/code_server.py:84` | `ROLE_FILES` | Add `'<hubtype>': {'suffix': '_xxx', 'icons': False}` |
| `BroadcastDial/BDialFirmware/code_server.py:84` | `ROLE_FILES` | Identical entry |
| `BroadcastBox/BBoxFirmware/bbox_server.py:676` | `_boot_scan_games()` | Add the new designator to the skip list |
| `BroadcastDial/BDialFirmware/bdial_server.py:668` | `_boot_scan_games()` | Identical change |

### Rules

- **A hubtype absent from `ROLE_FILES` is refused, not guessed at.** `_lookup()` returns
  `None` and the device gets an explicit zero-size reply, which it treats as terminal:
  it clears its flag and spends no retry. Handing a device a file written for different
  hardware is worse than telling it there is nothing for it.
- **`DEFAULT_ROLE = 'wand'` is untouched.** The `0xFF` sentinel is what lets one socket
  serve an un-updated wand and a hubtype-aware device.
- **Every designator must be in both `_boot_scan_games()` copies.** A staging file that
  is not skipped enrols in `index.json` as a playable game in its own right, appears in
  the menu under a name derived from its filename, and — being new this boot — can
  become the active game by mtime.
- **`icons` is the flag for a role that ships extra files with its game.** `False` means
  the transfer ends at the game file's ack, which is the wand's case and the default for
  a new device.

### Known gaps a new device inherits

- `do_games_delete()` (`bbox_server.py:480`, `bdial_server.py:472`) removes only
  `<slug>.py` and `<slug>.tags.json`. A staging file under a designator is left on flash.
- `do_games_clear()` removes `*.py` and `*.tags.json` at the top of `GAMES_DIR` only.

### Wire protocol — no change needed

```
v1:  device -> box :  len(1) | slug                        (len 0 = "serve active")
v2:  device -> box :  0xFF | len(1) | slug | len(1) | hubtype

     box -> device :  size(4B BE) | sha256(32B) | name_len(1B) | name
     box -> device :  file body, 512B chunks
     device -> box :  2-byte ack, b'OK' or b'NO'
```

v2 already carries the hubtype. A new device is a `ROLE_FILES` entry, not a protocol
revision. Any actual protocol change must be mirrored in all four files in one commit.

### Dial card-write menu

`dial_ui.py` reads `<slug>.tags.json`, pushed alongside the game. No change unless the
device introduces its own tag family.

---

## Surface 3 — the ChatBroadcast web app

The app calls a device a **role**. The wand role is the default: it is the tab a new
game starts on, the role an unmarked code block lands in, and the fallback everywhere a
role is not named.

### Files to modify

| File | Symbol | Change | Generic today? |
|---|---|---|---|
| `js/chat.js:63` | `ROLES` | Add the role key, in tab order | — |
| `js/chat.js:5` | `KNOWLEDGE_FILES` | Add `knowledge/<device>.py` | — |
| `js/chat.js:85` | `roleBefore()` | None. The `[DEVICE: …]` regex accepts any lowercase word; `ROLES` is the only gate | yes |
| `js/chat.js:100` | `extractCodeBlocks()` | None. An unmarked block defaults to the wand | yes |
| `js/upload.js:12` | `ROLE_SIGNATURES` | This device's `play()` parameter names, in order | — |
| `js/upload.js:27` | `OPTIONAL_PARAMS` | Parameters its `play()` may omit and still run | — |
| `js/app.js:~75` | `SYSTEM_PROMPT_BASE` | The required-signature line and the `[DEVICE: <role>]` marker | — |
| `js/editor.js` | `roleState` | None. Built from `ROLES`, so per-role code, history and tab membership come free | yes |
| `js/app.js:540` | `selectRole()` | None | yes |
| `js/app.js:265` | `syncRoleRail()` | Tab enable/label/visibility. Written for exactly two roles: one boolean decides whether the tab groups show at all, and the label is a wand/other ternary | **no** |
| `js/app.js:1695` | `updatePreview()` | A two-way switch over which preview is on screen. A further role needs its own branch | **no** |
| `js/app.js:1725` | `syncPreviewEmpty()` | Same two-way assumption, drives the placeholder glyph and caption | **no** |
| `js/app.js:2157` | `confirmSend()` | Validate this role's code and queue `<slug><designator>.py` into the same raw-REPL session. Written per-role today | **no** |
| `index.html:172`, `:240` | `.device-tab[data-role]` | One button per role in each of two groups — preview toolbar and code drawer. They are two views of one editor role and always move together | — |
| `js/hardware.js:29,96` | `buildHardwareReqs()` `stations` | Populate when the role has code, so the send-confirm overlay states the device is needed. Always `[]` today | — |
| `css/app.css:551` | `.device-tab` | None expected; confirm the rail does not overflow | — |

### Direct USB connection — only if the device connects without the Box

| File | Symbol |
|---|---|
| `js/device/bboxDeviceLink.js:32` | `EXPECTED_DEVICES`, `deviceShortName()`, `deviceProductName()` |
| `js/device/wandDeviceLink.js:30` | the model: `EXPECTED_DEVICE`, `FORWARDED_EVENTS`, and a `/hubtype.txt` check that refuses a mismatch |
| `js/device/wandGameInstaller.js` | the model: raw-REPL write to `/games/<slug>.py`, `set_last_pulled()`, exit raw REPL, Ctrl-D |
| `index.html:339` | connect-overlay picker entry |

### Knowledge file

`knowledge/<device>.py`, one per device type — there is no shared game API to document.
`knowledge/knowledge.py` is the wand's and the model to follow:

- A critical-contract block first: the exact signature to copy, and a
  forbidden-signatures list naming the other devices' signatures explicitly.
- What each argument is, whether it arrives already built, and what a game must never
  construct for itself.
- Which arguments can be `None` and the guard that requires.
- The hardware this device does **not** have.
- The ESP-NOW messages it exchanges with the other half of a pair.
- MicroPython rules: `%` formatting, no f-strings, no type annotations,
  `time.sleep_ms()` is milliseconds.

Where a device's generated code can name something that must already exist on it,
`getSystemPrompt()` (`js/app.js:~245`) appends the live inventory to the prompt and the
send is refused if the code names something absent. Read the inventory from its live
source, never hardcode it in the prompt.

### Preview

Only the wand has a simulator (`Bag3/Code/Simulator/`, Pyodide). A new device gets an
explicit branch in `updatePreview()` and `syncPreviewEmpty()` — a static preview if it
has visible output worth drawing, otherwise a "no preview for this device" state. Not a
second simulator.

---

## Surface 4 — host devtests

`Bag3/Code/BroadcastCode/tools/devtests/`.

| Test | Change for a new device |
|---|---|
| `compile_check.sh` | `py_compile` over `Bag3/Code`; picks the tree up automatically — confirm its glob reaches it |
| `wire_contract.py` → `wire_test.py`, `wire_test_dial.py` | New role cases: a v2 request resolves `<slug><designator>.py`, and an unknown hubtype is still refused. Run against Box and Dial |
| `game_menu_scan.py` | Assert the boot scan skips the new designator on both |
| `boot_<device>.py` (new) | Nothing radio-claiming imported before `_run_pull_mode()`; boot order; dispatch and force-switch chain; each pull outcome's feedback; loud load failure |
| `chatbroadcast_flow.mjs` | Extend to an N-block reply; assert the exact file list and ordering `pushPayload` writes, one raw-REPL session, one soft reset, reset last |
| `role_state.mjs` | Extend to an N-role cycle |
| `stubs/` | Add a stub for any module the tree imports that does not exist off-device |

Run the whole directory, not only the rows above — the rest is the existing regression
suite and must stay green. `check_tags.mjs` (under `ChatBroadcast/tools/`) going red is
a regression to report, not a test to edit: the tag checklist must not change for any
existing game.

Passing means the code compiles and the protocol, boot order, dispatch and static
derivations agree. It does not mean the device works — no radio, output hardware, card
reader or serial port is exercised.

---

## Surface 5 — documentation

| File | Change |
|---|---|
| `Bag3/AGENTS.md` | Add the tree to the broadcast-devices table (tree, device identity, hardware) |
| `Bag3/Code/HARDWARE_PROTOCOL.md` | The reserved designator list |
| `BroadcastBox/README.md` | The `ROLE_FILES` paragraph |
| `<Device>/README.md` | Layout, `play()` contract, an **Unverified** section |

---

## PEER copies a new device touches

Hand-duplicated, each carrying a `PEER:` comment. Adding a device grows the list.
Comments for now; deduplication is a later refactor.

| File | Copies |
|---|---|
| `code_server.py` | BroadcastBox, BroadcastDial |
| `code_puller.py` | MockWand, IconDisplay |
| `pull_flag.py` | MockWand, IconDisplay (byte-identical) |
| `game_store.py` | MockWand/lib, IconDisplay/lib (byte-identical) |
| `hubtype.py` | MockWand/lib, IconDisplay/lib, Bag3/Code/lib, Bag2/Code/lib — **divergent in content** |
| `espnow_manager.py` | MockWand/lib, IconDisplay/lib, Bag2/Code/lib, Bag3/Code/lib, hubCode2, M5Paper Remote, StickS3 Narrator, Simulator |
| `nfc_reader.py`, `ws1850s.py` | BBoxFirmware, IconDisplay/lib, Bag3/Code/lib |
| `json_link.py` | Box, Dial, IconDisplay, both Bag3 stations |
| `boot.py` | Box, Dial |

Tag vocabulary is duplicated separately with nothing enforcing consistency:
`Bag2/Code/lib/game_tags.py`, `Bag3/Code/lib/game_tags.py`,
`MockWand/lib/game_tags.py`, `IconDisplay/lib/display_tags.py`,
`Live_Page/WebApp2/hubCode2/game_tags.py`,
`Live_Page/WebApp2/js/utils/commands.json`, `Live_Page/wand_icons.html`,
`Simulator/vendor/lib/game_tags.py`.

---

## Rules summary

1. The wand is the baseline. A new device is described by how it deviates, and each
   deviation is declared in exactly one place.
2. Each device gets its own tree and its own `lib/`. No shared device abstraction.
3. hubtype string, `_CONFIGS` key and `ROLE_FILES` key are the same string.
4. No designator is the wand's. Every other device declares its own, distinct one.
5. Each designator becomes a reserved slug ending.
6. Add the role to `ROLE_FILES` in **both** `code_server.py` copies in one commit.
7. Add the designator to **both** `_boot_scan_games()` copies in the same commit.
8. `<slug><designator>.py` is a Box/Dial staging name only. On the device the file is
   always plain `<slug>.py`.
9. `pull_flag.is_pending()` is `main()`'s first statement; nothing radio-claiming is
   imported before it.
10. A `getcode` tap queues a pull and resets; it never pulls in place.
11. Radio comes up before any large allocation, unless `memprobe` proves otherwise on
    hardware.
12. Errors surface loudly. No `try/except: pass`, no silent degradation. A missing
    capability costs that capability and nothing else.
13. Games are optional skills. A tag for a game this device lacks gives a warning, not
    a load failure.
14. Device code is MicroPython: `%` formatting, no f-strings, no type annotations, no
    `typing`/`dataclasses`/`pathlib`/`logging`. Any loop doing serial I/O sleeps `1 ms`
    unconditionally every iteration. (The repo-root `AGENTS.md` says the opposite —
    "f-strings are used throughout, don't fix them". Flagged, not reconciled: no device
    tree under `Bag3/Code/` or `Bag2/Code/Wand Module/` contains an f-string, and both
    `knowledge/knowledge.py` and `knowledge/icon_display.py` state that f-strings crash
    this MicroPython build.)
15. One knowledge file per device type, naming the other devices' signatures as
    forbidden.
16. Fixing one PEER copy fixes only that copy. Say which tree was touched.
