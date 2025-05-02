# ESP32C6 Xiao Button Module Hardware Documentation

## Overview

This document provides hardware specifications and wiring information for the ESP32C6 Xiao powered programmable button modules used in the Smart Playground project. These large wireless arcade-style buttons are designed to teach computational thinking to kindergarten students through interactive physical components.

## Hardware Components

### Main Controller

- **Microcontroller**: Seeed Studio XIAO ESP32C6
- **Processor**: ESP32-C6 32-bit RISC-V with WiFi and Bluetooth 5.0 LE
- **Operating System**: MicroPython 1.25
- **Flash Memory**: 4MB
- **RAM**: 512KB
- **Power Supply**: LiPo battery
- **Size**: 21mm × 17.5mm

### Peripheral Components

Each button module includes:
- 12-LED NeoPixel Ring
- LIS2DW12 3-axis accelerometer
- Tactile button (large arcade-style)
- Piezo buzzer
- Audio recording and playback circuit
- Battery connection

### Physical Specifications
- **Dimensions**: 3 inches (76.2mm) in diameter
- **Form Factor**: Large wireless arcade-style button
- **Construction**: Durable plastic housing with integrated electronics

## Pin Assignments

| Component | GPIO Pin | Description |
|-----------|----------|-------------|
| NeoPixel LED Ring | 20 | 12 addressable RGB LEDs in ring configuration |
| Tactile Button | 0 | Large arcade-style button with internal pull-up resistor |
| LIS2DW12 Accelerometer SCL | 23 | I²C clock line |
| LIS2DW12 Accelerometer SDA | 22 | I²C data line |
| Audio Recording Trigger | 21 | Same pin used for vibration motor in stuffie modules |
| Piezo Buzzer | 19 | Sound output (lower volume) |
| WiFi Enable | 3 | Controls WiFi power |
| Antenna Configuration | 14 | Selects internal/external antenna |

## Audio Recording/Playback Circuit

This button module features an integrated audio circuit for higher-quality sound:

- **Microphone**: Integrated MEMS microphone for recording
- **Speaker**: Built-in 8Ω, 0.5W speaker for louder playback
- **Recording Trigger**: Activated via GPIO21 (same pin used for vibration in stuffie modules)
- **Playback Trigger**: Activated by the tactile button press (GPIO0)
- **Recording Duration**: Up to 10 seconds
- **Integration Features**: 
  - Can record buzzer sounds for louder playback
  - Audio circuit operates semi-independently from main MCU
  - Recordings persist across power cycles

## Connections Summary

The ESP32C6 Xiao connects to the peripheral components as follows:

- **NeoPixel LED Ring**: Data pin to GPIO20, powered from 3.3V
- **Tactile Button**: Connected between GPIO0 and GND (uses internal pull-up)
- **LIS2DW12 Accelerometer**: 
  - SDA to GPIO22
  - SCL to GPIO23
  - Powered from 3.3V
- **Audio Recording Trigger**: Activated via GPIO21
- **Piezo Buzzer**: Connected between GPIO19 and GND
- **WiFi Control**: 
  - Enable pin on GPIO3
  - Antenna selection on GPIO14

## Hardware Specifications

### NeoPixel LED Ring

- **Type**: WS2812B RGB LEDs
- **Count**: 12 LEDs arranged in ring formation
- **Power**: 3.3V logic compatible
- **Data Rate**: 800 kHz bitstream
- **Current Draw**: ~60mA max (all LEDs on full brightness)

### LIS2DW12 3-Axis Accelerometer

- **Interface**: I²C
- **Address**: 0x19 (default)
- **Range**: Programmable (±2g/±4g/±8g/±16g)
- **Resolution**: 12/14/16-bit
- **Features**: Free-fall detection, tap detection, orientation detection
- **Power Consumption**: 0.5μA in low-power mode

### Tactile Button

- **Type**: Large arcade-style momentary push button
- **Configuration**: 
  - Connected to GPIO0 with internal pull-up resistor for ESP32C6 input
  - Directly wired to audio playback circuit for independent triggering
- **Functions**: 
  - Provides input to ESP32C6
  - Directly triggers audio playback without microcontroller intervention
  - Used for wake from sleep
  - Physical press triggers audio circuit independently from software control

### Piezo Buzzer

- **Type**: Piezoelectric buzzer
- **Frequency Range**: 100Hz - 10kHz
- **Control**: PWM via GPIO19
- **Power**: 3.3V compatible
- **Current Draw**: ~10mA average
- **Usage**: Lower volume sound effects, can be recorded by audio circuit for louder playback

### Audio Circuit

- **Microphone**: MEMS microphone
- **Speaker**: 8Ω, 0.5W
- **Recording Quality**: 8-bit, 8kHz sampling rate
- **Playback Volume**: ~70dB at 10cm
- **Current Draw**: ~100mA during playback

## Power Management

### Battery

- **Type**: LiPo battery (3.7V nominal)
- **Charging**: Through XIAO USB-C port when connected

### Power States

The module implements three power states:
1. **Active**: Full functionality, all sensors active
2. **Deep Sleep**: Enters after 10 minutes of inactivity, wake on button press only

## Physical Installation

The button module is designed as a standalone interactive device:

- The electronics are protected by a durable plastic housing
- The large button surface (3 inches diameter) allows for easy interaction
- The LED ring encircles the button for clear visual feedback
- The USB-C port for charging is accessible on the side of the housing
- The button directly triggers the audio playback circuit through hardware connection

Key physical design considerations:
- Large, high-contrast button surface for ease of use by young children
- Bright LED feedback visible in various lighting conditions
- Loud audio playback for group activities
