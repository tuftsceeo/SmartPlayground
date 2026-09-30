# Device: Icon display  (`[DEVICE: icon]`)

## What it is and who sees it

A 16×16 grid of colored lights (256 pixels) that shows one big picture the **whole class** can see
from across the room. Board: XIAO ESP32-C6. It usually shows what the wands are doing: a team's
score, whose turn it is, a picture that matches a card.

It has **no buzzer, no motion sensor and no button**. It may have a card reader, used only to leave
a game.

## The `play()` contract

The display calls a game with exactly three arguments:

```python
def play(nfc, panel, enow):
```

| Argument | What it is | Notes |
|---|---|---|
| `nfc` | an `NfcReader`, **already built** (unlike the wand, which builds its own) | **May be `None`** when no reader is fitted — guard with `if nfc is not None:` |
| `panel` | the 16×16 display (`icon_matrix.Matrix`) | The only one; never build another |
| `enow` | ESP-NOW manager, already started | Poll every loop |

Never create another `ESPNowManager` or `Matrix`. Two light drivers on one pin fight each other.
Never keep `panel`, `nfc` or `enow` in a module-level variable or register a callback on `enow`:
the game is loaded and unloaded each time it is played, and a kept reference holds the whole game
in memory.

## Canonical template

```python
"""
<Game title> — <one line on what the class sees>
"""
import time

from display_tags import exit_tags_excluding
import icon_store

_EXIT_TAGS = exit_tags_excluding("your_game")
COMMANDS = _EXIT_TAGS

IDLE_ICON = "ready"
IDLE_INTENSITY = 0.12
ACTIVE_INTENSITY = 0.30
NFC_EVERY = 12
LOOP_MS = 40


def _show(panel, name, intensity):
    panel.set_intensity(intensity)
    icon_store.read_icon(name, into=panel.src)
    panel.draw_bytes(panel.src)


def play(nfc, panel, enow):
    frame = 0
    try:
        _show(panel, IDLE_ICON, IDLE_INTENSITY)
        while True:
            frame += 1

            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if msg_type == "raw" and isinstance(data, dict):
                if data.get("type") == "yourmsg":
                    _show(panel, "whale", ACTIVE_INTENSITY)

            if nfc is not None and frame % NFC_EVERY == 0:
                cmd, _uid = nfc.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return

            time.sleep_ms(LOOP_MS)
    finally:
        panel.clear()
```

Replace `"your_game"` with the game's slug, and `"ready"` / `"whale"` with icon names from the list
sent with the request.

## API

### The panel

| Call | What it does |
|---|---|
| `panel.set_intensity(v)` | Brightness, 0.0–0.50 |
| `panel.draw_bytes(src)` | Show 768 bytes: 256 (r, g, b) triples, row by row from the top-left |
| `panel.set_pixels(triples)` | Change some pixels: `(index, r, g, b)`, index 0–255 |
| `panel.clear()` | All off |
| `panel.redraw()` | Re-show the last picture at the current brightness |
| `panel.src` | The 768-byte frame buffer; draw into it instead of making a new one |

Pixel index = `row * 16 + col`, both 0–15, from the top-left.

**Brightness:** 0.50 is a hard ceiling (more would overload the power supply). A picture that stays
up all session should sit at 0.10–0.15; use 0.25–0.35 for a short celebration.

### Named icons

Pictures are stored on the display by name. Refer to them by name; never paste pixel data into a
game.

```python
import icon_store
icon_store.read_icon("whale", into=panel.src)
panel.draw_bytes(panel.src)
```

Use **only** names from "ICONS CURRENTLY AVAILABLE" sent with the request; the app refuses to send a
game that names any other. If the game needs a picture that is not in the list, say so and suggest
the closest one. `read_icon` raises if a name is missing — let it: a display that looks on but
shows nothing is the hardest failure to spot.

### Live numbers and shapes — `draw16`

For values known only while playing (a score, a countdown, a bar). For everything else, use a named
icon; a drawn picture looks better than one built from rectangles.

```python
import draw16
draw16.clear(panel.src)
draw16.number(panel.src, score, 5, color=(0, 200, 60))   # row 5, centered
draw16.show(panel)
```

- Shapes: `px, get, clear, rect, frame, circle, ellipse, line`. Text: `glyph, text, number,
  width` (3×5 font: digits, space, `- : .`). Flush: `show(panel)`.
- **All coordinates are `(row, col)`**, from the top-left.
- Drawing calls take `panel.src`, not `panel`, and do not display anything. Draw the whole frame,
  then call `draw16.show(panel)` **once**; showing after each shape flickers.
- `draw16.number(src, value, row, col=None, color=..., spacing=1)` — `col=None` centers it, so a
  score going from 9 to 10 does not jump sideways.
- Redraw only when something changed.

### Countable pictures — `chart16`

Young children understand a quantity they can **count** better than a numeral. `chart16` draws
counts using the same `SHAPE_*` pictures as the wand.

```python
import chart16, shapes
chart16.blocks(panel.src, [green, blue], [(0, 200, 60), (40, 120, 200)], empty=(45, 45, 45))
draw16.show(panel)
```

| Call | Use |
|---|---|
| `chart16.count_glyphs(src, n, shape, color, per_axis=3, gap=0, empty=None)` | One quantity as copies of a picture; 3×3 counts to nine, `per_axis=2` to four |
| `chart16.blocks(src, values, colors, cap=5, empty=None, labels=None)` | Blocks per team, up to five. With `labels=[(shape, color), ...]` pass `cap=4` |
| `chart16.grid(src, cells)` / `chart16.grid_row(src, entries)` | The 3×3 layout addressed cell by cell |
| `chart16.line_graph(src, values, color, baseline=None)` | Change over time |

`count_glyphs` and `blocks` return how many they could not fit. `empty=` draws unearned slots as dim
outlines ("we need two more").

## Everyday words → code

| The teacher says | Use |
|---|---|
| "show a picture of a whale" | named icon `"whale"` (if in the list) |
| "show the score" | `draw16.number(...)` |
| "show how many points each team has" | `chart16.blocks(...)` |
| "show 5 stars" | `chart16.count_glyphs(src, 5, shapes.SHAPE_STAR, color)` |
| "make it brighter when someone wins" | `set_intensity(0.30)` briefly, then back to 0.12 |

## Limits and why

- **Poll `enow` every loop**, or the game cannot be switched.
- **Cards every 12 loops**, only to leave the game. Rounds are driven by ESP-NOW messages from the
  wands, not by cards on the display.
- **Loop delay about 40 ms.** The panel keeps its picture; redraw only on change.
- **`draw16` and `chart16` live on the display.** A display with older firmware raises
  `ImportError` for them; named icons always work.

## Checklist

- [ ] `[DEVICE: icon]` before the block
- [ ] `def play(nfc, panel, enow):` — exactly three
- [ ] `enow.poll()` every loop; return on `"stop"` / `"start_game"`
- [ ] Every `nfc` use guarded with `if nfc is not None:`
- [ ] Every icon name is in the list sent with the request
- [ ] `set_intensity` never above 0.50
- [ ] `panel.clear()` in `finally`
- [ ] Live values use `draw16`; fixed pictures use named icons; counts for children use `chart16`
