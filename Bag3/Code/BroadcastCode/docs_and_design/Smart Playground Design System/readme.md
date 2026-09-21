# Smart Playground — Design System

Design guide and component library for **Smart Playground**, the maker toolkit behind *Wand & Station Coder*: a browser app where preschool and early-elementary **teachers** describe a playground game in plain words, an assistant writes MicroPython for a handheld **wand**, and the code is pushed over USB to a **Broadcast Box** that hands it out to wands via NFC tags.

The audience is two-sided and the visual language answers both: playful and pastel enough for young children looking over a teacher's shoulder, calm and legible enough for an adult doing hardware setup.

## Sources this system was built from

| Source | What was taken |
|---|---|
| `ChatBroadcast/` (mounted local codebase) | Everything. Tokens from `css/app.css` `:root`; screens from `index.html`; copy from `js/app.js`; example content from `js/examples.js`; the icon set verbatim from `js/icons.js`. |
| `ChatBroadcast/assets/new_improved_wand/` | `WAND_FRONT.svg`, the 21-file `WandGestures/` SVG set, and the wand surface gradient textures — copied into `assets/`. |
| `ChatBroadcast/assets/wand/WAND_filledbackgroundexample_pressed.png` | Wand-with-button-pressed photo/render. |

**Not accessible.** The wand **simulator** module is imported from `../../../Simulator/wand-sim.js`, outside the mounted folder — it could not be read, so no simulator component exists here and the UI kit substitutes the real wand art. `ChatBroadcast/css/{buttons,chat,layout,modals,editor}.css` and `bak/` are dead legacy files (only `app.css` and `editor.css` are linked) and were ignored. There is **no logo file** anywhere in the source; see Brand mark below.

---

## Content fundamentals

**Who is speaking.** The app talks to the *teacher*, in second person, about a *child's* game. It never speaks as "I" and never role-plays the wand.

**Casing.** Sentence case everywhere — headings, buttons, toasts. Deliberately lowercase in two places: taglines and helper text set in Patrick Hand ("make magic for your playground", "chat your idea into code", "remix a ready-made game"), and input placeholders ("type a request…", "search games…"). Only hardware proper nouns are capitalised mid-sentence: **the Box**, **Broadcast Box**, **Wands**, **Stations**.

**The em dash is the house punctuation mark.** Almost every status message states the fact, then the fix, joined by an em dash:
- "Broadcast Box disconnected — check the cable."
- "Nothing to save yet — generate or load some code first."
- "Lost the Box — check the cable."
- "No saved games yet — open a workspace and tap Save."
- "Sent from another computer — only the pickup and play cards are known."

**Errors blame the situation, never the user.** "That device isn't a Broadcast Box — check what's plugged in." "The Box isn't answering. If it stays quiet, try Restart the Box." No "invalid", no "failed", no error codes in the UI.

**Plain physical verbs.** Plug, hold, tap, shake, unplug, wake, nudge. Progress copy is literally physical: "Nudging the Box…", "Waking up the Box…", "Hold a card on the Box to write it."

**Length.** One sentence. Card blurbs run 3–6 words ("Shake for color.", "Recipe steps with ingredient tags."). Overlay subtitles run one line ("Plug it in, then pick it from the browser's list").

**Buttons are verb phrases and may carry an arrow.** "Remix this in chat", "Use as-is → send", "Send to Box →", "Connect via USB". The cancel is warm, not clinical: **"Not yet"**, not "Cancel", when the action is only postponed.

**No emoji, ever.** The one non-alphabetic glyph in the product is **✦** in the brand gem. Arrows (→, ←) and `</>` are used as literal text. Everything else is an SVG icon.

**Vibe check.** Warm, competent, unhurried. A calm classroom aide who knows the hardware. Not chirpy, not cute in words — the cuteness is entirely visual.

---

## Visual foundations

**Palette.** Four saturated hues carry meaning — pink `#ef4d92` (the primary action, the brand), purple `#6c4cd1` (writing / advanced / code), teal `#22c3a6` (connect, success, progress), yellow `#ffd23f` (warmth in the background only). Each has a dark partner used as the second gradient stop. Beneath them sits a family of **very pale violet-leaning pastels** — `#fff0f6`, `#f2eefc`, `#e9fbf6`, `#fff8e0`, `#f4f2fa` — which do all the state work: selected rows, mode chips, empty states. **There is no true grey in the system.** Every neutral is violet-tinted (`#231f2e` ink, `#8b859a` muted, `#e8e6f0` border, `#f7f7fb` page).

