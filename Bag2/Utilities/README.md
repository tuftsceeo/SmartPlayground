# Utilities

Standalone tools for NFC tag management and gesture training. These are interactive REPL-based scripts meant to be run during development and content setup — not during normal gameplay.

## Scripts

### readfromNFCcards.py

Full-featured NFC tag reader and inspector. Detects a tag, identifies its type (MIFARE Classic, NTAG/Ultralight), and dumps all readable data blocks with hex and ASCII views. Automatically decodes NDEF text and URI records. Also includes a UID-only mode for quickly cataloging tags without reading block data. Contains its own inline PN532 driver — no `lib/` dependency.

### writetoNFCcards.py

Interactive NFC tag writer with LED animations and buzzer feedback. Type a text string at the REPL prompt, place a tag on the reader, and press the button to write an NDEF text record. Supports both MIFARE Classic (block writes to sectors 1+) and NTAG/Ultralight (page writes starting at page 4). Includes write verification and progress display on the 25-LED NeoPixel matrix. Contains its own inline PN532 driver — no `lib/` dependency.

### gesture1.py

Sandbox for developing and testing gesture recognition without NFC tags. Provides an interactive REPL menu to record gesture samples (with 3-2-1 countdown and LED feedback), view extracted feature vectors, compare centroids across gestures, and run live classification. Useful for tuning thresholds and understanding which features distinguish different gestures. Contains its own inline accelerometer driver — no `lib/` dependency.

### pretraintag.py

Gesture trainer and NFC tag writer. The complete workflow for creating gesture NFC tags: train a gesture by recording multiple samples, compute a centroid feature vector, then write the template data directly to a MIFARE Classic tag. The written tag can then be used with the wand module's gesture engine in production. Also supports reading gesture tags back to verify their contents, and a live test mode that loads gestures from tags and runs real-time recognition. **Requires `/lib/pn532.py` and `/lib/gesture_engine.py`.**

## Usage

Copy the desired script to the device and run it from the REPL. Most scripts are fully self-contained (no `lib/` needed), except `pretraintag.py` which imports from `lib/`. All scripts use the same pin assignments as the wand module (SDA=22, SCL=23, NeoPixel=20, Buzzer=19, Button=0).
