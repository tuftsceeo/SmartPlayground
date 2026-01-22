# Battery-Based Device Tracking Implementation

## Overview

This implementation adds device visibility to the webapp by tracking battery messages sent by modules. Unlike the non-functional device scanning approach, this is a **one-way passive tracking system** that works within the hardware constraints.

**Key Principle:** Hub listens for battery messages, webapp displays what was heard. No bidirectional syncing.

---

## System Architecture

### Data Flow (One Direction Only)

```
Modules → Battery Messages (1/min) → Hub → Tracking Dict → Serial (30s) → Webapp → Display
```

**No responses sent back to modules** - this avoids the buffer overflow issues that made device scanning non-functional.

---

## Technical Constraints

### Why This Works (vs Device Scanning)

| Approach | Traffic Pattern | Result |
|----------|----------------|--------|
| Device Scanning (broken) | Hub broadcasts PING → All modules respond simultaneously | Buffer overflow ❌ |
| Battery Tracking (working) | Modules independently send battery → Hub passively listens | No congestion ✓ |

### Timing Parameters

- **Module battery send interval:** 60 seconds (already implemented in main.py)
- **Hub send to webapp interval:** 30 seconds (batches all updates)
- **Device expiry time:** 5 minutes (300 seconds)
- **Stale indicator threshold:** 3 minutes (180 seconds = 2 missed updates)

---

## Implementation Details

### 1. Hub Changes (App_Hub/simple_usb_hub/main.py)

#### Pattern Used: Override connect() (Like Now_sniffer.py)

The hub follows the **Now_sniffer.py pattern** of completely overriding `connect()` to customize the ESP-NOW callback:

```python
# games/Now_sniffer.py example:
class Controller(Control):
    def connect(self):
        def my_callback(msg, mac, rssi):
            self.queue.append((msg, mac, rssi))  # Custom behavior
        
        self.n = now.Now(my_callback)
        self.n.connect(False)
```

#### Hub Data Structure

```python
self.recent_devices = {
    'aa:bb:cc:dd:ee:ff': {
        'rssi': -45,
        'battery': 85,
        'last_seen': 123456789  # time.ticks_ms()
    }
}
```

#### Modified Methods

**SimpleHub.__init__():**
- Add `self.recent_devices = {}`
- Add `self.last_device_list_send = 0`

