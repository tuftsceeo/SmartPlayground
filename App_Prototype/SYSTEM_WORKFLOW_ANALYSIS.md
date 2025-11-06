# 🔄 Smart Playground System Workflow Analysis

**Date:** November 6, 2025  
**Purpose:** Complete system architecture documentation for debugging and redesign  
**Status:** Hub not receiving module ESP-NOW responses reliably

---

## 📊 Current System Architecture

### **Overview**
The system uses a **request-response polling pattern** where the web app initiates device discovery scans via the hub, which then broadcasts to modules and collects responses.

```
┌─────────────┐        ┌──────────┐        ┌──────────────┐
│   Web App   │◄──────►│   Hub    │◄──────►│   Modules    │
│  (Browser)  │  BLE   │  (ESP32) │ ESP-NOW│  (ESP32-C3)  │
└─────────────┘        └──────────┘        └──────────────┘
```

---

## 🔀 Complete Message Flow: App → Module → App

### **Phase 1: User Initiates Device Scan from Web App**

**App (`main.js`):**
```javascript
// User clicks refresh or connects to hub
sendCommand(`"PING":"${rssiThreshold}"`)  // e.g., "PING":"-54"
```

**Transmission:** BLE UART (Nordic UART Service)  
**Format:** String with newline terminator: `"PING":"-54"\n`

---

### **Phase 2: Hub Receives BLE Command**

**Hub BLE Interrupt Handler (`handle_cmd`):**
```python
def handle_cmd(chunk):
    # Called by BLE UART IRQ when data arrives
    global _rxbuf, ble_command_buffer
    _rxbuf += chunk  # Accumulate bytes
    
    while b"\n" in _rxbuf:
        line, _, _rxbuf = _rxbuf.partition(b"\n")
        command = line.decode().strip()
        ble_command_buffer.append(command)  # Buffer for main loop
```

**Timing:** IRQ-triggered (immediate, <1ms)  
**Current State:** ✅ Working correctly

---

### **Phase 3: Hub Main Loop Processes BLE Command**

**Hub Main Loop (`while True`):**
```python
while True:  # NO time.sleep() - runs continuously
    # Process buffered BLE commands
    if len(ble_command_buffer) > 0:
        process_ble_command(ble_command_buffer.popleft())
```

**Processing Function:**
```python
def process_ble_command(command_str):
    # Parse: "PING":"-54" → command='PING', threshold='-54'
    if command == "PING":
        start_device_scan(threshold)
```

**Timing:** Processes within one loop iteration (~0-10ms latency)  
**Current State:** ✅ Working correctly

---

### **Phase 4: Hub Starts Device Scan**

**Hub (`start_device_scan`):**
```python
def start_device_scan(rssi_threshold="all"):
    global scan_in_progress, scan_start_time, discovered_devices
    
    # Set state
    scan_in_progress = True           # ⚠️ CRITICAL FLAG
    scan_start_time = time.time()     # Start 5-second timeout
    discovered_devices = []
    
    # Send ESP-NOW broadcast to all modules
    send_espnow_command("PING", rssi_threshold)
```

**ESP-NOW Transmission:**
```python
def send_espnow_command(espnow_command, rssi_threshold):
    message = {"pingCall": {"RSSI": -54, "value": "app"}}
    message_str = json.dumps(message)
    
    success = espnow_interface.send(BROADCAST_MAC, message_str)
    # BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'
```

**Timing:** ESP-NOW send completes in ~2-5ms  
**Current State:** ✅ Working - modules receive this

---

### **Phase 5: Module Receives ESP-NOW Broadcast**

**Module ESP-NOW Interrupt Handler (`recv_cb`):**
```python
def recv_cb(a):
    global msg_buffer
    while True:
        mac, msg = a.irecv(0)  # Non-blocking read
        if mac is None:
            return
        try:
            receivedMessage = json.loads(msg)  # ✅ Parse JSON in IRQ
            print("Received from", mac.hex(), ":", receivedMessage)
            msg_buffer.append((bytes(mac), receivedMessage))  # ✅ Store as dict
        except Exception as error:
            print("recv_cb error:", error)

e.irq(recv_cb)  # ✅ IRQ is registered
```

