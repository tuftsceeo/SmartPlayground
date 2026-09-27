# Known issues and cleanup candidates

Dated triage backlog. Not exhaustive, not prioritized — a record of what was found while writing
the [AGENTS.md](../AGENTS.md) set on 2026-08-10, kept separate so those files can stay purely
descriptive. Update the date on an entry when you revisit it; don't silently delete resolved items,
mark them resolved.

## 2026-08-10

### Open hardware/design questions

- **Card storage format undecided.** NDEF text (current) vs. a 4-byte opcode at page/block 5
  (`Bag3/Code/lib/opcodes.py`, `Bag3/Code/utilities/migrate_cards.py`) is being explored on
  `origin/claude/pn532-5x5` ≡ `origin/opcodeexperiment`, commits `71e7c08` and `9ccd917`. Neither
  accepted nor rejected as of this writing.
- **5×5/PN532 revert not yet landed in Bag3.** The next hardware round's LED matrix and NFC reader
  choice (commit `8e567ca` on the same branch) needs merging into `Bag3/Code/` on `May_2026`; the
  currently committed 6×10/WS1850S code there is a one-off exploration that isn't going forward.
- **ChatApp is broken on this branch.** `ChatApp/` here is a 3-file fragment that cannot run
  standalone (missing `css/layout.css`, `css/buttons.css`, `css/chat.css`, `css/editor.css`,
  `js/app.js`). The working 22-file version lives on `origin/chatApp`, unmerged since 2026-06-16.

### Landmines

- **Adding a print to `code_server.py` or `code_puller.py` can stop a device's radio starting.**
  Both are imported before their radio claims the large contiguous IDF DRAM block it needs, and
  import-time allocation (docstrings, format strings) is paid whether or not the code runs. On
  2026-09-23 this left both Dials at `idf_largest=7680` and unable to arm until power-cycled, with
  `gc.mem_free()` reading a reassuring 81 KB — the failure is fragmentation, not exhaustion.
  Diagnostics belong in `serve_probe.py` / `pull_probe.py`, imported lazily after bring-up. See
  [Bag3/Code/BroadcastCode/docs_and_design/2026-09-23-ap-memory-order.md](../Bag3/Code/BroadcastCode/docs_and_design/2026-09-23-ap-memory-order.md).

### Verified drift

- `Live_Page/WebApp2/hubCode2/game_tags.py` vs `Bag3/Code/lib/game_tags.py`: hubCode2 has extra
  `jumpin1`–`jumpin5` entries and is missing `HIDDEN_TAGS = {"finddevice"}`. Confirmed by diff.
- `Bag2/Code/Wand Module/` and `Bag3/Code/Wand Module/` differ in 13 of 23 files. Nobody has
  classified which of those 13 are hardware-specific (fine to diverge) vs. hardware-agnostic bug
  fixes that should be back/forward-ported.

### Dead code — do not extend without a reason

- `Bag3/Code/lib/ble_splat.py` — zero importers anywhere in `Bag3/` (confirmed by grep); the wand's
  `hubtype.py` config has `uses_ble: False`.
- `Bag3/Code/Wand Module/improved_gestures.py` — a strictly more sophisticated gesture-recognition
  rewrite (gravity-vector tracking, DTW matching) than the currently wired `gestures.py`, but never
  registered in `GAME_DISPATCH` and never imports `game_tags`.
- `Bag3/Code/utilities/program_cards.py` — an orphaned LEGO-robot-derived opcode card scheme,
  importing a `wand` object shape (`_send_command`, `_nfc_ready`) that doesn't exist anywhere in
  Bag3. Unrelated to the opcode-card exploration on `origin/claude/pn532-5x5` despite similar names.
- `Live_Page/WebApp2/mpy/hub_bluetooth.py` — `BluetoothConnection.__init__` raises
  `NotImplementedError`; never imported. Same for `js/adapters/bluetoothAdapter.js` (5-line stub)
  and the BLE stub functions kept in `main.py`/`main.js`.
- `Live_Page/WebApp2/js/components/modals/connectionModal.js` — never imported by `main.js`.

### Latent bugs

- `Live_Page/WebApp2/js/main.js::handleHubDisconnect()` calls
  `PyBridgeToUse.disconnectHub()`, which `pyBridge.js` no longer defines (only
  `disconnectHubSerial()` exists). Currently unreachable because the hub connection mode is always
  `"serial"`, but it will throw `TypeError` the moment a second mode is added.
