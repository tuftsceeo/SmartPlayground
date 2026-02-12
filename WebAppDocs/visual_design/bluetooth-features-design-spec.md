# Bluetooth Connectivity Features - Design Specification

## Overview
This document specifies new Bluetooth connectivity features for the Smart Playground Control App. These features have been prototyped in React and need to be implemented in the existing vanilla JavaScript version.

**Critical Design Principle**: All layout changes must maintain visual stability. Elements should never shift position when toggling between connected/disconnected states.

---

## 1. State Management

### New State Properties
Add the following properties to the application's state object:

```javascript
state = {
  // ... existing properties
  isBluetoothConnected: false,      // Boolean: BLE connection status
  showSettings: false,               // Boolean: Settings overlay visibility
  showConnectionWarning: false,      // Boolean: Connection warning modal visibility
  flashMessageBox: false            // Boolean: Message box flash animation state
}
```

### State Dependencies
- `availableModules` array should be empty (`[]`) when `isBluetoothConnected === false`
- Device filtering logic should check BLE status first before RSSI filtering

---

## 2. Header Section: Bluetooth Status Integration

### Layout Structure
The "To:" section must incorporate BLE status controls **inline** with the existing device count display.

### HTML Structure
```html
<div class="bg-white border-b border-gray-200 px-4 py-2" onclick="handleRecipientsClick()">
  <div class="flex items-center gap-3 mb-2">
    <span class="text-gray-500 text-sm">To:</span>
    <span class="text-gray-700 text-sm font-medium">{deviceCount} devices</span>
    
    <!-- BLE Status Controls (right-aligned) -->
    <div class="flex items-center gap-1 ml-auto">
      <!-- BLE Status Button -->
      <button class="ble-status-button" onclick="handleBluetoothToggle(event)">
        <div class="status-dot"></div>
        <span class="status-text">{statusText}</span>
        <div class="flex-1"></div>
        <svg class="bluetooth-icon"><!-- Bluetooth icon --></svg>
      </button>
      
      <!-- Settings Button -->
      <button class="settings-button" onclick="handleSettingsClick(event)">
        <svg class="settings-icon"><!-- Settings icon --></svg>
      </button>
    </div>
  </div>
  
  <!-- Device Icons or Placeholder -->
  <div class="device-icons-container">
    <!-- Content depends on connection state -->
  </div>
  
  <!-- Range Slider -->
  <div class="range-slider-container">
    <!-- Existing range slider -->
  </div>
</div>
```

### BLE Status Button Specifications

#### Fixed Dimensions
- **Width**: `130px` (fixed, not min-width)
- **Padding**: `0.5rem` (8px) horizontal, `0.25rem` (4px) vertical
- **Border radius**: `0.5rem` (8px)
- **Display**: `flex`
- **Align items**: `center`
- **Gap**: `0.375rem` (6px)

#### Connected State Styling
```css
.ble-status-button.connected {
  background: transparent;
  transition: background-color 0.2s;
}

.ble-status-button.connected:hover {
  background: #f3f4f6; /* gray-100 */
}

.ble-status-button.connected .status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e; /* green-500 */
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  flex-shrink: 0;
}

.ble-status-button.connected .status-text {
  font-size: 0.75rem; /* 12px */
  color: #4b5563; /* gray-600 */
  flex-shrink: 0;
}

.ble-status-button.connected .bluetooth-icon {
  width: 14px;
  height: 14px;
  color: #16a34a; /* green-600 */
  flex-shrink: 0;
}
```

#### Disconnected State Styling
```css
.ble-status-button.disconnected {
  background: #fef3c7; /* amber-100 */
  transition: background-color 0.2s;
}

.ble-status-button.disconnected:hover {
  background: #fde68a; /* amber-200 */
}

.ble-status-button.disconnected .status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f59e0b; /* amber-500 */
  flex-shrink: 0;
}

.ble-status-button.disconnected .status-text {
  font-size: 0.75rem; /* 12px */
  color: #92400e; /* amber-800 */
  font-weight: 500;
  flex-shrink: 0;
}

.ble-status-button.disconnected .bluetooth-icon {
  width: 14px;
  height: 14px;
  color: #b45309; /* amber-700 */
  flex-shrink: 0;
}
```

#### Spacer Element
**Critical**: A `flex-1` spacer div must be placed between the status text and Bluetooth icon to prevent the icon from shifting position when text changes from "Connected" (9 characters) to "Disconnected" (12 characters).

```html
<div class="flex-1"></div>
```

### Settings Button Specifications
- **Width/Height**: `32px` (2rem)
- **Display**: Always visible (never conditionally hidden)
- **Border radius**: `50%` (full circle)
- **Flex-shrink**: `0`
- **Background**: Transparent, hover state `#f3f4f6` (gray-100)
- **Icon size**: `16px` (1rem)
- **Icon color**: `#4b5563` (gray-600)

