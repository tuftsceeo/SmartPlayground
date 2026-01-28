# Serial Message Flow Debug Guide

## ✅ Issue Fixed
**Problem:** `hub_serial.py` was pre-parsing JSON and filtering out non-JSON messages, but `on_serial_data()` expected raw strings.
**Solution:** Modified `hub_serial.py` to pass raw line data to callback instead of parsed JSON.

## 🔍 Console Logging Flow

When the hub sends a device list (every 30s), you should see this sequence in the browser console:

### 1. JavaScript Serial Adapter (serialAdapter.js)
```
🟢 [SerialAdapter] Read 245 bytes: {"type":"devices","timestamp":1408132,"list":[{"id":"M-80d064","mac":"b43a4580d064","rssi":-49...
```

### 2. Python Serial Handler (hub_serial.py)
```
🔵 hub_serial.py: Received 245 bytes
🔵 hub_serial.py: Passing line to callback: {"type":"devices","timestamp":1408132,"list":[...]...
```

### 3. Python Data Callback (main.py - on_serial_data)
```
================================================================================
🟢 on_serial_data() CALLED
📥 Serial data received (245 chars): {"type":"devices","timestamp":1408132,"list":[...]
Data type: <class 'str'>
================================================================================
```

### 4. Python Message Processor (main.py - process_complete_message)
```
🔵 process_complete_message: stripped data = '{"type":"devices","timestamp":1408132...
🔵 process_complete_message: starts with '{' ? True
=== PROCESSING HUB JSON ===
Full JSON message: {"type":"devices","timestamp":1408132,"list":[...]}
✅ JSON parsed successfully: type = 'devices'
🎯 Found 'devices' type - processing device list
Device list length: 5
```

### 5. Python Device Processing (main.py - device list handler)
```
Filtered 5 devices to 5 unique devices
DEBUG SANITIZATION: 'M-80d064' -> 'M-80d064'
DEBUG SANITIZATION: 'M-8614d8' -> 'M-8614d8'
... (one per device)
🟢 Python: Calling window.onDevicesUpdated()
📋 Devices to send: 5 devices
  Device 1: M-80d064 (RSSI: -49, Battery: 74.05%)
  Device 2: M-8614d8 (RSSI: -55, Battery: 73.28%)
  ... (one per device)
⏰ Hub timestamp: 1408132
✅ Converted to JS: 5 devices
✅ onDevicesUpdated() called successfully
Updated 5 devices from hub
```

### 6. JavaScript Device Handler (main.js - onDevicesUpdated)
```
================================================================================
🟢 JavaScript window.onDevicesUpdated() CALLED
📋 Received 5 devices from Python
⏰ Hub timestamp: 1408132
📊 State before update: 0 devices
================================================================================
  Device 1: M-80d064 | RSSI: -49 | Battery: 74.05% | Age: 6008ms | Stale: false
  Device 2: M-8614d8 | RSSI: -55 | Battery: 73.28% | Age: 12016ms | Stale: false
  ... (one per device)
✅ Processed 5 devices, updating state...
✅ State updated! New device count: 5
```

### 7. Hub Debug Messages (non-JSON)
Debug messages from the hub (like `Sent:5 devs`) will appear as:
```
📡 Hub debug: Sent:5 devs
```

## 🐛 Troubleshooting

### If you see NO logs at all:
- Serial port not connected
- Check connection status in settings overlay
- Try reconnecting

### If logs stop at #1 (SerialAdapter):
- `hub_serial.py` callback not set up
- Check line 508 in `main.py`: `serial.on_data_callback = create_proxy(on_serial_data)`

### If logs stop at #2 (hub_serial.py):
- Callback not properly proxied
- Check `create_proxy()` is imported and used

### If logs stop at #4 (process_complete_message):
- JSON parsing failed
- Look for `❌ Failed to parse hub JSON` message
- Check hub JSON format

### If logs stop at #5 (device processing):
- Check for "Missing 'list' field" or similar errors
- Verify hub JSON has `list` array

### If logs stop at #6 (onDevicesUpdated):
- `window.onDevicesUpdated` not defined
- Check main.js initialization (line 165)
- Verify JavaScript loaded before Python

### If logs complete but UI doesn't update:
- Check `state.deviceScanningEnabled === true` in console
- Run `state.allDevices` in console to see if devices are in state
- Check device list overlay rendering logic

## 🧪 Testing Steps

1. **Reload webapp page** to get fresh code with all logging
2. **Open browser console** (F12)
3. **Connect to hub via serial**
4. **Wait 30 seconds** for hub to send first device list
5. **Trace the logs** through all 6 steps above
6. **Identify where flow stops** if devices don't appear

## 🎯 Expected Hub JSON Format

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

## 🔧 Key Files Modified

1. **`mpy/hub_serial.py`** - Fixed to pass raw strings instead of parsed JSON
2. **`main.py`** - Enhanced logging in `on_serial_data()` and `process_complete_message()`
3. **`js/main.js`** - Enhanced logging in `onDevicesUpdated()`
4. **`js/adapters/serialAdapter.js`** - Added read loop logging

## 📊 Success Indicators

✅ Logs flow through all 6 steps
✅ Device count matches hub display (e.g., "Dev:5" → "5 devices")
✅ RSSI values are negative integers (-49, -55, etc.)
✅ Battery percentages are reasonable (0-100%)
✅ `state.allDevices.length` matches received device count
✅ Device list overlay shows devices with battery and last seen info

## ⚠️ Known Issues (Fixed)

- ❌ **OLD:** `hub_serial.py` filtered out non-JSON messages
- ✅ **FIXED:** Now passes all lines to callback as raw strings
- ❌ **OLD:** `on_serial_data()` received dict instead of string
- ✅ **FIXED:** Now receives string data as expected
