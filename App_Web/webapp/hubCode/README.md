# Simple Hub - USB Serial to ESP-NOW Bridge

## Overview

The Simple Hub is a single-processor ESP32 hub that bridges the webapp (via USB Serial/WebUSB) to playground modules (via ESP-NOW). It's designed as a streamlined, transmit-only hub suitable for development, testing, and classroom deployment.

## Features

- **WebUSB Serial Communication**: Connects to webapp via USB cable (Chrome/Edge browsers)
- **ESP-NOW Broadcasting**: Wireless command transmission to playground modules (2.4GHz)
- **External Antenna Support**: Optional external antenna for improved ESP-NOW range (C6)
- **Multi-Board Support**: Works with ESP32-C6 or ESP32-C3
- **Optional Display**: SSD1306 OLED display for debug messages and status
- **11 Games + Control Commands**: Full game suite synchronized with plushie modules
- **Minimal Complexity**: Transmit-only design, inherits from proven Control class

## Hardware Requirements

- **ESP32-C6** (recommended) or **ESP32-C3** microcontroller
- External antenna (optional but recommended for C6)
- USB cable for Serial communication with computer
- MicroPython firmware installed
- SSD1306 OLED display (optional, 128x64, I2C)

## Software Dependencies

- MicroPython
- `controller.py` - Control class with ESP-NOW methods
- `utilities/now.py` - ESP-NOW wrapper class
- `ssd1306.py` - Display driver (optional, only if using display)
- Python's `asyncio`, `json`, `sys`, `select`, `time` (built-in)

## Installation

### Option 1: Upload via Web App (Recommended)

1. Open the Smart Playground webapp in Chrome/Edge
2. Connect your ESP32 via USB
3. Click "Upload Hub Setup" from the message input
4. Browser automatically uploads all required files via REPL
5. Hub reboots and is ready to use

### Option 2: Manual Upload via Command Line

1. **Flash MicroPython** to your ESP32:
   ```bash
   # For ESP32-C6
   esptool.py --chip esp32c6 --port /dev/ttyUSB0 erase_flash
   esptool.py --chip esp32c6 --port /dev/ttyUSB0 write_flash -z 0x0 micropython_esp32c6.bin
   
   # For ESP32-C3
   esptool.py --chip esp32c3 --port /dev/ttyUSB0 erase_flash
   esptool.py --chip esp32c3 --port /dev/ttyUSB0 write_flash -z 0x0 micropython_esp32c3.bin
   ```

2. **Upload files** to the ESP32:
   ```bash
   # Upload all required files
   ampy --port /dev/ttyUSB0 put utilities/
   ampy --port /dev/ttyUSB0 put controller.py
   ampy --port /dev/ttyUSB0 put main.py
   
   # Optional: Upload display driver if using OLED
   ampy --port /dev/ttyUSB0 put ssd1306.py
   ```

3. **Configure antenna** (C6 only):
   - Edit `main.py` line 200: Set `antenna_enabled = True` for external antenna
   - Set `antenna_enabled = False` to use internal antenna

4. **Configure display** (optional):
   - Edit `main.py` lines 122-123: Uncomment appropriate I2C config for your board
   - C6 uses I2C on pins 23 (SCL), 22 (SDA)
   - C3 uses SoftI2C on pins 7 (SCL), 6 (SDA)

5. **Reset the board** - hub will start automatically

## Usage

### Starting the Hub

The hub starts automatically on boot and runs `main.py`. Debug output appears on stderr and optional display:

**Serial output (JSON only):**
```json
{"type":"ready","mac":"aa:bb:cc:dd:ee:ff"}
```

**Display/stderr debug messages:**
```
Hub Init
Connecting
MAC:dd:ee:ff
NOW Ready
Running
Wait CMD
```

### Connecting from Webapp

1. Open the Smart Playground webapp in Chrome or Edge
2. Click "Connect USB Hub" button
3. Browser prompts you to select a serial port
4. Choose the ESP32 port (usually labeled "USB JTAG/Serial" or similar)
5. Connection established! Hub sends ready message
6. Start sending game commands via the chat interface

### Operating Mode

The hub operates in **transmit-only mode**:
- Broadcasts game commands to all modules via ESP-NOW
- No device scanning or PING responses
- Simple, reliable operation
- Optimized for classroom use and demonstrations
- Uses Control class from `controller.py` for ESP-NOW communication

### Optional Display (SSD1306 OLED)

The hub supports an optional 128x64 I2C OLED display for debugging and status:

**Display shows (rolling 6-line buffer):**
- `Hub Init` - Initialization started
- `Connecting` - Setting up ESP-NOW
- `MAC:dd:ee:ff` - Last 3 bytes of MAC address
- `NOW Ready` - ESP-NOW connected
- `Running` / `Wait CMD` - Ready for commands
- `Gm:GameName` - Broadcasting game command
- `Unk:Command` - Unknown command received

**Benefits:**
- Debug without computer/Serial monitor
- Status at-a-glance in classroom
- Helps identify connection issues
- Shows which commands are being sent

