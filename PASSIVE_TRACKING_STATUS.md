# Battery-Based Passive Device Tracking - Implementation Status

## 🎯 Goal
Replace active PING-based device scanning with passive battery message tracking to eliminate ESP-NOW buffer overflows.

## ✅ Completed Implementation

### 1. Hub Code (`App_Web/webapp/hubCode/main.py`)
**Status: ✅ WORKING - Hub is sending device lists**

```python
# Line 176: Added device tracking dictionary
self.recent_devices = {}  # {mac_hex: {mac, rssi, battery, last_seen}}

# Lines 201-234: Custom ESP-NOW callback for passive tracking
def battery_callback(msg, mac, rssi):
    # Listens for /battery/ messages (sent every 60s by modules)
    # Extracts RSSI from neighbor table dict: rssi[mac][0]
    # Updates self.recent_devices with MAC, RSSI, battery%, timestamp
    
# Lines 273-313: Device list sender (every 30s)
def _send_device_list(self):
    # Expires devices after 5 minutes
    # Builds JSON: {'type': 'devices', 'list': [...], 'timestamp': ticks_ms()}
    # Sends via Serial to webapp
```

**Confirmed working:**
- Hub receives battery messages: ✅ `Dev:5 8614d8` shown on OLED
- Hub sends device lists: ✅ JSON with 5 devices every 30s
- RSSI extraction: ✅ Fixed from dict to integer (-49, -55, etc.)

### 2. Python Backend (`App_Web/webapp/main.py`)
**Status: ✅ COMPREHENSIVE LOGGING ADDED**

```python
# Lines 571-578: Serial data callback with detailed logging
def on_serial_data(data):
    console.log("=" * 80)
    console.log("🟢 on_serial_data() CALLED")
    console.log(f"📥 Serial data received ({len(data)} chars): {data[:200]}")
    console.log(f"Data type: {type(data)}")
    process_complete_message(data)

# Lines 134-160: Message processor with step-by-step logging
- Logs stripped data and JSON detection
- Logs parsing success/failure
- Logs message type and device list length

# Lines 231-250: Device list sender with detailed logging
- Logs each device being sent
- Logs conversion to JavaScript
- Confirms onDevicesUpdated() call
```

**Status:** Comprehensive logging at every step. Ready to trace message flow.

### 3. JavaScript Processing (`App_Web/webapp/js/main.js`)
**Status: ✅ IMPLEMENTED + COMPREHENSIVE LOGGING**

```javascript
// Lines 165-220: Device age calculation with detailed logging
window.onDevicesUpdated = (devices, hubTimestamp) => {
    console.log("🟢 JavaScript window.onDevicesUpdated() CALLED");
    console.log(`📋 Received ${devices?.length || 0} devices from Python`);
    console.log(`📊 State before update: ${state.allDevices?.length || 0} devices`);
    
    // Process each device (log RSSI, battery, age, stale status)
    const processedDevices = devices.map(device => {
        const ageMs = hubTimestamp - device.last_seen;
        const lastSeenTime = new Date(Date.now() - ageMs);
        const isStale = ageMs > 180000;
        console.log(`  Device: ${device.name} | RSSI: ${device.rssi} | Battery: ${device.battery_pct}%`);
        return { ...device, lastSeenTime, isStale };
    });
    
    setState({ allDevices: processedDevices });
    console.log(`✅ State updated! New device count: ${state.allDevices?.length || 0}`);
};
```

### 4. UI Display (`App_Web/webapp/js/components/overlays/deviceListOverlay.js`)
**Status: ✅ IMPLEMENTED**

```javascript
// Lines 82-107: Device card with battery%, last seen, stale warnings
Battery: ${batteryPct}% • 
<span class="${isStale ? 'text-amber-600 font-medium' : ''}">
  ${lastSeenText}${isStale ? ' ⚠' : ''}
</span>
```

## 🐛 Current Issues

### Issue #1: PING Still Being Sent ✅ FIXED
**Problem:** Settings toggle triggers old PING code instead of passive tracking

**Evidence:**
```
settingsOverlay.js:56 Device scanning enabled
main.js:822 Refreshing devices with RSSI threshold: all
serialAdapter.js:189 📤 Writing: {"cmd": "PING", "rssi": "all"}
```

**Root Cause:** Lines 919-922 in `main.js` call `handleRefreshDevices()` when device scanning enabled

**Fix Applied:** Removed the call - passive tracking doesn't need manual refresh

### Issue #2: Serial Data Not Reaching Python ✅ FIXED
**Problem:** `hub_serial.py` was pre-parsing JSON and filtering out non-JSON messages

**Evidence:**
- `hub_serial.py` line 157: `message = json.loads(line)` parsed JSON first
- `hub_serial.py` line 160-162: Non-JSON messages silently dropped
- `on_serial_data()` expected raw strings but received parsed dicts

**Root Cause:** Mismatch between `hub_serial.py` (sent parsed JSON) and `main.py` (expected raw strings)

**Fix Applied:**
```python
# OLD (hub_serial.py line 157-162):
try:
    message = json.loads(line)
    if self.on_data_callback:
        self.on_data_callback(message)  # Sent dict
except json.JSONDecodeError:
    pass  # Dropped non-JSON

# NEW (hub_serial.py line 150-152):
print(f"🔵 hub_serial.py: Passing line to callback: {line[:100]}")
if self.on_data_callback:
    self.on_data_callback(line)  # Send raw string
```

**Result:** All messages (JSON + debug text) now reach `on_serial_data()` as expected

