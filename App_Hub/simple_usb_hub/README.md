# Simple Hub - USB Serial to ESP-NOW Bridge

## Overview

The Simple Hub is a single-processor ESP32-C6 hub that bridges the webapp (via USB Serial/WebUSB) to playground modules (via ESP-NOW). It's designed as a simpler, faster-to-implement alternative to the dual-processor Hub V2, suitable for development, testing, and classroom deployment.

## Features

- **WebUSB Serial Communication**: Connects to webapp via USB cable (Chrome/Edge browsers)
- **ESP-NOW Broadcasting**: Wireless communication to playground modules (2.4GHz)
- **External Antenna Support**: Dedicated antenna for improved ESP-NOW range
- **Two Operating Modes**:
  - **Transmit-only mode**: Broadcasts commands without device scanning (like headless controller)
  - **Full scanning mode**: Supports PING/response for device discovery
- **Minimal Complexity**: Reuses proven code patterns from headless_controller.py

## Hardware Requirements

- ESP32-C6 microcontroller
- External antenna (connected and enabled)
- USB cable for Serial communication with computer
- MicroPython firmware installed

## Software Dependencies

- MicroPython
- `utilities/now.py` - ESP-NOW wrapper class
- Python's `asyncio`, `json`, `sys`, `select`, `time` (built-in)

## Installation

1. **Flash MicroPython** to your ESP32-C6:
   ```bash
   esptool.py --chip esp32c6 --port /dev/ttyUSB0 erase_flash
   esptool.py --chip esp32c6 --port /dev/ttyUSB0 write_flash -z 0x0 micropython_esp32c6.bin
   ```

2. **Upload files** to the ESP32-C6:
   ```bash
   # Upload utilities folder
   ampy --port /dev/ttyUSB0 put utilities/

   # Upload main.py
   ampy --port /dev/ttyUSB0 put main.py
   ```

3. **Connect external antenna** (if not already connected)

4. **Reset the board** - hub will start automatically

## Usage

### Starting the Hub

The hub starts automatically on boot and runs `main.py`. You'll see:

```
Simple Hub initialized (scanning_mode=True)
Connecting ESP-NOW...
ESP-NOW connected. MAC: aa:bb:cc:dd:ee:ff
{"type":"ready","mode":"scanning","mac":"aa:bb:cc:dd:ee:ff"}
Hub running. Press Ctrl+C to stop.
Waiting for commands from webapp via Serial...
```

### Connecting from Webapp

1. Open the Smart Playground webapp in Chrome or Edge
2. Click "Connect Hub"
3. Select "USB Serial Hub" from the connection modal
4. Browser will prompt you to select a serial port
5. Choose the ESP32-C6 port (usually labeled "USB JTAG/Serial")
6. Connection established!

### Operating Modes

#### Transmit-Only Mode (Like Headless Controller)
```python
hub = SimpleHub(scanning_mode=False)
```
- Broadcasts commands to modules
- No device scanning or PING responses
- Lowest complexity, fastest startup
- Use for: Direct control, testing, demonstrations

#### Full Scanning Mode (Device Discovery)
```python
hub = SimpleHub(scanning_mode=True)
```
- Broadcasts commands AND handles PING responses
- Supports device discovery and RSSI filtering
- Required for webapp device list feature
- Use for: Interactive webapp control, classroom deployments

### Commands

The hub accepts JSON commands via USB Serial:

#### PING - Scan for Devices (scanning mode only)
```json
{"cmd": "PING", "rssi": "all"}
{"cmd": "PING", "rssi": -70}
```

#### Game Commands
```json
{"cmd": "Notes"}
{"cmd": "Shake"}
{"cmd": "Hot_cold"}
{"cmd": "Jump"}
{"cmd": "Rainbow"}
{"cmd": "Off"}
```

### Responses

The hub sends JSON responses via USB Serial:

#### Ready Message
```json
{"type": "ready", "mode": "scanning", "mac": "aa:bb:cc:dd:ee:ff"}
```

