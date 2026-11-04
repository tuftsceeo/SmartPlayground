# WebApp2 — Wand Remote

Browser-based teacher/controller app for Bag2/Bag3 wand games. Connects to an ESP32 hub ("Hub2")
over USB Serial (Web Serial API, Chrome/Edge only) and sends game commands, which the hub relays to
wands over ESP-NOW.

**Team:** Smart Playground Project at Tufts CEEO  
**Funding:** NSF Award #2301249  
**Contributors:** J. Cross (front-end/backend), C. Rogers & M. Dahal (hub utilities)

## Features

- **USB Serial Connection**: connects to an ESP32 hub using the Web Serial API (Chrome/Edge only)
- **14 Games**: game commands defined in `js/utils/commands.json`, plus `stop` and `poll`
- **Command Broadcasting**: sends a command over serial to the hub, which relays it to wands over ESP-NOW; the UI is a chat-style message list (`js/components/messaging/`)
- **Installable (PWA)**: `manifest.json` declares standalone display; the viewport is locked (`user-scalable=no`) and `apple-mobile-web-app-capable` is set
- **Firmware Upload**: uploads hub firmware to the device from the browser, over the REPL
- **Command Acknowledgment**: the hub replies `{"type":"ack","command":"<tag>","status":"sent"}` after each command

## How it's built

Hybrid PyScript + JavaScript (PyScript `2024.1.1`, Pyodide interpreter):

- JavaScript (`js/adapters/serialAdapter.js`) owns the Web Serial API — port lifecycle,
  reader/writer locks, read loop.
- Python (`main.py` + `mpy/*.py`) owns protocol logic — REPL control sequences, firmware upload,
  JSON parsing, device-record normalization.
- `js/utils/pyBridge.js` is the only JS→Python call surface; Python calls back into JS via
  `window.on*` global callbacks.

Vanilla JS UI components (no framework): factory functions building detached DOM with Tailwind
utility classes. State lives in a single mutable object (`js/state/store.js`), re-rendered on
`requestAnimationFrame`.

## Adding a file

Every JS/Python file under this app **must** be listed in `pyscript.toml`'s `[files]` table or
PyScript's virtual filesystem 404s on it at runtime — except `main.py`, which is loaded via
`<script src>` and must **not** be listed there.

## Hub firmware

`hubCode2/` is the ESP32 hub firmware this app uploads over Serial/REPL. See
[hubCode2/README.md](hubCode2/README.md) for the hub's hardware, protocol, and file layout — that
document is the canonical protocol reference.

## More detail

See [../AGENTS.md](../AGENTS.md) for the full serial + ESP-NOW protocol, known traps
(`pyscript.toml`, hub validation handshake, `ticks_ms` timestamps), and which sub-app under
`Live_Page/` is canonical.
