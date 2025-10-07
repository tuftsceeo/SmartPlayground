# Smart Playground Control - Frontend

This is the frontend application for the Smart Playground Control system, built with PyScript and vanilla JavaScript.

## Quick Start

### 1. Start the Development Server

Open a terminal/command prompt and navigate to the frontend directory:

```bash
cd frontend
python -m http.server 8000
```

### 2. Open in Browser

Open your browser and go to: `http://localhost:8000`

### 3. Clear Cache if Needed

If you're seeing old code or errors, clear your browser cache:

-   **Hard Refresh**: Press `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
-   **Or**: Press `F12` to open DevTools, then right-click the refresh button and select "Empty Cache and Hard Reload"
-   **Or**: Use Incognito/Private mode to test without any cache

## Development Tips

### Browser Cache Issues

When developing, you might encounter caching issues where changes don't appear. To fix this:

1. **Hard refresh** the page (`Ctrl+Shift+R`)
2. **Clear browser cache** completely
3. **Use Incognito mode** for testing
4. **Check DevTools Console** for any JavaScript errors

### Stopping the Server

To stop the Python server:

-   Press `Ctrl+C` in the terminal
-   If that doesn't work, close the terminal window
-   Or find the Python process and kill it manually

### File Structure

```
app/
├── index.html          # Main HTML file - Entry point with PyScript integration
├── main.py            # Python backend (PyScript) - BLE communication and device management
├── pyscript.toml      # PyScript configuration - Dependencies and module paths
├── manifest.json      # PWA manifest - Mobile app configuration
├── js/
│   ├── main.js        # Main application logic - App class and initialization
│   ├── state/
│   │   └── store.js   # State management - Centralized state with reactive updates
│   ├── utils/
│   │   ├── constants.js    # Application constants - Command definitions
│   │   ├── helpers.js      # Utility functions - Time formatting, device type detection
│   │   └── pyBridge.js     # Python-JavaScript bridge - Interface to Python backend
│   └── components/
│       ├── icons.js                    # Icon components - Device and command icons
│       ├── recipientBar.js             # Recipient bar - Device count, range slider, BLE status
│       ├── messageHistory.js           # Message history - Command log display
│       ├── messageInput.js             # Message input - Command palette and send interface
│       ├── deviceListOverlay.js        # Device list - Modal showing available devices
│       ├── messageDetailsOverlay.js    # Message details - Command history details
│       ├── hubConnectionBar.js         # Hub connection - BLE status indicator
│       ├── bluetoothStatusButton.js    # BLE button - Connection status and controls
│       ├── settingsButton.js           # Settings button - App configuration access
│       ├── settingsOverlay.js          # Settings overlay - App configuration panel
│       ├── connectionWarningModal.js   # Connection warning - Modal for BLE prompts
│       └── toast.js                    # Toast notifications - User feedback messages
└── mpy/
    └── webBluetooth.py # BLE communication module - Web Bluetooth API wrapper
```

## Code Architecture

### Core Components Overview

#### 1. Application Entry Points
- **`index.html`**: HTML shell with PyScript integration, mobile-optimized viewport
- **`main.py`**: Python backend handling BLE communication with ESP32 hub
- **`js/main.js`**: JavaScript frontend with App class managing UI lifecycle

#### 2. State Management
- **`js/state/store.js`**: Centralized reactive state management
  - Device list and connection status
  - UI state (overlays, modals, input)
  - Message history and current command
  - Automatic re-rendering on state changes

#### 3. Python-JavaScript Bridge
- **`js/utils/pyBridge.js`**: Interface layer between JS frontend and Python backend
  - Async function calls to Python
  - Event handling for Python callbacks
  - Error handling and fallbacks
- **`main.py`**: Exposes functions to JavaScript via `window` object
  - BLE connection management
  - Device discovery and communication
  - Command transmission to ESP32 hub

#### 4. BLE Communication Stack
- **`mpy/webBluetooth.py`**: Web Bluetooth API wrapper
  - Nordic UART Service implementation
  - Connection management with ESP32 devices
  - Data serialization and notification handling
- **`main.py`**: Protocol layer
  - JSON message parsing from hub
  - Device list updates and RSSI filtering
  - Command formatting for ESP-NOW broadcast

#### 5. UI Component Architecture
- **Component-based design**: Each UI element is a self-contained function
- **Event-driven updates**: Components receive callbacks for user interactions
- **State-reactive rendering**: Components re-render when relevant state changes
- **Mobile-first responsive design**: Touch-optimized interactions and layouts

### Data Flow and Component Relationships

#### Application Initialization Flow
1. **`index.html`** loads PyScript and JavaScript modules
2. **`main.py`** initializes BLE wrapper and exposes functions to `window`
3. **`js/main.js`** creates App instance and sets up state management
4. **`js/state/store.js`** initializes reactive state with mock data
5. Components register for state changes and render initial UI

#### BLE Communication Flow
```
User Action → JavaScript → PyBridge → Python → WebBLE → ESP32 Hub → ESP-NOW → Modules
                    ↑                                        ↓
            State Update ← Event Handler ← Python Callback ← BLE Notification ← Hub Response
```

#### Key Component Relationships
- **`recipientBar.js`** ↔ **`deviceListOverlay.js`**: Device count display and detailed list
- **`messageInput.js`** ↔ **`messageHistory.js`**: Command input and sent message log
- **`bluetoothStatusButton.js`** ↔ **`connectionWarningModal.js`**: BLE status and connection prompts
- **`main.js`** → **All Components**: Passes state and event handlers to components
- **`store.js`** → **All Components**: Triggers re-renders on state changes

#### State Management Pattern
```javascript
// Centralized state in store.js
const state = { devices: [], hubConnected: false, ... };

// Components receive state and callbacks
function createComponent(stateSlice, callbacks) { ... }

// State updates trigger re-renders
setState({ hubConnected: true }); // → All dependent components re-render
```

#### Error Handling Strategy
- **Python Backend**: Graceful BLE error handling with user-friendly messages
- **JavaScript Frontend**: Fallback to mock data when Python unavailable
- **UI Components**: Loading states and error indicators for user feedback
- **Connection Management**: Automatic retry logic and connection status tracking

## Features

-   **BLE Hub Connection**: Connect to ESP32 hub via Bluetooth
-   **Device Management**: View and manage connected modules
-   **Command Sending**: Send commands to selected devices
-   **Message History**: Track sent commands and responses
-   **Real-time Updates**: Live device status and connection monitoring