**Gradients.** Always `135deg`, always exactly two stops, always a hue and its own dark partner — never a rainbow, never a hue jump except the brand gem (pink → purple). Filled buttons, the brand gem, the sent banner. The page ground is four **soft pastel radials** at 10–20% alpha pinned to the four corners over `#f7f7fb` — it reads as a wash, not a gradient.

**Type.** Two families. **Nunito** does 100% of the UI, and it is used *heavy*: 700 for labels, 800 for buttons and headings, 900 for the display. Weight, not size, creates hierarchy — headings live in a narrow 13–18px band. **Patrick Hand** is the handwritten accent, reserved for taglines and playful captions at ~20px; never for UI controls or body copy. `ui-monospace` marks machine truth: SSIDs, firmware versions, code, and empty-state captions.

**Backgrounds.** No photography, no illustration, no hand-drawn texture. Three grounds only: the pastel radial wash (page), flat white (cards and shells), and a **45° candy stripe** `repeating-linear-gradient(#fbfaff / #f4f2fa, 14px)` behind empty preview panels. The only imagery in the entire product is the **wand's own technical art** — flat vector, front-on, upright.

**Layout.** A centred `1100px` shell (`1280px` in advanced mode) with `24px` outer padding, holding one white rounded panel that owns the whole viewport height. Nothing scrolls at page level; panels scroll internally. Header `14px 20px`, cards `14px`, overlays `24px`, grid gaps `14px`. Two panes (chat 340px + preview) with a draggable 10px resizer; the code drawer is 480px fixed-right.

**Corner radii.** Nothing is square. 8–10px for small controls and thumbnails, 12–14px for buttons, chips and inputs, 16px for cards, 20px for overlays and pill tabs, **24px for the view shell**, 50% for round buttons and dots. Chat bubbles use an asymmetric tail: `14px 14px 3px 14px` (user, tail bottom-right) and `14px 14px 14px 3px` (bot, tail bottom-left).

**Borders.** `1px` for structural dividers; **`1.5px` for anything interactive** (buttons, inputs, cards, chips). `2px` only on splash cards. Border colour is `#e8e6f0`, quiet dividers `#f4f2fa`.

**Cards.** White, `1.5px` border, `16px` radius, **no shadow**. Elevation inside the shell comes from the border alone. Hover turns the border pink.

**Shadows are coloured, never neutral.** The shell glows purple (`0 18px 40px rgba(108,76,209,.18)`), the code drawer purple to the left, pink actions glow pink (`0 10px 22px rgba(239,77,146,.35)`), and overlays use the one near-black shadow (`0 24px 60px rgba(0,0,0,.22)`). Never stack a shadow on a bordered card.

**Hover.** Tint, don't darken: outline buttons take a pink or purple **border and text** colour with a pale pink fill; gradient buttons lighten by their own second stop; icon buttons swap ink for purple. **No press/active state is defined in the source** — no shrink, no darken, no transform. Don't invent one.

**Focus.** Border goes pink plus a 3px pink ring `0 0 0 3px rgba(233,78,155,.14)`; the background lifts from `#fafafd` to white. Resizers show `:focus-visible` by turning their hairline pink.

**Disabled.** Filled buttons go flat `#d8d4e6` with white text and **no shadow** — never a faded pink. Outline and pill controls drop to `opacity: .7–.85` and `cursor: not-allowed`.

**Motion.** Minimal and honest. `0.15s`/`0.2s`, plain `ease`, no spring or bounce. Only three animations exist: a spinner (`spin 1s linear infinite`), a 0.15s `pop` scale-in on the connect toast, and three blinking pink thinking dots. Layout transitions animate `max-width`/`height` only. No parallax, no scroll animation, no page transitions.

**Transparency & blur.** Almost none. The scrim is a flat `rgba(35,31,46,.35)` — the legacy stylesheet had `backdrop-filter: blur(4px)` but the shipping app dropped it, so **don't blur**. Alpha is otherwise used only inside gradient stops and shadow colours.

**Fixed elements.** Toast (bottom-centre), connect toast (top-right), sent banner (top-centre), code drawer (right edge), serial log (bottom, advanced only). Everything else lives inside the shell.

**Imagery vibe.** Cool, flat, saturated vector — no grain, no photography, no drop shadows on art. The wand art is shown at rest and upright; gesture glyphs are line drawings with motion arcs.

---

## Iconography