**Timing:** IRQ-triggered, <1ms to buffer message  
**Current State:** ✅ Working perfectly - logs show messages received

---

### **Phase 6: Module Main Loop Processes Message**

**Module Main Loop:**
```python
while True:
    time.sleep(0.1)  # 100ms loop interval
    
    if len(msg_buffer) > 0:
        mac, receivedMessage = msg_buffer.popleft()
        
        for key in receivedMessage:  # e.g., key = "pingCall"
            try:
                sender_rssi = e.peers_table[mac][0]  # Get hub's RSSI
                threshold = receivedMessage[key]["RSSI"]  # -54
                
                if sender_rssi > threshold:  # Check if hub is strong enough
                    s.mac_value = bytes(mac)  # Store hub MAC
                    if functionLUT.get(key):
                        functionLUT[key](receivedMessage[key]["value"])
                        # Calls s.sendPong("app")
```

**Function Lookup Table:**
```python
functionLUT = {
    "pingCall": s.sendPong,
    "pongCall": s.react2Pong,
    "finalCall": s.playGame,
    # ... other commands
}
```

**Timing:** Processes within 0-100ms (next loop iteration)  
**Current State:** ✅ Working - logs show "Calling pingCall function"

---

### **Phase 7: Module Sends Response**

**Module (`sendPong`):**
```python
def sendPong(self, argument = None):
    if(argument == "app"):
        message = {"deviceScan": {"RSSI": -45, "value": "Hippo 1"}}
        result = e.send(peer, json.dumps(message))
        # peer = b'\xff\xff\xff\xff\xff\xff' (broadcast)
        print("Send result:", result)  # Shows "True"
```

**Timing:** ESP-NOW send completes in ~2-5ms  
**Current State:** ✅ Module shows "Send result: True"  
**Problem:** ❌ Hub never receives this message!

---

### **Phase 8: Hub Should Receive Module Response**

**Hub ESP-NOW Interrupt Handler:**
```python
def espnow_recv_cb(interface):
    global espnow_msg_buffer, espnow_rx_count
    while True:
        mac, msg = interface.irecv(0)
        if mac is None:
            return
        try:
            espnow_msg_buffer.append((bytes(mac), msg))  # ⚠️ Stores RAW BYTES
            espnow_rx_count += 1
            # ⚠️ NO PRINT STATEMENT - can't see if IRQ fires
        except Exception as err:
            print("ESP-NOW recv error:", err)

espnow_interface.irq(espnow_recv_cb)  # ✅ IRQ is registered
```

**Timing:** Should be IRQ-triggered, <1ms  
**Current State:** ❌ **UNKNOWN** - no debug output to confirm IRQ fires!  
**Problem:** Either IRQ never fires OR messages are buffered but discarded later

---

### **Phase 9: Hub Main Loop Should Process ESP-NOW Response**

**Hub Main Loop:**
```python
while True:  # Continuous loop, no sleep
    current_time = time.time()
    
    # Process ESP-NOW messages
    if len(espnow_msg_buffer) > 0:
        mac, msg = espnow_msg_buffer.popleft()
        process_espnow_message(mac, msg)
```

**Processing Function:**
```python
def process_espnow_message(mac, msg):
    # ⚠️ CRITICAL BUG: State-based filtering
    if not scan_in_progress:
        print("IGNORED: scan not active")
        return  # ❌ DISCARDS MESSAGE!
    
    # ⚠️ CRITICAL BUG: Message type filtering
    response = json.loads(msg.decode())  # Parse here (too late?)
    if response.get("deviceScan") is None:
        print("IGNORED: not deviceScan")
        return  # ❌ DISCARDS MESSAGE!
    
    # If we get here, add to discovered_devices
    discovered_devices.append(device_info)
```

**Timing:** Processes within main loop iteration  
**Current State:** ❌ **BROKEN** - messages likely discarded by filters

