# Icon Station UI — handoff status

Status of the 8 gaps identified comparing the prototype to `webapp/`, for the implementing agent.

## 1. Color picker vs. LED gamut — needs prototype adjustment (in progress by design agent)
Picker will be redesigned to reflect `ledGamut.js`'s real palette (hue × lightness grid, size shrinks with brightness) instead of generic named-crayon tabs. Do not implement the current crayon-tab picker as-is; wait for updated mockup.

## 2. Document swatch strip — same function, just needs surface in mockup
This is the existing `documentSwatches.js` component (dedupe-by-JND, click to set brush). No new logic — implementing agent should mount the current component in both simple and advanced layouts; only the visual treatment needs to match the new UI, not the behavior.

## 3. Wand 5×5 profile — simple companion grid, ship as-is
Add a plain 5×5 variant of the existing grid alongside the 16×16 one (profile select already wired in `simpleTopBar.js`/advanced header). No special compression/layout treatment needed — same cell style, fewer cells. Implementing agent can build this directly from `profiles.js` grid dimensions.

## 4. Device/connection flow — in progress
Advanced-mode device panel (connect → connected/waiting → running/push/disconnect → power-refusal banner → save/list/delete on-device icons) is being mocked now against `simpleDeviceBar.js` states. Simple-mode top bar device icon/states still need the same pass. Hold implementation on device UI until this lands.

## 5. Toolbar icons (New/Open/Save/Rename, sample picker) — flag for implementing agent
These have no equivalent in `plan_simple_ui.plan.md` or current code. Implementing agent should resolve against actual product scope: confirm with product whether New/Open/Save/Rename are real features to build, or drop them and add the "Open sample…" fixture picker (apple/cherries/grapes) that the plan and no-upload demo path actually need. Do not build blind from the mockup icons.

## 6. Segment list assumes fixed 4 segments — implementation note, not a design gap
Design intent (swatch + eye per segment) is correct and doesn't need remocking. Implementing agent: build for variable segment count (1–12, 1–5 on wand) with auto-hide-when-zero-coverage, except segments the user explicitly hid stay hidden. Don't hardcode 4 rows.

## 7. Advanced mode — in progress
Full advanced layout (priority/merge, coverage %, lint/problems, serial monitor, firmware install, 12V toggle, current-draw) is being mocked now in `Icon Station Prototype advanced.dc.html`. Not ready for implementation yet — current file is partial.

## 8. Minor inconsistencies — hold for review with user
- Detail slider showing segment count ("5 segments") vs. plan's no-number rule
- Segmented reference image gated behind "adjust" toggle vs. plan's always-visible/read-only placement
Do not resolve either way until confirmed.
