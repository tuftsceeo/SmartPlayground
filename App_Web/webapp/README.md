# Smart Playground Control - Web Application

A mobile-first web application for controlling smart playground modules via ESP32 hub using USB Serial communication.

**Team:** Smart Playground Project at Tufts CEEO  
**Funding:** NSF Award #2301249  
**Contributors:** J. Cross (front-end/backend), C. Rogers & M. Dahal (hub utilities)

## Overview

Browser-based control interface for ESP32 playground modules. Connects to ESP32-C6 hub via USB Serial (Web Serial API), which broadcasts commands to modules using ESP-NOW wireless protocol. Uses PyScript (Python in browser) for backend logic and vanilla JavaScript for UI.

## Core Features

- **USB Serial Connection**: Connect to ESP32-C6 hub using Web Serial API (Chrome/Edge only)
- **Command Broadcasting**: Send game commands to playground modules via chat-style interface
- **Optional Device Scanning**: PING modules to discover available devices (disabled by default)
- **Mobile-First Design**: Touch-optimized, responsive layout with PWA support
- **Firmware Upload**: Upload hub firmware directly from browser via REPL mode

## Architecture

### Hybrid Python-JavaScript Design

The app splits responsibilities between JavaScript and Python for optimal performance:

**JavaScript Layer** (`js/adapters/`): Handles browser API operations
- Web Serial/Bluetooth API access using native Promises
- Connection management, read/write operations
- Timeout handling and lock management
- Direct DOM interactions

**Python Layer** (`main.py`, `mpy/`): Contains all application logic
- REPL protocol and firmware upload orchestration  
- Command construction and message formatting
- Device state management and error recovery
- Data validation and JSON parsing

**Design Benefits:**
- JavaScript handles I/O naturally (native browser APIs)
- Python handles logic cleanly (90% of codebase)
- Clean separation of concerns (APIs vs business logic)
- Easy to test (mock JS adapters, test Python logic)

### Technology Stack

- **PyScript 2024.1.1**: Python runtime in browser
- **Web Serial API**: USB communication
- **Tailwind CSS**: Styling
- **Lucide Icons**: Icon library

### Key Components

```
webapp/
├── index.html              # Entry point
├── main.py                 # Python backend (PyScript)
├── js/
│   ├── main.js            # App initialization
│   ├── adapters/          # Native JS API wrappers
│   ├── components/        # UI components
│   └── state/store.js     # State management
└── mpy/
    ├── webSerial.py       # Serial wrapper (thin)
    └── webBluetooth.py    # BLE wrapper (thin)
```

## Hub Integration

### Command Format (JSON over Serial)

**Send to Hub:**
```json
{"cmd": "Rainbow", "rssi": "all"}
{"cmd": "PING", "rssi": "-60"}
```

**Receive from Hub:**
```json
{"type": "ack", "command": "Rainbow", "status": "sent"}
{"type": "devices", "list": [{"id": "Module_1", "rssi": -45}]}
```

### Available Commands

| Command | ID | Description |
|---------|-----|-------------|
| Notes   | 0   | Music/sound game |
| Shake   | 1   | Motion sensor game |
| Hot_cold | 2  | Temperature/proximity game |
| Jump    | 3   | Accelerometer game |
| Clap    | 4   | Audio detection game |
| Rainbow | 5   | LED light show |
| Off     | 6   | Deep sleep mode |

## Getting Started

### Prerequisites

1. Chrome or Edge browser (Web Serial API support required)
2. ESP32-C6 with `simple_hub` firmware
3. ESP32-C3 playground modules with game firmware
4. USB cable

### Running the App

```bash
# Start server
cd webapp
python -m http.server 8000

# Open browser
# http://localhost:8000

# Connect hub
# 1. Click "Connect USB Hub"
# 2. Select ESP32 from serial port picker
# 3. Send commands via chat interface
```

### Uploading Hub Firmware

1. Connect hub via USB Serial
2. Click "Upload Hub Setup" in message history
3. Browser enters REPL mode automatically
4. Files upload and hub reboots

**Note:** Hub must be in normal mode (not running main.py) or upload will automatically interrupt running code.

## Browser Compatibility

**Supported:**
- Chrome 89+
- Edge 89+
- Opera 75+

**Not Supported:**
- Safari (no Web Serial API)
- Firefox (no Web Serial API)
- Mobile browsers (Web Serial API not available)

**Workaround for tablets:** Use Chrome/Edge desktop mode with USB OTG adapter.

## Troubleshooting

### Connection Issues

**"Port in use"**
- Close Arduino IDE, Thonny, or other serial monitors
- Unplug/replug USB cable

**"Web Serial API not available"**
- Use Chrome or Edge on desktop
- Check browser version (89+)

**Connection drops**
- Check USB cable
- Verify hub is powered
- Look for errors in browser console

### Upload Issues

**Upload fails or freezes**
- Ensure hub is connected via serial
- Check browser console for errors
- Try unplugging/replugging hub

**No automatic reboot after upload**
- Should reboot automatically using `machine.reset()`
- If not, manually press reset button on hub

### Device Scanning (if enabled)

**No modules appear**
- Ensure modules are powered and running firmware
- Increase proximity slider range
- Verify ESP-NOW configuration

## Development

### Adding New Commands

1. Update `GAME_MAP` in hub firmware (`hubCode/main.py`)
2. Add to `js/utils/constants.js`
3. Implement game logic in module firmware

### State Management

Reactive state system in `js/state/store.js`:

```javascript
// Update state
setState({ hubConnected: true });

// Register for updates
onStateChange(() => this.render());

// Get computed values
const devices = getAvailableDevices();
```

### Python-JavaScript Bridge

Python functions exposed to JavaScript via `window` object:

```javascript
// Connect hub
await window.connect_hub_serial();

// Send command
await window.send_command_to_hub("Rainbow", "all");

// Upload firmware
await window.upload_firmware(files);
```

## Support

For issues:
1. Check browser console for errors
2. Verify hub firmware version
3. Review troubleshooting section
