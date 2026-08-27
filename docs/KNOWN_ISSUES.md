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
