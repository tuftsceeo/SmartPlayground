# Remaining simulator + ChatBroadcast fixes

## Context
From the 2026-10-27 UI review (`Bag3/Code/Simulator/ui-review-2026-10-27.md`), the user confirmed a fix list. Done already: Splats as their own devices (main screen + overlay cards), square framed icon displays, overlay alignment, saved-game code block with View code, LED clear on stop, one green "View Multiple Device Simulation" button. This plan covers the rest. Rules from the user: no added text, tooltips only for labels, code keeps streaming into chat, nothing muted on Splats, commit only when asked.

Paths below are relative to `Bag3/Code/`.

## Status
- Done: icon display look (square cells, editor colour model, cartoon case).
- ChatBroadcast (§3, #11): in its own session.
- Remaining here: #2 reset per game, equal compact cards, × side, labels, tag picker, §2.

## 1. Multiple Device view (Simulator)
**#2 Reset per game** — `Simulator/sim-room.js` wands panel `update()` only calls `setFor()` when `gameWands` changes. Track a game identity (`room.game` or a source hash at load, not on code edits of the same game); when it changes, call `panel.setFor(room.gameWands)` and have the displays panel drop non-game displays (`js/panels/display.js` `sync()` – remove hand-added `auto:false` entries too on game change). No message at the cap.

**Equal, smaller cards (fits 2 rows of 4 wands + 8 Splats + 4 displays)** — in `js/panels/wands.js` dialog CSS:
- `.aw-grid` → fixed card width via `--card` (e.g. `clamp(150px, (100% - 5*gap)/6, 220px)`), `grid-template-columns: repeat(auto-fill, var(--card))`.
- Overlay wand cards show only the wand pad (hide the controls pane inside the dialog): add a `compact` attribute on `<wand-sim>` honored in `js/controls.js` CSS (`:host([compact]) .sim-pane-ctrl {display:none}`, pad fills width). Set it in `placeWand(card)` / `goLive`, remove on return home.
- `--wand-pad` becomes the card width; Splats/displays already size from it (`sizeDisplays()`).
- Moves (shake etc.) still available? In compact cards the wand's own button/tilt on the pad still work; motion buttons hidden — acceptable per "equal space" request.

**× placement by OS** — one helper `closeSide()` (`navigator.userAgentData?.platform || navigator.platform` matches /Mac/ → left). Chips row: `.chips` gets `flex-direction: row-reverse` on Mac so the × sits farthest left; otherwise `margin-left:auto` far right. Every card (wand, Splat, display) gets a × in the chips row; the room's own wand card has none. Splat × for other wands = remove from that wand (lower its Splat count) — skip if not supported by `lobbyGame`; display × already exists (moved into chips).

**#9 #20 Labels** — one chip style for all: "Wand 1", "Wand 2"…, "Splat", "Display 1/2". Drop "This wand"/"Playing" colors split. Display canvas stays black until the first frame (currently draws a green test grid before any message) — find the idle draw in `display.js` device and skip it.

**#10 Tag picker** — `js/controls.js` `.tag-pop` (absolute under the button, inside shadow DOM, clipped by card). Change to `position: fixed`, positioned in `setTagMenu(true)` from the button's `getBoundingClientRect()` (open beside/above the button, clamp to viewport), `z-index` high; reposition on scroll/resize while open. Works in both main and overlay (dialog is top layer — render the popover inside the same shadow root so it stays above the dialog contents).

**Icon display look** (done) — `js/panels/display.js` `drawSquares`: 16x16 rounded-square cells; lit cells coloured with the icon editor's `ledSwatchHex` model; off cells dark grey on a black (smoked) diffuser; rounded charcoal case with highlight and drop shadow, matching the wand and Splat style.

## 2. Simulator controls/layout
**Remove status line** — `js/controls.js:326-327` markup + CSS ~170-176; keep `renderStatus` writing to the wand's `title`/aria only (errors still need surfacing: show error text in the existing failure overlay).

**Remove play cards** — `wand-sim.js:70-77` "new-code" and "paused" overlays. ChatBroadcast `js/app.js:2344` (paused) and `:2415` (new-code): stop showing them; new code autostarts (`autostart = true` / call `start()`), and pause just stops silently (or drop the idle pause). Keep game-over / can't-simulate overlays.

**#13 #32 sizes** — Splats no longer in the pad (done); remove `.pad.has-extras` rules. Make `.icon-btn` (mute, Start over) `min-width/min-height: 44px`; wand button stays ≥44px.

**#11 Narrow screens** — `BroadcastCode/ChatBroadcast/css/app.css` `@media (max-width:768px)`: chat keeps `flex:1 1 auto` with a min height (e.g. `min-height: 55vh`); `.preview-col` capped (`max-height: 40vh`) with the simulator scaled down (`--wand-scale` / smaller `.sim-pane-wand` clamp min, e.g. 140px) instead of a nested scroll. Chat has priority.

## 3. ChatBroadcast
**#4 Saved replay** — `js/app.js` `openSavedGame` replay (~1639): skip a user turn whose content starts with "I would like to remix" (built in `remixCurrentExample` ~2159); still kept in `chatHistory` for the model. Going forward, mark it: push `{role:'user', content, hidden:true}` in `callClaude` when called from remix, and skip `hidden` turns on replay (prefix check covers already-saved games).

**#21 #26 #27 tooltips only** — add `title` (and matching `aria-label`) to `#btn-new-game`, `#btn-save-game`, `#btn-open-game` (index.html:163-171) and Start over (`controls.js` :336-338). Disabled `#btn-send-box` / `#btn-use-as-is`: set `title` to the reason ("Connect to the Box first") whenever disabled. Unsaved dialog (index.html:453, app.js:1355): put the game name in the dialog's title text only if it fits the existing string — e.g. "“Pass the Star” hasn't been saved yet" (no new text block).

**#31 Keyboard** — `.splash-card` (index.html:19,24,29), saved cards (app.js:1500-1525), gallery cards (app.js:1537-1546): add `tabindex="0"`, `role="button"`, Enter/Space → same click handler (one shared helper `makeActivatable(el, fn)`). Rename/delete buttons keep their own handlers.

**#33 Saved game icons** — replace the fixed `iconSvg('wand')` thumbnail (app.js:1505) with up to three small icons, no counts or text:
- one wand vs multiplayer: `simSettings.wands > 1` or game is a lobby game (`hardware`/code has `SPLATS_MIN` / `lobby_game`) → "wands" icon, else "wand".
- Splats shown only if the code declares `SPLATS_MIN` or `simSettings.wand_splats > 0` with a lobby game.
- icon display shown only if `roleCode.icon` (or `iconCode`) exists.
Hide `#btn-station-catalog` in simple mode (toggle with the existing advanced/simple mode switch, app.js ~665).

## Out of scope (dropped by user)
#3, #5 hiding, #6, #7 beyond removing cards, #8 (only via a test game if asked), #12, #15, #16–19, #22–25, #28–30, #34, remix chips.

## Verification
- `python3 -m pytest -q Simulator/tests` (97 pass) and `node --check` on touched JS.
- Simulator page http://localhost:8767/Simulator/ (start `python3 -m http.server 8767` from `Bag3/Code` if down): splattag + 4 wands + 4 displays → all cards equal, two rows fit at 1280×800; × side on Mac = left; switching games resets devices; tag picker fully visible in main view and overlay; no status line; no play cards.
- Resize to 768 and 375 (`resize_window`): chat usable, wand visible without nested scroll.
- ChatBroadcast http://localhost:8767/BroadcastCode/ChatBroadcast/: user types the access code; then check saved-game icons, reopened remix game hides the remix message, keyboard Tab/Enter on cards, tooltips, simple mode hides NFC Station button.
