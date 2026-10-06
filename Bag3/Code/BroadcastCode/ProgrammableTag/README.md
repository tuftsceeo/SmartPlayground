# ProgrammableTag

Proof of concept: a XIAO ESP32-C6 rewrites the NT3H2111 on a MIKROE NFC Tag 2 Click over I2C. A phone or the wand's WS1850S reader then reads the new contents by tap.

## Hardware

| Part | Detail |
|---|---|
| Board | XIAO ESP32-C6 on a Seeed expansion board (3.3V Grove) |
| I2C | SDA=GPIO22 (D4), SCL=GPIO23 (D5), 100 kHz `SoftI2C` |
| Tag | MIKROE NFC Tag 2 Click, NT3H2111, I2C 0x55, 3.3V only |
| OLED | on-board SSD1306, I2C 0x3C, same bus |
| Button | XIAO BOOT, GPIO9 |

The click's FD/INT line is not wired, so RF field presence comes from the NS_REG session register.

The StickS3 Grove port is 5V and off by default, so it is not used.

## Files

| File | Purpose |
|---|---|
| `nt3h.py` | NT3H2111 driver: block and page read/write, UID, CC, NS_REG, TLV area |
| `ndef.py` | NDEF text build/decode, copied from `BBoxFirmware/card_writer.py` |
| `ssd1306.py` | copy of `Live_Page/WebApp2/hubCode2/ssd1306.py` (third-party, unmodified) |
| `main.py` | OLED UI: short press cycles presets, long press writes and reads back |
| `tools/probe_nt3h.py` | bench check: scan, read blocks, write/read/restore one block |

Block 0 and the configuration block are never written. No lock bits or passwords are set.

## Deploy

Follow `Bag3/Code/HARDWARE_PROTOCOL.md`: confirm the port, then

```bash
python3 -m mpremote connect $PORT resume fs cp nt3h.py ndef.py ssd1306.py main.py :
```

then a plain `reset`. Run `tools/probe_nt3h.py` first by copying it to the board, or with `mpremote run`.

## Unverified

Memory map, NS_REG bit layout and the capability-container bytes come from memory of the NT3H2111 datasheet. Check the probe output against it before relying on writes.