---

## 3. Device Icons Area

### Container Specifications
```css
.device-icons-container {
  display: flex;
  align-items: center;
  margin-left: -0.5rem; /* -space-x-2 effect */
  margin-bottom: 0.5rem;
  min-height: 48px; /* CRITICAL: prevents layout shift */
}
```

### Connected State (Devices Available)
Show actual device icons as per existing design:
- 48px diameter circles
- Device type icons (Smartphone, Box, CircleDot)
- Overlapping with negative margin
- Border: 2px white

### Disconnected State (Zero Devices)
Show single placeholder icon:

```html
<div class="placeholder-icon">
  <svg class="bluetooth-off-icon"><!-- BluetoothOff icon --></svg>
</div>
```

#### Placeholder Styling
```css
.placeholder-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #e5e7eb; /* gray-200 */
  background: white;
}

.bluetooth-off-icon {
  width: 24px;
  height: 24px;
  color: #d1d5db; /* gray-300 */
}
```

**Design Rationale**: The white background with light gray icon clearly distinguishes this placeholder from active device icons (which have gray-500/gray-600 backgrounds).

---

## 4. Device Overlay Enhancements

### Disconnected State View

When `isBluetoothConnected === false`, replace the device list section with a connection prompt.

#### HTML Structure
```html
<div class="connection-prompt">
  <svg class="bluetooth-off-large"><!-- BluetoothOff icon --></svg>
  <div class="prompt-heading">Bluetooth Disconnected</div>
  <button class="connect-button" onclick="handleBluetoothToggle(event)">
    <svg class="bluetooth-icon-small"><!-- Bluetooth icon --></svg>
    Connect
  </button>
</div>
```

#### Styling Specifications
```css
.connection-prompt {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 1rem; /* py-16 px-4 */
}

.bluetooth-off-large {
  width: 48px;
  height: 48px;
  color: #9ca3af; /* gray-400 */
  margin-bottom: 1rem;
}

.prompt-heading {
  font-size: 0.875rem; /* 14px */
  font-weight: 500;
  color: #111827; /* gray-900 */
  margin-bottom: 1.5rem;
}

.connect-button {
  padding: 0.625rem 1.5rem; /* py-2.5 px-6 */
  background: #d97706; /* amber-600 */
  color: white;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: background-color 0.2s;
}

.connect-button:hover {
  background: #b45309; /* amber-700 */
}

.bluetooth-icon-small {
  width: 16px;
  height: 16px;
}
```

### Connected State View
Display normal device list as per existing implementation.

---

## 5. Connection Warning Modal

### Trigger Conditions
Show modal when:
1. User clicks send button AND
2. `isBluetoothConnected === false`

### HTML Structure
```html
<div class="modal-backdrop" onclick="handleModalBackdropClick()">
  <div class="modal-card" onclick="event.stopPropagation()">
    <div class="modal-content">
      <svg class="modal-icon"><!-- BluetoothOff icon --></svg>
      <div class="modal-heading">Bluetooth Disconnected</div>
      <button class="modal-primary-button" onclick="handleModalConnect()">
        <svg class="button-icon"><!-- Bluetooth icon --></svg>
        Connect
      </button>
      <button class="modal-secondary-button" onclick="handleModalCancel()">
        Cancel
      </button>
    </div>
  </div>
</div>
```

### Modal Styling
```css
.modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-card {
  background: white;
  border-radius: 1rem;
  padding: 2rem;
  margin: 0 1rem;
  max-width: 384px; /* 24rem */
}

.modal-content {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.modal-icon {
  width: 48px;
  height: 48px;
  color: #9ca3af; /* gray-400 */
  margin-bottom: 1rem;
}

.modal-heading {
  font-size: 1.125rem; /* 18px */
  font-weight: 600;
  color: #111827; /* gray-900 */
  margin-bottom: 1.5rem;
}

.modal-primary-button {
  width: 100%;
  padding: 0.625rem 1.5rem;
  background: #d97706; /* amber-600 */
  color: white;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  transition: background-color 0.2s;
}

.modal-primary-button:hover {
  background: #b45309; /* amber-700 */
}

.modal-secondary-button {
  font-size: 0.875rem;
  color: #6b7280; /* gray-500 */
  transition: color 0.2s;
}

.modal-secondary-button:hover {
  color: #374151; /* gray-700 */
}

.button-icon {
  width: 16px;
  height: 16px;
}
```

