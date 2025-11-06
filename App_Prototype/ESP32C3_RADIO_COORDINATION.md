# ESP32-C3 Radio Coordination Guide

**Date:** November 6, 2025  
**Hardware:** ESP32-C3 (single 2.4GHz radio shared between BLE and WiFi/ESP-NOW)  
**Issue:** Radio conflicts between BLE and ESP-NOW causing crashes and missed messages  
**Resolution:** Flag-based coordination with minimal timing delays

---

## 🚨 Critical Discovery: Query Operations Lock Radio

### The Crash

**Symptom:**
```
Initializing ESP-NOW...
[setup completes]
Initializing BLE UART service...  ← CRASH: Load access fault
```

**Root Cause:**
```python
# ❌ CRASHES - Radio queries before BLE init
espnow_interface.active(True)
espnow_interface.add_peer(peer)
espnow_interface.irq(callback)
espnow_interface.active()      # ← Query keeps radio locked!
espnow_interface.get_peers()   # ← Query keeps radio locked!
# BLE initialization fails - radio not available

# ✅ WORKS - Setup without queries
espnow_interface.active(True)
espnow_interface.add_peer(peer)
espnow_interface.irq(callback)
# Radio returns to idle state
# BLE initialization succeeds
```

**Lesson:** Status query operations (`.active()`, `.get_peers()`) keep the radio interface locked in a way that prevents other subsystems from initializing. Avoid these calls during initialization sequences.

---

## 📐 Timing Guidelines

### Initialization (One-Time Setup)

```python
# Step 1: ESP-NOW Setup
espnow_interface.active(True)           # <1ms
espnow_interface.add_peer(broadcast)    # <1ms
espnow_interface.irq(recv_callback)     # <1ms
print("ESP-NOW registered")

# Step 2: BLE Setup (no delay needed!)
p = Yell(HUB_NAME)                      # 50-100ms
print("BLE initialized")
```

**Key Points:**
- Order matters: ESP-NOW first, then BLE
- No explicit delay needed between them
- Do NOT query ESP-NOW status (`active()`, `get_peers()`) before BLE init
- Let ESP-NOW go idle (IRQ registered, no active operations)

---

### Runtime Operations

#### ESP-NOW Transmission
```python
success = espnow_interface.send(mac, message)
# send() is BLOCKING - returns when complete (~2-5ms)
# Radio immediately available after return
# No delay needed before BLE operations
```

#### BLE Transmission
```python
p.send(data)
# send() is BLOCKING - returns when complete (~10-50ms depending on size)
# Radio immediately available after return
# No delay needed before ESP-NOW operations
```

**Key Point:** Both `send()` operations are synchronous/blocking. When they return, the transmission is complete and the radio is available.

---

### Device Scanning (Critical Window)

This is where radio conflicts were most severe:

```python
# Phase 1: Start Scan
scan_in_progress = True
ble_paused = True                        # Block BLE transmission
espnow_interface.send(broadcast, ping)   # 2-5ms

# Phase 2: Wait for Responses (5 seconds)
# - ESP-NOW IRQ active, buffering incoming messages
# - BLE transmission blocked via ble_paused flag
# - App-side BLE polling skipped via isRefreshing flag

# Phase 3: Complete Scan
scan_in_progress = False
ble_paused = False
time.sleep_ms(50)                        # Let BLE stabilize
p.send(results)                          # Send via BLE
```

**Critical Timing:**
- **5 second ESP-NOW window:** BLE transmission must be blocked
- **50ms stabilization delay:** After resuming BLE, before first transmission
- **Empirical value:** Could be 20-30ms, but 50ms is safe and imperceptible

---

### Background Operations

```python
# ❌ BAD - BLE polling collides with ESP-NOW scans
setInterval(() => {
    checkConnectionStatus()  # BLE operation every 5 seconds
}, 5000)  # Same duration as scan window!

# ✅ GOOD - Coordinated polling
setInterval(() => {
    if (!state.isRefreshing) {  // Skip during ESP-NOW scans
        checkConnectionStatus()
    }
}, 30000)  // 6x less frequent, unlikely to collide
```

**Key Points:**
- Reduce BLE polling frequency (5s → 30s)
- Skip BLE operations during ESP-NOW scan windows
- Use flags for coordination, not just timing

---

## 🎯 Coordination Strategy: Flags Over Timing

### The Problem with Timing Alone

```python
# ❌ TIMING APPROACH (Brittle)
send_espnow_ping()
time.sleep(5)  # Hope responses arrive in 5 seconds
send_ble_results()
# Race conditions, no protection from overlapping operations
```

### The Solution: Flag-Based Coordination

```python
# ✅ FLAG APPROACH (Robust)
scan_in_progress = True    # Hub-side flag
ble_paused = True          # Hub-side BLE blocking
# (App sets isRefreshing = True)

send_espnow_ping()

# Main loop checks flags:
while True:
    if ble_paused:
        # Skip BLE operations
        continue
    
    if scan_in_progress:
        # Process ESP-NOW messages only
        process_espnow_buffer()
    
    # Check timeout
    if elapsed > timeout:
        finish_scan()
```

---

## 📊 Complete Timing Reference

