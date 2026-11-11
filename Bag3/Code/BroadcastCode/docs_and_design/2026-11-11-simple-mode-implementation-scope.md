# Simple mode design corrections: implementation scope

This sorts the corrections in [2026-11-11-simple-mode-design-corrections.md](2026-11-11-simple-mode-design-corrections.md) by how much code each one touches. It was checked against branch `Chat_to_Tap_Doggle` at `6fc4c78`. Paths are relative to `Bag3/Code/`.

> **Some mocked screens aren't in this branch.** These strings and features don't appear anywhere in the code: "Flash", "Keep the wands close", "N of M wands ready", the "Connected: <hub>" banner, "To play you need", the "1 wand / 2 wands" toggle, "Play more wands" and the "X's turn" banner. They may live in an unmerged branch, or come from game Python code rather than the UI, or exist only in the mockups. For those items, the rows below say where the change would go if built new.

## Quick: a few isolated lines

| Change | Where | Notes |
|---|---|---|
| "Flash" → "Find Me" | `BroadcastCode/ChatBroadcast/js/distribute.js` row markup (~350–360); the `.dist-find` handler is at :301 | The label is one string. The Distribute dialog has no simple/advanced split, so the new label shows in every mode. |
| "colour" → "color" | `ChatBroadcast/index.html:239` ("Pixelation & segment colours") | This is the only visible string. Others are comments: `examples.js:8`, `Simulator/js/panels/display.js:103–123`. `iconmaker/` has many more, which is out of scope unless you want those too. |
| "restarting…" → "Reconnecting…" | `ChatBroadcast/js/router.js:207` (status chip); `distribute.js:208` ("Waiting for the Dial to restart…") | router.js runs in every mode, so advanced and dev mode see the new wording too. |
| Remove the hint and battery-notice text in the share dialog | Status messages in `distribute.js` (`_setStatus` at :208, 212, 244, 252, 266, 272, 280, 286) | The exact strings aren't in the code, so this is a matter of not adding them, or of trimming these status lines. |
| Rounder, indented chat bubbles | `ChatBroadcast/css/app.css:673–700` (`.msg`, `.msg.user`, `.msg.bot`) | CSS only:<br>- Bigger corner radius (about 22px) with one tight tail corner.<br>- More padding.<br>- `max-width` about 78% for user bubbles, so they're indented from the left.<br>- A right margin on bot bubbles, which are 95% wide today.<br>These styles are shared, so advanced mode changes too. |
| No "You asked" label on user messages | Nothing to change | There's no such label in the code; user messages are already unlabeled `.msg.user` bubbles. |
| Remove card borders and backgrounds on device panels | `Simulator/js/panels/wands.js` styles (:53, :85, :89, :91); `.box` in `Simulator/sim-room.js` (~205–215); card styles in `display.js` and `splats.js` | CSS only, but it covers several files. Check whether advanced mode relies on the cards to separate panels. |

## Medium: one area, several functions or files

