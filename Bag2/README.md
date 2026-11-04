# Bag2 — Smart Playground Wand System

A multi-device NFC-driven playground system built on ESP32-C6 microcontrollers running MicroPython. Students program trigger→action rules by tapping NFC tags, play a color scavenger hunt game, and race against a live scoreboard.

The **Wand module** is the most numerous component (designed at roughly one per student). It is one
component among several: the **coding station**, **slide station**, **Splat Companion module**,
**narrator module**, **paper remote module**, **speaker station**, and **dial station** are separate
hardware that interface with wands. See [`Bag2/AGENTS.md`](AGENTS.md) for the full component list.

## Folder Structure

```
Bag2/
├── Code/               Main application code for all devices
│   ├── lib/                Shared MicroPython drivers and helpers
│   ├── Wand Module/        Wand module — programming engine + Color Quest game
│   ├── Stations/           Coding station (4-reader NFC) and slide station (scoreboard display)
│   ├── Splat Companion/    Bridge to a stock third-party splat toy
│   ├── StickS3 Narrator/   Narrator module (speaks game names, low-vision accessibility)
│   ├── M5Paper Remote/     Paper remote module (teacher e-ink remote)
│   ├── Speaker/            Speaker station (Freeze Dance music, headless)
│   └── DialSpeaker/        Dial station (Freeze Dance music, M5 Dial UI)
├── Documentation/      System-level documentation and diagrams
├── Unit Tests/         Hardware validation scripts for PCB bring-up
└── Utilities/          Standalone tools for NFC reading/writing and gesture training
```

## What each component does

- **Wand module**: 5×5 LED matrix, PN532 NFC reader, buzzer, vibration motor, accelerometer, button,
  battery gauge. Reads tap-coded NFC cards and plays 14 built-in games.
- **Coding station**: reads up to 4 NFC color tags at once and broadcasts the sequence to start a
  Color Quest round.
- **Slide station**: 40-LED strip mounted on a playground slide; displays scores as a bar graph
  (a mock-up use — the panel is meant for other, not-yet-designed wand games too).
- **Splat Companion module**: bridges ESP-NOW to a stock, unmodified third-party splat toy over BLE.
- **Narrator module**: listens on ESP-NOW and speaks the current game name aloud, with an on-screen
  label — built for low-vision accessibility.
- **Paper remote module**: e-ink teacher remote; broadcasts game commands directly to wands.
- **Speaker / dial stations**: Freeze Dance music playback, controlled over ESP-NOW.

## Hardware

All devices use **Seeed XIAO ESP32-C6** boards with MicroPython v1.27.0. The wand module includes a PN532 NFC reader, LIS2DW12 accelerometer, MAX17048 battery gauge, OPT3002 light sensor, 25-LED NeoPixel matrix, piezo buzzer, and vibration motor.

## Quick Start

1. Flash MicroPython onto each ESP32-C6
2. Copy the `lib/` folder to every microcontroller (see [`Code/README.md`](Code/README.md) for details)
3. Copy the appropriate `main.py` to each device
4. Update `target.py` with the scoreboard's MAC address
5. Power on all devices — they communicate wirelessly via ESP-NOW

See [`Bag2/AGENTS.md`](AGENTS.md) for hardware pin/address details, firmware conventions, and a
documentation trust map.
