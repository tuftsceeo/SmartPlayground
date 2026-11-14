# Designing icons for the icon display

The icon display is a 16x16 WS2812 matrix behind a dark smoked diffuser.
Icons are 256 `(r, g, b)` LED duty values, row-major from top-left. Use this
guide when drawing, recolouring or reviewing icons, including themed or
animated sets. Commands below run from this folder.

## Where things live

All paths are under `Bag3/Code/Stations/`.

| What | Path |
|---|---|
| Device icon set (source of truth) | `IconDisplay/icons/<name>.py` |
| Authoring tools, maps, drafts | `Icon Display Station/` |
| Grid maps waiting for review | `Icon Display Station/drafts/grids/*.json` |
| Grid → icon + preview tool | `Icon Display Station/grid_to_icon.py` |
| Promote sequence | `Icon Display Station/drafts/README.md` |
| LED colour model | `Icon Display Station/webapp/js/pipeline/ledGamut.js` (`ledSwatchHex`) |

## The recognisability test

The test: could a five-year-old who is not told the name, and not given a
list of options, guess what the icon shows?

- Draw a bold caricature. Use a big silhouette that fills the frame, and
  exaggerate the one defining feature: the trunk, the teeth, the tail fan,
  the carved face.
- Give each icon its own main colour. Icons that are often shown together
  (animals, foods) should not share a hue.
- Faces and emotions all use the same big circle that fills the frame. Only
  the expression changes.
- Check yourself blind. Render a numbered sheet without names, write down a
  guess for each icon, and only then compare. Rate each icon Yes, Maybe or
  No. For every Maybe or No, name the missing feature.

## Eyes depend on the subject

| Subject | Eyes |
|---|---|
| Animals with dark eyes (bird, bat, cat, dino) | 2x2 block: top-left white highlight, other three near-black |
| People and human-like faces | White sclera with a dark pupil |
| Jack-o'-lantern | Carved holes glowing yellow |
| Skulls | Empty dark sockets; calaveras get decorated sockets (flower or coloured ring) |
| Ghosts | Simple dark ovals |

Use the subject's traditional depiction rather than one eye style for
everything. Larger, stylised eyes read better than single pixels.

## Colour: think in LED duty, not screen RGB

The LEDs' blue is strong, and equal R=G=B is cyan, not grey. Check every
colour with `led_screen_rgb` in `grid_to_icon.py`; it is the same model the
icon editor and the simulator use.

| Name | Duty | Shows as |
|---|---|---|
| White | (185,255,150) | (218,218,218) |
| Light grey | (180,120,65) | (187,186,186) |
| Grey | (110,74,40) | (149,150,149) |
| Near black | (30,20,10) | (82,81,77) |
| Cream | (255,140,60) | (235,196,177) |
| Yellow | (255,150,0) | (238,201,0) |
| Orange | (255,60,0) | (255,118,0) |
| Red | (255,0,0) | (255,0,0) |
| Pink | (255,94,50) | (254,159,164) |
| Green | (20,160,0) | (0,220,0) |
| Dark green | (0,100,0) | (0,179,0) |
| Sky blue | (0,60,200) | (0,151,255) |
| Blue | (0,0,255) | (0,65,255) |
| Purple | (100,0,255) | (149,38,255) |
| Tan | (180,60,10) | (224,126,68) |
| Brown | (150,45,5) | (209,109,40) |
| Dark brown | (80,20,0) | (161,71,0) |

Rules that follow from the model:

- **Neutrals:** whites and greys use the warm ratio of about 1 : 0.67 : 0.36.
- **Pinks and purples:** keep blue very low.
- **Yellow:** (255,210,0) shows green-yellow. Use (255,150,0).
- **Red:** (230,20,20) shows magenta. Use pure red.
- **Green:** (0,200,60) shows teal. Use (20,160,0).
- **Dark subjects:** off pixels are dark, so a black subject (black cat, bat)
  needs a lit background behind it, such as a moon, to be seen.

## Workflow

1. **Draw** a grid map in `Icon Display Station/drafts/grids/<set>.json`:

   ```json
   {
     "ghost": {
       "key": {"W": [255,171,93], "K": [30,20,10]},
       "rows": ["................", "...", "16 rows of 16 chars"]
     }
   }
   ```

   `.` is off. An animated entry has `"frames": [rows, rows, ...]` and
   `"fps"` in place of `"rows"`.

2. **Preview:**

   ```bash
   python3 grid_to_icon.py drafts/grids/<set>.json
   ```

   This writes `previews/grids/<set>.png`, a labelled sheet, plus a GIF for
   each animated entry.

3. **Review** the sheet blind (see the recognisability test above) and
   redraw until every icon is a Yes. A person signs off on the sheet.

4. **Write the drafts:**

   ```bash
   python3 grid_to_icon.py drafts/grids/<set>.json --write
   ```

   This writes `drafts/icons/<name>.py`.

5. **Promote** by following `drafts/README.md`: copy the icon into
   `IconDisplay/icons/`, then regenerate the chat app's list:

   ```bash
   python3 ../../ChatBroadcast/tools/sync_icons.py
   ```

   An icon missing from that list works on the device, but a generated game
   that names it is refused.

To check an icon on the simulated display, open the Simulator
(`Bag3/Code/Simulator/`, served from `Bag3/Code/`) with a game that uses the
display.

## Animation

The device holds one frame per icon (`ICON` in `icons/<name>.py`), and
nothing plays frame sequences. `--write` stores each frame of an animated
entry as `<name>_1.py`, `<name>_2.py`, and so on.

`icon_server.py`'s bench-only `cycle` command (`names`, `hold_ms`) steps
through a list of stored icons, which gives a slow, crude animation.

Real playback would need:

- a multi-frame file format with an fps;
- a store that keeps frames as bytearrays;
- a timer in the main loop;
- frame-aware tooling in the icon maker and `sync_icons.py`.

Frames cost 768 bytes each, and the radio-first boot rule in `AGENTS.md`
applies.
