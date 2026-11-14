# IconEditor

Host-side tools for authoring 16x16 icons for the Broadcast icon display. Moved here on
2026-11-14 from `Stations/Icon Display Station/`, which now holds only the old USB-serial
firmware and bring-up scripts.

| Path | What |
|---|---|
| `webapp/` | Browser icon maker. Run `python3 serve.py`, then open `http://localhost:8757/webapp/`. |
| `icon_editor.py`, `image_to_icon.py` | Photo (PNG/JPEG in `assets/`) to icon, driven by `maps/<name>.json`. |
| `hand_author_icons.py` | Icons built from shapes, no source photo. A plain run is a dry run that lists which icons would change; `--write` writes, `--only NAME` limits it. 26 of its 27 recipes no longer match the committed icons, which were redrawn afterwards, so avoid a full `--write`. |
| `draw_icon.py`, `grid_to_icon.py` | Icons from a character grid. |
| `iconlib/` | Shared conversion, colour and preview code. |
| `icons/`, `maps/`, `previews/` | The tools' output and each icon's provenance. |
| `drafts/` | Grid maps waiting for review; `drafts/README.md` has the promote sequence. |
| `gallery.html` | Preview of every icon. |
| `ICON_DESIGN.md` | Icon design rules. |

`Stations/IconDisplay/icons/` is the source of truth for what devices and ChatBroadcast use.
`icons/` here is a working copy: `ChatBroadcast/tools/sync_icons.py --station` copies the device
set into it, and `--station --check` reports drift. `ChatBroadcast/iconmaker/` is a separate copy
of `webapp/`.
