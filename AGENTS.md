# AGENTS.md

Non-production research prototype: MicroPython firmware for playground devices (ESP32-C6, ESP32-S3,
M5Stack) plus static web tools. Small team, weekly iteration.

## Device code (MicroPython)

- **Cannot be imported off-device** — `machine`, `espnow`, `neopixel`, and `ubluetooth` do not exist.
  `python -m py_compile <file>` is the only static check available.
- Shipped style, across all targets: f-strings are used throughout — don't "fix" them. No type
  annotations, and no `typing` / `dataclasses` / `pathlib` / `logging`.
- Any loop doing serial I/O needs a `time.sleep_ms(1)` unconditional sleep every iteration.
- **ESP32-C6 (XIAO): default to the onboard antenna.** GPIO3 = 0 enables the RF switch and
  GPIO14 selects onboard (0) or external (1); the switch carries both WiFi/ESP-NOW and BLE. Only
  the wand prototypes have u.FL antennas fitted. Ask before selecting external on any other board.
  Each board's code has its own setting (e.g. `EXTERNAL_ANTENNA`, `MODEM_EXTERNAL_ANTENNA`).
- **Nothing may allocate before the radio claims its memory.** WiFi/ESP-NOW bring-up needs one
  large *contiguous* block of IDF DRAM and must take it first thing on boot; nothing later can
  un-fragment the heap enough to find it again. `gc.mem_free()` does not measure this — the failure
  is fragmentation, not exhaustion. Adding prints (their format strings and docstrings are allocated
  at import, whether or not the code runs) to a module imported ahead of the radio has taken devices
  down twice. Diagnostics go in a separate module, imported lazily after bring-up. See
  [Bag3/Code/BroadcastCode/docs_and_design/2026-09-23-ap-memory-order.md](Bag3/Code/BroadcastCode/docs_and_design/2026-09-23-ap-memory-order.md).

## Branches

- `main` is stale. Ask which branch to work from, or check `origin/HEAD` — the integration branch
  changes.
- Don't push directly to the default branch; it's protected.
- Don't add production gating, release process, or verification requirements unless asked.

## Bags

A Bag is a hardware+software generation, not a version. Bag1 and Bag2 are fielded; Bag3 is in
progress. Cross-generation compatibility is not a goal.

- **Read `Bag3/Code/known_issues/` before working in Bag3.** Known-issue notes live there, not
  beside the code. `README.md` indexes them by topic and device; each note's YAML front matter
  lists `status`, `devices`, `code` paths, `open` items and `keywords`, so
  `grep -l <term> Bag3/Code/known_issues/*.md` finds the relevant one. Add new notes there with
  the same front matter and an index row.
- **Don't re-verify known issues.** A documented, tested failure stands as recorded; don't spend
  time or tokens re-testing it or re-implementing a pathway it records as broken.
- **Confirm before working a known issue.** If asked to explore or fix one, first state the issue
  in one sentence, cite its note, and get confirmation before attempting a resolution.

- `Bag1/` is fielded and not under active development — ask before editing.
- `Bag2/Code/Wand Module/` and `Bag3/Code/Wand Module/` are independent copies. Divergence is
  expected. Never apply a change to both silently; say which tree you touched.

## Shared libraries are duplicated by hand

`espnow_manager.py`, `game_tags.py`, `ssd1306.py`, and `ws1850s.py` are our own libraries, kept as
separate per-tree copies rather than imported across directories. Fixing one fixes only that copy.
If you find a copy that has diverged from its Bag's version, flag it rather than silently
reconciling.

`Bag3/Code/TeacherTools/NFC Station/` holds copies of `ws1850s.py`, `card_writer.py`,
`dial_board.py`, `dial_input.py` and `json_link.py` from `BroadcastDial/BDialFirmware/`, and `game_tags.py` from
`Wand Module/lib/`. The Broadcast Dial runs the Station's screens: `BDialFirmware/`
holds copies of `station.py`, `station_ui.py`, `station_fonts.py`, `text_entry.py`, `kb_rings.json`
and `kb_letters.bin`. Its `station.py` drops the catalog and serial commands and takes games, card
text and radio control from `bdial_server.py` (the host); its `station_ui.py` builds the keyboard
on first use and uses the Dial's beeps. `dial_input.py` is identical in both trees.

Game tags are consumed in four places, with nothing enforcing consistency: each Bag's
`lib/game_tags.py`, `Live_Page/WebApp2/hubCode2/game_tags.py`,
`Live_Page/WebApp2/js/utils/commands.json`, and `Live_Page/wand_icons.html`.

The 16x16 icon set is the same shape of problem. `Stations/IconDisplay/icons/` is the
source of truth, and three things copy from it by hand or by script:
`ChatBroadcast/js/ledicons/defaultIcons.js` (generated — run
`ChatBroadcast/tools/sync_icons.py`, and `--check` to detect drift), the station's
`Stations/Icon Display Station/icons/`, and `ChatBroadcast/iconmaker/`, which keeps its own
`assets/`, `maps/` and `fixtures.js`. The generated list is what tells the chat model which
icons exist — a game naming one outside it is refused at send time, so an icon added only to
the device is unusable in a generated game. Nothing runs the check automatically.

Splat action names follow the same pattern: `SplatCompanion/Companion/splat_api.py` (`COLOR_RGB`,
`NOTE_VALUES`, `ANIMAL_SOUNDS`) is the source of truth, and
`ChatBroadcast/js/splat/splatActions.js` is generated from it by
`ChatBroadcast/tools/sync_splat_actions.py` (`--check` for drift). A Splat game naming an action
outside that list is refused at send time.

## Dead trees

`old_stuff/` and `WebAppDocs/` are dead, and will dominate a naive grep.

## "hub" means two things

In `Live_Page/`, the teacher-facing ESP32 that bridges USB serial to ESP-NOW. In the Bag trees, any
playground component (`hubtype.txt` → `HUB_CONFIG`).

## "Station" is not one thing

`Bag3/Code/Stations/` holds `Icon Display Station`, `IconDisplay` (the Broadcast icon display) and
`SplatCompanion` (historical), and the Broadcast Box and Dial are also called stations. All are beta or bench tests, not used by teachers. Always name the specific one; never
write "the Station".

`Bag3/Code/TeacherTools/` holds `NFC Station` (a one-off NFC tag-writing tool, not live to teachers
or the team), the Bag3 `M5Paper Remote`, and the Broadcast Box and Dial (`BroadcastBox`,
`BroadcastDial`). `Bag3/Code/BroadcastCode/` keeps the ChatBroadcast web app, `tools/` and
`docs_and_design/`.

`Bag3/Code/Experiments/` holds non-functioning hardware experiments (`Capsule PN5180`,
`CrowPanel5 Display`, `IPS096 Display`, `Music Board Station`, `Radar Station`,
`WirelessFileTransferBak`, `EmulatedTagDial`, `EspnowModem`, `ProgrammableTag`, and the earlier Bag3
`Wand Module`). Despite some names, none of these are stations.

Likewise, `goalrace`, `splatecho`, and `jumpin1`–`jumpin5` (code-slot experiment) are bench-only
games, not classroom games. The Bag3 wand (`Bag3/Code/Wand Module/`, the Mock Wand) uses plain NDEF text tags; `opcodes.py` is not used there.
