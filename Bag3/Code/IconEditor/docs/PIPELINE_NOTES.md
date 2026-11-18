# Icon pipeline notes

From the old `Stations/Icon Display Station/readme.md` (deleted 2026-11-15). Paths in these
notes predate the move to `IconEditor/`.

## Image → icon conversion

For designing icons by hand (style, colour table, child-recognisability review,
animation), see [ICON_DESIGN.md](ICON_DESIGN.md) and `grid_to_icon.py`.

Converting a PNG/JPEG to a recognizable 16×16 icon turned out to need more than a per-pixel nearest-color snap -- six earlier rounds of that approach each produced a *different* visible defect (an orange reading as a "round white peach", brown stems rendering as bright amber intruders, several distinct purples collapsing into one, a shadow appearing brighter than the body it's shading). All six traced back to one mechanical root cause, plus one hardware fact no color-space math fixes:

**WS2812 bytes are linear PWM duty, not sRGB code values.** Treating an authored `(r,g,b)` byte tuple the same way a PNG pixel is treated -- comparing colors, or judging "is this bright enough" -- silently applies or skips a gamma step depending on which side of the comparison you're on. `iconlib/ledcolor.py`'s `predict_led_appearance()` runs a byte tuple through the real chain (`byte -> ×INTENSITY -> int() truncate -> /255 = LINEAR LIGHT -> sRGB-encode`) and is what the preview renders through, instead of showing the raw authored bytes as if they were already the right thing to look at.

**Brown cannot exist on an additive emitter** -- it's a contrast effect (dark orange next to something brighter), not a color the LEDs can independently emit. The pipeline treats it as its own case (a dim, deliberately-capped amber) rather than letting the general hue-matcher blow it up to full brightness.

### The tool

```
Bag3/Code/Stations/Icon Display Station/
  webapp/                # the browser editor -- primary tool; see webapp/README.md
  serve.py               # dev server for webapp/ (no-store headers)

  main.py                # device: boots the JSON-over-serial icon server
  icon_matrix.py         # device: NeoPixel, serpentine + orientation, intensity LUT
  json_link.py           # device: non-blocking stdin line framing
  icon_store.py          # device: read/write icons/<name>.py
  icon_server.py         # device: command dispatch + main loop

  image_to_icon.py       # CLI: batch convert, --report, --check, --push, --swatch
  icon_editor.py         # the original local web editor, superseded by webapp/
  iconlib/               # ledcolor, segment, raster, emit, preview, palette, mapio

  maps/<name>.json       # COMMITTED -- the human's per-segment color decisions
  icons/<name>.py        # generated -- also what the device stores and reads back
  previews/<name>.png    # generated -- simulated-LED render for structural review
```

**Workflow:**

```
python3 tools/icon_editor.py assets/apple.png
```

opens `http://localhost:8756` (needs `pip install pillow`; the editor is stdlib `http.server` + plain HTML/JS, no other deps). The tool auto-segments the source into its exact flat-color fills (these are vector icons -- 3-6 exact fills typically cover >97% of opaque pixels, so an exact-color histogram *is* the segmentation, not an approximation of one) and proposes a starting color/priority/role for each segment: hue-matched against `lib/leds.py`'s palette by interpolating between the two nearest palette colors' *directions* on the hue wheel (never their raw magnitude -- amplifying by a magnitude ratio is exactly what blew out saturation in earlier attempts; and never a single nearest-name snap either -- that collapsed distinct hues like a real orange and a real lemon-yellow onto the same shared bucket whenever a third color sat almost exactly between them), with amplitude from the segment's own source lightness, brown routed to the dim-amber special case, and small fully-enclosed dark segments (shadows, seeds) proposed as `OFF`. Every proposal is just a starting point -- override any segment's color, turn it off, merge it into another, adjust its rasterization priority (the mechanism thin features like stems use to win their cells over a much larger neighboring fill), or hand-paint individual cells. `Save map` commits `maps/<name>.json`; `Export icon` writes `icons/<name>.py` + `previews/<name>.png`; `Push to device` shells out to `mpremote` (needs the device attached locally).

Everything the editor does is re-runnable headless afterward: `python3 tools/image_to_icon.py assets/*.png` reconverts every source against its committed map (decisions are keyed by exact source RGB, so they survive a source-art tweak instead of being discarded), `--report` prints each image's fill histogram and cells-won, `--check` lint-fails on things like a colored segment winning zero cells, too many distinct lit colors, or a channel value that will truncate to 0 on-device, and `--swatch` builds a 16-color test icon so a batch of hue questions can be settled with one flash instead of one per icon.

### Source assets and what has been converted

`assets/` holds 49 PNGs. Six of them -- `apple`, `cherries`, `grapes`, `lemon`,
`orange`, `watermelon` -- are the conversion-pipeline fixtures: they are the
only ones with a committed `maps/<name>.json`, and therefore the only ones
with an `icons/<name>.py` and a `previews/<name>.png` in this directory. The
other 43 are unconverted source art:

| Group | Files | Converted |
|---|---|---|
| Fruit fixtures (`apple.png` … `watermelon.png`) | 6 | 6 |
| `animalsprites [Converted]-01..19.png` | 19 | 0 |
| `animal faces 2-01..10.png` | 10 | 0 |
| `farm animals-01..09.png` | 9 | 0 |
| Named singles: `dino`, `dolphin`, `griffin`, `snake`, `trex` | 5 | 0 |

The sheet-derived names (`animalsprites [Converted]-07.png` and the like) are
export numbering, not icon names. An icon name is a separate decision made when
someone converts the image -- `icon_store.safe_name()` only accepts lowercase
letters, digits and underscore anyway. The `.ai` files alongside them are the
Illustrator sources the PNGs were exported from; the tools read only the PNGs.

Two files in `assets/` are not source art: `assets/duck.json` is a segment map
(its `"source"` is `null`) and `assets/sandcastle.py` is a generated icon file.
Neither is read by anything -- `image_to_icon.py` globs images, and maps and
icons are looked up in `maps/` and `icons/`.

`icons/` here is this station's own conversion output. The display's live icon
set is `Bag3/Code/TeacherTools/BroadcastBox/IconDisplay/icons/` (28 icons), most of which
were drawn in the web editor rather than converted from these PNGs; `snake` and
the six fruit exist in both trees from different provenance.

### Running the conversion tools

Both entry points need `pillow`, which is **not installed in this repository's
checkout environment** -- `import PIL` fails. Nothing under `iconlib/` that
touches pixels can run until `pip install pillow` is done locally.

```
python3 tools/image_to_icon.py assets/apple.png      # convert against maps/apple.json
python3 tools/image_to_icon.py --report assets/*.png # fill histogram + cells-won
python3 tools/image_to_icon.py --check assets/*.png  # lint the generated icons
python3 tools/image_to_icon.py --swatch              # 16-colour test icon
python3 tools/image_to_icon.py --push icons/apple.py # mpremote, device attached
```

```
python3 tools/icon_editor.py assets/trex.png   # segmentation UI on http://localhost:8756
python3 serve.py                         # dev server for webapp/, same port
```

Converting a PNG is a human decision, not a batch job: the auto-proposed
per-segment colours are starting points (see above), and the icon's name,
whether it earns a slot on the display at all, and whether the 16x16 result is
readable across a room are all curation. Running the converter over `assets/`
would produce 43 files that nobody has looked at.

The copied app at `Bag3/Code/TeacherTools/BroadcastBox/ChatBroadcast/iconmaker/` cannot see
any of this. Its `assets/` holds the editor's own UI SVGs only. Its fixture
picker (`FIXTURES` in `iconmaker/js/main.js`) names the same six fruit and
fetches `../assets/<name>.png`, i.e. `ChatBroadcast/assets/`, which holds only
`wand/` and `new_improved_wand/` -- so those six buttons fetch 404s there. The
station's own `webapp/` copy, served by `serve.py` from this directory, does
find them.

**Preview fidelity is honest, not complete:** the simulated render is reliable for cell-on/off, silhouette, thin-feature survival, and relative brightness ordering -- most of the failure modes that showed up on hardware, and the ones no one can eyeball from a table of RGB triples. It is *not* reliable for absolute hue -- WS2812 dies are narrowband and off-primary in a way no sRGB monitor simulation captures. Sign off on structure from the preview; sign off on hue only from the real matrix.

### Drawing an icon by hand: `draw_icon.py`

An icon can be drawn as a text grid instead of converted from a PNG. A spec is
a JSON file: a `name`, a `key` of single characters to LED duty `[r, g, b]`,
and 16 `rows` of 16 characters (`.` is off).

```
python3 tools/draw_icon.py --export dog > dog.json   # existing icon -> editable spec
python3 tools/draw_icon.py dog.json                  # preview PNG beside the spec
python3 tools/draw_icon.py dog.json --install        # write and sync every copy
```

`--install` writes `../IconDisplay/icons/<name>.py`, `maps/<name>.json` (the
whole design as a 256-cell overlay, mirrored to ChatBroadcast's
`iconmaker/maps/` when that copy has the map) and `previews/<name>.png`, then
runs `sync_icons.py` for `defaultIcons.js` and the station copy, and copies
`defaultIcons.js` into `Live_Page/ChatBroadcast/`. A new name also needs a row
in `gallery.html`. Previews use `iconlib/preview.py`: square cells coloured
with the web editor's LED model at full duty. Neutrals need the warm ratio
(white `[255, 171, 93]`); equal RGB shows as cyan.

`hand_author_icons.py` still holds older recipes for some of these names, and
`image_to_icon.py` raises channels below `CH_FLOOR` after applying the
overlay, so rerunning either one changes icons drawn here.

### Open tuning questions (need the physical device)

- `CH_FLOOR = 20` (`iconlib/emit.py`) -- does that survive the diffuser, or does the floor need to be higher?
- Brown-as-dim-amber (`BROWN_AMBER = (60, 40, 0)`, `iconlib/segment.py`) -- reads as an "amber intruder" next to a bright saturated body in early testing; whether it reads as brown over a larger field with no brighter reference nearby needs a real test.
- `DEFAULT_INTENSITY = 0.30` (`icon_matrix.py` -- `main.py` no longer carries this constant itself) -- matched by eye against the ceiling below, not measured; check against a sustained hold before trusting it for anything left on for minutes.

## Open questions / next steps

- Pick a concrete sustained-brightness ceiling (see Design guidance above) before leaving real content running for extended periods.
- Tune the items in "Open tuning questions" above against the physical matrix.
