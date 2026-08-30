# Broadcast Box firmware (M5Stack StickS3, UIFlow2 MicroPython)

Firmware for the Broadcast Box: USB JSON serial to the ChatBroadcast app,
NFC card writing, and SoftAP + TCP code push to wands.

## Filesystem

Write all device files to **`/flash`**, not `/`.

## Hardware (confirm with probe)

| Item | Default in code | Notes |
|------|-----------------|-------|
| Board | M5Stack StickS3 | ESP32-S3, UIFlow2 |
| Display | `M5.Lcd` landscape 240×135 | `ROTATION = 1` in `bbox_ui.py` |
| NFC | PN532 @ I2C `0x24` | Grove HY2.0-4P — run `probe_stick.py` for SDA/SCL |
| Button | `M5.BtnA` | short / ~800 ms long press |
| USB | `/dev/cu.usbmodem3101` (example) | `mpremote` |

## Phase 0 probe results (2026-08-29)

| Check | Result |
|-------|--------|
| `ap_socket` | **PASS** — AP + listen on 8266 |
| `lcd` | **PASS** — DejaVu18, rotation 1 |
| `nfc_pins` | Confirm Grove wiring — default SDA=4 SCL=5 |
| `button_api` | **PASS** — `M5.BtnA` |
| Short/long press | Manual — press during probe window |

I2C defaults in `bbox_server.py`: SDA=4, SCL=5 @ 0x24. Update after probe if different.


## Deploy firmware

```bash
cd Bag3/Code/BroadcastBox/BBoxFirmware
for f in *.py; do
  mpremote connect /dev/cu.usbmodem3101 fs cp "$f" :/flash/"$f"
done
mpremote connect /dev/cu.usbmodem3101 reset
```

Or use ChatBroadcast's firmware installer + `manifest.js`.

## Serial protocol

Host `cmd` → device; device replies with `type`. See
`Bag3/Code/Stations/serial_protocol_notes.md`.

Commands: `hello`, `info`, `arm`, `disarm`, `repl`, `reboot`

Events: `hello`, `info`, `heartbeat`, `armed`, `card_present`, `card_written`,
`error`, `bye`, `fatal`

**Hello contract:** firmware announces at boot and answers `{"cmd":"hello"}`
with the same payload shape. Host must not await hello to connect — use
heartbeat for liveness.

## Payload flow

1. App pushes `/flash/payload.py` via raw REPL (base64 write).
2. App sends `arm` — Box brings up `SP-FILEPUSH` AP and waits for wand TCP pull.
3. Box writes `getcode` opcode to NFC card when tapped.
4. Wand taps card, joins AP, pulls `jumpin.py` via `code_server` / `c6_receiver`.

## Verify checklist (mpremote)

See plan §Verify — Box firmware. Key checks:

- Boot grace + `# ` debug lines only before JSON
- Query `hello` after boot with matching payload
- Heartbeat without catching boot hello
- Unmodified `c6_receiver.py` byte-identical pull

## opcodes.py

Contains `OP_BROADCAST` / `getcode`. **Must match** `MockWand/lib/opcodes.py`.
