# IconEditor

Authoring for the 16x16 icons the Broadcast icon display and ChatBroadcast use.

**The web app is `webapp/`** — the Icon Maker. Run `python3 serve.py` here and open
`http://localhost:8757/IconEditor/webapp/` (dev mode: Save writes the repo icon library).
ChatBroadcast embeds the same app for teachers (`?embed=1`: Save goes into the open game).
See `webapp/README.md`, "Modes".

| Path | What |
|---|---|
| `webapp/` | The Icon Maker web app (the only copy). Open accepts images and `rows`+`pal` JSON icons (pixel-for-pixel; samples in `Stations/IconDisplay/drafts/matrixicons/json16/`). |
| `serve.py` | Dev server for `webapp/`: serves `Bag3/Code/` on 127.0.0.1, no-cache, and `POST /api/icon` for the dev Save. |
| `tools/` | Python command-line tools; run them from this folder (`python3 tools/<name>.py`). |
| `tools/icon_editor.py`, `tools/image_to_icon.py` | Photo (PNG/JPEG in `assets/`) to icon, driven by `maps/<name>.json`. |
| `tools/hand_author_icons.py` | Icons built from shapes. A plain run is a dry run; `--write` writes, `--only NAME` limits it. 26 of its 27 recipes no longer match the committed icons, which were redrawn afterwards, so avoid a full `--write`. |
| `tools/draw_icon.py`, `tools/grid_to_icon.py` | Icons from a character grid. |
| `tools/iconlib/` | Shared conversion, colour and preview code. |
| `docs/` | `ICON_DESIGN.md` (icon design rules), `PIPELINE_NOTES.md` (conversion-tool notes from the deleted `Stations/Icon Display Station/`), `wand_icon.md`, the simple-UI plan, and `redesign/` mockups. |
| `icons/`, `maps/`, `previews/`, `assets/` | The tools' output and each icon's provenance. |
| `drafts/` | Grid maps waiting for review; `drafts/README.md` has the promote sequence. |
| `gallery.html` | Preview of every icon. |

`Stations/IconDisplay/icons/` is the source of truth for what devices and ChatBroadcast use.
`icons/` here is a working copy: `ChatBroadcast/tools/sync_icons.py --station` copies the device
set into it, and `--station --check` reports drift.
