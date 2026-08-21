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