- The antenna-config and C3-display regex patches in `Live_Page/WebApp2/js/components/modals/hubSetupModal.js`
  and `Live_Page/Flasher/js/hubConfig.js` are silent no-ops: the `__ANTENNA_CONFIG_START__`/
  `__DISPLAY_CONFIG_C3__` markers they look for are absent from `Live_Page/WebApp2/hubCode2/main.py`.
  Antenna config is handled automatically for C6 elsewhere, but **a C3 hub flashed via WebApp2 or
  Flasher will get the wrong I2C pins** for its OLED.
- `Live_Page/If_Splats/py/splats.py` defines `setLEDs` twice (once at line ~101, again at ~108);
  the first definition is dead, shadowed by the second.

### Stale / cleanup candidates

- `WebAppDocs/` documents a directory layout (`App_Web/webapp/...`) removed in an earlier
  reorganization. Recommend deletion — not touched in this pass.
- `Live_Page/Code_Upload/` has ~90% functional overlap with `Flasher/` and is hardcoded to the
  stale branch `beta_January_2026`. Candidate for deletion once confirmed nothing still links to it
  besides the landing page.
- `.github/CODEOWNERS` has exactly one active rule, for `/Plushie_Module/` — a path that moved to
  `Bag1/Plushie_Module/` in an earlier reorganization. As written, it is inert: no PR anywhere in
  the repo currently requests a code-owner review.
- `Live_Page/WebApp/version.json` and `Live_Page/WebApp2/version.json` are identical and read by
  neither app.
- Roughly 30 remote branches beyond `May_2026`/`main` appear abandoned; worth a pass to close stale
  PRs and delete merged/dead branches.
- `Live_Page/index.html:163` has a malformed heading (`<h1></h1>SmartPlayground @ Tufts Homepage</h1>`).
- `Live_Page/Wand Pages/student-guide.html` is not linked from `Live_Page/index.html`.

## 2026-08 (Bag1/Bag2 documentation pass)