---

### **Phase 10: Hub Scan Timeout**

**Hub Main Loop:**
```python
# After 5 seconds, finish scan
if scan_in_progress:
    if (current_time - scan_start_time) > device_scan_timeout:  # 5.0 seconds
        finish_device_scan()
```

**Timing:** 5 seconds after `start_device_scan()` was called  
**Current State:** ✅ Working - scan completes on time

---

### **Phase 11: Hub Sends Results to App**

**Hub (`finish_device_scan`):**
```python
def finish_device_scan():
    scan_in_progress = False  # ⚠️ Now further messages will be ignored!
    
    # Apply RSSI filtering
    device_list = [d for d in discovered_devices if d["rssi"] >= threshold]
    
    # Send via BLE
    response_json = json.dumps({"type": "devices", "list": device_list})
    send_ble_framed(response_json.encode(), chunk_size=100)
```

**BLE Transmission:**
```python
def send_ble_framed(data_bytes, chunk_size=100):
    # Send header: "MSG:118|"
    header = f"MSG:{len(data_bytes)}|"
    p.send(header.encode())
    time.sleep_ms(20)
    
    # Send payload in chunks (100 bytes each)
    for i in range(0, len(data_bytes), chunk_size):
        chunk = data_bytes[i:i+chunk_size]
        p.send(chunk)
        time.sleep_ms(20)  # 20ms between chunks
```

**Timing:** 
- Header: ~20ms
- Each 100-byte chunk: ~20ms
- Total for 118 bytes: ~60ms

**Current State:** ✅ Working - app receives empty device list

---

### **Phase 12: App Receives and Displays Results**

**App BLE Handler:**
```javascript
// Receives fragmented messages and reassembles
// Parses JSON: {"type": "devices", "list": [...]}
// Updates UI
```

**Timing:** Near-instant once message is complete  
**Current State:** ✅ Working - but receives empty list

---

## ⏱️ Complete Timing Breakdown

### **Total Latency (Expected):**
```
App Click                    → 0ms (user action)
BLE Transmission (App→Hub)   → ~10-20ms
Hub BLE Processing           → <10ms
Hub ESP-NOW Send             → ~5ms
───────────────────────────────────────
Module ESP-NOW IRQ           → <1ms
Module Main Loop Processing  → 0-100ms (depends on loop timing)
Module ESP-NOW Response      → ~5ms
───────────────────────────────────────
❌ Hub ESP-NOW IRQ           → ??? (NEVER FIRES or SILENT)
❌ Hub Message Processing    → DISCARDED
───────────────────────────────────────
Hub Scan Timeout (wait)      → 5000ms
Hub BLE Send Results         → ~60ms
App Receives & Updates UI    → <10ms
───────────────────────────────────────
TOTAL: ~5.2 seconds (mostly waiting)
```

### **Actual Latency (Observed):**
```
Full cycle: ~5.0-5.2 seconds
BUT: Zero devices found (messages lost)
```

---

## 🐛 Critical Issues Identified

### **Issue #1: Hub ESP-NOW IRQ Has No Debug Output**
**Module:** ✅ Prints "Received from [mac] : [message]" in IRQ  
**Hub:** ❌ No print statement in `espnow_recv_cb`

**Impact:** Can't tell if IRQ ever fires or if messages are received

---

### **Issue #2: Hub Doesn't Parse JSON in IRQ**
**Module:** ✅ Parses in IRQ: `receivedMessage = json.loads(msg)`  
**Hub:** ❌ Stores raw bytes: `espnow_msg_buffer.append((bytes(mac), msg))`

**Impact:** Parsing happens later in main loop, adds latency

---

### **Issue #3: Hub Discards Messages Based on Scan State**
**Module:** ✅ Processes ALL messages regardless of state  
**Hub:** ❌ Checks `if not scan_in_progress: return`

**Impact:** If module responds slightly late (>5s), message is discarded  
**Likelihood:** HIGH - module has 0-100ms loop delay + processing time

