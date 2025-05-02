# ESP32C6 Xiao Module Hardware Documentation

## Overview

This document provides hardware specifications and wiring information for the ESP32C6 Xiao powered
Plush Stuffed Animal modules used in the Smart Playground project. These modules are designed to teach computational thinking to kindergarten students through interactive physical components.

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

Each module includes:
- 12-LED NeoPixel Ring
- LIS2DW12 3-axis accelerometer
- Tactile button
- Vibration motor
- Piezo buzzer
- Battery connection

## Pin Assignments

| Component | GPIO Pin | Description |
|-----------|----------|-------------|
| NeoPixel LED Ring | 20 | 12 addressable RGB LEDs in ring configuration |
| Tactile Button | 0 | Button with internal pull-up resistor |
| LIS2DW12 Accelerometer SCL | 23 | I²C clock line |
| LIS2DW12 Accelerometer SDA | 22 | I²C data line |
| Vibration Motor | 21 | Haptic feedback actuator |
| Piezo Buzzer | 19 | Sound output |
| WiFi Enable | 3 | Controls WiFi power |
| Antenna Configuration | 14 | Selects internal/external antenna |

## Connections Summary

The ESP32C6 Xiao connects to the peripheral components as follows:

- **NeoPixel LED Ring**: Data pin to GPIO20, powered from 3.3V
- **Tactile Button**: Connected between GPIO0 and GND (uses internal pull-up)
- **LIS2DW12 Accelerometer**: 
  - SDA to GPIO22
  - SCL to GPIO23
  - Powered from 3.3V
- **Vibration Motor**: Connected between GPIO21 and GND
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

- **Type**: Momentary push button
- **Configuration**: Connected to GPIO0 with internal pull-up resistor
- **Functions**: Used for user input, wake from sleep, mode selection
- **Special Notes**: GPIO0 also affects boot mode when module is powered on or reset

### Vibration Motor

- **Type**: Eccentric Rotating Mass (ERM) vibration motor
- **Voltage**: 3.3V compatible
- **Current Draw**: ~100mA at full power
- **Control**: Digital on/off via GPIO21

### Piezo Buzzer

- **Type**: Piezoelectric buzzer
- **Frequency Range**: 100Hz - 10kHz
- **Control**: PWM via GPIO19
- **Power**: 3.3V compatible
- **Current Draw**: ~10mA average

## Power Management

### Battery

- **Type**: LiPo battery (3.7V nominal)
- **Capacity**: ~400-600mAh recommended
- **Charging**: Through XIAO USB-C port when connected

### Power States

The module implements three power states:
1. **Active**: Full functionality, all sensors active
2. **Deep Sleep**: Enters after 10 minutes of inactivity, wake on button press only

## Physical Installation

The module is designed to be integrated into a stuffed animal keychain:

- The electronics are protected by a 3D printed casing inside the stuffed animal's body
- The LED ring faces outward from the stuffed animal's body
- The tactile button is located in the middle of the LED ring for easy access
- The USB-C port for charging the module is located in the animal's head

Key physical design considerations:
- Ensures visibility of the LED ring for clear visual feedback
- Provides easy access to the button for kindergarten users
- Protects the electronics from impacts through the 3D printed casing
- Allows for charging through the accessible USB-C port
