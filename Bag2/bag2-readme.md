# Bag2 — Smart Playground Wand System

A multi-device NFC-driven playground system built on ESP32-C6 microcontrollers running MicroPython. Students program trigger→action rules by tapping NFC tags, play a color scavenger hunt game, and race against a live scoreboard.

## Folder Structure

```
Bag2/
├── Code/               Main application code for all devices
│   ├── lib/            Shared MicroPython drivers and helpers
│   ├── Wand Module/    Wand device — programming engine + Color Quest game
│   └── Stations/       Hub station (4-reader NFC) and scoreboard display
├── Documentation/      System-level documentation and diagrams
├── Unit Tests/         Hardware validation scripts for PCB bring-up
└── Utilities/          Standalone tools for NFC reading/writing and gesture training
```

## Hardware

All devices use **Seeed XIAO ESP32-C6** boards with MicroPython v1.27.0. The wand module includes a PN532 NFC reader, LIS2DW12 accelerometer, MAX17048 battery gauge, OPT3002 light sensor, 25-LED NeoPixel matrix, piezo buzzer, and vibration motor.

## Quick Start

1. Flash MicroPython onto each ESP32-C6
2. Copy the `lib/` folder to every microcontroller (see `Code/README.md` for details)
3. Copy the appropriate `main.py` to each device
4. Update `target.py` with the scoreboard's MAC address
5. Power on all devices — they communicate wirelessly via ESP-NOW