**Example Timeline:**
```
T=0.000s: Hub sends PING, sets scan_in_progress=True
T=0.005s: Module receives PING
T=0.095s: Module processes (next loop iteration at 100ms interval)
T=0.100s: Module sends deviceScan response
T=5.000s: Hub timeout → scan_in_progress=False
T=5.001s: Hub receives response from buffer → DISCARDED (scan_in_progress=False)
```

---

### **Issue #4: Hub Only Accepts "deviceScan" Messages**
**Module:** ✅ Uses function lookup table, handles any message type  
**Hub:** ❌ Hardcoded check: `if response.get("deviceScan") is None: return`

**Impact:** Cannot handle other message types (gameplay, pongs, etc.)

---

### **Issue #5: Race Condition Between Buffer and State**
**Problem:** Messages are buffered in IRQ but processed asynchronously in main loop.  
By the time processing happens, `scan_in_progress` may already be `False`.

**Module Doesn't Have This Problem Because:** It doesn't use state-based filtering.

---

## 🔧 Architectural Comparison

### **Module (Working Pattern):**
```python
# IRQ: Fast, parse immediately, buffer dict
def recv_cb(a):
    while True:
        mac, msg = a.irecv(0)
        if mac is None: return
        receivedMessage = json.loads(msg)  # ✅ Parse here
        print("Received:", receivedMessage)  # ✅ Debug
        msg_buffer.append((bytes(mac), receivedMessage))  # ✅ Store dict

# Main loop: Simple, no state checks
while True:
    time.sleep(0.1)
    if len(msg_buffer) > 0:
        mac, receivedMessage = msg_buffer.popleft()
        for key in receivedMessage:
            if sender_rssi > threshold:  # Only filter by RSSI
                if functionLUT.get(key):  # ✅ Lookup table
                    functionLUT[key](receivedMessage[key]["value"])
```

### **Hub (Broken Pattern):**
```python
# IRQ: Fast but no debug, stores raw bytes
def espnow_recv_cb(interface):
    while True:
        mac, msg = interface.irecv(0)
        if mac is None: return
        # ❌ No print statement
        espnow_msg_buffer.append((bytes(mac), msg))  # ❌ Raw bytes

# Main loop: Complex, state-based filtering
while True:
    # No sleep
    if len(espnow_msg_buffer) > 0:
        mac, msg = espnow_msg_buffer.popleft()
        process_espnow_message(mac, msg)

def process_espnow_message(mac, msg):
    if not scan_in_progress: return  # ❌ State check
    response = json.loads(msg.decode())  # ⚠️ Parse late
    if response.get("deviceScan") is None: return  # ❌ Type check
    # Finally process...
```

---

## 💡 Alternative Detection/Update Strategies

### **Current Strategy: Request-Response Polling**
```
App → "PING" → Hub → broadcast → Modules
Modules → "deviceScan" → Hub → collect for 5s → App
```

**Pros:**
- Simple to understand
- App controls when scans happen
- RSSI filtering at scan time

**Cons:**
- ❌ 5-second wait every scan
- ❌ Modules must respond within timeout window
- ❌ State management complexity (scan_in_progress flag)
- ❌ Race conditions between IRQ buffering and state checks
- ❌ Wasted time waiting when no modules present
- ❌ Cannot handle asynchronous module events (button presses, battery alerts)

---

### **Alternative 1: Event-Driven Push Model**
```
Modules → Periodic heartbeats → Hub → maintains device registry → App queries registry
```

**How It Works:**
1. Modules send periodic "hello" messages (every 1-5 seconds)
2. Hub maintains a registry of "last seen" times for each device
3. App queries hub's cached registry (instant response)
4. Hub marks devices as "offline" if no hello in X seconds

**Pros:**
- ✅ Instant app response (no 5s wait)
- ✅ Hub always knows what's connected
- ✅ Can handle asynchronous events (button press → immediate notification)
- ✅ No state flags or timeouts needed
- ✅ Simpler code

**Cons:**
- More ESP-NOW traffic (periodic heartbeats)
- Modules must track last-sent time

---

