# Draft icons

Conversions that were generated but not promoted into the library. They are here
rather than in `icons/` so they don't reach the device set by accident — nothing
in this folder is referenced by a game or listed in `gallery.html`.

`contact_sheet.png` shows all of them: source at 16x16 on top, current conversion
below.

Each has the same three files a promoted icon has, so they are a starting point to
hand-edit, not a rerun from scratch:

    drafts/icons/<name>.py       device ICON tuple
    drafts/maps/<name>.json      the per-segment colour decisions
    drafts/previews/<name>.png   simulated-LED render

Sources stay in `assets/<name>.png` — the editors read from there.

## Why each was set aside

| Icon | Source | Issue |
|---|---|---|
| `helicopter` | 40x40 | Reads acceptably; set aside on a judgement call that was too harsh. Rotor is a detached line. |
| `mouse` | 16x16 | Thin body; with the outline off the silhouette goes lacy. |
| `goat` | 16x16 | Thin legs and horns fragment. |
| `monkey` | 16x16 | Source includes an opaque frame that fills the whole panel. |
| `shark` | 16x16 | Almost entirely mid-grey; reads as an abstract mass. |
| `griffin` | 16x16 | Busiest source in the set — more detail than 16x16 holds. |
| `slide` | 40x40 | Ladder and rail are thin lines. |
| `sparkles` | 40x40 | Very sparse — only a handful of cells light. |
| `grass` | 40x40 | Blades merge into one green mass. |
| `bicycle` | 40x40 | Frame and wheel rims are 1px at source; they don't survive 2.5:1. |
| `sandwich` | 40x40 | Layers merge into a single blob. |
| `fire_truck` | 40x40 | Detail-dense; loses the truck shape. |
| `mail_carrier` | 40x40 | Converts cleanly, but is not distinguishable from `police` at 16x16. |

## Editing one

Either editor works. Both need the map in `maps/`, not `drafts/maps/`, because
their paths are fixed:

    cp drafts/maps/<name>.json maps/

**Python editor** (edits the committed map in place, live LED preview):

    python3 icon_editor.py assets/<name>.png     # http://localhost:8756

**Web editor** (16x16 grid painting, undo, downloads `.py`/`.json`/`.png`):

    python3 serve.py                             # http://localhost:8757/webapp/

Then regenerate the icon and preview from the edited map:

    python3 image_to_icon.py assets/<name>.png
    python3 image_to_icon.py --check assets/<name>.png   # lint

Hand-painting in the web editor writes per-cell overrides into the map's
`overlay`, so those survive a re-run of `image_to_icon.py` — edit the map, not
`icons/<name>.py`.

## Promoting a finished one

Four steps. The second is the one that actually puts it on hardware:

1. Leave `icons/<name>.py`, `maps/<name>.json` and `previews/<name>.png` in place —
   that is where the toolchain writes them and where the provenance lives.
2. Copy the icon into the live device set, which is what games load by name:

       cp icons/<name>.py ../../BroadcastCode/IconDisplay/icons/<name>.py

3. Add a row to the `ICONS` array in `gallery.html`: `["<name>", "<category>", true]`.
4. Delete the three draft files for it from `drafts/`.

Names must be lowercase letters, digits and underscore, not starting with a digit,
24 characters or fewer (`icon_store.safe_name`).
