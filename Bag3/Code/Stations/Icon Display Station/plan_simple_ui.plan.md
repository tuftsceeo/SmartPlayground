# Simple mode for the Icon Maker

## Context

The editor grew feature-first and now shows everything at once: segment RGB
triplets, coverage percentages, cells-won counts, a lint list headed
"Problems", a byte-level serial monitor, firmware install/restart controls and
power-injection checkboxes. That is the right surface for developing icons and
debugging hardware. It is the wrong surface for a kindergarten teacher who wants
to draw a picture and put it on the LED panel.

Split into two modes:
- **Advanced** — today's UI, essentially unchanged. The dev surface.
- **Simple** — MS-Paint-shaped: pencil, eraser, palette, three read-only
  reference images, light segmentation controls, a file list, import, and three
  prominent actions (Download / Connect / Show on device).

One change lands in **both** modes: a **document swatch strip** showing the
colours actually used in the current icon. Today those only appear as small
per-row swatches inside the segment list, and the generated panel palette often
doesn't contain them — so there is no way to re-pick a colour already in your
drawing.

## Decisions (settled)

| | |
|---|---|
| Default mode | **Simple**, remembered in `localStorage`; gear icon top-right switches |
| Simple segment controls | Colour swatch + show/hide eye + a "detail" slider |
| Zero-cell segments | **Auto-hidden** in simple mode — *except* ones explicitly turned off, which stay visible so they can be restored |
| Problems panel | **Hidden entirely** in simple mode |
| Eraser | Two tools: **eraser** paints off, **revert** restores the cell to the imported image |
| Icons | Lucide, already loaded but currently unused (zero `data-lucide` in the tree) — free to adopt |

---

## Inventory and triage

Legend: **keep** · **cut** · **simplify**

### Top bar
| Control | Simple | Note |
|---|---|---|
| Icon name | keep | editable; it's how you save |
| Mode badge `exact · 5 segments` | **cut** | jargon, no action attached |
| Segments slider | **simplify** | "Detail: fewer ←→ more", no number |
| Segment count readout | **cut** | |
| Profile select (16×16 / Wand 5×5) | keep | auto-detects on connect; still needed offline |
| Fixture select | **simplify** | folded into the open/import area |
| Download map / icon / preview | **simplify** | one **Download**; map + preview are dev artifacts |
| Status text | **cut** | toasts already cover it |

### Left column — import + reference images
| Control | Simple | Note |
|---|---|---|
| File input / drop zone | keep | as a labelled **Import image** |
| `512×512px · whole image` | **cut** | |
| Crop & scale | keep | useful to everyone |
| source + segmented canvases | keep, read-only | two of the three reference images |

### Middle column — segment list
| Control | Simple | Note |
|---|---|---|
| Source colour swatch | keep | |
| `seg 0 · src rgb(209,56,52) · 89.0%` | **cut** | most jargon-dense line in the app |
| `cells won: 135` | **cut** | but still *drives* the auto-hide rule |
| Role select (color/off/merge) | **simplify** | becomes the eye toggle |
| Colour button → palette | keep | the main thing a teacher touches |
| Merge target | **cut** | |
| Off button | **simplify** | becomes the eye toggle |
| Priority slider + value | **cut** | |

### Right column
| Control | Simple | Note |
|---|---|---|
| Preview canvas (bloom) | keep, read-only | third reference image |
| Brightness slider / `30%` | keep / **cut** the % | |
| **Grid canvas** | keep — **promoted, larger** | the artist canvas |
| Brush swatch | keep | part of the tool row |
| Helper sentence | **cut** | replaced by visible tools |
| Undo | keep | |
| Problems panel | **cut** | |
| Connect / disconnect | keep — promoted | |
| Live push | keep | as "Show on device" |
| 12V / power injection | **cut** | |
| `est. draw: 412mA` | **cut** | |
| Power refusal banner | **simplify** | keep the "too bright" fix button, drop mA |
| On-device icon list | keep | the file list |
| Save to device | keep — promoted | |
| Install / Restart firmware | **cut** | dev-only recovery |