**Note:** Display is completely optional. Hub works fine without it.

### Commands

The hub accepts JSON commands via USB Serial. Each command is a single-line JSON object ending with `\n`.

#### Game Commands (0-10)

```json
{"cmd": "Notes"}
{"cmd": "Shake"}
{"cmd": "Hot_cold"}
{"cmd": "Jump"}
{"cmd": "Clap"}
{"cmd": "Rainbow"}
{"cmd": "Hibernate"}
{"cmd": "Pattern_btn"}
{"cmd": "Pattern_plush"}
{"cmd": "Color_Press"}
{"cmd": "Color_Press_Mult"}
```

#### Control Commands

```json
{"cmd": "Stop"}
{"cmd": "Pause"}
{"cmd": "Off"}
```

**Note:** `"Off"` is an alias for `"Hibernate"` (shows warning, then sleeps). `"Stop"` and `"Pause"` stop the current game and return modules to idle mode.

### Responses

The hub sends JSON responses via USB Serial (stdout). Each response is a single-line JSON object ending with `\n`.

#### Ready Message
Sent when hub initializes:
```json
{"type": "ready", "mac": "aa:bb:cc:dd:ee:ff"}
```

#### Command Acknowledgment
Sent after successfully broadcasting a game command:
```json
{"type": "ack", "command": "Notes", "status": "sent"}
```

**Note:** Debug messages (like "Hub Init", "Connecting", etc.) are sent to stderr and do not appear on the Serial JSON stream.

## Protocol

### Serial Protocol (Hub ↔ Webapp)
- Format: Line-delimited JSON
- Baud rate: 115200
- Each message ends with `\n`
- Commands: Webapp → Hub
- Responses: Hub → Webapp

### ESP-NOW Protocol (Hub ↔ Modules)
- Format: JSON with topic/value structure
- Channel: 1 (2.4GHz)
- Broadcast MAC: `ff:ff:ff:ff:ff:ff`

Example ESP-NOW messages:
```json
{"topic": "/ping", "value": 1}
{"topic": "/game", "value": 0}
{"topic": "/game", "value": -1}
{"topic": "/notify", "value": 1}
```

## Game Mapping

Commands are mapped to game numbers that match the plushie module's game list. This mapping is synchronized with `Plushie_Module/config.py`.

| Webapp Command    | Game Number | Module Game                    | Description                                      |
|-------------------|-------------|--------------------------------|--------------------------------------------------|
| Notes             | 0           | Musical Notes                  | Each plushie plays a different note              |
| Shake             | 1           | Shake Counter                  | Lights fill up as you shake harder               |
| Hot_cold          | 2           | Proximity Finding              | Find hidden module (red = far, fewer = close)    |
| Jump              | 3           | Jump Counter                   | Count jumps with LED lights                      |
| Clap              | 4           | Range Test                     | Buzz to show which modules hear the hub          |
| Rainbow           | 5           | Battery + Celebration          | Show battery level, then rainbow animation       |
| Hibernate (Off)   | 6           | Sleep Mode                     | Red warning flash, then deep sleep               |
| Pattern_btn       | 7           | Button Pattern Match           | Copy button light patterns                       |
| Pattern_plush     | 8           | Plushie Pattern Match          | Copy plushie movement patterns                   |
| Color_Press       | 9           | Single Color Selection         | Cycle and choose a color                         |
| Color_Press_Mult  | 10          | Multi-Color Stacking           | Build up layers of colors                        |
| Stop (Pause)      | -1          | Stop Current Game              | Return to idle mode                              |

**Command Aliases:**
- `"Off"` → Hibernate (game 6)
- `"Pause"` → Stop (game -1)
- `"Stop"` → Stop (game -1)

## Code Structure

```
hubCode/
├── main.py                 # Main hub implementation (SimpleHub class)
├── controller.py           # Control base class with ESP-NOW methods
├── ssd1306.py             # OLED display driver (optional)
├── manifest.js            # File manifest for web upload
├── utilities/
│   ├── now.py             # ESP-NOW wrapper
│   ├── wifi.py            # WiFi utilities
│   ├── lights.py          # LED/NeoPixel control
│   ├── colors.py          # Color definitions
│   ├── utilities.py       # General utilities
│   ├── i2c_bus.py         # I2C bus management
│   ├── lc709203f.py       # Battery gauge (LC709203F)
│   ├── max17048.py        # Battery gauge (MAX17048)
│   └── secrets.py         # WiFi credentials (not tracked in git)
└── README.md              # This file
```

### Key Classes

**`SimpleHub`** (in `main.py`):
- Inherits from `Control` class
- Manages Serial ↔ ESP-NOW bridge
- Handles command parsing and acknowledgments
- Optional display integration

**`SerialBridge`** (in `main.py`):
- Non-blocking Serial I/O using `select`
- JSON message parsing
- Command callback system

**`HubDisplay`** (in `main.py`):
- Rolling debug message display on SSD1306 OLED
- Configurable for C6 or C3 I2C pins
- Graceful degradation if display unavailable

