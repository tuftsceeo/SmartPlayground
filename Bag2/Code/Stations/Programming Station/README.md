# Programming Station

The hub device that reads a sequence of NFC color tags and broadcasts them wirelessly to all wands and scoreboards in the area.

## What It Does

An operator places up to 4 NFC tags (each programmed with a color command like `turnred`, `turnblue`, etc.) onto the 4 reader slots. When the button on GPIO0 is pressed, all 4 readers are polled simultaneously and the resulting color sequence is broadcast over ESP-NOW to every listening device. This is how a new round of Color Quest begins — the wand modules receive the sequence as the colors to hunt, and the scoreboard resets for a new game.

After a successful broadcast, the 18-LED NeoPixel strip blinks the scanned colors in sequence and runs a short chase animation as visual confirmation.

## How It Works

### Hardware

The station uses a **PCA9546 I2C multiplexer** to share a single I2C bus across 4 separate PN532 NFC readers. Since the PN532 has a fixed I2C address (0x24), the mux switches between channels so only one reader is active at a time.

```
ESP32-C6
   │
   ├── GPIO22 (SDA) ──┐
   ├── GPIO23 (SCL) ──┤── PCA9546 I2C Mux (0x70)
   ├── GPIO1 ─────────┘   RESET
   ├── GPIO2 ──────────── All PN532 RSTPDN pins
   ├── GPIO21 ─────────── 18-LED NeoPixel strip DIN
   └── GPIO0 ──────────── Button (active LOW, internal pull-up)

PCA9546 Channels:
   CH0 → PN532 Reader #0
   CH1 → PN532 Reader #1
   CH2 → PN532 Reader #2
   CH3 → PN532 Reader #3
```

Both SDA and SCL need 4.7kΩ pull-up resistors to 3.3V.

### Boot Sequence

1. Initialize I2C bus at 100 kHz and scan for devices.
2. Hard-reset the PCA9546 mux and all PN532 readers via their reset pins.
3. Cycle through mux channels 0–3, initializing each PN532 (firmware version check + SAM configuration). Readers that fail are excluded from future scans.
4. Initialize ESP-NOW in broadcast mode (`FF:FF:FF:FF:FF:FF`).
5. Enter the main loop, waiting for button presses.

### Scan Cycle (on button press)

Each button press triggers this sequence:

1. **Full hardware reset** — both the mux and all PN532 readers are power-cycled to clear any stale I2C state. This is critical because MIFARE Classic tags lose their authentication state after a mux channel switch.
2. **Re-initialize all readers** — a quick SAM reconfiguration on each channel.
3. **Read each reader** — for each active channel, the station selects the mux channel, re-initializes the reader, and attempts to read NDEF text from the tag. Each reader gets up to 3 retry attempts. The NDEF reading process authenticates MIFARE Classic sectors 1–2 using common keys and decodes the text payload.
4. **Broadcast** — if any tags were successfully read, the color commands are packed into a JSON array (e.g., `["turnred", "turnblue", "turngreen"]`) and broadcast via ESP-NOW.
5. **LED feedback** — the NeoPixel strip blinks each scanned color in sequence, then runs a chase animation mixing all the colors.

### Tag Reading Details

The station reads MIFARE Classic 1K tags. It tries multiple common authentication keys (`FF FF FF FF FF FF`, `D3 F7 D3 F7 D3 F7`, `A0 A1 A2 A3 A4 A5`, etc.) with both Key A and Key B on sectors 1 and 2. The NDEF text record is extracted from the TLV structure and decoded to a lowercase string. Recognized color commands include: `turnred`, `turngreen`, `turnblue`, `turnpurple`, `turnyellow`, `turnwhite`.

### ESP-NOW Message

The station sends a single broadcast message:

```json
["turnred", "turnblue", "turngreen", "turnpurple"]
```

All wand modules and scoreboards within ESP-NOW range receive this. Wands use it as the color sequence to hunt. The scoreboard treats any station broadcast as a new-game signal and resets its display.

## Dependencies

Requires these files in `/lib/` on the device:

- `pn532.py` — PN532 NFC reader driver
- `nfc_reader.py` — NDEF text decoding and common key definitions

## Deployment

1. Copy `lib/pn532.py` and `lib/nfc_reader.py` to `/lib/` on the device.
2. Copy `main.py` to the root of the device.
3. Power on — the station prints reader initialization status to the serial console and waits for button presses.
