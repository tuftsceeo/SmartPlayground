# Smart Playground Control - Developer Guide

**Version:** 1.0  
**Date:** December 6, 2025  
**Purpose:** Comprehensive design and implementation guide

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Adapter Layer Design](#2-adapter-layer-design)
3. [Communication Patterns](#3-communication-patterns)
4. [State Management](#4-state-management)
5. [Component System](#5-component-system)
6. [Application Flow](#6-application-flow)
7. [Connection Management](#7-connection-management)
8. [Error Handling Strategy](#8-error-handling-strategy)
9. [UI/UX Patterns](#9-uiux-patterns)
10. [Browser Compatibility](#10-browser-compatibility)

---

## 1. Architecture Overview

### 1.1 High-Level Architecture

The Smart Playground Control application uses a **hybrid Python-JavaScript architecture** that leverages the strengths of each language:

- **JavaScript Layer**: Handles all browser API operations natively (Web Serial, Web Bluetooth)
- **Python Layer**: Manages business logic, protocol handling, and state management
- **Communication Bridge**: bidirectional function calls via window object

### 1.2 Why Hybrid Architecture?

**Design Rationale:**
- Native JavaScript provides direct, reliable access to Web Serial/Bluetooth APIs
- PyScript/Pyodide is less able to keep up with demands of rapid async handling of browser APIs
- Python is better suited for protocol logic and state management
- Separation of concerns: I/O in JS, logic in Python

### 1.3 Component Hierarchy

```
Browser (Chrome/Edge 89+)
├── index.html (Entry Point)
│   ├── PyScript 2024.1.1
│   ├── Tailwind CSS (CDN)
│   └── Lucide Icons (CDN)
│
├── JavaScript Layer (Native Browser APIs)
│   ├── main.js - Application orchestrator
│   ├── Adapters (Browser API wrappers)
│   │   ├── serialAdapter.js
│   │   └── bluetoothAdapter.js
│   ├── State Management
│   │   └── store.js
│   ├── Utils
│   │   ├── pyBridge.js
│   │   ├── helpers.js
│   │   └── constants.js
│   └── Components (UI rendering)
│       ├── messaging/
│       ├── overlays/
│       ├── modals/
│       ├── states/
│       ├── connection/
│       └── common/
│
└── Python Layer (PyScript/Pyodide)
    ├── main.py - Backend orchestrator
    └── mpy/ (MicroPython utilities)
        ├── webSerial.py
        └── webBluetooth.py
```

---

## 2. Adapter Layer Design

### 2.1 Serial Adapter (serialAdapter.js)

**Purpose**: Thin JavaScript I/O layer over Web Serial API (handles only browser API calls)

**IMPORTANT**: This is the THIN layer. The Python wrapper (webSerial.py) contains the THICK business logic layer.

**Key Responsibilities:**
- Connect/disconnect to serial ports
- Read/write data with native Promise handling
- Timeout management using Promise.race
- Reader/Writer lock management
- Port selection UI via browser's native dialog

**Design Pattern**: Object literal with stateful properties

**Critical Implementation Details:**

```javascript
{
  port: null,         // SerialPort instance
  reader: null,       // ReadableStreamDefaultReader
  writer: null,       // WritableStreamDefaultWriter
  
  // Methods handle native async operations
  connect()           // Request port, open at 115200 baud
  disconnect()        // Release locks, close port
  write(data)         // Write UTF-8 string to port
  read(timeout_ms)    // Read with Promise.race timeout
  readUntil(expected, timeout) // Read until string match
  startReadLoop(onData, onError) // Continuous reading
}
```

**Why This Approach:**
- Python's await in Pyodide doesn't play well with browser API Promises
- Native JavaScript can reliably handle asynchronous browser APIs
- Single point of failure: if adapter works, everything works

**Used By:** `mpy/webSerial.py` (thin Python wrapper)

### 2.2 Bluetooth Adapter (bluetoothAdapter.js)

**Purpose**: Thin JavaScript I/O layer for Web Bluetooth API (Nordic UART Service)

**IMPORTANT**: This is the THIN layer. The Python wrapper (webBluetooth.py) contains the business logic for message assembly and protocol handling.

**Key Responsibilities:**
- Connect/disconnect to BLE devices
- Read/write data with native Promise handling
- Notification handling (TX characteristic)
- GATT service management

**Nordic UART Service Implementation:**
```javascript
{
  SERVICE_UUID: '6e400001-b5a3-f393-e0a9-e50e24dcca9e',
  TX_UUID: '6e400003-b5a3-f393-e0a9-e50e24dcca9e', // Device -> App
  RX_UUID: '6e400002-b5a3-f393-e0a9-e50e24dcca9e', // App -> Device
  
  // State tracking
  device: null,              // BluetoothDevice
  server: null,              // BluetoothRemoteGATTServer
  service: null,             // BluetoothRemoteGATTService
  txCharacteristic: null,    // For receiving notifications
  rxCharacteristic: null,    // For writing
  notificationCallback: null // Python callback
}
```

**GATT Connection Flow:**
1. Request device with name filter (e.g., "ESP32")
2. Connect to GATT server
3. Get primary service (Nordic UART)
4. Get TX/RX characteristics
5. Start notifications on TX characteristic
6. Register disconnect handler

**Used By:** `mpy/webBluetooth.py` (thin Python wrapper)

---

## 3. Communication Patterns

### 3.1 JavaScript → Python Communication

**Method**: Direct function calls via PyBridge

**Pattern:**
```javascript
// PyBridge wraps window.* Python functions
await PyBridge.connectHubSerial()
await PyBridge.sendCommandToHub(command, rssi)
await PyBridge.refreshDevices(rssiThreshold)
```

**Implementation:**
- Python functions exposed to `window` object during PyScript initialization
- JavaScript calls them as async functions
- PyBridge provides error handling and readiness checking

**Error Handling:**
- `PythonNotReadyError` if function not available
- Enhanced error context with function name and arguments
- Automatic Python readiness detection

### 3.2 Python → JavaScript Communication

**Method**: Direct `window.*` callback invocation

**Pattern:**
```python
# Python calls JavaScript directly
window.onDevicesUpdated(js_devices)
window.onHubConnected(js_data)
window.onBLEDisconnected()
```

**Callback Registration:**
JavaScript registers callbacks during initialization:
```javascript
window.onDevicesUpdated = (devices) => { /* update state */ }
window.onHubConnected = (data) => { /* update UI */ }
```

**Why This Approach:**
- Simple, direct communication
- No event bus overhead
- Explicit, easy to debug
- Works reliably across PyScript/Pyodide boundary

### 3.3 Python → Browser API Communication

**Method**: Python calls JavaScript adapter, adapter calls browser API

**Serial Example:**
```python
# webSerial.py
success = await self.adapter.connect()      # JS: serialAdapter.connect()
await self.adapter.write(message)           # JS: serialAdapter.write()
data = await self.adapter.read(timeout_ms)  # JS: serialAdapter.read()
```

**Bluetooth Example:**
```python
# webBluetooth.py
success = await self.adapter.connect(namePrefix)  # JS: bluetoothAdapter.connect()
await self.adapter.write(data)                    # JS: bluetoothAdapter.write()
```

---

## 4. State Management

### 4.1 Centralized State (store.js)

**Pattern**: Observer pattern with reactive updates

**Design Philosophy:**
- Single source of truth for application state
- Reactive updates: components automatically re-render on state changes
- Batched rendering using `requestAnimationFrame` for performance
- Computed values for derived state (device filtering, RSSI calculations)
- Component registration system for state change notifications

**State Structure:**

```javascript
{
  // Connection State
  hubConnected: false,
  hubDeviceName: null,
  hubConnecting: false,
  hubConnectionMode: null,  // "ble" or "serial"
  pythonReady: false,
  
  // Browser Compatibility
  isBrowserCompatible: true,
  
  // UI State
  showSettings: false,
  showConnectionWarning: false,
  showCommandPalette: false,
  showDeviceList: false,
  showMessageDetails: false,
  flashMessageBox: false,
  
  // Modal State
  showBrowserCompatibilityModal: false,
  showPermissionBlockedModal: false,
  showErrorDetailModal: false,
  errorDetail: null,
  
  // Device Management
  deviceScanningEnabled: false,
  range: 40,  // 0-100 slider value
  allDevices: [],
  moduleNicknames: {},
  lastUpdateTime: null,
  isRefreshing: false,
  
  // Messaging
  messageHistory: [],
  currentMessage: "",
  viewingMessage: null,
  editingDeviceId: null,
  
  // Connection Monitoring
  connectionLastChecked: null
}
```

**Update Flow:**

```
User Action
    ↓
Event Handler (main.js)
    ↓
setState({...updates})
    ↓
Batch updates via requestAnimationFrame
    ↓
Notify all registered callbacks
    ↓
App.render()
    ↓
Update DOM
```

**Performance Optimization:**
- Batched updates prevent multiple renders per frame
- `requestAnimationFrame` ensures rendering at 60fps
- Only changed components re-render
- Computed values cached until dependencies change

### 4.2 Computed Values

**getAvailableDevices()**: Filters devices by RSSI range
- Converts slider value (1-100) to RSSI threshold
- Returns devices within signal strength range
- Used for device list display and command targeting

**getRangeLabel()**: Converts slider value to human-readable label
- 1-20: "Very Close"
- 21-40: "Close"
- 41-60: "Medium"
- 61-80: "Far"
- 81-100: "Very Far"

---

## 5. Component System

### 5.1 Component Philosophy

**Pattern**: Functional components (NOT React, NOT Vue)

**Design Principles:**
- Pure functions that return DOM elements
- Props passed as function parameters
- No component state (state managed centrally)
- No virtual DOM (direct manipulation)
- No lifecycle methods (render on state change)

**Component Structure:**
```javascript
export function createComponent(prop1, prop2, onCallback) {
  const container = document.createElement('div');
  container.className = 'styles...';
  
  container.innerHTML = `...`;
  
  // Event handlers
  container.querySelector('#btn').onclick = onCallback;
  
  return container;
}
```

### 5.2 Component Categories

#### Messaging Components

**recipientBar.js**
- **Purpose**: Main control bar at top of application
- **Features**:
  - Device count display with visual device avatars
  - Range slider for RSSI-based device filtering (Near to Far)
  - Last update timestamp with refresh capability
  - Hub connection status and controls
  - Settings access button
- **Visual Elements**:
  - Device avatars showing connected module types
  - Hub status indicator (connected/disconnected)
  - Range slider with Near/Far labels
  - Timestamp showing data freshness
  - Settings gear icon
- **Interactions**:
  - Click entire bar to open device list overlay
  - Drag range slider to filter devices by signal strength
  - Click timestamp to refresh device list
  - Click hub button to connect/disconnect
  - Click settings button to open configuration
- **Props**: devices, range, lastUpdateTime, hubConnected, hubDeviceName, callbacks

**messageInput.js**
- **Purpose**: Command input interface at bottom of application
- **Features**:
  - Command selection interface with visual command palette
  - Expandable drawer design for space efficiency
  - Visual command icons with color-coded backgrounds
  - Send button with state-aware styling
  - Clear command functionality
  - Touch-optimized command buttons for mobile
- **Visual Elements**:
  - Message input box showing selected command or placeholder
  - Command palette with icon buttons for each available command
  - Send button that changes color based on readiness
  - Clear button (X) when command is selected
  - Smooth expand/collapse animations
- **Interactions**:
  - Click input area to open command palette
  - Click command buttons to select commands
  - Click clear button to deselect command
  - Click send button to transmit command
  - Palette automatically closes after command selection
- **Command Flow**:
  1. User clicks input area → palette opens
  2. User selects command → palette closes, command appears in input
  3. User clicks send → command transmitted to devices
  4. Input clears and ready for next command
- **Props**: currentMessage, showPalette, canSend, flashMessageBox, callbacks

**messageHistory.js**
- **Purpose**: Display sent commands and their metadata
- **Features**: Command list with timestamps, recipients, and status
- **Empty States**: 
  - Welcome state (not connected)
  - Connected empty state (connected, no commands sent)

#### Overlay Components

**deviceListOverlay.js**
- **Purpose**: Full-screen device list with management
- **Features**: Device cards with RSSI, battery, edit nicknames
- **Interactions**: Edit device names, refresh list, adjust range

**messageDetailsOverlay.js**
- **Purpose**: Detailed view of sent message
- **Features**: Command info, recipient list, timestamp, resend option

**settingsOverlay.js**
- **Purpose**: Application settings
- **Features**: Device scanning toggle, hub setup access

**commandInfoOverlay.js**
- **Purpose**: Display command descriptions
- **Features**:
  - Centered modal overlay with command description
  - Shows command icon for visual reference
  - Closes via X button or clicking outside
  - Smooth fade-in/fade-out animations
  - Mobile-optimized (max-w-md)
- **Props**:
  - commandLabel: Display name of command
  - commandDescription: Description text
  - commandIcon: Icon element
  - onClose: Callback when overlay closes

#### Modal Components

**browserCompatibilityModal.js**
- **Purpose**: Blocking modal for unsupported browsers
- **Trigger**: Displayed when browser doesn't support required Web APIs
- **Dismissal**: Cannot be dismissed (blocking)
- **Required APIs**: Web Serial API (for USB hub connection)
- **Compatible Browsers**:
  - Chrome/Chromium 89+
  - Edge 89+
  - Opera 75+
- **Incompatible Browsers**:
  - Firefox (no Web Serial support)
  - Safari (no Web Serial support)
  - Mobile browsers (limited support)
- **Design**: Guides users to use compatible browser on desktop/laptop

**connectionWarningModal.js**
- **Purpose**: Prompt to connect when user tries to send without connection
- **Features**: Connect button, cancel option

**errorDetailModal.js**
- **Purpose**: Detailed error messages with troubleshooting
- **Use Cases**:
  - Connection errors with detailed causes and solutions
  - Debugging information users need to read carefully
  - Multi-step troubleshooting guidance
- **Different from Toasts**: For errors needing more reading time
- **Structure**: Title, message, causes list, solutions list

**permissionBlockedModal.js**
- **Purpose**: Help when permission dialogs are blocked
- **Trigger**: Browser supports Web Serial but device selection dialog blocked
- **Causes**:
  - Popup blockers
  - Browser permissions
  - Security settings
- **Different from Browser Incompatibility**: Browser CAN support it, but something prevents permission prompt
- **Solutions**: Step-by-step troubleshooting for unblocking

**hubSetupModal.js**
- **Purpose**: Upload hub firmware to ESP32 via serial
- **States**:
  - loading: Connecting and querying device information
  - initial: Confirmation screen with device info
  - uploading: Progress bar and file list
  - success: Success message with reset button
  - resetting: Device performing hard reset
  - error: Error message with retry option
- **Features**: Device detection, progress tracking, firmware upload

#### State Components

**welcomeState.js**
- **Purpose**: Onboarding when app first loads
- **Displayed When**: No hub connected, no messages sent
- **Features**:
  - Helpful onboarding instructions
  - Guides users through first connection
  - Connect hub button
  - Setup hub firmware option
- **Design Philosophy**: Replace empty state with actionable guidance

**connectedEmptyState.js**
- **Purpose**: Instructions after successful connection
- **Displayed When**: Hub connected but no commands sent yet
- **Features**:
  - Success indicator (hub connected)
  - Instructions to use send command field
  - For Serial connections: option to flash hub firmware
- **Design Philosophy**: Help users understand next steps

#### Connection Components

**bluetoothStatusButton.js**
- **Purpose**: Hub connection status display and control
- **States**:
  - Not supported (browser incompatible)
  - Loading (Python initializing)
  - Disconnected (click to connect)
  - Connected (shows device name)
- **Features**: Proper layout stability, connection toggle

---

## 6. Application Flow

### 6.1 Initialization Sequence

**Critical**: Load order matters for proper operation

**Initialization Flow:**

1. **index.html loads**
   - PyScript CDN
   - Tailwind CSS CDN
   - Lucide Icons CDN
   
2. **JavaScript adapters load** (BEFORE PyScript)
   - `serialAdapter.js` → `window.serialAdapter`
   - `bluetoothAdapter.js` → `window.bluetoothAdapter`
   - **Why first**: Python checks for these at startup
   
3. **PyScript initializes**
   - Loads `main.py`
   - Checks for `window.serialAdapter` and `window.bluetoothAdapter`
   - Creates `WebSerial()` and `WebBLE()` instances
   - Exposes functions to `window.*`
   
4. **JavaScript main.js loads** (ES6 module)
   - Imports components
   - Creates `App` instance
   - Registers `window.on*` callbacks for Python
   - Waits for Python with `PyBridge.waitForPython()`
   - Renders initial UI

**Critical Dependencies:**
1. Adapters MUST load before PyScript (verified in index.html)
2. Python checks for adapters at startup (verified in main.py:38-46)
3. JavaScript waits for Python functions (verified in main.js)

### 6.2 App.init() Method

**Purpose**: Initialize application and set up all core systems

**Initialization Steps:**

1. **Browser Compatibility Check**
   - Check for Web Serial API support
   - Show blocking modal if unsupported
   - Set `isBrowserCompatible` state

2. **State Initialization**
   - Initialize with empty device list
   - Set Python ready state to false
   - Configure UI flags

3. **Python Backend Integration**
   - Register `window.on*` callbacks for Python events:
     - `onDevicesUpdated`: Device list updated from hub
     - `onBLEConnected`: BLE connection established
     - `onHubConnected`: Any hub connection (BLE/Serial)
     - `onBLEDisconnected`: BLE disconnected
     - `onHubDisconnected`: Any hub disconnect
     - `showSerialConnectionLostError`: Connection lost
     - `showToast`: Toast notification
     - `onUploadProgress`: Firmware upload progress

4. **Event Listener Setup**
   - Click-outside handlers for overlays
   - Keyboard shortcuts (if any)
   - Window resize handlers

5. **State Management**
   - Register App.render() with state change system
   - Set up reactive rendering pipeline

6. **Connection Monitoring**
   - Start polling for connection status
   - Auto-disconnect detection

7. **Initial Render**
   - Render all components with initial state
   - Initialize Lucide icons

**Error Handling:**
- Show blocking modal for incompatible browsers
- Graceful fallback if Python unavailable
- Comprehensive logging for debugging
- Continues operation even if some systems fail

---

## 7. Connection Management

### 7.1 Connection Monitoring

**Method**: `startConnectionMonitoring()`

**Purpose**: Auto-disconnect detection by polling Python backend

**Implementation:**
- Polls connection status every 30 seconds
- Only when connected AND not scanning
- Helps detect unexpected disconnections

**Why Polling Paused During Scans:**
- **CRITICAL**: Prevents BLE traffic from interfering with ESP-NOW IRQ on ESP32-C3's shared radio
- ESP-NOW and BLE share radio hardware on ESP32-C3
- Simultaneous BLE polling and ESP-NOW scanning can cause IRQ conflicts
- Solution: Skip polling during device scans (isRefreshing flag)

**Timing Rationale:**
- 30 second interval (reduced from 5s)
- Reduces BLE traffic by 6x
- Only logs when state actually changes (reduces noise)

**Production Considerations:**
- Interval runs for application lifetime (acceptable for MVP)
- For production: store interval ID and clear on app cleanup

### 7.2 Serial Connection Flow

**Connection Steps:**
1. User clicks connect button
2. Browser shows native port selection dialog
3. User selects port (or cancels)
4. Open port at 115200 baud
5. Python callback notifies JavaScript
6. UI updates to show connected state

**Error Scenarios:**
- User cancellation (handled silently)
- Port already in use (show error with solution)
- Permission denied (show permission modal)
- Device disconnected (show connection lost error)

### 7.3 BLE Connection Flow

**Connection Steps:**
1. User clicks connect button
2. Browser shows BLE device picker
3. Filter by name prefix ("ESP32")
4. User selects device (or cancels)
5. Connect to GATT server
6. Get Nordic UART service
7. Get TX/RX characteristics
8. Start notifications on TX
9. Register disconnect handler
10. Python callback notifies JavaScript
11. UI updates to show connected state

**Error Scenarios:**
- User cancellation (handled silently)
- Device not found (show error)
- GATT connection failed (retry up to 3 times)
- Service not found (show error)
- Disconnected (auto-detect and update UI)

---

## 8. Error Handling Strategy

### 8.1 Unified Error Handler

**Function**: `handleError(result, context)`

**Purpose**: Consistent error handling across all Python function calls

**Design Philosophy:**
- Distinguish between real errors and user cancellations
- User cancellations are normal operations (not errors)
- Real errors show toasts with helpful messages
- Enhanced logging for debugging

**Error Categories:**

1. **Success States** (not errors):
   - `status: "success"`
   - `status: "sent"`
   - `status: "disconnected"`
   - Return false (not an error)

2. **User Cancellations** (not errors):
   - `status: "cancelled"`
   - User closed dialog
   - Log but don't show error toast
   - Return false (not an error)

3. **Real Errors**:
   - `status: "error"`
   - Show error toast to user
   - Log error details
   - Return true (is an error)

### 8.2 Error Display Methods

**Toast Notifications**
- For quick, dismissible errors
- Auto-dismiss after 3 seconds
- Non-blocking
- Use for: connection failures, command errors, validation errors

**Error Detail Modal**
- For errors needing more context
- Shows causes and solutions
- User must dismiss
- Use for: serial connection lost, port in use, complex errors

**Blocking Modals**
- For critical errors preventing app use
- Cannot be dismissed
- Must resolve issue to continue
- Use for: browser incompatibility

### 8.3 Error Context Enhancement

All Python function calls include enhanced error context:
```javascript
try {
  return await fn(...args);
} catch (error) {
  error.pythonFunction = fnName;
  error.pythonArgs = args;
  console.error(`Python call failed: ${fnName}`, error);
  throw error;
}
```

This enables better debugging and error reporting.

---

## 9. UI/UX Patterns

### 9.1 Command Sending Flow

**Method**: `handleSendMessage()`

**Priority-Based Validation:**

**PRIORITY 1: Hub Connection**
- Check if hub is connected
- If not: show connection warning modal
- User can choose to connect or cancel

**PRIORITY 2: Device Availability**
- Check if devices are in range
- If none: show flash animation on message box
- Toast: "No devices in range"

**PRIORITY 3: Command Selection**
- Check if command is selected
- If not: flash message box
- Toast: "Select a command first"

**Command Transmission Process:**

1. **Pre-transmission Validation**
   - Hub connected: ✓
   - Devices available: ✓
   - Command selected: ✓

2. **Refresh Device List**
   - Get current device status
   - Warn if device count changed

3. **Send Command**
   - Format command with RSSI threshold
   - Send via hub (Serial or BLE)
   - Handle transmission errors

4. **Update UI**
   - Add to message history
   - Clear input field
   - Show success feedback

**User Experience Principles:**
- Progressive disclosure of requirements
- Visual feedback for all states
- Automatic state cleanup after transmission
- Confirmation prompts for potentially destructive actions

### 9.2 Device Refresh Flow

**Method**: `handleRefreshDevices(rssiThreshold, retryCount)`

**Purpose**: Refresh device list from ESP32 hub with RSSI-based filtering

**IMPORTANT**: Filtering happens at module level, not client-side!
- Hub broadcasts PING with RSSI threshold
- Only modules with strong enough signal respond
- Ensures modules CAN receive commands at that strength

**Visual Feedback:**
- Shows loading spinner during entire ping/response cycle
- Maximum 7 second timeout per attempt (5s scan + 2s buffer)
- Loading state shown in recipient bar and device list overlay

**Error Handling:**
- **GATT errors**: Automatically retries up to MAX_GATT_RETRIES (2) times with 1s delays
- **Empty device lists**: No retry (legitimate result - no devices in range)
- **Timeout per attempt**: 7 seconds (hub scans for 5s + buffer for response)
- **Silent retries**: No user interruption during automatic retries

**Cooldown Management:**
- 2 second minimum between scans
- Prevents radio conflicts
- Enforced via `SCAN_COOLDOWN_MS`

### 9.3 Mobile Optimizations

**Touch-Friendly Interactions:**
- Button tap highlights (transform: scale(0.95))
- No hover states (use active states instead)
- Larger tap targets (minimum 44x44px)
- Touch-optimized range sliders

**Viewport Management:**
- Dynamic viewport height (dvh) for mobile browsers
- Safe area insets for notched devices
- Prevent zoom on double tap
- Force scrollable content to hide address bar

**Performance:**
- Smooth animations (hardware accelerated)
- Batched renders (requestAnimationFrame)
- Minimal reflows
- Efficient DOM updates

---

## 10. Browser Compatibility

### 10.1 Required APIs

**Web Serial API** (Primary)
- Required for USB hub connection
- Chrome/Chromium 89+
- Edge 89+
- Opera 75+
- **Not supported**: Firefox, Safari, mobile browsers

**Web Bluetooth API** (Legacy)
- Optional, for BLE connections
- Same browser support as Serial
- Legacy feature, Serial is primary

### 10.2 Compatibility Detection

**Check Method**:
```javascript
function isBrowserCompatible() {
  return 'serial' in navigator;
}
```

**User Experience:**
- Check on app initialization
- Show blocking modal if incompatible
- Provide clear guidance to compatible browsers
- Cannot proceed without compatible browser

### 10.3 Fallback Strategies

**No Fallback Available:**
- Web Serial is required (no polyfill exists)
- App cannot function without it
- Must use compatible browser on desktop/laptop

**User Guidance:**
- Clear explanation of why browser isn't supported
- List of compatible browsers with download links
- Emphasize desktop/laptop requirement
- Cannot be dismissed (blocking)

---

## 11. Python Backend Details

### 11.1 Main Module (main.py)

**Purpose**: PyScript backend for Smart Playground Control

**Original Detailed Description:**
> This module serves as the PyScript backend for the Smart Playground Control application. It handles Bluetooth Low Energy (BLE) communication with ESP32 hub devices and manages the ESP-NOW protocol for communicating with playground modules.

**Key Responsibilities (Detailed):**
- **BLE Connection Management**: With ESP32C6 hub using Nordic UART Service
- **Device Discovery**: RSSI-based filtering of playground modules  
- **Command Transmission**: Response handling via ESP-NOW protocol
- **Data Parsing**: Format conversion between JSON and JavaScript objects
- **Event Dispatching**: To JavaScript frontend for real-time UI updates

**Communication Flow (Detailed):**
1. Web app connects to ESP32 hub via BLE (Nordic UART Service) or Serial (USB)
2. Hub broadcasts commands to playground modules via ESP-NOW
3. Modules respond with status/sensor data back through hub
4. Hub forwards responses to web app via BLE notifications or Serial messages
5. Python backend parses responses and updates JavaScript frontend

**Dependencies (Full List):**
- **PyScript 2024.1.1**: Browser Python execution
- **mpy/webSerial.py**: Web Serial API wrapper
- **mpy/webBluetooth.py**: Web Bluetooth API wrapper
- **js/adapters/serialAdapter.js**: Native browser Serial API access
- **js/adapters/bluetoothAdapter.js**: Native browser Bluetooth API access
- **js/utils/pyBridge.js**: JavaScript-Python function bridge

### 11.2 Python Functions Reference

#### Connection Functions

**connect_hub() - BLE Connection (Legacy)**

**Full Documentation:**
```python
async def connect_hub():
    """
    Connect to ESP32C6 hub via Bluetooth Low Energy.
    
    This function initiates a BLE connection to an ESP32 hub device using the
    Nordic UART Service. It handles device discovery, connection establishment,
    and error management including user cancellation scenarios.
    
    Connection Process:
    1. Use WebBLE to scan for devices with Nordic UART Service
    2. Present device selection dialog to user
    3. Establish GATT connection and service discovery
    4. Set up notification handlers for incoming data
    5. Update connection state and notify JavaScript frontend
    
    Returns:
    --------
    dict : JavaScript object with connection result
        - status: "success" | "cancelled" | "error"
        - device: Device name if successful
        - error: Error message if failed
    
    Error Handling:
    - User cancellation is treated as normal operation (not an error)
    - Connection failures are logged and reported to user
    - Graceful fallback for various BLE error conditions
    
    Side Effects:
    - Updates global ble_connected and hub_device_name variables
    - Dispatches BLE connection events to JavaScript frontend
    - Sets up data callback for ongoing communication
    """
```

**Current Status**: Deprecated - Use `connect_hub_serial()` for primary connections

**connect_hub_serial() - Serial Connection (Primary)**

**Full Documentation:**
```python
async def connect_hub_serial():
    """
    Connect to hub via USB Serial (primary connection method).
    
    This is the primary connection method for the application. It provides
    more reliable communication than BLE and supports higher data rates.
    
    Connection Process:
    1. Request serial port from user via browser's native dialog
    2. Open port at 115200 baud (standard for ESP32)
    3. Set up data callback for incoming messages
    4. Update connection state
    5. Notify JavaScript frontend
    
    Returns:
    --------
    dict : JavaScript object with connection result
        - status: "success" | "cancelled" | "error"
        - device: "USB Serial Hub"
        - mode: "serial"
        - error: Error message if failed
    
    Error Handling:
    - User cancellation (status: "cancelled")
    - Port in use (status: "error", specific message)
    - Generic connection failures
    """
```

**Why Serial is Primary:**
- More reliable than BLE
- Higher data rates
- No MTU limitations
- Simpler protocol (line-delimited JSON)
- Better error detection

#### Command Functions

**send_command_to_hub() - Send Commands to Modules**

**Full Documentation:**
```python
async def send_command_to_hub(command, rssi_threshold="all"):
    """
    Send command to hub for ESP-NOW broadcast to playground modules.
    
    This function formats and transmits commands to the ESP32 hub, which then
    broadcasts them to playground modules via ESP-NOW protocol. The hub uses
    RSSI thresholding to control which modules receive the command.
    
    Parameters:
    -----------
    command : str
        Command to send to modules (e.g., "play", "pause", "win", "off")
        Must match command definitions in commands.json
    
    rssi_threshold : str, optional
        RSSI filter for command broadcast:
        - "all": Send to all modules regardless of signal strength (default)
        - "-XX": Send only to modules with RSSI >= -XX dBm (e.g., "-60")
        
    Returns:
    --------
    dict : JavaScript object with transmission result
        - status: "sent" | "error"
        - command: Original command if successful
        - threshold: RSSI threshold used
        - error: Error message if failed
    
    Communication Flow:
    1. Format command according to hub protocol (BLE or Serial)
    2. Send command to hub via active connection
    3. Hub broadcasts via ESP-NOW to modules within RSSI range
    4. Modules execute command and may send responses back
    5. Responses are processed by data callbacks
    
    Protocol Formats:
    - Serial: {"cmd": "command_name", "rssi": "threshold_value"}
    - BLE: "command_name":"threshold_value"
    
    RSSI Filtering:
    - Filtering happens at the MODULE level, not client-side
    - Only modules that receive hub broadcast at threshold respond
    - Ensures modules can reliably receive commands at that signal strength
    """
```

**Important**: RSSI filtering is module-side, not client-side filtering

#### Device Discovery Functions

**refresh_devices_from_hub() - Refresh Device List**

**Full Documentation:**
```python
async def refresh_devices_from_hub(rssi_threshold="all"):
    """
    Request device list from hub with RSSI filtering.
    
    Sends a PING command to the hub, which broadcasts it to all modules.
    Only modules that can receive the ping at the specified RSSI threshold
    will respond with their device information.
    
    Parameters:
    -----------
    rssi_threshold : str or int
        RSSI threshold for device filtering:
        - "all": Return all devices that respond (no filtering)
        - "-XX": Only devices with RSSI >= -XX dBm will respond
        
    The filtering happens at the module level - only modules that can
    receive the hub's broadcast at the specified RSSI will respond to the ping.
    This ensures that the returned devices can reliably receive commands at
    that signal strength.
    
    Returns:
    --------
    JavaScript array : List of device objects
        Each device object contains:
        - id: Device identifier (e.g., "M-A3F821")
        - rssi: Signal strength in dBm
        - battery: Battery level (if available)
        - Other device-specific properties
    
    Implementation Notes:
    - Uses "PING" command with RSSI threshold
    - Response handled by on_ble_data() or on_serial_data()
    - Updates global devices list
    - Converts Python list to JavaScript array using to_js()
    
    Timeout: 7 seconds total (5s scan + 2s buffer)
    """
```

**Why Module-Level Filtering:**
- Ensures devices CAN receive commands at that strength
- More accurate than client-side RSSI filtering
- Reflects real-world communication capability

#### Firmware Upload Functions

**upload_firmware() - Upload Hub Firmware**

**Full Documentation:**
```python
async def upload_firmware(files_json):
    """
    Upload hub firmware files to ESP32 via Serial connection.
    
    This function handles the complete firmware upload process including
    entering REPL mode, uploading files, and restarting the hub with
    the new firmware.
    
    Parameters:
    -----------
    files_json : list of dicts
        List of file objects to upload:
        [{"path": "main.py", "content": "..."}, 
         {"path": "lib/module.py", "content": "..."}, ...]
        
    Each file object must have:
        - path: Relative path on device (e.g., "main.py", "lib/utils.py")
        - content: Full file content as string
    
    Returns:
    --------
    dict : JavaScript object with upload result
        Success:
            - status: "success"
            - files_uploaded: Number of files uploaded
        Error:
            - status: "error"
            - error: Error message string
    
    Upload Process:
    1. Enter normal REPL mode (interrupt running code with Ctrl-C)
    2. Enter raw REPL mode (needed for file operations)
    3. For each file:
       a. Create directory if needed
       b. Upload file content
       c. Notify progress via window.onUploadProgress()
    4. Exit raw REPL mode back to normal REPL
    5. Start uploaded main.py using paste mode
    6. Hub is now running new firmware
    
    Progress Callbacks:
    - window.onUploadProgress() called for each file
    - Progress object: {current, total, file, status}
    - Status: "uploading" | "uploaded"
    
    Error Recovery:
    - Attempts to exit REPL mode on error
    - Leaves device in known state even if upload fails
    
    REPL Modes:
    - Normal REPL: Interactive Python prompt (>>>)
    - Raw REPL: For programmatic operations (no echo, OK responses)
    - JSON Mode: Hub's normal operation mode (sends JSON messages)
    """
```

**Critical for Hub Setup:**
- Must be done via Serial (not BLE)
- Requires stopping current firmware
- Restarts hub after upload
- Progress feedback to user

#### Helper Functions (Legacy)

**get_devices() - Get Cached Device List**
```python
def get_devices():
    """
    Return list of available devices from cache.
    
    Returns the current device list without triggering a new scan.
    Used for initial page load and quick checks.
    
    Status: Legacy - prefer refresh_devices_from_hub() for fresh data
    
    Returns: JavaScript array of device objects
    """
```

**refresh_devices() - Legacy Refresh**
```python
def refresh_devices():
    """
    Refresh device list (deprecated, use refresh_devices_from_hub).
    
    Original BLE-only device refresh function.
    Superseded by refresh_devices_from_hub() which supports both BLE and Serial.
    
    Status: Deprecated - calls refresh_devices_from_hub() internally
    """
```

**send_command() - Legacy Command Send**
```python
def send_command(command, device_ids):
    """
    Send command to specific devices (legacy, use send_command_to_hub).
    
    Original function for device-specific commands.
    Superseded by send_command_to_hub() with RSSI threshold filtering.
    
    Status: Legacy - prefer send_command_to_hub() with RSSI filtering
    """
```

### 11.3 Data Callback Functions

**on_serial_data() - Serial Data Handler**

**Full Documentation:**
```python
def on_serial_data(data):
    """
    Handle incoming Serial data from ESP32 hub.
    
    Serial data is line-delimited and can be:
    - JSON messages (starting with '{')
    - Debug/print statements from hub (other text)
    
    Processing:
    1. Receive line of text from Serial
    2. Check if it's JSON (starts with '{')
    3. If JSON: process as structured message
    4. If not JSON: log as debug output
    
    JSON Message Types:
    - {"type": "devices", "list": [...]} - Device list update
    - {"type": "ack", "command": "...", "status": "..."} - Command acknowledgment
    - {"type": "error", "message": "..."} - Error from hub
    
    Called by: webSerial.py read loop when data arrives
    """
```

**on_ble_data() - BLE Data Handler**

**Full Documentation:**
```python
def on_ble_data(data):
    """
    Handle incoming BLE data from ESP32 hub with message reassembly.
    
    BLE data uses framed message protocol due to MTU limitations:
    Format: MSG:<length>|<payload>
    
    Example:
        Fragment 1: "MSG:330|"
        Fragment 2: '{"type":"devices","list":[...]}'
    
    State Machine:
    - waiting_header: Looking for "MSG:<length>|"
    - receiving_payload: Collecting payload fragments
    
    Fragmentation:
    - BLE notifications limited to ~100 bytes (MTU)
    - Large JSON responses require multiple fragments
    - 2 second timeout for message completion
    
    Called by: webBluetooth.py when BLE notification arrives
    
    Implementation: Lines 267-395 in main.py
    """
```

**Why Different Protocols:**
- Serial: No MTU limit, can send complete JSON per line
- BLE: MTU ~100 bytes, requires framing and reassembly
- Serial is simpler and more reliable

### 11.4 Connection Loss Handlers

**on_serial_connection_lost() - Serial Disconnect**

**Full Documentation:**
```python
def on_serial_connection_lost():
    """
    Handle unexpected Serial connection loss.
    
    Called when Serial port is disconnected unexpectedly (cable unplugged,
    device reset, USB issues, etc.)
    
    Actions:
    1. Update connection state variables
    2. Clear device list
    3. Show detailed error modal to user via JavaScript
    4. Log disconnect for debugging
    
    Error Modal:
    - Explains connection was lost
    - Provides troubleshooting steps
    - Allows user to retry connection
    
    Different from disconnect_hub_serial():
    - disconnect_hub_serial(): User-initiated, clean shutdown
    - on_serial_connection_lost(): Unexpected, error condition
    
    Called by: webSerial.py when read loop detects disconnect
    """
```

---

## 12. Utility Modules Details

### 12.1 pyBridge.js - Python-JavaScript Bridge

**Original Full Documentation:**

**Purpose**: Clean interface for JavaScript to communicate with Python backend running in PyScript

**Key Features (Detailed):**
- **Direct Function Calls**: To Python backend via window object
- **Async/Await Support**: For Python function calls with proper Promise handling
- **Automatic Readiness Detection**: Waits for Python to initialize before allowing calls
- **Error Handling**: Proper error propagation with enhanced context
- **Event System**: For Python-initiated callbacks
- **Timeout Handling**: For initialization (prevents infinite waits)

**Python Integration Details:**
- Python functions are exposed to JavaScript via window object during PyScript init
- PyBridge provides a consistent interface regardless of Python readiness state
- Handles connection between JavaScript frontend and Python backend
- Manages device data flow and command transmission

**Available Functions (Complete List):**
- `getDevices()` - Retrieve current device list from cache
- `getConnectionStatus()` - Check hub connection status (serial/BLE)
- `connectHub()` - Initiate BLE connection to ESP32 hub (legacy)
- `disconnectHub()` - Disconnect from BLE hub
- `connectHubSerial()` - Connect via USB Serial (primary method)
- `disconnectHubSerial()` - Disconnect from Serial hub
- `sendCommandToHub()` - Send command via hub for ESP-NOW broadcast
- `refreshDevices()` - Request fresh device scan from hub with RSSI filter
- `uploadFirmware()` - Upload firmware files to hub
- `getDeviceBoardInfo()` - Query device information
- `hardResetDevice()` - Perform hardware reset on device

**Error Handling (Detailed):**
- **PythonNotReadyError**: Thrown if Python backend not initialized
  - Includes function name that was attempted
  - Allows UI to show "Loading..." state
- **Error Propagation**: Errors propagate to caller for proper UI handling
  - Original error preserved
  - Enhanced with Python function context
  - Includes function name and arguments in error object
- **Logging**: All errors logged for debugging with full context

**Custom Error Class:**
```javascript
class PythonNotReadyError extends Error {
  constructor(functionName) {
    super(`Python function '${functionName}' not available. PyScript may still be initializing.`);
    this.name = 'PythonNotReadyError';
    this.functionName = functionName;
  }
}
```

**Error Context Enhancement:**
```javascript
async function callPython(fnName, ...args) {
  const fn = window[fnName];
  if (typeof fn !== 'function') {
    throw new PythonNotReadyError(fnName);
  }
  
  try {
    return await fn(...args);
  } catch (error) {
    // Add context to error for better debugging
    error.pythonFunction = fnName;
    error.pythonArgs = args;
    console.error(`Python call failed: ${fnName}`, error);
    throw error;
  }
}
```

### 12.2 helpers.js - Utility Functions

**Original Full Documentation:**

**Purpose**: Common utility functions used throughout application for data formatting, time calculations, device type detection

**Key Functions (Detailed):**

**Time Formatting**
```javascript
/**
 * Convert timestamp to human-readable relative time string.
 * 
 * Time Ranges:
 * - < 1 minute: "just now"
 * - 1-59 minutes: "X minute(s) ago"
 * - 60+ minutes: "X hour(s) ago" (rounded)
 * 
 * Use Cases:
 * - Last device update timestamp
 * - Message sent timestamp
 * - Connection time display
 * 
 * Example:
 * getRelativeTime(new Date(Date.now() - 180000)) // "3 minutes ago"
 */
function getRelativeTime(timestamp)
```

```javascript
/**
 * Format date object to display time in user's locale.
 * 
 * Format: Uses user's locale with hour and minute display
 * Examples:
 * - en-US: "2:30 PM"
 * - 24-hour locales: "14:30"
 * 
 * Use Cases:
 * - Message details display
 * - Connection time
 * - Log timestamps
 */
function formatDisplayTime(date)
```

**Device Type Detection**
```javascript
/**
 * Determine device type from device ID string.
 * 
 * ID Conventions:
 * - M-XXXXXX or Module*: Main playground modules
 * - E-XXXXXX or Extension*: Extension/add-on modules  
 * - B-XXXXXX: Button/input modules
 * - Note: XXXXXX is the last 6 digits of the device MAC address
 * - Default: "module" for unrecognized patterns
 * 
 * Returns: "module" | "extension" | "button"
 * 
 * Use Cases:
 * - Device icon selection
 * - Device categorization
 * - UI display logic
 * 
 * Examples:
 * getDeviceType("M-A3F821") // "module"
 * getDeviceType("E-B4C932") // "extension"
 * getDeviceType("B-C5D043") // "button"
 * getDeviceType("Module_1") // "module"
 */
function getDeviceType(deviceId)
```

**Device Counting**
```javascript
/**
 * Count devices by type for display purposes.
 * 
 * Usage: For displaying device type summaries in UI components
 * 
 * Returns: {moduleCount, extensionCount, buttonCount}
 * 
 * Example:
 * countDevicesByType(["M-A3F821", "E-B4C932", "M-C5D043"])
 * // Returns: {moduleCount: 2, extensionCount: 1, buttonCount: 0}
 * 
 * Use Cases:
 * - Device list headers
 * - Summary displays
 * - Statistics
 */
function countDevicesByType(deviceIds)
```

**Device ID Format Details:**
- **Format**: `PREFIX-MACADDR`
  - PREFIX: M (Module), E (Extension), B (Button)
  - MACADDR: Last 6 hex digits of MAC address
- **Legacy Format**: `Module_N` or `Extension_N`
  - Still supported for backward compatibility
  - N is a sequential number
- **Why Last 6 Digits**: Unique enough for playground networks, shorter for display

### 12.3 constants.js - Application Constants

**Original Full Documentation:**

**Purpose**: Define all constant values used throughout application

**Key Constants (Detailed):**

**COMMANDS Array**
- **Source**: Loaded from commands.json
- **Structure**: Array of command objects
- **Command Properties**:
  - `id`: Unique command identifier (e.g., "Hot_cold")
  - `label`: Display name (e.g., "Hot/Cold")
  - `bg`: Background color class (Tailwind)
  - `icon`: Icon name (Lucide icons)
  - `textColor`: Text color class (Tailwind)
  - `description`: Help text for command info overlay

**Command Configuration Philosophy:**
- All command data is loaded from commands.json (not hardcoded)
- To add/edit commands: simply update commands.json
- No code changes needed for command modifications
- Each command includes description for info overlay

**Usage Patterns:**
- Import COMMANDS array for command palette generation
- Use consistent command IDs throughout application
- Colors, icons, descriptions defined in commands.json for easy updates

**Helper Functions:**
```javascript
/**
 * Get command label from command ID
 * Useful for display when only ID is available
 * 
 * Example:
 * getCommandLabel("Hot_cold") // "Hot/Cold"
 */
function getCommandLabel(commandId)

/**
 * Get complete command object by ID
 * Useful when need all command properties
 * 
 * Returns: command object or null if not found
 * 
 * Example:
 * getCommandById("Hot_cold") 
 * // {id: "Hot_cold", label: "Hot/Cold", bg: "bg-red-500", ...}
 */
function getCommandById(commandId)
```

**Command JSON Structure:**
```json
{
  "id": "Hot_cold",
  "label": "Hot/Cold",
  "bg": "bg-gradient-to-r from-red-500 to-blue-500",
  "icon": "thermometer",
  "textColor": "text-white",
  "description": "Play hot/cold proximity game..."
}
```

### 12.4 store.js - State Management

**Original Full Documentation (Complete):**

**Purpose**: Reactive state management system for the application

**Design Philosophy:**
> Similar to Redux or Vuex but simpler and lighter. Provides centralized state storage with automatic component re-rendering when state changes occur.

**Key Features (Detailed):**

1. **Centralized Application State**: Single object holding all state
   - Single source of truth
   - Predictable state updates
   - Easy debugging with state snapshots

2. **Reactive Updates**: Components automatically re-render on state changes
   - Observer pattern implementation
   - Components register callbacks
   - Automatic notification on state change

3. **Batched Rendering**: Using requestAnimationFrame for performance
   - Prevents multiple renders per frame
   - Optimizes for 60fps
   - Reduces unnecessary DOM updates

4. **Computed Values**: For derived state (device filtering, RSSI calculations)
   - `getAvailableDevices()` - Filtered by RSSI range
   - `getRangeLabel()` - Human-readable range labels
   - Cached until dependencies change

5. **Component Registration**: System for state change notifications
   - `onStateChange(callback)` - Register component
   - Callbacks invoked on every state change
   - Components decide if re-render needed

6. **Optimized Updates**: For specific state changes (e.g., refresh animations)
   - Some state changes trigger immediate renders
   - Others can be batched
   - Configurable per state property

**State Structure (Complete):**

**Device Management:**
- `allDevices`: Array of all discovered devices
- `range`: RSSI slider value (0-100, maps to signal strength)
- `moduleNicknames`: Object mapping device IDs to user nicknames
- `lastUpdateTime`: Date of last device scan
- `isRefreshing`: Boolean indicating active device scan

**Connection Status:**
- `hubConnected`: Boolean, true if hub connected
- `hubDeviceName`: String, name of connected hub
- `hubConnecting`: Boolean, true during connection attempt
- `hubConnectionMode`: String, "ble" or "serial"

**UI State:**
- `showSettings`: Boolean, settings overlay visible
- `showDeviceList`: Boolean, device list overlay visible
- `showMessageDetails`: Boolean, message details overlay visible
- `showCommandPalette`: Boolean, command palette expanded
- `flashMessageBox`: Boolean, flash animation on input box
- `editingDeviceId`: String or null, device being edited
- `viewingMessage`: Object or null, message being viewed

**Message System:**
- `messageHistory`: Array of sent messages with metadata
- `currentMessage`: String, currently selected command

**Usage Pattern (Detailed):**

1. **Component Registration:**
```javascript
// Component registers to receive state updates
onStateChange((newState) => {
  // Decide if this component needs to re-render
  if (newState.hubConnected !== this.lastConnected) {
    this.render();
  }
});
```

2. **State Updates:**
```javascript
// Update state and trigger re-renders
setState({
  hubConnected: true,
  hubDeviceName: "USB Serial Hub"
});
// All registered components notified via batched callback
```

3. **Computed Values:**
```javascript
// Get derived state
const devices = getAvailableDevices(); // Filtered by range
const rangeLabel = getRangeLabel(state.range); // "Close", "Far", etc.
```

4. **State Changes Automatically Propagate:**
   - setState() called
   - Updates queued via requestAnimationFrame
   - All registered callbacks invoked
   - Components re-render as needed

---

## Appendix A: Key Metrics

### Performance Targets

- **Initial Load**: < 3 seconds
- **Render Time**: < 16ms (60fps)
- **Connection Time**: < 2 seconds
- **Device Refresh**: < 7 seconds
- **Command Send**: < 500ms

### Code Statistics

- **JavaScript Files**: 25+
- **Python Files**: 3
- **Total Components**: 20
- **State Properties**: 25+
- **Python Functions Exposed**: 16
- **Active Functions**: 11 (69%)

---

**End of Developer Guide**

