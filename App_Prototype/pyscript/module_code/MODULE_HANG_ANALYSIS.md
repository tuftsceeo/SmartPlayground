# Module Hang Analysis - "Hippo" Not Responding to Pings

## Problem Summary
After gameplay for a period of time, the plushie/module stops responding to ping commands from the hub. Restarting both devices temporarily fixes the issue.

## Root Causes Identified

### 🔴 CRITICAL: Broadcast Peer Deletion in reset()
**Location**: `pyscript/module_code/main.py` lines 212-215

**Issue**: The `reset()` function deletes ALL ESP-NOW peers, including the broadcast peer (`b'\xff\xff\xff\xff\xff\xff'`) that was added on line 45. After any game interaction triggers a reset, the module can no longer receive broadcast messages from the hub.

**Current Code**:
```python
def reset(self):
    self.PINGED = False
    self.PONGED = False
    self.GAME_TIME = 0
    try:
        for old_friend in e.get_peers():
            e.del_peer(old_friend[0])  # ❌ Deletes broadcast peer too!
    except Exception as error:
        print(error)
    self.FRIEND_LIST = []
    self.clearBuffer = True
```

**Recommended Fix**:
```python
def reset(self):
    self.PINGED = False
    self.PONGED = False
    self.GAME_TIME = 0
    try:
        BROADCAST_PEER = b'\xff\xff\xff\xff\xff\xff'
        for old_friend in e.get_peers():
            # Don't delete the broadcast peer - we need it for hub commands!
            if old_friend[0] != BROADCAST_PEER:
                e.del_peer(old_friend[0])
    except Exception as error:
        print(error)
    self.FRIEND_LIST = []
    self.clearBuffer = True
```

---

### 🔴 CRITICAL: RSSI Check Fails for Broadcast MAC
**Location**: `pyscript/module_code/main.py` line 398

**Issue**: When checking RSSI, code looks up the sender MAC in `e.peers_table`. But broadcast messages use MAC `b'\xff\xff\xff\xff\xff\xff'` which may not have an entry in the peers table. This throws a KeyError (silently caught), preventing the message from being processed at all.

**Current Code**:
```python
for key in receivedMessage:
    try:
        if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):  # ❌ Fails for broadcast
            s.mac_value = bytes(mac)  
            if functionLUT.get(key):
                functionLUT[key](receivedMessage[key]["value"])
    except Exception as err:
        print(err)
```

**Recommended Fix**:
```python
for key in receivedMessage:
    try:
        # For broadcast messages or missing peers, assume good RSSI
        try:
            sender_rssi = e.peers_table[mac][0]
        except (KeyError, IndexError):
            # Broadcast or unknown sender - assume strong signal
            sender_rssi = -30
        
        if sender_rssi > receivedMessage[key]["RSSI"]:
            s.mac_value = bytes(mac)  
            if functionLUT.get(key):
                functionLUT[key](receivedMessage[key]["value"])
    except Exception as err:
        print(err)
```

---

### 🟡 HIGH PRIORITY: Heavy JSON Parsing in Interrupt Context
**Location**: `pyscript/module_code/main.py` lines 373-387

**Issue**: The `recv_cb()` interrupt handler does JSON parsing (CPU intensive). If messages arrive rapidly during gameplay, this can:
- Block the system and prevent other interrupts
- Cause buffer overflow
- Miss incoming messages

**Current Code**:
```python
def recv_cb(a):
    global msg_buffer
    while True:
        mac, msg = a.irecv(0)
        if mac is None:
            return
        try:
            receivedMessage = json.loads(msg)  # ❌ Heavy processing in interrupt!
            msg_buffer.append((bytes(mac), receivedMessage))
        except Exception as error:
            print(error)
```

**Recommended Fix** (in two parts):

Part 1 - Minimal interrupt handler:
```python
def recv_cb(a):
    global msg_buffer
    while True:
        mac, msg = a.irecv(0)
        if mac is None:
            return
        # Just buffer raw message - parse in main loop
        msg_buffer.append((bytes(mac), msg))
```

Part 2 - Parse in main loop (around line 393):
```python
while True:
    time.sleep(0.1)
    if len(msg_buffer) > 0:
        mac, raw_msg = msg_buffer.popleft()  # Get raw message
        
        # Parse JSON here in main loop, not in interrupt
        try:
            receivedMessage = json.loads(raw_msg)
        except Exception as err:
            print(f"JSON parse error: {err}")
            continue
        
        # Rest of processing...
        for key in receivedMessage:
            # ... existing code
```

---

### 🟡 HIGH PRIORITY: Button Interrupt Does Too Much Work
**Location**: `pyscript/module_code/main.py` lines 147-167

**Issue**: The button interrupt handler (`check_switch()`) does extensive work in interrupt context:
- Calls `reset()` which iterates over peers
- Calls `buzz()` with blocking `time.sleep()`
- Does JSON encoding
- Sends ESP-NOW message

This can cause deadlocks if it conflicts with the ESP-NOW receive interrupt.

**Current Code**:
```python
def check_switch(self,p):
    self.time_of_button_press = time.ticks_ms()
    if(self.time_of_button_press - self.old_pressed_time) < 350:
        return
    self.old_pressed_time = self.time_of_button_press
    
    # ❌ All this work in interrupt context!
    self.buzz(0.08,1)
    self.reset()
    self.PINGED = True
    self.GAME_TIME = time.ticks_ms()
    message = {"pingCall": {"RSSI": self.THRESHOLD_RSSI, "value": self.name}}
    e.send(peer, json.dumps(message))
```

**Recommended Fix**:

