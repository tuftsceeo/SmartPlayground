# Icon Maker (web app)

Pure-JS, no-build-step port of `tools/icon_editor.py` / `tools/image_to_icon.py`: browser icon
authoring (any PNG/JPEG/etc, no Python required) plus live Web Serial preview on the icon display.
This is the only copy. ChatBroadcast embeds it in place (`../IconEditor/webapp/?embed=1`), the
same way it loads `../Simulator/`; the old `ChatBroadcast/iconmaker/` copy was removed 2026-11-15.

## Modes

| | Embedded (teachers) | Standalone (dev team) |
|---|---|---|
| Opened as | ChatBroadcast's Icons view, `?embed=1` | `python3 serve.py` → `http://localhost:8757/IconEditor/webapp/` |
| UI | Simple mode only, no device bar, game-library row | Simple or advanced, device bar, "Icon library (dev)" badge |
| Save | Adds or replaces the icon **in the open game** (ChatBroadcast passes its per-game store in through `iconMaker.library.setBackend`); nothing else | Writes **`Stations/IconDisplay/icons/<name>.py`** via `serve.py`'s `POST /api/icon`, which runs `sync_icons.py` so `defaultIcons.js` (ChatBroadcast's starter icons and samples overlay) and `IconEditor/icons/` follow; then the device too, when one is running. Replacing an existing icon asks first. Without `serve.py`, downloads the `.py` instead |
| Open list | The game's icons, then the starter set | The repo set (`defaultIcons.js`) |

The capability API for the host is `js/api.js` (`window.iconMaker`); the library seam is
`js/libraryBridge.js`. The browser firmware install is retired: the Broadcast icon display
(`Stations/IconDisplay/`) answers the editor over USB while idle; flash it from its own tree.

## Status

Editor works end-to-end: import (PNG/JPEG/WebP/SVG) with a crop/scale tool, per-segment
role/colour/priority editing, 16x16 grid painting with undo, lint, and download of
`.py` / `.json` / `.png`.

Device side is **verified on real hardware** (XIAO ESP32-C6): firmware flashed, `hello`
handshake with `fast: true`, a full 1058-byte frame accepted in a single unpaced write with a
~15ms round trip, intensity clamping, and save/list/show/delete all confirmed over the wire.
The Serial Monitor (bottom bar) logs every byte in both directions plus line-framing decisions,
which is the tool to reach for when the link misbehaves.

**Known-unverified**: the raw-REPL install path in `replController.js` / `firmwareInstaller.js`
(the firmware was flashed with `mpremote` for the hardware test, not through the browser), and
the current-draw estimate in `frameThrottle.js`, which is a nominal figure from datasheet
values rather than a measurement -- see its docstring.

**Panel orientation**: `icon_matrix.py` defaults to `MIRROR_X = True` because this panel needs
it. Set it `False` for a panel wired the other way, or send `{"cmd":"orient","mirror_x":false}`
at runtime. Note the row-rainbow bring-up test in `icon_test.py` *cannot* detect a horizontal
mirror -- a mirrored solid row is still a solid row; use an asymmetric shape.

## The pipeline

`js/pipeline/` converts a source image into the 16x16 `ICON` tuple:

- **exact-fill path** -- when an image is genuinely flat (a handful of solid colours covering
  >=90% of it), each colour becomes a segment directly.
- **quantize path** (`quantize.js`) -- everything else. Median cut over a 5:5:5 histogram,
  splitting by colour spread rather than pure population, then merging representatives that are
  within an OKLab JND. Splitting by population alone spends the whole budget subdividing the
  dominant region (whose spread is just resampling noise) and starves small distinct features.

`pngExact.js` decodes 8-bit non-interlaced RGBA PNGs directly (chunk parse, `DecompressionStream`
inflate, PNG scanline defilter) rather than through a canvas. Reason: both
`createImageBitmap(blob, {premultiplyAlpha:'none'})` and `new ImageDecoder({premultiplyAlpha:'none'})`
**still round-trip semi-transparent pixels through premultiplied alpha internally**, regardless of
the API-level hint (confirmed empirically -- a flat fill with alpha-only AA edges comes back with
RGB drifting as alpha rises, exactly the premultiply/unpremultiply rounding signature). That drift
invents spurious near-duplicate colours at every AA edge, which needlessly pushes flat artwork off
the exact-fill path. Anything outside that PNG shape falls back to the canvas decode in `decode.js`.

## Colour spaces -- the one thing to get right

Authored/stored values (`PALETTE`, `maps/*.json` `color`, `icons/*.py`, `doc.pixels`) are
**linear PWM duty**. Anything on screen or from an `<input type="color">` is **sRGB**. Convert at
the boundary with `ledcolor.js`'s `authoredToDisplay()` / `displayToAuthored()`, never in the
middle. Painting duty straight into a CSS colour renders it far too dark -- `PALETTE.RED` is
`[130,0,0]`, which shown raw is `#820000` (dark maroon) while the LED it describes is a vivid red.

Truncation (`Math.trunc(c * intensity)`), not rounding, is the canonical device brightness model
-- MicroPython's `round()` rounds half away from zero while CPython's rounds half to even, so a
round-based model would diverge between toolchain and device.

## Running it

Web Serial needs a secure context; `localhost` qualifies. Use `python3 serve.py` from
`IconEditor/` (no-cache headers, serves `Bag3/Code/` so the `ChatBroadcast/js/ledicons/` imports
resolve, and provides the dev Save endpoint). Chrome/Edge only (same constraint as Web Serial).
