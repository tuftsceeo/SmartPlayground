# Live_Page/AGENTS.md — web apps

Read [../AGENTS.md](../AGENTS.md) first for the Bag model and the Bag2 verification gate (it applies
here too — a WebApp2 change that alters what gets sent to Bag2 wands still needs hardware testing).
This file covers the static web apps deployed from this directory.

## Deploy reality

Everything under `Live_Page/` is served as-is by GitHub Pages — no build step, no bundler, no
`package.json`. `.github/workflows/static.yml` deploys **only on push to `May_2026`**; changes on
any other branch, including this one, are not live regardless of correctness. All JS is native ES
modules loaded directly by the browser; libraries come from CDNs (Tailwind, Lucide) rather than a
package manager.

## Which sub-app is canonical

| App | Role | Notes |
|---|---|---|
| `WebApp2/` | **Canonical** — teacher-facing hub controller for Bag2/Bag3 wand games | |
| `Flasher/` | **Canonical** — code uploader | Best REPL implementation in the repo: chunked base64, binary-safe, retry/backoff GitHub fetch |
| `WebApp/` | Legacy | Bag1 plushie controller; 16 of ~30 JS files are byte-identical to WebApp2's |
| `Code_Upload/` | Dead predecessor of Flasher | Single 1240-line file, hardcoded to the stale branch `beta_January_2026`, ~90% functional overlap with Flasher |
| `If_Splats/` | Standalone demo | Web Bluetooth → third-party "Open Splat" toys, unrelated to the ESP-NOW hub stack. Uses a newer PyScript version (`2026.2.1`, `type="mpy"`) and a cleaner `js_modules` JS↔Python interop than WebApp2's `window.*` globals — prefer that pattern for new PyScript work |
| `wand_icons.html` | Static reference, not an app | LED-icon meaning guide with its own inline matrix renderer |

`Flasher/manifests/wand.yml` sources `Bag2/Code/lib` + `Bag2/Code/Wand Module` — intentional, since
most wand hardware in circulation is Bag2. `hub.yml` sources `Live_Page/WebApp2/hubCode2`;
`m5paper.yml` sources `Bag2/Code/M5Paper Remote`. There is no manifest yet for Bag3 wand hardware.

**`Live_Page/WebApp2/README.md` describes WebApp2 accurately** (it was rewritten from a stale copy
of `WebApp/README.md`). Trust it, along with `WebApp2/hubCode2/README.md`, over inferring behavior
from code alone.

## WebApp2 architecture

Hybrid PyScript + JavaScript. The split is deliberate, not historical accident:

- **JavaScript** (`js/adapters/serialAdapter.js`) owns everything that touches native
  Promise-based browser APIs: `navigator.serial`, reader/writer lock lifecycle, timeouts.
- **Python** (`main.py` + `mpy/*.py`) owns protocol logic: REPL control sequences, firmware upload
  orchestration, JSON parsing, device-record normalization.

PyScript version is `2024.1.1` (Pyodide interpreter, `type="py"`). `js/utils/pyBridge.js` is the
**only** JS→Python call surface, calling `window.*` globals that `main.py` exports; Python calls
back into JS the same way, via `window.on*` callbacks registered in `App.init()`.

**Component pattern:** vanilla factory functions returning detached `HTMLElement`s — build with
`document.createElement`, set Tailwind utility classes on `className`, assign an `innerHTML`
template literal, `querySelector` the interactive nodes and assign `.onclick =` (property
assignment, not `addEventListener`). `js/state/store.js` is a single mutable object; `setState()`
batches renders onto one `requestAnimationFrame`. `App.render()` in `js/main.js` does a full
teardown-and-rebuild on every state change.

## Traps

- **`pyscript.toml`'s `[files]` list must include every JS and Python file you add** under
  `WebApp2/`, or PyScript's virtual filesystem 404s on it at runtime. `main.py` itself is the
  `<script src>` and must **not** be listed there.
- Tailwind (`cdn.tailwindcss.com`) and Lucide (`unpkg.com/lucide@latest`) are both unpinned CDN
  imports — a version bump upstream can change behavior with no diff in this repo.
- **Hub validation handshake:** connecting over serial doesn't mark the hub "connected" — the app
  waits up to 10 s for either a `ready` or `heartbeat` message before setting `hubConnected: true`.
  On timeout the port is deliberately kept open (not closed) so the user can retry or open the
  firmware-setup flow. `hubValidationEnabled` is toggled off during firmware upload, since a device
  sitting at a REPL prompt will never emit a heartbeat.
- **Hub timestamps are `time.ticks_ms()` since boot, not epoch time.** The browser re-stamps
  incoming device reports with its own clock; don't treat hub timestamps as wall-clock time.

## Protocol, in full

**Layer 1 — web app ↔ hub**, line-delimited JSON over 115200-baud serial:

```
App → Hub:  {"cmd": "<game_tag>"}
            {"cmd": "stop"}
            {"cmd": "poll"}
            {"cmd": "find", "mac": "AA:BB:CC:DD:EE:FF"}

Hub → App:  {"type": "ready", "mac": "...", "version": "...", "timestamp": <ticks_ms>}
            {"type": "heartbeat", "timestamp": <ticks_ms>, "uptime": <ms>}
            {"type": "ack", "command": "<tag>", "status": "sent"}
            {"type": "poll_started", "timestamp": <ticks_ms>}
            {"type": "device_report", "id": "...", "mac": "...", "battery": <int>, "rssi": <int>, "timestamp": <ticks_ms>}
            {"type": "devices", "list": [...], "timestamp": <ticks_ms>}
            {"type": "error", "message": "..."}
```

Lines that don't start with `{` are hub debug text, logged rather than parsed.

**Layer 2 — hub → wands**, ESP-NOW JSON, broadcast to `FF:FF:FF:FF:FF:FF`:

| Serial `cmd` | ESP-NOW payload | Sent |
|---|---|---|
| `<game_tag>` | `{"type":"start_game","name":"<tag>"}` | ×2, 100 ms apart |
| `stop` | `["stop"]` (a JSON **list**, not a dict) | ×2, 100 ms apart |
| `poll` | `{"type":"status_poll"}` | ×3, 60 ms apart |
| `find` | `{"type":"find_device","mac":"<mac>"}` | ×2, 100 ms apart |

No pairing, no channel negotiation — everything is broadcast-first. Wands reply
`{"type":"status_report","battery":<int|null>,"rssi":<int|null>}`, staggered by a slot derived from
each wand's own MAC to avoid collisions.

**Layer 3 (WebApp/Bag1 only) — hub → plushies**, a separate topic/value scheme:
`{"topic":"/game","value":<int>}`, unrelated to the ESP-NOW layer above.

## Flasher

Manifest-driven, over Web Serial, no PyScript:

1. Pick a version (curated branch) and a device (`wand`/`hub`/`m5paper`), each backed by a YAML
   manifest under `manifests/`.
2. Fetch source from GitHub's trees API (SHA-pinned raw URLs, Cache API, retry/backoff on
   rate-limiting, binary-aware).
3. Upload over the REPL using **chunked base64** (`js/serial.js`) — binary-safe, unlike WebApp2's
   text-only triple-quote upload method.

Adding a new flashable device = a new `manifests/<device>.yml` (hand-rolled YAML parser — keep the
same minimal shape as the existing three files) plus an entry in `js/devices.js`.
