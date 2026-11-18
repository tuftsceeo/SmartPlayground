# SplatTagWriter

A bench tool that labels Splat NFC stickers. It runs on Bag3 wand hardware: a XIAO ESP32-C6 with a
PN532 at I2C 0x24, the 5x5 LED matrix and the buzzer.

The wand listens for nearby Splats over BLE and picks the closest one. It then writes
`splat-<MAC>` as NDEF text onto the sticker you hold against it, which is the format the wand's
`parse_splat_card()` reads. It never connects to or pairs with a Splat; it only reads their
advertisements.

It is not a classroom tool and is not installed on wands. While you are labelling, it replaces the
wand's `/main.py`.

## Load

The wand must already have the normal Bag3 `/lib`: `pn532.py`, `nfc_reader.py`, `hubtype.py`,
`leds.py` and `buzzer.py`. Run these from the repo root.

1. Back up the wand's own `/main.py` (the one-line `import wand_main`):

    ```bash
    python3 -m mpremote connect $PORT resume fs cp :/main.py :/main_wand.py
    ```

2. Reset, then copy the labeller straight away. Copying into the running program can fail with
   "could not enter raw repl"; if it does, reset and copy again.

    ```bash
    python3 -m mpremote connect $PORT reset
    ```

    ```bash
    python3 -m mpremote connect $PORT resume fs cp Bag3/Code/TeacherTools/SplatTagWriter/main.py :/main.py
    ```

3. Reset to start it, and watch the log if you want it:

    ```bash
    python3 -m mpremote connect $PORT reset
    ```

    ```bash
    python3 Bag3/Code/tools/serial_monitor.py $PORT 1800 > labeller.log
    ```

**Restore the wand when you are done:**

```bash
python3 -m mpremote connect $PORT resume fs cp :/main_wand.py :/main.py
```

## Use

Turn on one Splat near the wand, keeping other Splats further away. Then follow the lights:

| Display | Meaning |
|---|---|
| Amber star | No Splat heard |
| LEDs off | Splats heard, but none is close enough (-65 dBm) or 10 dB ahead of the next |
| Blue star + beep | A Splat was picked. Hold its sticker on the wand (20 s) |
| Short tick | Sticker seen |
| Green check + two beeps | Written, read back and matched |
| Red X + low beep | Failed. The log says why |

Each display has exactly one meaning. A Splat that is already labelled can be written again.

## How it works

- **BLE scan:** listens for 1.5 s at 30 % duty, then pauses 1 s. The IRQ only checks for "Splat" in
  the advertisement.
- **Tag detection:** uses the Broadcast Dial's timing: an 80 ms detect, with tries 2 ms apart.
  RFConfiguration item 5 limits the PN532 to one passive-activation try per poll. A tag must be seen
  on two polls in a row.
- **Tag buffer:** after every result, pass or fail, the PN532 is aborted with an ACK frame, its
  stale answers are read off, and the tag is released (InRelease).
- **Writing:**
  - MIFARE Classic 1K (the Splat stickers): NDEF goes in from block 4, skipping sector trailers.
    The tool re-selects and authenticates before each block, using the keys in `COMMON_KEYS`.
  - NTAG: written from page 4.
- **What it overwrites:** only blank stickers, or ones holding `sp:...` or `splat-...` text. Any
  other text is refused.
- **Checking a write:** the text is read back and compared in lowercase, because
  `read_ndef_text()` lowercases what it reads.

**Caution:** a sticker that already holds a different Splat's tag is overwritten with the Splat
that BLE picked. Keep only one Splat close to the wand.

2026-11-17: 10 Splats were labelled with this tool.