- **Wand module `readme.md` + `GAME_AUTHORING_GUIDE.md` are byte-identical across Bag2 and Bag3**
  (md5 `fe70b536…` / `3397c092…`) — correct for Bag2, unverified for Bag3 (Bag3's committed hardware
  doesn't match what these files describe; see `Bag3/AGENTS.md`). Bag3 needs its own copy or an
  explicit hardware-section correction once its target hardware is confirmed.
- `__pycache__/` directories are committed in `Bag2/Code/lib/`, `Bag2/Code/Wand Module/`,
  `Bag2/Code/StickS3 Narrator/`, `Bag2/Code/Speaker/`, `Bag2/Code/DialSpeaker/`, and
  `Bag3/Code/lib/` (including two Bag3-only `.pyc` files).
- `Bag2/Documentation/README.md` links `FREEZE_DANCE_README.md`; the file on disk is
  `freeze-dance-readme.md`.
- **Readme casing was inconsistent across the repo** (`README.md` vs `readme.md`, sometimes both
  within the same tree). Fixed within `Bag2/` only during this pass — all 9 lowercase `readme.md`
  files there were renamed to `README.md` (`Bag2/README.md`, `Code/README.md`, `Code/Speaker/`,
  `Code/Stations/Programming Station/`, `Code/Stations/Slide Score Station/`,
  `Code/Wand Module/`, `Documentation/`, `Unit Tests/`, `Utilities/`), using a two-step rename so
  git records them as renames rather than delete+add. `Bag2/Code/lib/README.md`,
  `Bag2/Code/M5Paper Remote/README.md`, and `Bag2/Code/StickS3 Narrator/README.md` were already
  uppercase and untouched. **`Bag2/Code/Wand Module/README.md` and `Bag3/Code/Wand Module/readme.md`
  are now differently cased** despite being byte-identical content — Bag3's was left as-is since
  Bag1/Bag3 casing normalization was out of scope for this pass.
- `Bag1/Plushie_Module/games/nfc_sound.py` and `games/Now_sniffer.py` exist but are unregistered in
  every `Config` variant in `config.py`.
- `Bag2/Code/StickS3 Narrator/README.md` references `assets/_generate_phrases.py` as "not present in
  this checkout" — confirm whether the WAV-generation script should be tracked.
- **Speaker station and dial station implement overlapping but different `FD_*` ESP-NOW command
  sets.** Speaker station (`Bag2/Code/Speaker/`) handles `FD_GO`, `FD_FREEZE`, `FD_NEXT`, `FD_PREV`,
  `FD_VOL_UP`, `FD_VOL_DOWN`. Dial station (`Bag2/Code/DialSpeaker/Dial_Music.py`) handles only
  `FD_GO`, `FD_FREEZE`, `stop`. Worth a decision on whether these should converge into one command
  set, given they serve the same Freeze Dance role on different hardware.
- **Bag2↔Bag3 Wand module divergence, recorded as fact, not a defect to fix:** `lib/` differs only in
  `hubtype.py`, `leds.py`, `pn532.py` (plus Bag3-only `power_led.py`, `ws1850s.py`; Bag2-only
  `lib/README.md`); 13 `Wand Module/` files differ by 2–17 lines each, predominantly LED-geometry
  index math (`NUM_LEDS 25→60`, `i // 5`/`* 5` → `i // 6`/`* 6`). Given the current August 2026
  hardware direction (5×5 for the next round), most of this divergence is expected to reduce once
  Bag3 adopts matching geometry — but that is not yet decided, see `Bag3/AGENTS.md`.
- `Bag2/Code/legacy/` (`gesture.py`, `gesture_engine.py`) and `Bag2/Battery Tests/` /
  `Bag2/Design Files/` contents were not read in detail during this pass — flagged in
  `Bag2/AGENTS.md` as unverified rather than described.
- `Bag2/Code/encrypted_key.txt` and `Bag2/Utilities/encrypted_key.txt` exist in a public repo with
  undocumented purpose. Reviewed with the project owner during this pass and explicitly not flagged
  as a security concern — noted here only so the files' existence isn't rediscovered as a surprise.

## 2026-08-28 (AGENTS.md condensation pass)

- **No Flasher manifest exists for Bag3 wand hardware.** `Live_Page/Flasher/manifests/` covers
  `wand` (sourced from Bag2), `hub`, and `m5paper` only; Bag3 firmware has to be uploaded via
  MicroPico manual connect. Moved here from `Bag3/AGENTS.md`.
- **`Live_Page/WebApp2/pyscript.toml`'s `[files]` list carries ~20 unnecessary `js/*` entries.**
  JS is loaded by the browser as native ES modules and never enters PyScript's virtual filesystem;
  `js/adapters/serialAdapter.js` and `js/adapters/bluetoothAdapter.js` are unlisted and work.
  Only Python modules imported by `main.py` (`mpy/*`, `hubCode2/*`) actually need listing. The
  earlier claim that every JS and Python file must be listed was wrong.
- **`Bag2/Documentation/README.md` links `FREEZE_DANCE_README.md`; the file on disk is
  `freeze-dance-readme.md`.** One-character fix; previously recorded in `Bag2/AGENTS.md`.

## 2026-09-26 (Splat Companion EUM pass)

Found while writing the Splat Companion bridge, then at
`Bag3/Code/BroadcastCode/EspnowModem/SplatCompanionEUM/`, since moved to
`Bag3/Code/BroadcastCode/SplatCompanion/` (2026-09-26, device-onboarding pass, below). None of
these were changed in the trees they are in; details in that directory's README, "Drift and
findings".

### Verified drift

- Splat note names: `Bag2/Code/lib/actions.py` (and the note cards) use `note_a` … `note_c_high`;
  `Bag2/Code/Splat Companion/main.py` `NOTE_MIDI` uses `notea` … `noteb`, so card note names are
  dropped there silently. Note values also differ between that file (`c`=0 … `b`=11, velocity
  127, instrument 17) and `legacy_jan26_wand_ble_splat_ctrl.py` (`c`=1 … `b`=15, velocity 255,
  instrument 16). Confirmed by reading both.
- `Bag2/Code/Splat Companion/ble_splat.py` holds the wand-side `ble_splat_ctrl.py` controller, not
  the `OpenSplat` driver its sibling `main.py` imports; the import only works when
  `/lib/ble_splat.py` wins. Confirmed by reading the file header and `grep "class OpenSplat"`.

### Latent bugs

- `Bag2/Code/lib/ble_splat.py` ≡ `Bag3/Code/lib/ble_splat.py`: `_handle_button` updates
  `_last_raw_state` before its 80 ms debounce check, so a release < 80 ms after a press is dropped
  and the button stays "pressed" until the next full press. Reproduced in
  `EspnowModem/tests/test_splat_companion.py` before `SplatLink` overrode the handler.
- Same driver: a late `SCAN_DONE` IRQ clears `_scanning` while a newer scan runs; the next
  `gap_scan()` raises `EALREADY`. Reproduced in the same simulation (fake BLE).
- `send_splat_config()` is defined in every `espnow_manager.py` copy and called nowhere, so no
  fielded wand sends `splat_config` to the Bag2 companion. Confirmed by grep across `Bag2/`,
  `Bag3/`, `Live_Page/`.

### Dead code update

- `Bag3/Code/lib/ble_splat.py` still has no importers in `Bag3/Code/`, but a byte copy is now used
  by `SplatCompanion/lib/ble_splat.py` (copy checked by its test).

## 2026-09-26 (Splat Companion device-onboarding pass)

Found while turning the bridge above into a full `Bag3/Code/BroadcastCode/SplatCompanion/`
device tree per `Bag3/Code/BroadcastCode/docs_and_design/DEVICE_ONBOARDING_SURFACES.md`. Not
fixed in the trees they're in unless noted.

### Latent bugs

- **`IconDisplay/main.py`'s `main()` calls `ESPNowManager().init()` before
  `pull_flag.is_pending()`**, violating the onboarding doc's rule 1 (nothing radio-claiming may run
  ahead of the pull check) and its own file's comment saying otherwise. `SplatCompanion/main.py`
  follows the rule correctly and `tools/devtests/boot_splat.py` calls the real `main()` with a
  pending flag to prove it (asserting `ubluetooth`/`espnow_manager` never enter `sys.modules`);
  `tools/devtests/boot_display.py` never calls IconDisplay's `main()` at all, so this went
  unnoticed. Not fixed on `IconDisplay/` — flagged per AGENTS.md's "flag rather than silently
  reconcile."