### Modal Behavior
- **Show**: Set `state.showConnectionWarning = true`, render modal
- **Hide**: Click backdrop or Cancel button sets `state.showConnectionWarning = false`
- **Connect**: Calls `handleBluetoothToggle()`, then hides modal

---

## 6. Send Button Feedback System

### Updated `handleSendMessage()` Logic

```javascript
function handleSendMessage() {
  // PRIORITY 1: Check Bluetooth connection
  if (!state.isBluetoothConnected) {
    showConnectionWarningModal();
    return;
  }
  
  // PRIORITY 2: Check message selection
  if (!state.currentMessage) {
    if (!state.showStickers) {
      // Drawer closed - open it
      state.showStickers = true;
      render();
    } else {
      // Drawer already open - flash message box
      flashMessageBox();
    }
    return;
  }
  
  // PRIORITY 3: Send message
  if (state.availableModules.length > 0) {
    // ... existing send logic
  }
}
```

### Message Box Flash Animation

#### Trigger
When drawer is open and user clicks send without selecting a command.

#### Implementation
```javascript
function flashMessageBox() {
  const messageBox = document.querySelector('.message-input-box');
  messageBox.classList.add('flash-active');
  
  setTimeout(() => {
    messageBox.classList.remove('flash-active');
  }, 500);
}
```

#### CSS
```css
.message-input-box {
  flex: 1;
  background: #f3f4f6; /* gray-100 */
  border-radius: 9999px;
  padding: 0.625rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: text;
  transition: all 0.2s;
}

.message-input-box.flash-active {
  background: #fffbeb; /* amber-50 */
  box-shadow: 0 0 0 2px #fbbf24; /* amber-400 ring */
}
```

---

## 7. Command Drawer Behavior Updates

### Click-Away Detection

The command drawer should close when clicking anywhere **except**:
1. The command palette itself
2. The message input area
3. Modal overlays

#### Implementation
```javascript
function handleClickAway(event) {
  if (!state.showStickers) return;
  
  // Check if click is outside allowed areas
  const isCommandPalette = event.target.closest('.command-palette');
  const isMessageInput = event.target.closest('.message-input-area');
  
  if (!isCommandPalette && !isMessageInput) {
    state.showStickers = false;
    render();
  }
}

// Attach to document
document.addEventListener('click', handleClickAway);
```

#### Required CSS Classes
Add these classes to existing elements:
- `.command-palette` - on the command palette container div
- `.message-input-area` - on the message input wrapper div

---

## 8. Settings Overlay

### Basic Implementation
Settings button is always visible but overlay is initially a placeholder.

#### HTML Structure
```html
<div class="settings-overlay">
  <div class="settings-header">
    <button class="back-button" onclick="handleSettingsBack()">
      <svg><!-- ArrowLeft icon --></svg>
    </button>
    <h2 class="settings-title">Settings</h2>
  </div>
  <div class="settings-content">
    <div class="placeholder-text">Settings placeholder</div>
  </div>
</div>
```

#### Styling
```css
.settings-overlay {
  position: absolute;
  inset: 0;
  background: white;
  z-index: 50;
  display: flex;
  flex-direction: column;
}

.settings-header {
  background: white;
  border-bottom: 1px solid #e5e7eb;
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.back-button {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background-color 0.2s;
}

.back-button:hover {
  background: #f3f4f6;
}

.settings-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #111827;
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.placeholder-text {
  text-align: center;
  color: #9ca3af;
  padding: 3rem 0;
  font-size: 0.875rem;
}
```

---

## 9. Event Handlers

### New Event Handlers Required

```javascript
function handleBluetoothToggle(event) {
  event.stopPropagation(); // Prevent triggering parent click handlers
  state.isBluetoothConnected = !state.isBluetoothConnected;
  
  // Update available modules based on connection state
  if (!state.isBluetoothConnected) {
    state.availableModules = [];
  } else {
    // Re-filter based on RSSI and current range
    updateAvailableModules();
  }
  
  render();
}

function handleSettingsClick(event) {
  event.stopPropagation();
  state.showSettings = true;
  render();
}

function handleSettingsBack() {
  state.showSettings = false;
  render();
}

function showConnectionWarningModal() {
  state.showConnectionWarning = true;
  render();
}

function handleModalBackdropClick() {
  state.showConnectionWarning = false;
  render();
}

function handleModalCancel() {
  state.showConnectionWarning = false;
  render();
}

function handleModalConnect() {
  handleBluetoothToggle({ stopPropagation: () => {} });
  state.showConnectionWarning = false;
  render();
}
```

---

## 10. Integration Checklist

### Step 1: State Setup
- [ ] Add new state properties
- [ ] Update `availableModules` filtering logic to check BLE status

