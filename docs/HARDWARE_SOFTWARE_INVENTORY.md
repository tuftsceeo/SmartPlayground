# SmartPlayground Hardware and Software Inventory

Compiled 2026-11-05 from repository folders, READMEs, `AGENTS.md` files and `hubtype.py`. Not
checked against physical hardware.

Counting rules:

- One device is counted once, however many folders hold its code.
- One software tool is counted once, however many copies exist. `Live_Page/` holds publicly hosted
  copies for teachers; it does not add components.
- Battery tests and other measurement scripts are not counted.
- Where it is unclear whether two items are the same thing, they are listed together and marked
  **possibly the same**.

## Summary

| Stage | Hardware devices | Software components | Bench / development prototypes |
|---|---|---|---|
| Pre-Bag | 11 | 3 | (all pre-Bag items were prototypes) |
| Bag1 | 6 | 2 | 1 set of unit tests; 4 controller variants, 3 hardware revisions |
| Bag2 | 9 | 9 | 1 (PCB bring-up tests) |
| Bag3 | 6 | 5 | 11 |

---

## Pre-Bag (Feb – Summer 2025, `old_stuff/`)

This stage is the least organized in the repo. Dates come from folder names and READMEs.

### Hardware devices (11)

| # | Device | Source | Notes |
|---|---|---|---|
| 1 | Music Control Board | `old_stuff/Music_Control_Board/` | Feb 2025 pilot station. Displays and plays notes collected on a plushie. Hardware folder is a placeholder. |
| 2 | Obstacle Control Board | `old_stuff/Obstacle_Control_Board/` | Software only; hardware folder is a placeholder. |
| 3 | Splats / Splat button | `old_stuff/Splats/`, `old_stuff/More Summer 2025/Splat Related Code/` | Third-party BLE splat toy and a splat button. **Possibly the same device** in two folders. |
| 4 | Plushie (early) | `old_stuff/More Summer 2025/Other random code/` (`Plushie_connect.py`, `plushie_button.py`) | Precursor of the Bag1 Plushie module. |
| 5 | Big Buttons | `old_stuff/Big_Buttons/` | ESP32 + accelerometer. |
| 6 | ESP-based controller | `old_stuff/ESP_based_controller/` | ADXL345, encoder, servo, SSD1306 OLED. |
| 7 | IR controller + IR decoder | `old_stuff/IRController/`, `old_stuff/Summer 2025 Additions/IR Extensions/` | Summer 2025 adds Robot and Traffic Light variants. Counted as one IR pair. |
| 8 | Light extension (LED matrix / LED strip) | `old_stuff/LED lights/`, `old_stuff/Summer 2025 Additions/Light Extensions/` | **Possibly the same device** in two folders. |
| 9 | Movement extension (servo "Cactus") | `old_stuff/Summer 2025 Additions/Movement Extensions/` | |
| 10 | Splat Companion (Summer 2025) | `old_stuff/Summer 2025 Additions/Splat Companion/` | Ancestor of the Bag1–3 Splat Companions. |
| 11 | Dual-ESP UART hub | `old_stuff/old_dual_esp_uartESP_hub/` | Earlier form of the USB hub. |

Not counted as a device: **Control Panel** (`old_stuff/Control Panel/`,
`old_stuff/Summer 2025 Additions/Control Panel/`). It sends configuration to nearby ESP32s and
"fakes pairing" by proximity, which reads as a workaround for missing targeted pairing rather than
a component in its own right.

### Software components (3)