#### Acknowledgment
```json
{"type": "ack", "command": "Notes", "status": "sent"}
```

#### Device List (scanning mode only)
```json
{
  "type": "devices",
  "list": [
    {"id": "M-aabbcc", "mac": "aa:bb:cc:dd:ee:ff", "rssi": -45, "battery": 85, "type": "plushie"},
    {"id": "M-112233", "mac": "11:22:33:44:55:66", "rssi": -62, "battery": 72, "type": "plushie"}
  ]
}
```

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

| Webapp Command | Game Number | Module Game |
|---------------|-------------|-------------|
| Notes         | 0           | Music/Notes |
| Play          | 0           | Music/Notes |
| Shake         | 1           | Shake       |
| Hot_cold      | 2           | Hot/Cold    |
| Jump          | 3           | Jump        |
| Clap          | 4           | Clap        |
| Rainbow       | 5           | Rainbow     |
| Pause         | -1          | Stop        |
| Off           | -1          | Stop        |

## Code Structure

```
new_simple_hub/
├── main.py                 # Main hub implementation (SimpleHub class)
├── headless_controller.py  # Original controller (reference implementation)
├── utilities/
│   ├── now.py             # ESP-NOW wrapper (DO NOT MODIFY)
│   ├── wifi.py            # WiFi utilities
│   ├── utilities.py       # General utilities
│   └── base64.py          # Base64 encoding
└── README.md              # This file
```

## Troubleshooting

### Hub not appearing in browser's serial port list
- Check USB cable is connected
- Ensure browser is Chrome or Edge (Firefox doesn't support Web Serial API)
- Verify webapp is served over HTTPS or localhost
- Try unplugging and replugging the USB cable
- Check Device Manager (Windows) or `ls /dev/tty*` (Linux/Mac) to confirm port exists

### ESP-NOW not working
- Verify external antenna is connected (if `antenna=True`)
- Check modules are powered on and running
- Ensure modules are on same WiFi channel (channel 1)
- Check distance - ESP-NOW range is ~100m outdoors, less indoors

### Device scanning returns empty list
- Modules must implement `/deviceScan` response (see plan.md Phase 1)
- Check modules are responding to PING
- Verify `scanning_mode=True` in main.py
- Check RSSI threshold isn't too strict

### Serial communication issues
- Baud rate mismatch: Must be 115200
- Buffer overflow: Messages too long or sent too fast
- Check for proper line termination (`\n`)
- Use `sys.stdout.flush()` after printing

## Performance Notes

- **Startup time**: ~2 seconds
- **PING response time**: 5 second scan window
- **Command latency**: ~50ms Serial + ESP-NOW transmission
- **Max devices**: Limited by 5-second scan window (typically 50-100 devices)

## Browser Compatibility

| Browser | Web Serial Support | Status |
|---------|-------------------|--------|
| Chrome  | ✅ Yes            | Fully supported |
| Edge    | ✅ Yes            | Fully supported |
| Firefox | ❌ No             | Not supported |
| Safari  | ❌ No             | Not supported |

## Next Steps

Once the Simple Hub is working:

1. **Test with actual modules** - Verify full end-to-end communication
2. **Implement Phase 1** - Add device scan response to modules (see plan.md)
3. **Hub V2 Development** - Dual-processor architecture with concurrent BLE + ESP-NOW
4. **Production hardening** - Error recovery, reconnection handling, deployment guides

## References

- `/new_simple_hub/plan.md` - Full implementation plan
- `/new_simple_hub/headless_controller.py` - Reference controller implementation
- `/ESPNOW_PROTOCOL_V2.md` - ESP-NOW message format specification
- Web Serial API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Serial_API

## Support

For questions or issues:
1. Check this README troubleshooting section
2. Review plan.md for architecture details
3. Compare with headless_controller.py for reference implementation
4. Check ESP-NOW and Serial protocol specifications