**`Control`** (in `controller.py`):
- Base class providing ESP-NOW functionality
- `connect()` - Initialize ESP-NOW with antenna config
- `choose(game_num)` - Broadcast game command
- Used by both hub and headless controller

## Troubleshooting

### Hub not appearing in browser's serial port list
- **Check USB cable** is properly connected
- **Ensure browser is Chrome or Edge** (Firefox/Safari don't support Web Serial API)
- **Verify webapp is served over HTTPS or localhost** (required for Web Serial API)
- **Try unplugging and replugging** the USB cable
- **Check device is recognized** by OS:
  - Windows: Device Manager → Ports (COM & LPT)
  - Mac: `ls /dev/tty.*` or `ls /dev/cu.*`
  - Linux: `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`

### Hub connects but modules don't respond
- **Verify external antenna** is connected if enabled (C6 with `antenna_enabled=True`)
- **Check modules are powered on** and running game firmware
- **Ensure modules use ESP-NOW** on channel 1
- **Check distance** - ESP-NOW range varies:
  - With external antenna: ~100-200m outdoors, 30-50m indoors
  - Internal antenna: ~50m outdoors, 10-20m indoors
- **Try the Clap command** to test which modules can hear the hub

### Display not working
- **Verify I2C pins** match your board:
  - C6: SCL=23, SDA=22 (hardware I2C)
  - C3: SCL=7, SDA=6 (SoftI2C)
- **Check display connection** (VCC, GND, SCL, SDA)
- **Verify display address** is 0x3C (default for most SSD1306 displays)
- Hub will work fine without display - it's optional

### Commands not acknowledged
- **Check JSON format** - must be valid JSON with `"cmd"` field
- **Ensure line termination** - each command must end with `\n`
- **Watch browser console** for errors
- **Unknown commands** will show on display/stderr as "Unk:..."

### Upload via webapp fails
- **Ensure hub is connected** via USB Serial (not running)
- **Check browser console** for REPL errors
- **Try manual reset** before upload
- **Verify files in manifest.js** match actual files to upload

## Performance Notes

- **Startup time**: ~2 seconds (ESP-NOW initialization)
- **Command latency**: ~10-50ms (Serial receive + ESP-NOW broadcast)
- **Broadcast range**: 
  - External antenna (C6): 100-200m outdoors, 30-50m indoors
  - Internal antenna: 50m outdoors, 10-20m indoors
- **Module support**: Unlimited (broadcast to all modules in range)
- **Command throughput**: Can handle rapid commands (10ms loop interval)

## Browser Compatibility

| Browser | Web Serial Support | Status |
|---------|-------------------|--------|
| Chrome  | ✅ Yes            | Fully supported |
| Edge    | ✅ Yes            | Fully supported |
| Firefox | ❌ No             | Not supported |
| Safari  | ❌ No             | Not supported |

## Development & Testing

### Testing Game Commands

1. **Connect hub via webapp** (Chrome/Edge, localhost or HTTPS)
2. **Send test commands** via chat interface:
   - Try each game command to verify ESP-NOW broadcast
   - Use "Clap" to test which modules are in range
   - Use "Rainbow" to check battery levels
3. **Monitor display** (if connected) for debug messages
4. **Check acknowledgments** in webapp to confirm command receipt

### Adding New Games

To add a new game to the system:

1. **Update plushie firmware** (`Plushie_Module/config.py`):
   - Add game to `games` list
   - Implement game logic in module

2. **Update hub firmware** (`hubCode/main.py`):
   - Add command to `GAME_MAP` dictionary
   - Use next available game number (11, 12, etc.)

3. **Update webapp** (`webapp/js/utils/commands.json`):
   - Add command with label, description, color, icon
   - Command will appear in webapp UI automatically

4. **Keep synchronized**: All three files must have matching game numbers!

### Hardware Configuration

**For ESP32-C6:**
```python
# main.py line 122 - Use hardware I2C
i2c = I2C(scl=Pin(23), sda=Pin(22))

# main.py line 200 - Enable external antenna
antenna_enabled = True
```

**For ESP32-C3:**
```python
# main.py line 123 - Use SoftI2C
i2c = SoftI2C(scl=Pin(7), sda=Pin(6))

# main.py line 200 - Internal antenna only
antenna_enabled = False
```

## References

- **Webapp README**: `../README.md` - Full web application documentation
- **Plushie Module**: `../../Plushie_Module/` - Module firmware and game implementations
- **Commands**: `../js/utils/commands.json` - Complete game command reference
- **Controller Base**: `controller.py` - ESP-NOW communication class
- **Web Serial API**: https://developer.mozilla.org/en-US/docs/Web/API/Web_Serial_API

## Support

For questions or issues:

1. **Check troubleshooting** section above
2. **Review webapp README** for connection issues
3. **Test with Clap command** to verify ESP-NOW range
4. **Check browser console** for Serial/JavaScript errors
5. **Monitor display/stderr** for hub-side errors

---

**Last Updated**: January 2026  
**Synchronized with**: Plushie_Module games 0-10, webapp commands.json