### Bottom bar / modals
| Control | Simple | Note |
|---|---|---|
| Serial monitor (all of it) | **cut** | outside the render pass — needs its own hide call |
| Palette picker | **simplify** | drop count line + explanation paragraph |
| Crop modal | **simplify** | drop stats/smoothing/lock; keep presets + live preview |
| Toasts | keep | |

### New in both modes
- **Document swatch strip** — colours used in this icon, clickable
- **Tool row** — pencil / eraser / revert / undo (makes today's hidden
  right-click behaviour visible)

---

## Implementation

### 1. Canvases must be created outside any `innerHTML`

**This is the crux.** All four canvases are currently created inside
`buildShell()`'s template string (`main.js:370,374,383,388`). If a mode switch
re-ran that, you'd get *new* canvas elements: blank bitmaps, and the
`mousedown`/`mousemove`/`contextmenu` handlers from `wireGridCanvas()` still
bound to a detached orphan. Painting would silently stop.

Split `buildShell()` in `main.js` into three:

```
createCanvases()   // ONCE in the constructor: document.createElement x4,
                   // cache on this.*, then wireGridCanvas()
buildShell()       // writes the layout for state.uiMode into this.root
adoptCanvases()    // slot.appendChild(this.xCanvas) -- AFTER the innerHTML
```

`appendChild` on an already-parented node **moves** it; bitmap contents, backing
store and event listeners all survive. Adoption must happen after the layout's
`innerHTML`, never before.

Two layout templates with empty `<div data-canvas="grid">` slots:
`js/layouts/advancedLayout.js` (today's `grid-cols-[320px_360px_1fr]` verbatim,
canvases replaced by slots) and `js/layouts/simpleLayout.js`. Both must declare
**all seven mount ids** so `renderReactive()` never needs a null check.

`changeProfile()`'s resize path (`main.js:197-200`) gets more robust, not less —
it works off cached references that now never change.

### 2. Grid canvas sizing

`GRID_CANVAS_SIZE` (main.js:47) currently does three jobs: backing store, CSS
size, and the `cell = GRID_CANVAS_SIZE / W` divisor in `paintGrid()`. Decouple:

- **`paintGrid()` reads `this.gridCanvas.width`**, not the const. One line, and
  it makes the method correct at any size and any `W` including the 5×5 wand.
- Backing store `GRID_BACKING = 640`, snapped to divide by `W` (640 → 40px/cell
  at 16, 128px/cell at 5) so grid lines land on whole pixels. Add the grid canvas
  to the `changeProfile()` resize loop.
- CSS size comes from the slot wrapper, not inline style: `#gridCanvas { width:
  100%; aspect-ratio: 1/1 }` in `css/app.css`, capped per layout.

`cellAt()` needs no change — it already normalises through
`getBoundingClientRect()`.

### 3. Tools

`activeTool: 'pencil' | 'eraser' | 'revert'` goes in `store.js` (the tool row is
reactive and must re-render to show selection). `wireGridCanvas()` gains one
helper and keeps its stroke-coalescing contract exactly — one
`pushUndoSnapshot()` on mousedown, none on mousemove, one `setState` on mouseup:

```js
applyTool(idx) {
  const t = state.activeTool;
  if (t === 'revert') doc.overlay.delete(idx);
  else if (t === 'eraser') doc.overlay.set(idx, OFF_DUTY.slice());
  else doc.overlay.set(idx, state.brushColor.slice());
  this.recomputePixelsFromOverlay();
}
```

Side benefit: eraser and revert become **draggable strokes**, which they aren't
today (right-click clears exactly one cell). Keep `contextmenu` as a revert
shortcut in both modes. Use `OFF_DUTY` from `ledGamut.js`, not a literal — the
existing `isOff()`/`swatchStyle()` already render it as the slashed swatch.