- **`tools/devtests/game_menu_scan.py` fails independently of this pass**: `_run_one("Box", ...)`
  raises `ModuleNotFoundError: No module named 'bbox_server'`, and the Dial case is presumably hit
  the same way. Confirmed with `git stash` that it fails identically on the pre-onboarding tree, so
  it is not a regression from `SplatCompanion/` or the `STAGING_SUFFIXES` change to
  `bbox_server.py`/`bdial_server.py`. `tools/devtests/nfc_display.py` fails for the same shape of
  reason (`ModuleNotFoundError: No module named 'card_writer'`). Not investigated further; not
  fixed.

### `hubtype.py` divergence, widened

- `SplatCompanion/lib/hubtype.py`'s own `"splat_companion"` entry now has `has_nfc: True`,
  `nfc_addr: 0x24` and `i2c_freq: 100_000`, matching this device's actual PN532 + MAX17048 bus. The
  four other copies (`MockWand/lib/`, `Bag3/Code/lib/`, `Bag2/Code/lib/`, and the tree removed by
  this pass) still carry the earlier bridge-only entry (`has_nfc: False`, `i2c_freq: 400_000`).
  Deliberately not reconciled: those four are peers of each other and of the wand's own hubtype
  handling, not of this device's actual hardware.

### Dead code, updated again

- `Bag3/Code/lib/ble_splat.py` is still imported nowhere in `Bag3/Code/` proper; its only real
  consumer remains `SplatCompanion/lib/ble_splat.py`, a checked byte copy in the tree this pass
  created.

### Stale paths

- `Bag3/AGENTS.md`'s broadcast-devices table rows for `broadcast_box` and `broadcast_dial` give
  their trees as `Code/BroadcastBox/BBoxFirmware/` and `Code/BroadcastDial/BDialFirmware/`, missing
  the `BroadcastCode/` component both actually live under (confirmed against the real tree). The
  new `splat_companion` row added by this pass uses the correct full path; the other two are left
  as found.

## 2026-09-27 (Splat Companion review follow-up)

### Behavior change

- **The Bag3 Splat Companion no longer handles `splat_config`, `splat_cmd` or `splat_event`.** The
  idle ESP-NOW↔BLE bridge carried over from the Bag2 companion was removed; the station is
  games-only, like the icon display. The `send_splat_config()` helpers in the other trees'
  `espnow_manager.py` copies, and the modem's `splat_config` classification in
  `EspnowModem/modem/lib/eum_classify.py`, are unchanged and now have no Bag3 consumer.