### **Alternative 2: Hybrid: Cached Registry + On-Demand Scan**
```
Normal operation: App queries hub's cached registry (instant)
Forced refresh: App triggers full scan (5s wait, optional)
```

**How It Works:**
1. Modules send heartbeats when state changes (button press, battery low, etc.)
2. Hub maintains registry with last-seen times
3. App normally queries cached registry (instant)
4. User can trigger full scan if needed (like current system)

**Pros:**
- ✅ Best of both worlds
- ✅ Fast normal operation
- ✅ Comprehensive scan when needed
- ✅ Handles events

**Cons:**
- More complex (two code paths)

---

### **Alternative 3: Module-Initiated Registration**
```
Module boots → announces presence → Hub adds to registry → App notified
```

**How It Works:**
1. When module boots, it broadcasts "I'm here" message
2. Hub receives and adds to registry
3. Hub immediately notifies connected app via BLE
4. Module re-announces periodically (every 30s) to stay alive

**Pros:**
- ✅ No app-initiated scans needed
- ✅ Hub always has current state
- ✅ Real-time updates

**Cons:**
- App must handle unsolicited notifications
- More complex state management

---

## 🎯 Recommended Next Steps

### **Immediate Fix (Match Module Pattern):**

1. **Add debug print to hub ESP-NOW IRQ:**
   ```python
   def espnow_recv_cb(interface):
       while True:
           mac, msg = interface.irecv(0)
           if mac is None: return
           print("ESP-NOW RX from", mac.hex())  # ← ADD THIS
           espnow_msg_buffer.append((bytes(mac), msg))
   ```

2. **Parse JSON in IRQ (like module does):**
   ```python
   def espnow_recv_cb(interface):
       while True:
           mac, msg = interface.irecv(0)
           if mac is None: return
           try:
               receivedMessage = json.loads(msg)  # ← PARSE HERE
               print("Received from", mac.hex(), ":", receivedMessage)
               espnow_msg_buffer.append((bytes(mac), receivedMessage))  # ← STORE DICT
           except Exception as err:
               print("ESP-NOW recv error:", err)
   ```

3. **Remove scan_in_progress gate:**
   ```python
   def process_espnow_message(mac, receivedMessage):  # Now receives dict
       # NO STATE CHECK - process all messages
       for key in receivedMessage:
           if functionLUT.get(key):
               functionLUT[key](mac, receivedMessage[key])
   ```

4. **Add function lookup table (like module):**
   ```python
   def handle_device_scan(mac, data):
       if scan_in_progress:  # Only add to scan if scan is active
           discovered_devices.append(...)
   
   functionLUT = {
       "deviceScan": handle_device_scan,
       "pongCall": handle_pong,
       "finalCall": handle_final,
       # ... etc
   }
   ```

### **Long-Term Redesign (Alternative Strategy):**

Consider implementing **Alternative 2 (Hybrid)** for better UX:
- Hub maintains device registry from periodic heartbeats
- App gets instant responses from cache
- Optional forced full-scan for troubleshooting

---

## 📋 Summary for Next Session

**What's Working:**
- ✅ BLE communication (App ↔ Hub)
- ✅ ESP-NOW Hub → Module (ping)
- ✅ Module receives, processes, and responds
- ✅ Module ESP-NOW transmission reports success

**What's Broken:**
- ❌ Hub doesn't receive module ESP-NOW responses (or receives but discards them)
- ❌ Hub has no debug output in ESP-NOW IRQ (can't confirm receipt)
- ❌ Hub uses state-based filtering that creates race conditions
- ❌ Hub parses JSON too late (in main loop instead of IRQ)

**Root Cause Hypothesis:**
Hub's architectural pattern differs from the working module pattern, specifically:
1. No IRQ debug output (can't see if messages arrive)
2. State-based filtering (discards valid messages)
3. Late JSON parsing (adds latency)
4. Race condition between async buffer and sync state flags

**Recommendation:**
Make hub's ESP-NOW handling **exactly match** the module's working pattern.

---

**End of Analysis**

