# WebApp2/AGENTS.md

Teacher-facing controller for the USB hub. Hybrid PyScript + JavaScript: JS owns `navigator.serial`
and reader/writer lock lifecycle, Python owns protocol logic. `js/utils/pyBridge.js` is the only
JS→Python call surface.

## `pyscript.toml`

New Python modules under `mpy/` must be added to `[files]`, or `main.py`'s import fails at runtime.
`main.py` itself is the `<script type="py" src>` and is not listed there.

JS files do **not** need listing — they're loaded by the browser as native ES modules and never enter
PyScript's virtual filesystem. The existing `js/*` entries in `[files]` are unnecessary;
`js/adapters/serialAdapter.js` and `bluetoothAdapter.js` are unlisted and work fine.

## Connect ≠ connected

The app waits up to 10 s for a `ready` or `heartbeat` message before setting `hubConnected`, and
keeps the port open on timeout. Validation is disabled during firmware upload, because a device
sitting at a REPL prompt never sends a heartbeat.

## Hub timestamps are `time.ticks_ms()` since boot, not epoch time.

## Protocol — app ↔ hub

Line-delimited JSON over 115200-baud serial. Lines not starting with `{` are hub debug text.

```
App → Hub:  {"cmd": "<game_tag>"}
            {"cmd": "stop"}
            {"cmd": "poll"}
            {"cmd": "find", "mac": "AA:BB:CC:DD:EE:FF"}

Hub → App:  {"type": "ready",        "mac": ..., "version": ..., "timestamp": <ticks_ms>}
            {"type": "heartbeat",    "timestamp": <ticks_ms>, "uptime": <ms>}
            {"type": "ack",          "command": "<tag>", "status": "sent"}
            {"type": "poll_started", "timestamp": <ticks_ms>}
            {"type": "device_report","id": ..., "mac": ..., "battery": <int>, "rssi": <int>, "timestamp": <ticks_ms>}
            {"type": "devices",      "list": [...], "timestamp": <ticks_ms>}
            {"type": "error",        "message": ...}
```

## Protocol — hub → wands

ESP-NOW JSON, broadcast to `FF:FF:FF:FF:FF:FF`. No pairing, no channel negotiation. This is the hub
side only; confirm the wand side against the target Bag's `espnow_manager.py`.

| Serial `cmd` | ESP-NOW payload | Sent |
|---|---|---|
| `<game_tag>` | `{"type":"start_game","name":"<tag>"}` | ×2, 100 ms apart |
| `stop` | `["stop"]` — a JSON **list**, not a dict | ×2, 100 ms apart |
| `poll` | `{"type":"status_poll"}` | ×3, 60 ms apart |
| `find` | `{"type":"find_device","mac":"<mac>"}` | ×2, 100 ms apart |

Wands reply `{"type":"status_report","battery":<int|null>,"rssi":<int|null>}`, staggered by a slot
derived from each wand's MAC to avoid collisions.
