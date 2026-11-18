# Variant Studio

An internal tool for trying out interface variants of Playground Coder (Chat Broadcast). Describe a look in plain words. Claude turns it into a **variant**, which can hide parts of the screen, change colors and fonts, restyle parts, and rename labels. You see the change right away on the real app in the preview.

A variant never changes what the app does. Studio and runner load the unmodified `../ChatBroadcast/index.html` in a same-origin frame and inject only a stylesheet, a font link and label text. Devices connect and work as normal through the frame; this was checked with a dial on 2026-11-18.

## Run it

```bash
cd Bag3/Code && python3 -m http.server 8790
```

Then open:
- **The studio:** http://localhost:8790/VariantStudio/
- **A variant on its own:** `play.html#v=…`. This is the **Copy link** and **Open full screen** link. It also takes a file next to it: `play.html?src=examples/big-buttons.json`.

Enter the magic code, which is the same one Chat Broadcast uses. The studio also types it into the preview for you.

## What a variant can do

| | |
|---|---|
| Hide | Parts marked hideable in `js/regions.js`. Locked parts (connect, send, home, ⋮ menu, chat, dialog buttons…) can't be hidden, and one start screen card must stay. |
| Labels | Text on parts marked `label`, and placeholders (`attr`). The app sometimes rewrites labels, for example "Send to Box →" when the device changes; the variant's wording is put back right away. |
| Colors | The `:root` tokens in `ChatBroadcast/css/app.css`. About half of that file's colors are hard-coded, so tokens recolor most of the app but not all of it. Per-part `styles` cover the rest. |
| Fonts | Body and headings, from the allowed list. |
| Styles | Per part: colors, backgrounds, borders, roundness, shadows, font properties, padding and gap. Not display, size or position. |
| Mode | Opens in simple or advanced mode. |

It can't style the simulator (`<sim-room>`) or the Icon Maker, because they sit inside their own shadow DOM or frame.

## Good to know

- The studio and the real app share browser storage on the same site: saved games, panel widths and the simple/advanced setting. A variant's mode carries over to the real app on that computer.
- Variants are saved in this browser. To move one elsewhere, use **Export** and **Import**, or a link.
- When Chat Broadcast's markup changes, run the test. It fails if a catalog part no longer exists.

## Files

- `index.html`, `studio.css`, `js/studio.js`: the studio
- `play.html`: the runner
- `js/regions.js`: the parts, tokens, fonts and properties a variant may use
- `js/variant.js`: validation, compiling to CSS, and link encoding (no DOM)
- `js/apply.js`: injects a compiled variant into the app frame
- `js/claude.js`: "describe it", using structured output with a schema built from the catalog
- `serial-check.html`: the Step 0 device-through-frame check

## Test

```bash
node tools/variant_test.mjs
```

## Publishing for the team

Copy this folder to `Live_Page/VariantStudio/`; see `Live_Page/AGENTS.md`. The paths resolve the same way there. GitHub Pages publishes when `September_2026` is pushed.
