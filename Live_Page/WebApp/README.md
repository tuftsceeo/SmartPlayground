# Smart Playground Control - Web Application

A mobile-first web application for controlling smart playground modules via ESP32 hub using USB Serial communication.

**Team:** Smart Playground Project at Tufts CEEO  
**Funding:** NSF Award #2301249  
**Contributors:** J. Cross (front-end/backend), C. Rogers & M. Dahal (hub utilities)

## Overview

Browser-based control interface for ESP32 playground modules. Connects to ESP32 hub (C6 or C3) via USB Serial (Web Serial API), which broadcasts commands to modules using ESP-NOW wireless protocol. Uses PyScript (Python in browser) for backend logic and vanilla JavaScript for UI.

## Core Features

- **USB Serial Connection**: Connect to ESP32 hub using Web Serial API (Chrome/Edge only)
- **11 Interactive Games**: Full suite of games including music, motion, patterns, and colors
- **Command Broadcasting**: Send game commands to playground modules via chat-style interface
- **Mobile-First Design**: Touch-optimized, responsive layout with PWA support
- **Firmware Upload**: Upload hub firmware directly from browser via REPL mode
- **Real-time Feedback**: Acknowledgment messages confirm command transmission

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
├── index.html              # Entry point, loads PyScript
├── main.py                 # Python backend (PyScript)
├── js/
│   ├── main.js            # App initialization
│   ├── adapters/          # Browser API wrappers
│   │   ├── serialAdapter.js      # Web Serial (native JS)
│   │   └── bluetoothAdapter.js   # Web Bluetooth (future)
│   ├── components/        # UI components (vanilla JS)
│   ├── state/store.js     # Reactive state management
│   └── utils/commands.json # Game definitions
├── mpy/                    # Python modules
│   ├── hub_serial.py      # Serial communication logic
│   ├── firmware_manager.py # Upload orchestration
│   └── repl_controller.py # REPL protocol
└── hubCode/               # ESP32 hub firmware files
    ├── main.py            # Hub implementation
    └── utilities/         # Hub dependencies
```

## Games & Activities

The app supports 11 interactive games designed for physical play with smart plushies, buttons, and other modules:

### Music & Motion (0-3)
- **Notes**: Each module plays a different musical note
- **Shake**: Motion counter with LED feedback
- **Hot_cold**: Hide-and-seek proximity game
- **Jump**: Jump counter with LED tracking

### Testing & Fun (4-6)
- **Clap**: Range test - buzzes modules in range
- **Rainbow**: Battery check + synchronized light show
- **Hibernate**: Energy-saving sleep mode

### Pattern & Color Games (7-10)
- **Pattern_btn**: Memory game with button patterns
- **Pattern_plush**: Follow-along with plushie patterns
- **Color_Press**: Choose your favorite color
- **Color_Press_Mult**: Build colorful light layers

### Control
- **Stop**: Return to idle mode

All games are designed to be accessible, engaging, and encourage physical activity and social interaction.

## Hub Integration

### Command Format (JSON over Serial)

**Send to Hub:**
```json
{"cmd": "Rainbow"}
{"cmd": "Notes"}
{"cmd": "Pattern_btn"}
```

**Receive from Hub:**
```json
{"type": "ready", "mac": "aa:bb:cc:dd:ee:ff"}
{"type": "ack", "command": "Rainbow", "status": "sent"}
```

### Available Commands

| Command           | ID  | Description |
|-------------------|-----|-------------|
| Notes             | 0   | Musical notes - each plushie plays a different note |
| Shake             | 1   | Shake counter - lights fill up with motion |
| Hot_cold          | 2   | Proximity finding game (hot and cold) |
| Jump              | 3   | Jump counter with LED tracking |
| Clap              | 4   | Range test - buzz to show connectivity |
| Rainbow           | 5   | Battery check + rainbow celebration |
| Hibernate (Off)   | 6   | Sleep mode with button warning |
| Pattern_btn       | 7   | Button pattern matching game |
| Pattern_plush     | 8   | Plushie pattern matching game |
| Color_Press       | 9   | Single color selection |
| Color_Press_Mult  | 10  | Multi-color stacking |
| Stop (Pause)      | -1  | Stop current game, return to idle |

**Command Aliases:**
- `Off` → Hibernate (game 6)
- `Pause` → Stop (game -1)
- `Stop` → Stop (game -1)

For detailed game descriptions, see [`js/utils/commands.json`](js/utils/commands.json).

## Getting Started

### Prerequisites

1. **Chrome or Edge browser** (Web Serial API support required)
2. **ESP32-C6 or ESP32-C3** with hub firmware (see [`hubCode/`](hubCode/))
3. **ESP32-C3 playground modules** (plushies, buttons, splats) with game firmware
4. **USB cable** for hub connection

### Running the App

**Option 1: Use Live Demo (Main Branch)**

Visit [https://tuftsceeo.github.io/SmartPlayground/](https://tuftsceeo.github.io/SmartPlayground/) - automatically deployed from main branch.

**Option 2: Run Locally (Development)**

```bash
# Navigate to webapp directory
cd webapp

