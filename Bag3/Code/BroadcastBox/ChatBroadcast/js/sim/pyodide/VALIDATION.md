# Pyodide wand sim — manual validation checklist

Serve the app over HTTP (required for Pyodide CDN + module fetches):

```bash
cd Bag3/Code/BroadcastBox/ChatBroadcast
python3 -m http.server 8765
```

Open `http://localhost:8765/`, unlock, open workspace with an example or generated code.

## Expected behavior

1. Status line shows **"Loading Python simulator…"** then **"Simulating with Python"**.
2. **Press button** on a smile/jumpin-style game lights `SHAPE_HAPPY_FACE` in yellow.
3. **Release** returns LEDs to black (matrix reset each tick).
4. **Shake** on shake-rainbow / jumpin shake example fills matrix with color.
5. **NFC tap** buttons appear from `deriveRequiredTags()`; tapping queues a tag read.
6. **ESP-NOW** Stop/Start buttons enqueue messages readable via `enow.poll()`.
7. On failure, red **"Could not be simulated"** banner + heuristic quick preview remains.

## Reference examples (in `js/examples.js`)

| Example | What to test |
|---------|----------------|
| `jumpin` | Shake fills color; button resets |
| `shakerainbow` | Shake advances rainbow `leds.fill()` |
| `melody` | NFC note tags via tap buttons |
| AI smile game | Press → yellow happy face |

## Console

Filter DevTools console for `[pySim]` — load progress, tick OK, errors.
