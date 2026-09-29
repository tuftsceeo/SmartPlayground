# Hub bench bring-up

Run these on the hub in order, from `SplatCompanion/Companion/`. Each is
run with `mpremote run`, so the script itself is not copied to the board.
Only the listed files must already be on it. Report each PASS/FAIL line
(stage 2 is a visual check).

| Stage | Command | Files on the hub first |
|---|---|---|
| 1 modem link | `mpremote connect $HUB resume run bench/1_modem_link.py` | `hubtype.txt`, `lib/hubtype.py`, `lib/espnow_manager.py`, `lib/eum_proto.py` -- and the modem flashed (`../ESPNowModem/README.md`) |
| 2 LED ring | `mpremote connect $HUB resume run bench/2_leds.py` | + `status_leds.py` |
| 3 BLE Splats | `mpremote connect $HUB resume run bench/3_ble_splat.py` | + `splat_link.py`, `splat_hub.py`, `splat_api.py`, `lib/ble_splat.py` |
| 3b scan vs link (diagnostic) | `mpremote connect $HUB resume run bench/3b_scan_while_connected.py` | stage-3 files; one Splat on. Reports drops with and without a scan running |
| 4 NFC reader | `mpremote connect $HUB resume run bench/4_nfc.py` | + `lib/pn532.py`, `lib/nfc_reader.py`, `lib/splat_tags.py` |

Copy with, for example:

```bash
mpremote connect $HUB resume fs cp hubtype.txt : + fs mkdir :lib + \
  fs cp lib/hubtype.py lib/espnow_manager.py lib/eum_proto.py :lib/
```

**Remove `/main.py` from the hub while benching** (or never copy it yet).
Otherwise the full station boots first and holds BLE and the UART.

After all four pass, deploy the full tree (`../README.md` "Deploying") and
continue with `../HARDWARE_TEST.md` from step 2.