### 4. Component strategy — hybrid

Branch in place where only a few fields differ (`state` is already the first
argument to every factory, so no signature churn): `sourcePane.js`,
`previewPane.js` (unchanged), `problemsPanel.js` (one-line early return).

New files where the simple form shares no markup: `components/simple/`
`simpleTopBar.js`, `simpleSegmentList.js`, `toolRow.js`, `simpleDeviceBar.js`.

Shared: `components/documentSwatches.js`.

Explicitly **not** a visibility-descriptor config object — with ~15 hidden things
across 6 components that's a schema nobody can hold in their head.

### 5. Mode switching

Hydrate from `localStorage` in the constructor *before* first `buildShell()` so
there's no flash. The switch is synchronous and shell-first — **not** via
`setState`, whose rAF subscriber only runs `renderReactive()` and would
repopulate mounts the old layout still owns:

```js
setUiMode(next) {
  localStorage.setItem('iconmaker.uiMode', next);
  state.uiMode = next;
  this.palette.close();          // anchored to a node about to be destroyed
  this.buildShell();             // replaces layout, re-adopts canvases
  this.renderReactive();         // repopulate mounts + lucide
  this.applyMonitorVisibility(); // and clear its body padding
  this.paintAll();
}
```

Disable the gear while the crop modal is open rather than closing it — its
pending `onApply` closure captures `doc.source`, and losing an in-progress crop
is worse than briefly blocking the switch.

`applyMonitorVisibility()` must toggle `monitor.root`'s `hidden` class **and**
clear `document.body.style.paddingBottom` — `serialMonitor.js:190` sets that
padding from its own height, so hiding the root alone leaves a dead gap.

### 6. Document swatch strip

`components/documentSwatches.js` exporting `createDocumentSwatches(state, {
onPick })` plus a local `collectDocumentColors(decisions, overlay, intensity)`.
Keep the helper here, not in `ledGamut.js` — that module should stay free of
`doc` awareness.

Order: `state.decisions[].color` where `role === 'color'` (segment order is
roughly largest-area-first, since `histogramFills` sorts by fraction), then
`doc.overlay.values()` in insertion order. Dedupe with `ledDeltaE(a,b,intensity)
< JND` — **not** hex equality, since two duties that differ numerically but
render identically on the panel must collapse to one swatch. Filter `isOff()`
out, then append one explicit "off" swatch if the overlay contains any.

Clicking sets `brushColor`, so it composes with the pencil for free. Mounted in
`gridControlsMount` in advanced (no layout change needed) and the centre column
in simple.

---

## Traps

1. **Segment indices must survive the auto-hide filter.** Every callback in
   `segmentList.js` is keyed by loop index into `state.decisions`. The simple
   list must iterate all of `state.fills` and `continue` on hidden rows — not
   `filter().forEach()`, which renumbers and silently edits the wrong segment.
2. **`wireGridCanvas()` is called from `buildShell()` (main.js:411)** and
   registers a `window` mouseup listener. It must **move** into
   `createCanvases()`, not be copied, or every mode switch stacks a duplicate
   listener and duplicate `runTier5()` per stroke.
3. **The auto-hide predicate reads `state.cellsWon`**, only refreshed by
   `runTier5()`. `livePriorityInput()` deliberately skips that, so rows won't
   appear/disappear mid-drag — correct, but be deliberate: do not add
   `runTier5()` to the live path.
4. **`liveColorInput()` never calls `setState`**, so the swatch strip shows the
   pre-drag colour until release. Acceptable and consistent with `cellsWon`; do
   not "fix" it by adding a `setState` that would destroy the fast path.
5. **`previewCanvas` self-sizes** its backing in `renderPreview()` but its inline
   `style="width:320px;height:320px"` does not — move to a class or the 5×5
   profile stretches oddly.