### Step 2: Header Section
- [ ] Modify "To:" section HTML generation
- [ ] Add BLE status button with exact styling
- [ ] Add settings button
- [ ] Implement placeholder icon for zero devices
- [ ] Test layout stability during state toggles

### Step 3: Device Overlay
- [ ] Add conditional rendering for disconnected state
- [ ] Implement connection prompt view
- [ ] Verify range slider behavior (should it be disabled when disconnected?)

### Step 4: Modal System
- [ ] Create connection warning modal HTML generation
- [ ] Implement show/hide logic
- [ ] Add backdrop click handler
- [ ] Test Connect and Cancel actions

### Step 5: Send Button Logic
- [ ] Update `handleSendMessage()` with priority checks
- [ ] Implement message box flash animation
- [ ] Test all feedback scenarios

### Step 6: Drawer Behavior
- [ ] Update click-away detection
- [ ] Add required CSS classes to existing elements
- [ ] Test drawer closing on various clicks

### Step 7: Settings
- [ ] Implement basic settings overlay
- [ ] Add back button handler
- [ ] Ensure overlay z-index hierarchy is correct

### Step 8: Visual Testing
- [ ] Test all state transitions
- [ ] Verify no layout shifting
- [ ] Check responsive behavior
- [ ] Validate color consistency
- [ ] Test hover states

---

## 11. Color Palette Reference

### Connection Status Colors
```css
/* Connected (Green) */
--green-500: #22c55e;  /* Pulsing dot */
--green-600: #16a34a;  /* Icon */

/* Disconnected (Amber) */
--amber-50: #fffbeb;   /* Flash background */
--amber-100: #fef3c7;  /* Button background */
--amber-200: #fde68a;  /* Button hover */
--amber-400: #fbbf24;  /* Flash ring */
--amber-500: #f59e0b;  /* Status dot */
--amber-600: #d97706;  /* Primary buttons */
--amber-700: #b45309;  /* Button hover, icon */
--amber-800: #92400e;  /* Status text */
```

### Neutral Colors
```css
--gray-100: #f3f4f6;   /* Hover states */
--gray-200: #e5e7eb;   /* Borders */
--gray-300: #d1d5db;   /* Placeholder icon */
--gray-400: #9ca3af;   /* Disabled text */
--gray-500: #6b7280;   /* Secondary text */
--gray-600: #4b5563;   /* Primary text */
--gray-700: #374151;   /* Text hover */
--gray-900: #111827;   /* Headings */
```

---

## 12. Accessibility Notes

### Focus States
Add focus styles for all interactive elements:
```css
button:focus-visible {
  outline: 2px solid #3b82f6; /* blue-500 */
  outline-offset: 2px;
}
```

### ARIA Labels
Add appropriate labels:
- BLE button: `aria-label="Bluetooth connection status: {connected|disconnected}"`
- Settings button: `aria-label="Open settings"`
- Modal: `role="dialog"`, `aria-modal="true"`

### Keyboard Navigation
- Modal: Focus trap within modal when open
- Close modal: ESC key support
- Tab order: Logical flow through interactive elements

---

## 13. Testing Scenarios

### Scenario 1: Initial Load (Disconnected)
- BLE button shows amber "Disconnected"
- 0 devices shown
- Placeholder BluetoothOff icon visible
- Send button appears enabled but shows warning when clicked

### Scenario 2: Connecting BLE
- Click BLE button
- Button changes to "Connected" with green styling
- Devices appear (filtered by RSSI)
- Placeholder icon replaced with device icons

### Scenario 3: Send Without Command (Connected)
- Click send with empty message, drawer closed → Opens drawer
- Click send with empty message, drawer open → Flash animation

### Scenario 4: Send Without Command (Disconnected)
- Click send → Connection warning modal appears
- Modal backdrop click → Modal closes
- Modal Connect button → Toggles BLE, closes modal
- Modal Cancel → Closes modal

### Scenario 5: Layout Stability
- Toggle BLE status multiple times
- Verify no elements shift position
- Verify button text doesn't push icon
- Verify device icon area height remains constant

---

## 14. Implementation Notes

### Performance Considerations
- Flash animation uses CSS transitions (hardware accelerated)
- Modal backdrop uses `rgba()` for transparency (performant)
- State updates trigger single render pass

### Browser Compatibility
- All CSS uses standard properties
- Flexbox layout (widely supported)
- No CSS Grid dependencies
- Event handlers use standard DOM APIs

### Code Organization
- Keep BLE-related logic in separate section
- Modal rendering can be modular function
- Event handlers should be top-level functions
- State updates should trigger single `render()` call

---

## End of Specification

This document provides complete specifications for implementing Bluetooth connectivity features in the vanilla JavaScript version of the Smart Playground Control App. All measurements, colors, and behaviors match the React prototype exactly.