| **Operation** | **Duration** | **Wait After** | **Notes** |
|--------------|-------------|----------------|-----------|
| `espnow_interface.active(True)` | <1ms | 0ms | Setup operation |
| `espnow_interface.add_peer()` | <1ms | 0ms | Setup operation |
| `espnow_interface.irq(callback)` | <1ms | 0ms | Setup operation |
| `espnow_interface.send()` | 2-5ms | 0ms | Blocking, returns when done |
| `Yell()` initialization | 50-100ms | 0ms | One-time setup |
| `p.send()` (BLE) | 10-50ms | 0ms | Blocking, returns when done |
| **ESP-NOW scan window** | **5000ms** | **50ms** | **Block BLE, resume after** |
| **BLE stabilization** | **50ms** | **0ms** | **After ble_paused=False** |

### Special Cases - AVOID THESE NEAR INIT:

| **Operation** | **Duration** | **Safe Distance** | **Why Dangerous** |
|--------------|-------------|-------------------|-------------------|
| `espnow_interface.active()` (query) | <1ms | 100ms+ from BLE init | Locks radio interface |
| `espnow_interface.get_peers()` | <1ms | 100ms+ from BLE init | Locks radio interface |

---

## ✅ Best Practices Checklist

### Initialization
- [ ] Initialize ESP-NOW first, BLE second
- [ ] Do NOT query ESP-NOW status before BLE init
- [ ] Let ESP-NOW go idle (IRQ registered, no operations)
- [ ] No explicit delays needed between setup steps

### Runtime Coordination
- [ ] Use `ble_paused` flag to block BLE during ESP-NOW scans
- [ ] Use `scan_in_progress` flag to track scan state
- [ ] Use `isRefreshing` flag (app-side) to skip BLE polling
- [ ] Trust `send()` blocking behavior - no manual delays needed

### Critical Timing
- [ ] Block BLE for entire 5-second ESP-NOW scan window
- [ ] Wait 50ms after `ble_paused=False` before sending
- [ ] Reduce BLE polling from 5s to 30s intervals
- [ ] Skip polling during active scans

### Error Recovery
- [ ] Force resume BLE if `ble_paused` stuck True
- [ ] Prevent overlapping scans (check `scan_in_progress`)
- [ ] Clear stale ESP-NOW buffer between scans
- [ ] Watchdog timer resets state after 10s

---

## 🔬 Why These Specific Values?

### 50ms BLE Stabilization
**Origin:** Empirical testing  
**Purpose:** BLE stack needs time to re-acquire radio after pause  
**Trade-off:** Could be 20-30ms, but 50ms is safe with negligible UX impact  
**Why not longer?** Scan already takes 5s, extra 50ms is imperceptible

### 5s Scan Window
**Origin:** Device response time requirements  
**Purpose:** Allow modules time to receive ping and respond  
**Trade-off:** Longer = more devices found, shorter = faster UX  
**Why not longer?** Most responses arrive within 1-2s, 5s provides buffer

### 30s BLE Polling
**Origin:** Collision avoidance  
**Purpose:** Reduce likelihood of polling during 5s scan windows  
**Trade-off:** Less responsive to disconnects vs. less radio interference  
**Why not longer?** Users expect disconnect detection within reasonable time

---

## 🎓 Key Lessons Learned

1. **Query operations lock radio** - `.active()` and `.get_peers()` prevent other subsystems from acquiring radio
2. **Flags beat timing** - Use coordination flags, not just delays
3. **Blocking is predictable** - `send()` operations return when complete
4. **Minimal delays needed** - Only 50ms for BLE stabilization
5. **Single radio requires coordination** - ESP32-C3 cannot do BLE + ESP-NOW simultaneously

---

## 🚀 Results After Implementation

### Before (Broken)
- ❌ Hub crashes on boot (radio lock from queries)
- ❌ Intermittent message loss (BLE/ESP-NOW conflicts)
- ❌ Rapid re-polling causes state corruption
- ❌ Recovery requires hub restart

### After (Fixed)
- ✅ Clean boot sequence (no radio queries)
- ✅ Reliable message reception (flag coordination)
- ✅ Graceful handling of rapid user actions
- ✅ Automatic recovery from stuck states

---

## 📝 Code Patterns

### Initialization Pattern
```python
# ESP-NOW first
espnow_interface.active(True)
espnow_interface.add_peer(BROADCAST_MAC)
espnow_interface.irq(espnow_recv_cb)
# No queries here!

# BLE second
p = Yell(HUB_NAME)
# Success!
```

### Scan Pattern
```python
def start_scan():
    global scan_in_progress, ble_paused
    
    # Prevent overlapping
    if scan_in_progress:
        return
    
    # Setup
    scan_in_progress = True
    ble_paused = True
    espnow_msg_buffer.clear()  # Clear stale messages
    
    # Send
    espnow_interface.send(BROADCAST_MAC, ping)

def finish_scan():
    global scan_in_progress, ble_paused
    
    scan_in_progress = False
    ble_paused = False
    time.sleep_ms(50)  # Stabilize
    
    p.send(results)  # Now safe
```

### BLE Send Pattern
```python
def send_ble_message(data):
    global ble_paused
    
    if ble_paused:
        print("Cannot send: BLE paused")
        return False
    
    p.send(data)  # Blocking, returns when done
    return True
```

---

## 🔗 Related Files

- `pyscript/hub_code/main_c3.py` - Hub implementation with coordination
- `pyscript/app/js/main.js` - App-side polling coordination
- `pyscript/module_code/main.py` - Module reference (no BLE, works perfectly)

---

**Status:** ✅ Resolved  
**Hardware Limitation:** ESP32-C3 single radio requires careful coordination  
**Recommendation:** For future projects, consider ESP32 (original) with dual-core and better BLE/WiFi coexistence

