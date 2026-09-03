# Wand Game Simulator

Browser-based Pyodide simulator that runs unmodified wand game modules (`jump`, `shake`, `shake_rainbow`, `sound`, `rainbow`) against fake MicroPython hardware. Ships as a `<wand-sim>` custom element.

## Run locally

From this directory:

```bash
cd Simulator
python3 -m http.server 8000
```

Open [http://localhost:8000/index.html](http://localhost:8000/index.html).

Pyodide loads from jsDelivr (pinned). Asset URLs resolve from `import.meta.url`, so the element works when embedded on another origin path as long as the `Simulator/` tree is served intact.

## Sync vendored sources

Games and verbatim libs are copied into `vendor/` from `Bag2/Code/`:

```bash
python3 tools/sync_sources.py          # refresh vendor/ + MANIFEST.json
python3 tools/sync_sources.py --check  # exit 1 if vendor drifted
```

A pre-commit hook at `.githooks/pre-commit` runs `--check`. Enable with:

```bash
git config core.hooksPath Simulator/.githooks
```

(or copy the hook into `.git/hooks`).

## Tests

```bash
cd Simulator
python3 -m pytest tests/test_transform.py -v
python3 -m pytest tests/test_golden_frames.py -v
```

- `test_transform.py` — pure AST sync→async transform (no Pyodide).
- `test_golden_frames.py` — CPython asyncio harness that loads shims + devices + transformed games and asserts LED frames under scripted input.

## Design notes

- **Verbatim**: `leds.py`, `buzzer.py`, `brightness.py`, `hubtype.py`, `game_tags.py`, … (AST-transformed to async).
- **Faked wholesale**: `lis2dw12`, `max17048`, `opt3002`, `pn532`, `nfc_reader`, `espnow_manager`.
- **Platform shims**: `machine`, `neopixel`, `time.sleep_ms` / `ticks_*`, `_thread`, `network`, …
- Stop = cancel the `play()` asyncio task; games' `try/finally: leds.off()` still runs.
