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
| NFC | PN532 @ I2C `0x24` | Grove HY2.0-4P — SDA=G9, SCL=G10 (confirmed via `mpremote` `i2c.scan()`, fw 1.6) |
| Button | `M5.BtnA` | short / ~800 ms long press |
| USB | `/dev/cu.usbmodem3101` (example) | `mpremote` |

## Phase 0 probe results (2026-08-29)

| Check | Result |
|-------|--------|
| `ap_socket` | **PASS** — AP + listen on 8266 |
| `lcd` | **PASS** — DejaVu18, rotation 1 |
| `nfc_pins` | **PASS** (2026-08-31, via `mpremote`) — SDA=9 SCL=10, PN532 fw 1.6 |
| `button_api` | **PASS** — `M5.BtnA` |
| Short/long press | Manual — press during probe window |

I2C in `bbox_server.py`: SDA=9, SCL=10 @ 0x24. (SDA=4/SCL=5 was the original
assumption and does not work — `i2c.scan()` on those pins comes back empty.)


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

**Arming is self-driven, not host-driven.** `payload.py` existing on flash
is a standing fact, not a session state — the Box decides for itself
whether to arm (`bbox_server.py`'s `_try_arm()`, called from `run()` right
after boot) rather than waiting for the laptop to send `arm`. This matters
because the Box has to keep working (AP up, ready to write cards) after
it's unplugged from USB and carried to the playground, which a
laptop-driven handshake can't guarantee. `arm`/`disarm` still exist as
manual overrides (REPL testing, forcing a re-arm, or turning broadcast off
on purpose) but the app no longer calls `arm` after pushing code.

## Payload flow

1. App pushes `/flash/payload.py` via raw REPL (base64 write) and soft-resets.
2. On that reboot, the Box sees `payload.py` on flash and arms itself —
   brings up the `SP-FILEPUSH` AP and enables NFC card writing — with no
   further command from the app.
3. Box writes plain NDEF text `"getcode"` to the NFC card when tapped
   (`card_writer.py` — see note below, **not** the Bag3 opcode scheme).
4. Wand taps card, joins AP, pulls `jumpin.py` via `code_server` / `c6_receiver`.

## Card format: plain NDEF text, not opcodes.py

`card_writer.py` writes/reads plain NDEF text records (`write_text` /
`existing_text`), ported from `Bag2/Utilities/writetoNFCcards.py` (write)
and `Bag2/Code/lib/nfc_reader.py`'s `_decode_ndef_text` (read) — both
proven on real hardware. It deliberately does **not** use this repo's
`opcodes.py` 4-byte scheme, which is Bag3-only and untested. `MockWand/lib/nfc_reader.py`
was switched to match (Bag2-style NDEF reading) so Box and wand agree.
Revisit this once opcodes.py has been bench-tested end to end.

## Verify checklist (mpremote)

See plan §Verify — Box firmware. Key checks:

- Boot grace + `# ` debug lines only before JSON
- Query `hello` after boot with matching payload
- Heartbeat without catching boot hello
- Unmodified `c6_receiver.py` byte-identical pull

## opcodes.py

Contains `OP_BROADCAST` / `getcode`. **Must match** `MockWand/lib/opcodes.py`.