6. **`state.selectedFillIndex` is declared and never read** (verified). Don't
   build selection on it assuming it works.

---

## Sequencing

1. `store.js`: add `uiMode` (hydrated from localStorage), `activeTool`.
2. **`main.js` canvas split** — `createCanvases()` / `buildShell()` /
   `adoptCanvases()`, move `wireGridCanvas()`. Verify advanced mode is unchanged
   before touching anything else. **Riskiest step; land it alone.**
3. `paintGrid()` reads the canvas; `GRID_BACKING`; resize path; `app.css`.
4. `applyTool()` + `toolRow.js`.
5. `simpleLayout.js` + `simple/*` + `setUiMode()` + gear buttons.
6. `documentSwatches.js`, mounted in both modes.
7. Hide-list cleanups in `topBar.js`, `sourcePane.js`, `problemsPanel.js`,
   `deviceBar.js`; Lucide icons throughout.

## Todos

- [ ] **store-state** — `webapp/js/state/store.js`: add `uiMode` (hydrate from `localStorage` before first shell) and `activeTool`.
- [ ] **canvas-split** — Split `buildShell()` in `webapp/js/main.js` into `createCanvases()` / `buildShell()` / `adoptCanvases()`; move `wireGridCanvas()` into `createCanvases()` (do not copy — trap 2). Land and verify advanced mode unchanged (load fixture, priority drag, paint, undo, 16×16 ↔ 5×5) before any simple UI.
- [ ] **grid-sizing** — `paintGrid()` reads `this.gridCanvas.width`; `GRID_BACKING = 640`; include grid canvas in `changeProfile()` resize; CSS size via slot (`#gridCanvas` 100% + aspect-ratio). Move `previewCanvas` inline size to a class (trap 5).
- [ ] **tools** — `applyTool()` + `components/toolRow.js`; keep stroke-coalescing; `OFF_DUTY` from `ledGamut.js`; `contextmenu` stays revert in both modes.
- [ ] **simple-shell** — `js/layouts/advancedLayout.js` + `simpleLayout.js` (all seven mount ids); `components/simple/*`; `setUiMode()` (not via `setState`); gear disabled while crop modal is open; `applyMonitorVisibility()` hides monitor **and** clears `body` padding.
- [ ] **document-swatches** — `components/documentSwatches.js`; JND dedupe; mount in both modes. Do not `setState` from `liveColorInput()` (trap 4).
- [ ] **simple-hide-list** — Hide/cut/simplify in `topBar.js`, `sourcePane.js`, `problemsPanel.js`, `deviceBar.js`; simple segment list iterates all fills and `continue`s (trap 1); Lucide icons; auto-hide uses `cellsWon` only after `runTier5()` (trap 3). Do not use `state.selectedFillIndex` (trap 6).
- [ ] **verify** — `python3 serve.py`; per-mode tool strokes + undo coalesce; mode-switch canvas re-parenting; serial padding gone; zero-cell vs explicitly-hidden segments; swatch click sets brush; `node --check` + import-graph sweep.

## Verification

```bash
cd "Bag3/Code/Stations/Icon Display Station" && python3 serve.py
```

After step 2, before anything else: advanced mode must look and behave exactly
as it does today — load a fixture, drag a priority slider, paint the grid,
undo, switch profile 16×16 ↔ 5×5.

Then, per mode: paint with each of the three tools and confirm strokes drag and
coalesce into one undo; switch modes repeatedly and confirm the canvases keep
their contents and painting still works (this is the re-parenting check, and it
only fails *after* a switch — exactly the bug nobody tests for); confirm the
serial monitor's body padding is gone in simple mode; confirm a zero-cell
segment disappears from the simple list while an explicitly-hidden one stays;
confirm the swatch strip lists the icon's own colours and clicking one sets the
brush.

Node-side checks that need no browser: `node --check` every touched file, and
the existing import-graph sweep (every named import resolves) — that catches the
missing-export class of error that has bitten twice this session.