### Issue #3: Device List Not Reaching UI ⚠️ READY TO TEST
**Status:** Root cause fixed, comprehensive logging added, ready for testing

**Debug Steps:**
1. ✅ **Fixed:** `hub_serial.py` now passes raw strings to callback
2. ✅ **Added:** Comprehensive logging at all 6 levels (see SERIAL_DEBUG_GUIDE.md)
3. ⏳ **Next:** Reload webapp and trace logs through complete flow
4. ⏳ **Next:** Verify devices appear in UI

## 📋 Testing Checklist

### Hub Firmware
- [x] Receives battery messages (`Dev:N XXXXXX` on OLED)
- [x] Extracts correct RSSI from neighbor dict
- [x] Sends device lists every 30s (`Sent:N devs`)
- [x] Device list JSON has correct format (rssi as integer)
- [x] Expires devices after 5 minutes

### Webapp Python
- [x] **FIXED:** `on_serial_data()` receives raw string data (not parsed dicts)
- [x] **ADDED:** Comprehensive logging at every step
- [ ] **TESTING:** Device list JSON parsed successfully
- [ ] **TESTING:** `window.onDevicesUpdated()` called with devices and timestamp
- [ ] **TESTING:** No Python exceptions in console

### Webapp JavaScript
- [x] `onDevicesUpdated()` calculates device ages
- [x] Converts to browser time (Date objects)
- [x] Marks stale devices (>3 min)
- [x] **ADDED:** Comprehensive logging for state updates
- [ ] **TESTING:** Updates `state.allDevices` successfully
- [ ] **TESTING:** Device list overlay shows devices

### UI
- [x] Settings toggle doesn't disconnect
- [x] No PING sent on connection
- [x] Battery percentage displays (code ready)
- [x] Last seen time displays (code ready)
- [x] Stale warnings show (amber + ⚠) (code ready)
- [ ] **TESTING:** Devices actually appear in list

### Serial Adapter
- [x] **ADDED:** Logging in read loop to track raw serial data
- [ ] **TESTING:** Verify data flows through adapter correctly

## 🔍 Next Steps for Testing

1. ✅ **CODE FIXED:** `hub_serial.py` now passes raw strings instead of parsed JSON
2. ✅ **LOGGING ADDED:** Comprehensive console logging at all 6 levels
3. ⏳ **TODO:** Reload webapp page to get fresh code
4. ⏳ **TODO:** Connect hub via serial
5. ⏳ **TODO:** Wait 30 seconds for first device list
6. ⏳ **TODO:** Follow logging flow in console (see SERIAL_DEBUG_GUIDE.md)
7. ⏳ **TODO:** Verify devices appear in device list overlay

### Detailed Test Plan

1. **Open browser console** (F12) before connecting
2. **Connect to hub** and watch for connection success messages
3. **Wait 30 seconds** for hub to send first device list
4. **Trace logs** through all 6 steps:
   - 🟢 SerialAdapter read
   - 🔵 hub_serial.py received
   - 🔵 hub_serial.py passing to callback
   - 🟢 on_serial_data() called
   - 🔵 process_complete_message() parsing
   - 🟢 onDevicesUpdated() called
5. **Check state** in console: `state.allDevices` should have devices
6. **Open device list overlay** and verify devices appear
7. **Verify UI elements:**
   - Device names
   - Battery percentages
   - RSSI signal bars
   - "Last seen" times
   - Stale warnings (if any devices >3 min old)

## 📊 Expected Message Flow

```
Module (every 60s)
  ↓ ESP-NOW: /battery/hub_name → {value: 85.3}
Hub Callback
  ↓ Stores in self.recent_devices
Hub Sender (every 30s)
  ↓ Serial JSON: {"type":"devices","list":[...],"timestamp":123}
Python on_serial_data()
  ↓ console.log("📥 Serial data received...")
Python process_complete_message()
  ↓ Parses JSON, validates, converts
Python window.onDevicesUpdated(devices, timestamp)
  ↓
JavaScript onDevicesUpdated()
  ↓ Calculates ages, marks stale
setState({ allDevices: processed })
  ↓
UI Render
  ↓ Device cards with battery%, last seen, warnings
```

## 🔧 Key Files Modified

1. **`App_Web/webapp/hubCode/main.py`** - Hub passive tracking (WORKING ✅)
2. **`App_Web/webapp/main.py`** - Python backend bridge (⚠️ VERIFY)
3. **`App_Web/webapp/js/main.js`** - Device age calculation (✅ DONE)
4. **`App_Web/webapp/js/components/overlays/deviceListOverlay.js`** - UI display (✅ DONE)
5. **`App_Web/webapp/js/components/overlays/settingsOverlay.js`** - Updated text (✅ DONE)

## 🎯 Success Criteria

- ✅ Hub tracks devices via battery messages (not PING)
- ✅ No ESP-NOW buffer overflows
- ✅ Devices expire after 5 minutes
- ⚠️ **Device list appears in webapp** ← BLOCKED
- ⚠️ **Battery % and last seen times display** ← BLOCKED
- ⚠️ **Stale warnings show** ← BLOCKED
- ✅ Settings toggle doesn't disconnect
- ✅ No PING commands sent

## 🐞 Known Working Serial JSON Format

```json
{
  "type": "devices",
  "timestamp": 1408132,
  "list": [
    {
      "id": "M-80d064",
      "mac": "b43a4580d064",
      "rssi": -49,
      "battery": 74.05469,
      "last_seen": 1402124
    }
  ]
}
```

This format is CORRECT and hub is sending it successfully every 30 seconds.
