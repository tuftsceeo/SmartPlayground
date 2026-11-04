# Emulated Tag Dial

Firmware variant pulled from a Broadcast Dial on 2026-10-23. It drives an NXP NT3H2111
(MIKROE NFC Tag 2 Click) over I2C as an NDEF text tag that a wand reads like a card
(`nt3h2111.py`, `tag_emulator.py`), booted by `main.py` -> `etdial_server.py`.

These files are the ones on that Dial that were new or differed from `../BDialFirmware/`
at `fa2db5d`. Every other file on it (`boot.py`, `card_writer.py`, `code_sender.py`,
`dial_input.py`, `json_link.py`, `reset_log.py`, `station_fonts.py`, `stats_log.py`,
`text_entry.py`, `ws1850s.py`, `kb_rings.json`) matched `BDialFirmware/` byte for byte.