# Start local server
python3 -m http.server 8000

# Open in browser
# http://localhost:8000
```

**Connecting & Using:**

1. Click "Connect USB Hub" button
2. Select your ESP32 from the serial port picker
3. Wait for "Hub connected!" confirmation
4. Select a game command from the list or type in chat
5. Send command - modules will respond
6. Watch for acknowledgment message

### Uploading Hub Firmware

1. Connect hub via USB Serial
2. Click "Upload Hub Setup" button in message input area
3. Browser enters REPL mode automatically
4. Files upload sequentially (progress shown in UI)
5. Hub reboots and is ready to use

**Note:** Upload automatically interrupts running code if needed.

### Testing Games

After connecting the hub:

1. **Test connectivity**: Send "Clap" command - modules in range will buzz
2. **Check batteries**: Send "Rainbow" - modules show battery level then animate
3. **Try games**: Select any game from the command list
4. **Stop games**: Use "Stop" to return modules to idle mode
5. **Put to sleep**: Use "Hibernate" when done (saves battery)

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

### Module Communication

**Modules not responding to commands**
- Ensure modules are powered on and running game firmware
- Check hub's ESP-NOW range (use "Clap" command to test)
- Verify modules are within range:
  - External antenna (C6): 100-200m outdoors, 30-50m indoors
  - Internal antenna: 50m outdoors, 10-20m indoors
- Check browser console for acknowledgment messages

## Development

### Adding New Commands

To add a new game to the system, you need to update three places:

1. **Plushie Module Firmware** (`Plushie_Module/config.py`):
   - Add game to `games` list with next available index
   - Implement game logic in module firmware

2. **Hub Firmware** (`hubCode/main.py`):
   - Add command to `GAME_MAP` dictionary
   - Map webapp command name to game number

3. **Webapp Commands** (`js/utils/commands.json`):
   - Add command with id, label, description, color, and icon
   - Command automatically appears in UI

**Important:** Keep game numbers synchronized across all three files!

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

// Send command (broadcasts to all modules)
await window.send_command_to_hub("Rainbow");

// Upload hub firmware
await window.upload_firmware(files);

// Disconnect
await window.disconnect_hub();
```

## Project Structure

```
webapp/
├── index.html                    # Main entry point
├── main.py                       # PyScript backend logic
├── pyscript.toml                 # PyScript configuration
├── manifest.json                 # PWA manifest
├── hubCode/                      # ESP32 hub firmware
│   ├── main.py                   # Hub implementation
│   ├── controller.py             # ESP-NOW control class
│   ├── manifest.js               # Upload file list
│   └── utilities/                # Hub utility modules
├── js/
│   ├── main.js                   # App initialization
│   ├── adapters/                 # Browser API wrappers
│   │   ├── serialAdapter.js      # Web Serial API
│   │   └── bluetoothAdapter.js   # Web Bluetooth API (future)
│   ├── components/               # UI components
│   │   ├── connection/           # Connection UI
│   │   ├── messaging/            # Chat interface
│   │   ├── modals/               # Dialog boxes
│   │   ├── overlays/             # Settings & info
│   │   └── states/               # Empty/welcome states
│   ├── state/                    # State management
│   │   └── store.js              # Reactive state store
│   └── utils/
│       ├── commands.json         # Game definitions
│       ├── constants.js          # App constants
│       └── helpers.js            # Utility functions
└── mpy/                          # Python modules (PyScript)
    ├── hub_serial.py             # Serial hub interface
    ├── hub_bluetooth.py          # BLE hub interface (future)
    ├── firmware_manager.py       # Firmware upload
    └── repl_controller.py        # REPL mode handler
```

## Resources

- **Hub Firmware Documentation**: [`hubCode/README.md`](hubCode/README.md)
- **Developer Guide**: [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md)
- **Game Command Reference**: [`js/utils/commands.json`](js/utils/commands.json)
- **Live Demo**: [https://tuftsceeo.github.io/SmartPlayground/](https://tuftsceeo.github.io/SmartPlayground/)

## Support

For issues or questions:

1. **Check browser console** for JavaScript/PyScript errors
2. **Review troubleshooting section** above
3. **Verify hub firmware** is up to date (use "Upload Hub Setup")
4. **Test with "Clap" command** to verify ESP-NOW connectivity
5. **Check hub documentation** at [`hubCode/README.md`](hubCode/README.md)

## Contributing

When contributing:
- Keep game numbers synchronized across plushie firmware, hub firmware, and webapp
- Update `commands.json` when adding new games
- Test on both Chrome and Edge browsers
- Verify upload functionality works after changes