Part 1 - Minimal interrupt handler:
```python
def check_switch(self, p):
    # Just debounce and set flag - do work in main loop
    self.time_of_button_press = time.ticks_ms()
    if (self.time_of_button_press - self.old_pressed_time) < 350:
        return
    self.old_pressed_time = self.time_of_button_press
    self.button_event = True  # Signal main loop
```

Part 2 - Handle in main loop (around line 391):
```python
while True:
    time.sleep(0.1)
    
    # Handle button press from interrupt
    if s.button_event:
        s.button_event = False
        s.buzz(0.08, 1)
        s.reset()
        s.PINGED = True
        s.GAME_TIME = time.ticks_ms()
        message = {"pingCall": {"RSSI": s.THRESHOLD_RSSI, "value": s.name}}
        e.send(peer, json.dumps(message))
    
    # ... rest of main loop
```

---

### 🟡 MEDIUM PRIORITY: Unused clearBuffer Flag
**Location**: `pyscript/module_code/main.py` lines 109, 217

**Issue**: The `clearBuffer` flag is set in `reset()` but never checked or used. Stale messages can accumulate in the buffer and be processed after a reset, causing incorrect behavior.

**Current Code**:
```python
# In __init__ (line 109):
self.clearBuffer = False

# In reset() (line 217):
self.clearBuffer = True

# But nowhere is this checked!
```

**Recommended Fix** - Add check in main loop (around line 393):
```python
while True:
    time.sleep(0.1)
    
    # Clear buffer if reset was called
    if s.clearBuffer:
        msg_buffer.clear()
        s.clearBuffer = False
    
    if len(msg_buffer) > 0:
        # ... rest of message processing
```

---

### 🟡 MEDIUM PRIORITY: Unhandled Reset Exceptions Can Stick State
**Location**: `pyscript/module_code/main.py` lines 418-420

**Issue**: If `reset()` throws an exception (caught in line 214), the `PONGED` flag remains `True`. The module will then try to reset every loop iteration, potentially causing continuous errors.

**Current Code**:
```python
if(s.PONGED):
    if(time.ticks_ms() - s.PONG_TIME) > s.PONG_TIME_TIMEOUT:
        s.reset()  # ❌ If this fails, PONGED stays True
```

**Recommended Fix**:
```python
if s.PONGED:
    if (time.ticks_ms() - s.PONG_TIME) > s.PONG_TIME_TIMEOUT:
        try:
            s.reset()
        except Exception as err:
            print(f"Reset timeout failed: {err}")
            # Force state clear even if reset fails
            s.PONGED = False
            s.PINGED = False
            s.GAME_TIME = 0
```

---

### 🟢 LOW PRIORITY: Log File Can Fill Storage
**Location**: `pyscript/module_code/main.py` lines 181-184

**Issue**: Continuous appending to `log.txt` without size limit. After extended gameplay, this could fill the filesystem and cause write operations to fail, potentially hanging the system.

**Current Code**:
```python
def log_collected_color(self, pinged, ponged, color):
    f = open("log.txt","a")
    f.write(f'[{str(self.game)}, {str(pinged)} , {str(ponged)} , {str(color)}, {str(time.ticks_ms())}]')
    f.close()
```

**Recommended Fix**:
```python
def log_collected_color(self, pinged, ponged, color):
    try:
        # Check file size, rotate if too large
        try:
            import os
            if os.stat("log.txt")[6] > 50000:  # 50KB limit
                os.remove("log.txt")
        except:
            pass
        
        f = open("log.txt", "a")
        f.write(f'[{str(self.game)}, {str(pinged)}, {str(ponged)}, {str(color)}, {str(time.ticks_ms())}]\n')
        f.close()
    except Exception as e:
        # Don't let logging errors crash the system
        print(f"Log write failed: {e}")
```

---

## Implementation Priority

**Fix these in order for best results:**

1. ✅ **Broadcast peer deletion** (Critical) - This alone likely causes most hangs
2. ✅ **RSSI check for broadcast MAC** (Critical) - Prevents all hub commands from working
3. ⚠️ **Move JSON parsing out of interrupt** (High) - Improves stability under load
4. ⚠️ **Implement clearBuffer check** (Medium) - Prevents stale message confusion
5. ⚠️ **Button interrupt to flag-based** (High) - Prevents interrupt deadlocks
6. ⚠️ **Reset exception handling** (Medium) - Prevents stuck states
7. 💡 **Log file size limit** (Low) - Prevents long-term storage exhaustion

---

## Testing Recommendations

After implementing fixes:

1. **Add debug logging** to track peer count:
   ```python
   def reset(self):
       print(f"Reset called - peers before: {len(e.get_peers())}")
       # ... reset code
       print(f"Reset done - peers after: {len(e.get_peers())}")
   ```

2. **Monitor message processing**:
   ```python
   # In main loop message handling:
   print(f"Processing {key} from {mac.hex()}")
   ```

3. **Test sustained gameplay**:
   - Run for 10+ minutes with multiple ping/pong cycles
   - Button press multiple times during play
   - Send hub pings every 30 seconds

4. **Check for the bug**:
   - After several game rounds, send a ping from hub
   - Module should still respond with deviceScan
   - If it doesn't, check peer count with `print(len(e.get_peers()))`

5. **Memory monitoring** (if available):
   ```python
   import gc
   print(f"Free memory: {gc.mem_free()}")
   ```

---

## Expected Behavior After Fixes

✅ Module maintains broadcast peer through all reset cycles  
✅ Module processes hub commands regardless of sender MAC  
✅ No blocking operations in interrupt handlers  
✅ Buffer is cleared appropriately after state resets  
✅ System recovers gracefully from errors  
✅ Log file doesn't grow indefinitely  

The module should remain responsive to hub pings indefinitely, even after extensive gameplay sessions.