- **One system, already in the codebase.** `ChatBroadcast/js/icons.js` is an inline-SVG map — mock-specific paths for the hardware glyphs (box, nfcCard, modeServe, shakePhone, plug, floppy, wifi) plus **Lucide** (ISC) paths for the generic ones. It is copied into `components/icons/Icon.jsx`; the untouched original is preserved at `assets/icons/icons.original.js.txt`. **No CDN icon font, no npm package, no PNG icons.**
- **The sparkles family carries the magic.** `wand` is Lucide **wand-sparkles** (it replaced the app's simpler two-path wand); `pencil-sparkles` means creating or authoring; `sparkles` means new or exciting; `mop-sparkles` means clearing or resetting. Reach for these before any plain equivalent — they are the one place the product lets itself be whimsical in iconography.
- **Style:** 24×24 viewBox, `fill: none`, `stroke: currentColor`, **`stroke-width: 1.8`**, round caps and joins. A handful of dots are filled rather than stroked.
- **Sizes in use:** 12 (inline status), 13–16 (buttons, chips, rows), 18 (nav/rail), 22 (overlay icon rows), 40–46 for hero and empty states — the large ones drop to `stroke-width: 1.3`.
- **Colour** is always `currentColor`, inherited from the parent's state (pink for accents, `#5b5468` default ink, `#c2b8d6` for quiet/inactive).
- **Unicode as icon:** three characters are used as literal text — **✦** (brand gem), **→ / ←** (buttons and back link), **`</>`** (show-code button, in monospace). **Emoji are never used.**
- **Product art** is separate from icons: `assets/wand/` (wand front view, pressed example, surface textures) and `assets/gestures/` (21 shake / twist / wiggle / tag-tap / sound / vibrate glyphs). Use these instead of drawing motion diagrams.

## Brand mark

**No logo file exists in the source.** The identity is a CSS construct: a rounded square (`9px` at 30px, `28px` at 96px) filled with the pink→purple gradient, holding the character **✦** in white, followed by the product name in Nunito 800. That is reproduced faithfully in `BrandMark`. Where a mark is impossible, set the words *Smart Playground* or *Wand & Station Coder* in plain Nunito 800 — **do not draw a substitute logo.** If a real mark exists, please supply it.

## Fonts

Both faces load from Google Fonts via `@import` in `tokens/fonts.css`, exactly as the app does — **Nunito** (400/600/700/800/900) and **Patrick Hand**. These are the app's genuine choices, not substitutes, so no font files are vendored. If you want offline/self-hosted copies, send the woff2 files and I'll add `@font-face` rules.

## Intentional additions

- **`Icon`** — a React wrapper around the codebase's existing path map. Not a new icon set; a mount for the one that exists.
- **Pastel tint scale** (`--pink-50…300`, `--purple-50…300`, `--teal-50/100`, `--yellow-50/100`) — names given to hex values already scattered through `app.css`, so components can reference them semantically.
- **`--led-*` tokens** — the six wand LED colours the firmware cycles through, needed to render any wand preview.

---

## Index

**Root**
- `styles.css` — the single stylesheet consumers link; `@import` lines only.
- `readme.md` (this file), `SKILL.md`, `thumbnail.html`.

**`tokens/`** — `fonts.css`, `colors.css`, `gradients.css`, `typography.css`, `spacing.css`, `radius.css`, `elevation.css`, `motion.css`, `semantic.css`.

**`components/`**
- `core/` — **Button**, **IconButton** (+ SendButton), **Chip** (+ StarterChip), **ModePill** (+ ConnChip, SsidChip, TagBadge), **BrandMark**
- `icons/` — **Icon** (+ ICON_NAMES, ICON_PATHS, categoryIcon)
- `forms/` — **TextField** (+ SearchInput, ChatInput)
- `surfaces/` — **ViewPanel** (+ SplashCard, ExampleCard, CardActionButton, OverlayCard, OverlayScrim)
- `chat/` — **ChatMessage** (+ ThinkingDots, CodeBlock)
- `feedback/` — **Toast** (+ ConnectToast, SentBanner, ProgressBar, TagBars, TagRow, RequirementRow)
- `navigation/` — **AppHeader** (+ TabBar), **RoleRail** (+ PaneResizer)

Each directory carries a `*.card.html` specimen; each component has a `.d.ts` props contract and a `.prompt.md` usage note.

**`ui_kits/wand-station-coder/`** — click-through recreation of the app. See its own `README.md`.

**`guidelines/`** — 18 foundation specimen cards (Colors, Type, Spacing, Brand).

**`assets/`** — `wand/` (front view SVG, pressed render, surface textures), `gestures/` (21 SVGs), `icons/` (the original icon source, preserved).
