# Wand & Station Coder — UI kit

A click-through recreation of the ChatBroadcast web app (`ChatBroadcast/index.html` + `css/app.css` + `js/app.js`). Teachers describe a playground game in chat, the assistant writes MicroPython for the wand, and the code is sent over USB to a **Broadcast Box** that hands it out to wands over NFC tags.

## Files
- `index.html` — the interactive kit. Splash → Examples gallery → game detail → chat workspace → connect → send → tag checklist → sent banner.
- `splash.html` — splash screen only, registered as a starting point.
- `Screens.jsx` — Shell, HeaderBar, SplashScreen, GalleryScreen, DetailScreen, WorkspaceScreen.
- `Overlays.jsx` — ConnectOverlay, SendOverlay, TagChecklistOverlay, BoxLibraryOverlay.
- `App.jsx` — view state machine and the fake chat/send flows.
- `data.js` — the seven real example games, verbatim from `js/examples.js`.

## What to click
1. **Browse examples** → pick *Melody* → **Remix this in chat**.
2. Type anything (or tap a starter chip); a canned reply arrives and the wand preview appears.
3. **Send to Box →** → **Connect via USB** → **Send** → step through the tag checklist.
4. **Connected** in the header opens the My Box library.

## Known gaps (not recreated)
- The wand **simulator** (`<wand-sim>`) lives outside the mounted folder at `../../../Simulator/wand-sim.js` and could not be read. The preview pane shows the real wand art and a gesture glyph instead of the live simulator.
- The CodeMirror editor is shown as a static `<pre>`; the serial log panel and firmware installer are omitted.