| Change | Where | Notes |
|---|---|---|
| Sparkle avatar beside Coder replies | `addMsg` in `ChatBroadcast/js/chat.js:37`; `.msg.bot` CSS | Wrap bot messages in a row with a round avatar using the home icon gradient, aligned to the bottom of the bubble. This affects every caller of `addMsg`, including history replay (`app.js:1726–1738`) and streaming replies. Decide whether `.msg.system` messages get an avatar too. |
| Battery "Critical", with low wands listed but unchecked | `distribute.js:357` (battery label); `upsertReport` at :102–103 (rows start `selected: true`) | Add a threshold, a label, and a default of `selected: false` when the battery is low. |
| Warn on browsers without Web Serial, on app open and before the magic code prompt | Today the only check is a debug log at `ChatBroadcast/js/app.js:987–988` ("need Chrome/Edge"), which teachers never see. The magic code modal is `initAuthModal` in `js/auth.js:45`, and its markup is `#modal-overlay` in `index.html`. | Check `'serial' in navigator` at startup, before `initAuthModal`. Show a plain banner or blocking note such as "Use Chrome or Edge on a computer to send games to devices." Decide whether teachers can still continue to chat and use the simulator (recommended) or are blocked. It shows in every mode. |
| Distribute dialog layout: Refresh icon at top right, no bottom row, subtitle "Tap a wand to choose it." | `distribute.js:188` (close-X), :212 (Rescan); dialog markup in `index.html` (`dist-*`); `css/app.css` | Move Rescan next to Close and remove the button row. |
| Progress: a single "Sending…" button, gray until all wands finish, then "Done" | `distribute.js` `STATUS_TEXT` (:166), `_setStatus` (:252 "N of M devices updated", :280) | Drive the button state from `state.running` plus every row being done or failed. Remove the count line. |
| After sending: heading "Send it to the wands now?" | Post-send flow at `ChatBroadcast/js/app.js` ~1811 and ~2750–2780 | The heading copy doesn't exist yet, so it means adding a prompt step to the flow. |
| Requirement pills (UI side) | `ChatBroadcast/js/hardware.js` (`buildHardwareReqs` :35, `formatHardwareReqs` :97, `baselineTags` :15); `checklist.js:5` | There are no pills yet; requirements are listed as words. To build them:<br>- Skip the wand pill below 2, and skip other pills at 0.<br>- Exclude `getcode:<slug>` and `<slug>` (added by `baselineTags`) from the NFC tag count. |
| 5×5 saved-game thumbnails from the game's icon | `app.js:138` (`savedGameIcons`, used at :1587); the icon is parsed at `chat.js:159–168` and stored at `library.js:52`; shapes come from `js/ledicons/` | The data is already stored per game, so this is only the renderer. The library shows in both modes. |
| Minimize button per wand and icon display | Wand cards at `Simulator/js/panels/wands.js:76–82`, ~127–135; display cards in `panels/display.js` | New collapsed state that shows the illustration only. Needs a per-panel toggle and possibly persisted state. |
| Design-system device icons | `ChatBroadcast/js/icons.js` (`iconSvg` ~120–160); `Simulator/js/icons.js` | Swapping the icon markup is medium. Replacing the simulator's hand-drawn wand, display and Splat art (`renderer.js`, `wand-sim.js`, `display.js`, `splats.js`) would be large. |

## Large: cross-cutting, affects advanced and dev modes, the data model or the prompt

| Change | Where | Why it's large |
|---|---|---|
| The agent states minimum devices for a playable game (wands, icon displays, NFC tags, Splats) | `ChatBroadcast/js/prompt/buildRequest.js`; knowledge files loaded at `chat.js:15–35`; the `[GAME_SETTINGS:]` parser (`chat.js` ~200–230); `hardware.js` | The game-settings marker currently carries only `wands` (1–4) and `wand_splats`. Adding minimums for the other devices and a fixed or open-ended flag changes the prompt, the parser, the stored game data, and every consumer, including advanced and dev views. |
| Open with the minimum; fixed-count games start all wands and hide the add buttons; open-ended games show them | `Simulator/sim-room.js:36–39` (settings), :132 (`gameWands`), :472 (when the wands panel shows), :483–485 (`panel.setFor`); `panels/wands.js:117–118`, :179–189 (add buttons hide only when full) | There's no fixed vs open-ended flag. The flag needs the schema change above, plus simulator logic and `Simulator/README.md` (:83–122). The "1 wand / 2 wands" toggle and "Play more wands" aren't in this branch. |
| Splats as a shared group, not tied to a wand | `sim-room.js:375–455` (builds "the wand's own Splats" from `lobbyGame.wandSplats`, attached to `room.wand`; simple mode draws them in the wand pad at :214–215; all-wands dialog `splatCard` :426–439); `js/lobby_game.js`; `js/splats.js` | Splats are owned by a wand in the data model today. Ungrouping them changes how sim-room, the lobby game and the Splat bus relate. |
| Splat zone fills (inside vs outside, left vs right) with a gradient only between zones | `Simulator/js/panels/splats.js` (15 LEDs with inner/outer flag :76–78, drawn :131–132, colored :179–191) | Inside vs outside is already modeled per LED, so drawing it as two fills is medium. Left vs right needs new geometry and a new way to address LEDs, and it must stay in step with `SplatCompanion/Companion/splat_api.py` and the generated `splatActions.js`. |

## Not found in this branch

These are the turn banner ("X's turn…"), the "Connected: <hub>" banner and the "To play you need" header. Before scoping them, confirm which branch holds the newer simple-mode screens, or whether the turn text comes from game code.
