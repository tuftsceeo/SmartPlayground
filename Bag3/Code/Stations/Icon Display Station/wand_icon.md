# Wand icons — what's ready, what the firmware still needs

Notes for bringing RGB icon authoring to the Bag3 wand (5×5, 25 LEDs), written
while the hardware is still on order. The web tool and the station firmware are
already prepared; this is the remaining wand-side work.

Bag3 is moving away from monochrome `SHAPE_*` glyphs for icons. Those stay as
shapes for the games that use them; icons become per-pixel RGB, the same format
the station panel uses.

---

## Already done (no wand hardware required)

**Device profiles** — `webapp/js/pipeline/profiles.js` describes each target
board: grid size, working resolution, addressing, thresholds, power ceiling.
`wand5` is defined and the whole pipeline runs under it (verified: a source
image segments, rasters and emits 25 pixels / 5 rows of 5, lint clean).

Selectable in the top bar, and auto-adopted when a board connects — the
firmware's `hello` reports `w`/`h`, so plugging in the right board generally
picks the right profile.

**Size-agnostic protocol.** `frame` and `save` accept optional `w`/`h`; a frame
whose declared size is smaller than the panel is scaled up on arrival. A 5×5
frame is **75 bytes** — worth noting, since that fits in a single ESP-NOW packet
where the 16×16 panel's 768 bytes never could.

**Self-describing icon files.** Both the web app and `icon_store.write_icon()`
now stamp `SIZE = (w, h)`. `read_icon()` uses it to block-scale a smaller icon up
onto a bigger panel, so the station can display a wand icon directly. Files
without `SIZE` are assumed panel-native, so existing icons keep loading.

**Addressing flag.** `icon_matrix.SERPENTINE` sits alongside `MIRROR_X`/`FLIP_Y`
and is settable at runtime via `orient`. The wand strip is plain row-major
(`index = row*W + col`), so it wants `SERPENTINE = False`.

### Scaling: integer factor, centred

16/5 is 3.2, so filling the panel would need some cells 3px and others 4px, which
visibly distorts a glyph drawn on a 5×5 grid. Scaling **3×** gives a clean 15×15
centred in 16×16 with one row/column of margin — the same placement
`icon_test.py` already uses for the 5×5 `SHAPE_*` glyphs.

Downscaling 16×16 → 5×5 is deliberately **not** implemented. It throws away ~90%
of the cells, thin features vanish, and averaged colours are no longer panel
colours. Re-import the artwork with the `wand5` profile selected instead — the
segmenter makes far better choices at the target size than a resample can.

---

## What the wand firmware needs

**1. Correct `hubtype.py`.** It currently declares `num_leds: 60, matrix_cols: 6,
matrix_rows: 10`, and `leds.py`'s glyphs are drawn natively for 6×10. That was a
short-lived prototype; the real board is 5×5 / 25 LEDs. Bag3's own AGENTS.md says
to trust `hubtype.py` over documentation, so until this is fixed it will mislead
anyone reading the tree — and it will break the profile auto-detect, since the
wand would announce the wrong geometry in `hello`.

**2. Port the four server modules.** `icon_matrix.py`, `json_link.py`,
`icon_store.py`, `icon_server.py` are already written against `W`/`H`/`N` rather
than literals, so the port is mostly configuration:

| setting | wand value |
|---|---|
| `W`, `H`, `N` | 5, 5, 25 — ideally read from `hubtype.HUB_CONFIG` |
| `DATA_PIN` | `hubtype`'s `led_pin` (20 on current config) |
| `SERPENTINE` | `False` |
| `MIRROR_X`, `FLIP_Y` | unknown until a board is in hand — use `orient` to find out |
| `MAX_INTENSITY` | needs a real number; see power below |

**3. An icon mode, not a replacement `main.py`.** The wand boots into its game
loop and games are modules exposing
`play(nfc, leds, buz, accel, i2c, enow)`. The station's approach — `main.py` *is*
the icon server — would displace that. Add an `icon_edit.py` game module that
hands control to `IconServer` and returns when it exits, so icon mode is entered
like any other game.

**4. Bypass `_ScaledNeoPixel` while in icon mode.** `leds.py` wraps NeoPixel and
multiplies every write by `brightness.MULTIPLIER`, which `brightness.calibrate()`
sets from the ambient light sensor at boot. That would silently stack with the
icon server's own intensity LUT, so authored colours would not match the preview
and brightness would drift with room lighting. Either write to the raw NeoPixel
in icon mode, or fold the multiplier into the LUT deliberately.

**5. Power ceiling.** The `wand5` profile currently carries `ceilingMa: 400` as a
**conservative guess** — there is no wand equivalent of the readme's bench
measurements, and unlike the station this runs on battery with a `max17048` fuel
gauge available. Measure before trusting live push; 25 LEDs at full white is a
real load on a small cell.

---

## The decision that shapes the rest: transport

**Direct USB** — the wand appears as a serial port and the existing browser
device layer works unchanged. Nearly free.

**Through the hub over ESP-NOW** — a different transport, but a favourable one: a
75-byte frame fits in a single ESP-NOW packet (250-byte limit), so live preview to
a wand is genuinely practical in a way it never was for the 16×16 panel. Needs a
hub-side relay that forwards `frame`/`show`/`save` to a selected wand and returns
replies, plus a target-wand selector in the app. `Live_Page/WebApp2`'s hub already
does broadcast ESP-NOW messaging and is the obvious model.

This is worth deciding before writing the wand server, since it determines whether
`json_link.py` is talking to stdin or to an ESP-NOW callback.

---

## Smaller open questions

- **Icon storage on the wand.** The station keeps `icons/*.py` on flash and reads
  them back. Does the wand have room and a reason to, or should icons live only in
  game modules that `import` them?
- **Palette.** `ledGamut.js` is geometry-independent, so the panel-colour palette
  carries over unchanged — but it is built from *station* LED datasheet figures. If
  the wand uses different WS2812 parts, the primaries want re-checking.
- **`iconlib/emit.py`** (the legacy CLI writer) does not stamp `SIZE`. Harmless —
  files without it are read as panel-native — but the formats have drifted apart.