**SimpleHub.connect():**
- Override completely (don't call parent)
- Custom callback tracks battery messages
- Update `recent_devices` dict on `/battery` topic
- Ignore all other messages (no responses)

**New: SimpleHub._cleanup_expired_devices():**
- Remove entries where `ticks_diff(now, last_seen) > 300000`
- Called before each device list send

**New: SimpleHub._send_device_list():**
- Convert dict to list: `[{'id': mac, 'rssi': ..., 'battery': ..., 'last_seen': ...}]`
- Send JSON: `{'type': 'devices', 'list': [...], 'timestamp': current_ticks}`
- Include hub timestamp for webapp time calculations

**SimpleHub.run():**
- Add timer check every loop iteration
- Every 30 seconds: cleanup + send device list
- Uses `time.ticks_diff()` for accurate timing

---

### 2. Webapp Python Changes (App_Web/webapp/main.py)

#### Critical Architecture: Python Does I/O ONLY

Following the tested pattern where Python handles browser APIs and JavaScript has all logic:

**Modified: on_serial_data():**

```python
elif parsed.get("type") == "devices":
    # Device list from hub
    devices = parsed.get("list", [])
    hub_timestamp = parsed.get("timestamp", 0)
    
    # Convert to JS array (minimal processing)
    js_devices = to_js(devices, dict_converter=Object.fromEntries)
    
    # Pass to JavaScript for ALL logic
    if hasattr(window, 'onDevicesUpdated'):
        window.onDevicesUpdated(js_devices, hub_timestamp)
```

**What Python does NOT do:**
- No time calculations
- No state management
- No data transformation beyond JSON parsing
- No business logic

---

### 3. Webapp JavaScript Changes

#### 3a. main.js - Callback Handler

**New/Modified: window.onDevicesUpdated():**

```javascript
window.onDevicesUpdated = (devices, hubTimestamp) => {
    console.log(`Received ${devices.length} devices from hub`);
    
    // Hub timestamp is in ticks_ms(), convert to webapp time
    const now = Date.now();
    
    // Process each device with relative timestamps
    const processedDevices = [];
    for (let i = 0; i < devices.length; i++) {
        const d = devices[i];
        
        // Calculate when device was last seen in webapp time
        // hubTimestamp - d.last_seen = milliseconds ago on hub
        const ageMs = hubTimestamp - d.last_seen;
        const lastSeenTime = new Date(now - ageMs);
        
        processedDevices.push({
            id: d.id,           // MAC address
            name: d.id,         // Use MAC as name (nicknames applied in UI)
            type: 'module',
            rssi: d.rssi,
            battery: d.battery,
            lastSeenTime: lastSeenTime,
            isStale: ageMs > 180000  // >3 minutes = stale (2 missed updates)
        });
    }
    
    setState({
        allDevices: processedDevices,
        lastUpdateTime: new Date(),
        isRefreshing: false
    });
};
```

**Key Calculations:**

1. **Time conversion:** Hub uses `time.ticks_ms()`, webapp uses `Date.now()`
2. **Age calculation:** `hubTimestamp - device.last_seen = ageMs`
3. **Webapp timestamp:** `now - ageMs = lastSeenTime`
4. **Stale detection:** `ageMs > 180000` (3 minutes = 2 missed 1-minute updates)

#### 3b. deviceListOverlay.js - Display Updates

**Modified: Device card rendering:**

```javascript
card.innerHTML += `
  <div class="flex-1 min-w-0">
    <div class="font-medium text-gray-900">${displayName}</div>
    <div class="text-xs text-gray-500 flex items-center gap-2">
      <span>RSSI: ${device.rssi} dBm</span>
      <span>•</span>
      <span>Battery: ${device.battery}%</span>
      <span>•</span>
      <span class="${device.isStale ? 'text-amber-600 font-medium' : ''}">
        ${device.isStale ? '⚠ ' : ''}${getRelativeTime(device.lastSeenTime)}
      </span>
    </div>
  </div>
  ${device.isStale ? '<i data-lucide="help-circle" class="w-5 h-5 text-amber-500"></i>' : ''}
`;
```

**Visual Indicators:**

- **Fresh (<3 min):** Normal text, no icon
- **Stale (>3 min):** Amber text, warning icon, "⚠" prefix
- **Expired (>5 min):** Not shown (removed by hub cleanup)

---

## Message Format Specification

### Hub → Webapp (Serial JSON)

```json
{
  "type": "devices",
  "list": [
    {
      "id": "aa:bb:cc:dd:ee:ff",
      "rssi": -45,
      "battery": 85,
      "last_seen": 123456789
    }
  ],
  "timestamp": 123489000
}
```

**Field Descriptions:**
- `type`: Always "devices" for device list messages
- `list`: Array of device objects
- `id`: MAC address as string (colon-separated hex)
- `rssi`: Signal strength in dBm (negative integer)
- `battery`: Percentage 0-100
- `last_seen`: Hub's `time.ticks_ms()` when battery message received
- `timestamp`: Hub's `time.ticks_ms()` when list was sent

---

## State Management

### Hub State (Ephemeral)

```python
self.recent_devices = {}  # Cleared on restart
self.last_device_list_send = 0  # Reset on restart
```

**No persistence** - hub doesn't remember devices across reboots.

### Webapp State (Existing Structure)

```javascript
state.allDevices = [
  {
    id: "aa:bb:cc:dd:ee:ff",
    name: "aa:bb:cc:dd:ee:ff",  // Or nickname if set
    type: "module",
    rssi: -45,
    battery: 85,
    lastSeenTime: Date,  // JavaScript Date object
    isStale: false
  }
]
```

---

## Timing Analysis

### Normal Operation Timeline

```
T+0s:   Module sends battery → Hub receives → Updates recent_devices
T+30s:  Hub cleanup (no expired) → Send device list → Webapp displays
T+60s:  Module sends battery → Hub receives → Updates recent_devices
T+60s:  Hub cleanup (no expired) → Send device list → Webapp displays
T+90s:  Hub cleanup (no expired) → Send device list → Webapp displays
T+120s: Module sends battery → Hub receives → Updates recent_devices
T+120s: Hub cleanup (no expired) → Send device list → Webapp displays
T+180s: Last update 3min ago → Device marked STALE (⚠ warning)
T+300s: Last update 5min ago → Device EXPIRED (removed from list)
```

### Why 30s Hub Send Interval?

- **Too frequent (e.g., 1s):** Unnecessary serial traffic
- **Too infrequent (e.g., 60s):** Webapp feels unresponsive
- **30s sweet spot:** 
  - Receives 1-2 battery updates per send
  - Smooth UI updates without lag
  - Batches updates if multiple devices send simultaneously

---

## Testing Checklist

### Hub Testing

- [ ] Hub starts and overrides connect() successfully
- [ ] Battery messages update recent_devices dict
- [ ] Device list sent every 30s via serial
- [ ] Expired devices removed after 5 minutes
- [ ] Multiple simultaneous battery messages handled
- [ ] Hub doesn't crash with empty device list

### Webapp Testing

- [ ] Python parses 'devices' message type
- [ ] JavaScript receives callback with correct data
- [ ] Time calculations produce correct lastSeenTime
- [ ] Stale detection triggers at 3 minutes
- [ ] Device list overlay displays all fields
- [ ] Warning icon appears for stale devices
- [ ] Nicknames apply correctly
- [ ] Relative time updates naturally

### Integration Testing

- [ ] End-to-end: Module battery → Hub → Webapp display
- [ ] Multiple devices tracked independently
- [ ] Device expiry removes from webapp list
- [ ] Hub restart clears device list (expected)
- [ ] No buffer overflows or crashes during operation

---

## Differences from Device Scanning

| Feature | Device Scanning (Broken) | Battery Tracking (Working) |
|---------|-------------------------|---------------------------|
| **Initiation** | Hub broadcasts PING | Modules send independently |
| **Traffic Pattern** | Burst (all respond at once) | Distributed (1/min per device) |
| **Hub Action** | Send + Receive | Receive only |
| **Buffer Load** | High (simultaneous responses) | Low (staggered messages) |
| **Reliability** | Non-functional (overflows) | Stable (tested) |
| **User Control** | User triggers scan | Passive observation |
| **Discovery Speed** | 5 seconds (if working) | Up to 60 seconds |
| **Settings Toggle** | deviceScanningEnabled | Always on (passive) |

---

## Future Enhancements (Not Implemented)

### Possible Improvements

1. **Battery icon visualization:** Color-coded battery level indicator
2. **RSSI history:** Track signal strength over time
3. **Device type detection:** Parse module type from messages
4. **Hub persistence:** Store devices in flash (requires write cycles)
5. **Manual refresh button:** Force immediate device list send

### Why Not Implemented Now

- **Scope:** Minimal viable feature first
- **Testing:** Prove core concept before adding complexity
- **Hardware:** Flash writes have limited cycles
- **UI:** Keep interface simple and fast

---

## Troubleshooting

### Hub not sending device list

**Check:**
1. Are modules sending battery messages? (see main.py game loop)
2. Is hub's connect() override working? (check debug output)
3. Is 30s timer triggering? (add debug print in run loop)

### Webapp not displaying devices

**Check:**
1. Is Python parsing 'devices' messages? (console.log in on_serial_data)
2. Is window.onDevicesUpdated defined? (check browser console)
3. Are time calculations correct? (verify lastSeenTime values)

### Devices disappearing prematurely

**Check:**
1. Module battery send interval (should be 60s)
2. Hub expiry time (should be 300000ms = 5min)
3. Hub timestamp vs device last_seen calculations

### Stale warnings not appearing

**Check:**
1. Is ageMs calculation correct? (hubTimestamp - last_seen)
2. Is 180000ms threshold correct? (3 minutes)
3. Is CSS applying amber color? (check browser inspector)

---

## Code Style Notes

### Hub Code (MicroPython)

- Use `time.ticks_ms()` for timestamps
- Use `time.ticks_diff()` for time comparisons
- Print debug to `sys.stderr`, JSON to `stdout`
- Follow existing SerialBridge pattern
- Keep methods under 20 lines when possible

### Webapp Python Code (PyScript)

- Minimal logic - I/O only
- Use `to_js()` for data conversion
- Call JavaScript callbacks for all logic
- No state management in Python
- Follow existing on_serial_data pattern

### Webapp JavaScript Code

- All business logic lives here
- Use setState() for all state changes
- Use computed getters for derived values
- Follow existing callback pattern
- Keep rendering pure (no side effects)

---

## Summary

This implementation provides **passive device visibility** without triggering the buffer overflow issues that made active device scanning non-functional. By leveraging battery messages that modules already send, the webapp gains awareness of nearby devices without requiring bidirectional communication or complex synchronization protocols.

**Key Success Factors:**
1. One-way data flow (no responses)
2. Staggered timing (not simultaneous)
3. Batched updates (30s hub interval)
4. Minimal hub state (just recent devices)
5. JavaScript owns all logic (Python does I/O only)
