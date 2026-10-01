# Splat Companion modem (XIAO ESP32-C6)

UART <-> ESP-NOW bridge for the Splat Companion hub (`../Companion/`).
Plain MicroPython on a Seeed XIAO ESP32-C6.

## Upload

```bash
cd Bag3/Code/BroadcastCode/SplatCompanion/ESPNowModem
python3 -m mpremote connect $MODEM_PORT resume \
  fs cp main.py :main.py + \
  fs mkdir :lib + \
  fs cp lib/eum_proto.py lib/eum_classify.py :lib/
python3 -m mpremote connect $MODEM_PORT reset
```

`fs mkdir` fails if `/lib` already exists; drop that step then.

## Pins

| Modem pin | Goes to |
|---|---|
| GPIO16 (D6), UART1 TX | hub GPIO17 (D7), RX |
| GPIO17 (D7), UART1 RX | hub GPIO16 (D6), TX |
| GND | hub GND |

UART1 at 921600 baud. At boot the modem prints
`EUM modem: MAC ... uart1 tx=16 rx=17 @921600` on the USB REPL.

## What differs from `../../EspnowModem/modem/main.py`

- **C6 only:** no board detection and no S3 branch.
- **Pins:** UART TX/RX are GPIO16/17 (the proof of concept's C6 branch
  used GPIO0/1).
- **Ring:** `RING_SLOTS = 64` (no PSRAM).
- **Antenna:** the antenna select (GPIO3/14) always runs;
  `MODEM_EXTERNAL_ANTENNA = False` selects the onboard antenna. This
  station's modem board has no u.FL antenna fitted.

Everything else, including `lib/`, is the proof of concept's code
unchanged; `lib/` is byte-checked by `../Companion/test_splat_companion.py`.

## Not verified on hardware

- UART0 boot-log noise on GPIO16/17 at reset. EUM frames are CRC-checked,
  so it should show only as `crc_err` counts; see the hub's
  `bench/1_modem_link.py`.