| # | Component | Source | Notes |
|---|---|---|---|
| 1 | Common device libraries | `old_stuff/Common/Software/` | CEEO `networking.py` ESP-NOW library, display/LED/sensor drivers, sound files. |
| 2 | App prototype | `old_stuff/App_Prototype/` | React/TSX demo plus implementation plan. |
| 3 | PyScript chat assistant | `old_stuff/example assistant from pyscript/` | **Possibly the same lineage** as `ChatApp/` (Bag2, software #8): same `RS232.py`/`main.py`/knowledge layout. |

---

## Bag1 (fielded, frozen, `Bag1/`)

Bag1 has one firmware (`Plushie_Module/`) with each module type selected in `config.py`. It uses
the `{'topic','value'}` ESP-NOW protocol, which later Bags don't understand.

### Hardware devices (6)

| # | Device | Notes |
|---|---|---|
| 1 | Plushie module | 12 LEDs, accelerometer, battery; PN532 NFC on some units. Ancestor of the Wand. |
| 2 | Box module | 25 LEDs, rigid case. |
| 3 | Button module | 12 LEDs. |
| 4 | Splats module | 3 LEDs, talks to a third-party BLE splat toy. |
| 5 | Controller (teacher) | 0 LEDs, SSD1306 OLED. Four hardware variants (see bench). |
| 6 | Splat Companion | Only CAD STLs (`Design Files/CAD Files/Splat Companion/`); its code is not located. **Possibly the same** as the Splats module (#4) running in a companion case. |

### Software components (2)

| # | Component | Source | Notes |
|---|---|---|---|
| 1 | Plushie firmware + game catalog | `Bag1/Plushie_Module/` | 15 game files: Now_sniffer, clap, color_press, color_press_mult, hibernate, hotcold, jump, nfc_sound, pattern_rainbow_btn, pattern_rainbow_plushie, rainbow, shake, shake_rainbow, sound, splat_notes. |
| 2 | WebApp (Smart Playground Control) + its hub firmware | `Live_Page/WebApp/` (`hubCode/`) | **Bag assignment uncertain.** It looks like Bag1-era because `hubCode` has `controller.py`/`utilities`, but the repo doesn't say. If it is Bag1, the hub that runs `hubCode` is a seventh device. |

### Bench / development

- 4 controller hardware variants: `controller.py`, `controller_sm.py`, `controller_sophie.py`, `controller_ws.py`.
- 3 hardware revisions recorded in `config.py`: Sophie's version (v1), second version (v2), box version (v3).
- `unit_tests/` (5 scripts) and `not_used/` (NFC, websocket and LED-matrix experiments).

---

## Bag2 (fielded, maintained, `Bag2/`)

All devices are Seeed XIAO ESP32-C6 boards unless noted.

### Hardware devices (9)

| # | Device | Source | Hardware |
|---|---|---|---|
| 1 | Wand module | `Code/Wand Module/` | 5×5 NeoPixel, PN532 NFC, LIS2DW12 accelerometer, MAX17048 battery gauge, OPT3002 light sensor, buzzer, vibration motor, button |
| 2 | Coding (Programming) Station | `Code/Stations/Programming Station/` | 4× PN532 behind a PCA9546 mux, 18 LEDs |
| 3 | Slide Score Station | `Code/Stations/Slide Score Station/` | 40-LED strip. CAD: `Design Files/CAD Files/Slide Loom/` |
| 4 | Splat Companion | `Code/Splat Companion/` | C6 + BLE to a stock splat toy. CAD in `Design Files/` |
| 5 | StickS3 Narrator | `Code/StickS3 Narrator/` | M5 StickS3, UIFlow2, WAV playback and LCD |
| 6 | M5Paper Remote | `Code/M5Paper Remote/` | M5Paper (ESP32-D0WDQ6), e-ink teacher remote |
| 7 | Speaker Station | `Code/Speaker/` | Headless, SD card, Freeze Dance music. Board not stated. |
| 8 | Dial Station (DialSpeaker) | `Code/DialSpeaker/` | M5 Dial, Freeze Dance music |
| 9 | USB hub ("Hub2") | `Live_Page/WebApp2/hubCode2/` | ESP32 bridging USB serial to ESP-NOW |

### Software components (9)

| # | Component | Source | Notes |
|---|---|---|---|
| 1 | Wand firmware | `Code/Wand Module/`, `Code/lib/` | 14 built-in games plus tap-coding. Shared `lib/` (14 modules) is part of this. |
| 2 | WebApp2 (Wand Remote) | `Live_Page/WebApp2/` | Teacher app over Web Serial. Its README says it serves Bag2 and Bag3. |
| 3 | Flasher | `Live_Page/Flasher/` | Uploads Wand, Hub and M5Paper Remote firmware. |
| 4 | Code_Upload | `Live_Page/Code_Upload/` | **Possibly overlaps** with the Flasher (#3). |
| 5 | If_Splats | `Live_Page/If_Splats/` | PyScript Splat programming page. |
| 6 | Wand icons page | `Live_Page/wand_icons.html` | One of the four game-tag consumers. |
| 7 | Student guide | `Live_Page/Wand Pages/student-guide.html` | |
| 8 | ChatApp (Wand Programmer) | `ChatApp/` | **Possibly the same lineage** as the pre-Bag PyScript chat assistant. |
| 9 | NFC card and gesture utilities | `Utilities/` | `writetoNFCcards.py`, `readfromNFCcards.py`, `gesture1.py`, `pretraintag.py`, `color_selection.py`, `Knowledgebase.py`. REPL tools. |

### Bench / development (1)

| # | Item | Source |
|---|---|---|
| 1 | PCB bring-up tests | `Unit Tests/` (`SideOne.py`, `SideTwo.py`) |

Not counted: `Battery Tests/` (measurement) and `Code/legacy/` plus the `legacy_jan26_*` Splat
files (superseded code). `Bag2/AGENTS.md` calls the Narrator, Paper Remote, Speaker and Dial
"early proof-of-concept", but they are listed above as Bag2 devices.

---

## Bag3 (in development, `Bag3/Code/`)

### Hardware devices (6)

| # | Device | Source | Hardware | Status |
|---|---|---|---|---|
| 1 | Wand module (Mock Wand) | `Wand Module/` | C6; Bag2 layout plus a power LED on GPIO2 and PN532 | Active; pulls games from the Box/Dial |
| 2 | Broadcast Box | `TeacherTools/BroadcastBox/` | M5 StickS3 + Grove RFID 2 (WS1850S) | Fielded prototype |
| 3 | Broadcast Dial | `TeacherTools/BroadcastDial/` | M5 Dial 2 (StampS3A) | Sibling port; Phase 0 pins open |
| 4 | Icon Display | `Stations/IconDisplay/` (Broadcast firmware) and `Stations/Icon Display Station/` (bring-up and icon pipeline) | XIAO C6 + 16×16 WS2812B panel | One device, two firmware folders. Beta. |
| 5 | Splat Companion | `Stations/SplatCompanion/` (`Companion/` + `ESPNowModem/`) | Two XIAO C6 + PN532 + MAX17048, BLE to stock Splats | Marked historical |
| 6 | M5Paper Remote | `TeacherTools/M5Paper Remote/` | M5Paper | **Possibly the same** as Bag2 device #6; its README says it targets Bag2 wands. |

### Software components (5)

| # | Component | Source | Notes |
|---|---|---|---|
| 1 | ChatBroadcast | `BroadcastCode/ChatBroadcast/`, hosted copy `Live_Page/ChatBroadcast/` | LLM game generation, sending games to the Box/Dial, card writing. Includes `iconmaker/` and the `sync_icons` / `sync_splat_actions` tools. |
| 2 | Wand Game Simulator | `Simulator/`, hosted copy `Live_Page/Simulator/` | Pyodide; runs unmodified wand games. |
| 3 | Icon display web app | `Stations/Icon Display Station/webapp/` (+ `gallery.html`, `icon_editor.py`) | Goes with the Icon Display (device #4). **Possibly the same tool** as ChatBroadcast's `iconmaker/`. |
| 4 | Deploy tool | `tools/deploy.py` | Developer-facing. |
| 5 | NFC card writer utility | `utilities/writetoNFCcards.py` | Bag3 version of the Bag2 REPL tool. |

Shared with Bag2: WebApp2, the Flasher and the USB hub. Per its README, WebApp2 serves both Bags;
these are counted under Bag2 only.

### Bench / development prototypes (11)

| # | Prototype | Source | Hardware |
|---|---|---|---|
| 1 | Opcode Wand (earlier Bag3 wand) | `Experiments/Opcode Wand/` | C6 wand. `AGENTS.md` calls this `Experiments/Wand Module`. |
| 2 | Emulated Tag Dial | `EmulatedTagDial/` and `Experiments/EmulatedTagDial/` | Broadcast Dial + NT3H2111 tag. Two folders, **possibly the same** prototype (READMEs differ). |
| 3 | ProgrammableTag | `Experiments/ProgrammableTag/` | C6 rewriting an NT3H2111 |
| 4 | ESP-NOW UART Modem (EUM) | `Experiments/EspnowModem/` | ESP32-S3 radio modem + host. The Splat Companion uses it. |
| 5 | Capsule PN5180 | `Experiments/Capsule PN5180/` | PN5180 NFC (library only) |
| 6 | CrowPanel5 Display | `Experiments/CrowPanel5_Display/` | Elecrow 5" ESP32-S3, LVGL |
| 7 | IPS096 Display | `Experiments/IPS096 Display/` | XIAO ESP32-S3 0.96" ST7789 |
| 8 | Music Board Station | `Experiments/Music Board Station/` | Revives the pre-Bag Music Control Board |
| 9 | Radar Station (+ its webapp) | `Experiments/Radar Station/` | C6 + HLK-LD2450 mmWave |
| 10 | Wireless file transfer | `Experiments/WirelessFileTransferBak/` | C6 receiver (backup of a transfer test) |
| 11 | NFC Station | `TeacherTools/NFC Station/` | M5 Dial 2 card writer; firmware never run on hardware |

Also development-only: `tools/devtests/` and `utilities/UnitTest/`.

---

## Open questions

1. Which Bag `Live_Page/WebApp` and its hub belong to (Bag1 or pre-Bag).
2. The Bag2 Speaker Station board.
3. Whether the Bag1 Splat Companion CAD belongs to the Splats module or to a separate device.
4. Whether `Code_Upload` is superseded by the Flasher.
5. Whether the Icon Display Station webapp and ChatBroadcast `iconmaker/` are one tool.
6. Which `EmulatedTagDial` folder is current.
