# Bag2/AGENTS.md

Bag2 hardware is in classrooms.

## Wand hardware

From `Code/lib/hubtype.py`, `"wand"`: 25 LEDs (5×5) on GPIO 20, PN532 NFC @ I2C 0x24, buzzer GPIO 19,
vibration motor GPIO 21, button GPIO 0 (active low), accelerometer INT1 on GPIO 1, I2C SDA 22 /
SCL 23 @ 100 kHz, `uses_ble = False`.

## Coding station I2C

A PCA9546 mux @ 0x70 fans one I2C bus out to 4 PN532 readers that all share the fixed address 0x24 —
only one channel is active at a time. This is not an address conflict.

## Not every component uses the shared `HUB_CONFIG`

The paper remote and narrator modules run M5Stack UIFlow2 and never import `hubtype.py`
(`paper_remote` is not a valid `HUB_CONFIG` key); the speaker and dial stations have no
`hubtype.txt` at all.

This is expected for early proof-of-concept hardware. As a component's design matures, migrating it
onto the shared `hubtype.py` / `HUB_CONFIG` utilities is the intended direction.

## `ESPNowManager.poll()`

`poll(timeout_ms)` blocks inside a C call with no Python-level yield point. Call `poll()` with no
argument and pace the loop with `time.sleep_ms()`.
