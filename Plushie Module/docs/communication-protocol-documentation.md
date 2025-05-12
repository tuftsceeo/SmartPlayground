# ESP-NOW Communication Protocol: Complete Specification

## 1. Introduction

This document specifies the communication protocol for the educational module system, designed for a classroom environment with up to 30 ESP32C6-based modules and a hub device. The protocol is optimized for kindergarten educational activities with an emphasis on simplicity, reliability, and efficiency.

## 2. Protocol Design Goals

1. **Simplicity**: Straightforward implementation for educational modules
2. **Reliability**: Robust operation in classroom environments
3. **Efficiency**: Minimal power consumption for battery-operated modules
4. **Scalability**: Support for up to 30 modules in a single classroom
5. **Responsiveness**: Low-latency interaction for 5-year-old users

## 3. Network Architecture

### 3.1 Communication Protocols

1. **Module-to-Module & Module-to-Hub**: ESP-NOW
   - Low-latency communication (~5-10ms)
   - Low power consumption
   - Peer-to-peer without infrastructure
   - Range: ~100m line-of-sight

2. **Hub-to-Tablet**: Bluetooth Low Energy (BLE)
   - Standard tablet connectivity
   - User-friendly connection process
   - Sufficient bandwidth for configuration data

### 3.2 Module Clustering Architecture

To overcome ESP-NOW's 20-peer limitation while supporting up to 30 modules:

1. **Logical Groups**: Modules organized into activity-based groups (<20 modules per group)
2. **Group Leaders**: One module per group serves as communication point to hub
3. **Local Communication**: Modules within a group communicate directly
4. **Cross-Group Messaging**: Messages between groups route through hub

### 3.3 ESP-NOW Configuration

- **Channel**: Fixed channel 1 (2412 MHz)
- **Peer Management**: Dynamic with priority-based allocation
- **Encryption**: Optional AES-128 (disabled for prototype)
- **Peer Maximum**: 20 per ESP32C6 device

## 4. Message Format

All messages follow this binary structure:

```
+---------------+---------------+----------------+----------------+----------------+
| HEADER (1B)   | TYPE (1B)     | SOURCE ID (2B) | LENGTH (1B)    | PAYLOAD (0-247B)|
+---------------+---------------+----------------+----------------+----------------+
```

- **HEADER**: Fixed byte `0xED` (Educational)
- **TYPE**: Message type identifier (see Message Types)
- **SOURCE ID**: Unique identifier for sending module
- **LENGTH**: Length of payload in bytes
- **PAYLOAD**: Variable-length message data

## 5. Message Types

### 5.1 System Messages (0x00-0x0F)

| Type | Name | Description | Direction |
|------|------|-------------|-----------|
| 0x00 | ANNOUNCE | Module announces presence | Module → All |
| 0x01 | DISCOVER | Request for module announcement | Hub → All |
| 0x02 | PING | Connectivity check | Any → Any |
| 0x03 | PONG | Ping response | Any → Any |
| 0x04 | TIME_SYNC | Synchronize time | Hub → All |
| 0x05 | STATUS_REQUEST | Request module status | Hub → Module |
| 0x06 | STATUS_REPORT | Report module status | Module → Hub |
| 0x07 | ERROR | Error notification | Any → Any |
| 0x08 | RESET | Reset module | Hub → Module |

### 5.2 Configuration Messages (0x10-0x1F)

| Type | Name | Description | Direction |
|------|------|-------------|-----------|
| 0x10 | CONFIG_UPDATE | Configuration change | Hub → Module |
| 0x11 | CONFIG_REQUEST | Request configuration | Module → Hub |
| 0x12 | CONFIG_RESPONSE | Send configuration | Hub → Module |
| 0x13 | RULE_ADD | Add a new rule | Hub → Module |
| 0x14 | RULE_UPDATE | Update existing rule | Hub → Module |
| 0x15 | RULE_DELETE | Delete rule | Hub → Module |
| 0x16 | RULE_SYNC | Synchronize all rules | Hub → Module |
| 0x17 | GROUP_ASSIGN | Assign module to group | Hub → Module |

### 5.3 Operational Messages (0x20-0x2F)

| Type | Name | Description | Direction |
|------|------|-------------|-----------|
| 0x20 | TRIGGER | Rule triggered notification | Module → Module/Hub |
| 0x21 | ACTION | Action to perform | Module → Module |
| 0x22 | SENSOR_DATA | Sensor reading broadcast | Module → All/Hub |
| 0x23 | COMMAND | Direct command | Hub → Module |
| 0x24 | ACTIVITY_START | Start educational activity | Hub → Module(s) |
| 0x25 | ACTIVITY_STOP | Stop educational activity | Hub → Module(s) |
| 0x26 | GROUP_ACTION | Action for all modules in group | Hub/Module → Group |

### 5.4 Power Management Messages (0x30-0x3F)

| Type | Name | Description | Direction |
|------|------|-------------|-----------|
| 0x30 | BATTERY_STATUS | Battery level report | Module → Hub |
| 0x31 | SLEEP_REQUEST | Request to enter sleep mode | Hub → Module |
| 0x32 | WAKE_REQUEST | Request to wake from sleep | Hub → Module |
| 0x33 | POWER_MODE | Change power mode | Hub → Module |

## 6. Message Payloads

### 6.1 System Messages

#### ANNOUNCE (0x00)
```json
{
  "name": "Module-5",
  "capabilities": ["button", "leds", "accelerometer", "vibration", "buzzer"],
  "battery": 85,
  "version": "1.0.0"
}
```

#### STATUS_REPORT (0x06)
```json
{
  "battery": 85,
  "uptime": 3600,
  "last_activity": 120,
  "rules_count": 5,
  "errors": [],
  "sensor_state": {
    "button": "released",
    "orientation": "up"
  }
}
```

### 6.2 Configuration Messages

#### RULE_ADD (0x13)
```json
{
  "rule": {
    "id": "12345",
    "source": {
      "type": "BUTTON_PRESS",
      "parameters": {}
    },
    "target": {
      "module_id": "0x1234",
      "type": "LED_COLOR",
      "parameters": {
        "color": [255, 0, 0]
      }
    },
    "mapping": {
      "type": "DIRECT"
    }
  }
}
```

#### GROUP_ASSIGN (0x17)
```json
{
  "group_id": 2,
  "group_name": "Team Blue",
  "color": [0, 0, 255]
}
```

### 6.3 Operational Messages

#### TRIGGER (0x20)
```json
{
  "rule_id": "12345",
  "input_type": "BUTTON_PRESS",
  "input_value": true,
  "timestamp": 1234567890
}
```

#### ACTION (0x21)
```json
{
  "action_type": "LED_COLOR",
  "parameters": {
    "color": [255, 0, 0],
    "duration_ms": 1000
  }
}
```

#### ACTIVITY_START (0x24)
```json
{
  "activity_id": "pattern_game",
  "parameters": {
    "difficulty": 1,
    "duration_sec": 60,
    "mode": "collaborative"
  },
  "initial_state": {
    "led_color": [0, 255, 0],
    "pattern": "blink"
  }
}
```

## 7. Message Optimization

### 7.1 Binary Message Encoding

For frequently used operational messages, compact binary encoding:

| Message | Binary Format | Size Reduction |
|---------|---------------|----------------|
| LED_COLOR | [0xED, 0x21, SRC_H, SRC_L, 0x04, R, G, B, DUR] | 75% smaller than JSON |
| BUTTON_PRESS | [0xED, 0x20, SRC_H, SRC_L, 0x01, 0x01] | 90% smaller than JSON |
| VIBRATION | [0xED, 0x21, SRC_H, SRC_L, 0x02, INT, DUR] | 80% smaller than JSON |

### 7.2 Message Batching

Status updates batched to reduce transmission frequency:

```
+--------+--------+--------+--------+--------+
| Module | Status | Module | Status | ...    |
+--------+--------+--------+--------+--------+
```

### 7.3 Graduated Retransmission

For critical messages (configuration, rules):
- Initial retry: 50ms
- Second retry: 100ms
- Third retry: 200ms

## 8. Communication Sequence Examples

### 8.1 Module Discovery

```
Hub → All: DISCOVER
Module A → All: ANNOUNCE
Module B → All: ANNOUNCE
...
Hub: Records all modules
```

### 8.2 Rule Configuration

```
Hub → Module A: RULE_ADD (Button→LED rule)
Module A → Hub: CONFIG_UPDATE (Success)
Hub → Module B: RULE_ADD (Button→LED rule)
Module B → Hub: CONFIG_UPDATE (Success)
```

### 8.3 Rule Execution

```
[User presses button on Module A]
Module A: Detects button press
Module A: Evaluates rules
Module A → Module B: ACTION (LED_COLOR)
Module B: Performs LED action
Module B → Module A: ACTION (Optional acknowledgment)
```

### 8.4 Group Coordination

```
Hub → Group 1: GROUP_ACTION (LED_COLOR)
[All modules in Group 1 change LED color]
```

## 9. Reliability Mechanisms

### 9.1 Message Acknowledgment

- **Acknowledged Messages**: Critical configuration changes, rule updates, activity controls
- **Unacknowledged Messages**: Routine status updates, sensor broadcasts, some actions
- **Implicit Acknowledgment**: Activity feedback (visual/audio) serves as user-friendly confirmation

### 9.2 Message Retry

| Priority | Max Retries | Retry Intervals | Example Messages |
|----------|-------------|-----------------|------------------|
| Critical | 5 | 50ms, 100ms, 200ms, 400ms, 800ms | RULE_ADD, CONFIG_UPDATE |
| Important | 3 | 50ms, 100ms, 200ms | ACTION, TRIGGER |
| Normal | 1 | 100ms | PING, STATUS_REQUEST |
| Low | 0 | None | STATUS_REPORT, ANNOUNCE |

### 9.3 Error Recovery

1. **Connection Loss**:
   - Automatic reconnection attempts (3 times with increasing intervals)
   - Fallback to local-only operation after failed attempts
   - Periodic rediscovery (every 30 seconds)

2. **Transmission Failures**:
   - Sequence numbers for multi-part messages
   - Message checksums (CRC-8) for validation
   - Partial message recovery when possible

3. **Hub Unavailability**:
   - Modules continue peer-to-peer operation
   - Store critical updates for later sync
   - Group leaders take temporary coordination role

## 10. Power Management Integration

### 10.1 Power States and Communication

| Power State | Communication Behavior | Wake-up Sources |
|-------------|------------------------|-----------------|
| Active | Continuous reception | Any |
| Light Sleep | Check every 100ms | Any |
| Deep Sleep | Manual wake only | Button, Timer |

### 10.2 Sleep Coordination

Based on the standardized 10-minute inactivity trigger:

1. Module detects 10 minutes of inactivity
2. Module sends BATTERY_STATUS with sleep notification
3. Hub acknowledges and updates module status
4. Module enters deep sleep
5. Module wakes on button press
6. Module sends ANNOUNCE upon wake-up

### 10.3 Transmission Windows

For grouped communications to preserve power:

1. **Group Time Slots**: Allocated transmission windows for each group
2. **Aggregated Updates**: Hub collects and distributes in batches
3. **Coordinated Reporting**: Staggered status reports to avoid congestion

## 11. Classroom-Specific Optimizations

### 11.1 Teacher Controls

1. **Emergency Broadcast**: Special high-priority message to all modules
   - Format: [0xED, 0xFF, HUB_H, HUB_L, 0x01, CMD]
   - Guaranteed immediate processing regardless of state
   - Examples: freeze activity, prepare for end of class

2. **Attention Signal**: Visual/audio cue on all modules
   - Special GROUP_ACTION targeting all modules
   - Predefined patterns for classroom management
   - Examples: "look at me", "rotate groups", "clean up"

3. **Activity Transitions**: Synchronized state changes
   - Two-phase commit protocol for consistent transitions
   - All modules confirm readiness before executing
   - Coordinated visual/audio effects for clear transitions

### 11.2 Multi-Module Activities

1. **Synchronized Patterns**: Coordinated visual displays
   - TIME_SYNC message establishes common time reference
   - Precise timing offsets in instructions
   - Multi-node choreographed light/sound patterns

2. **Chain Reactions**: Sequential activations
   - Defined propagation paths in configuration
   - Timing controls for speed of propagation
   - Loop and branch support for complex patterns

3. **Collaborative Challenges**: Distributed inputs/outputs
   - Shared goal tracking via hub
   - Progress indicators across multiple modules
   - Success/completion coordination

### 11.3 Child-Friendly Features

1. **Immediate Feedback**: Minimize latency for interactivity
   - Direct module-to-module communication for critical interactions
   - Local feedback while waiting for remote response
   - Prioritized message processing for user interactions

2. **Resilient Operation**: Handle unexpected interactions
   - Debounce and filtering for accidental button mashing
   - Rate limiting for repeated triggers
   - Graceful handling of unexpected state transitions

3. **Clear Indicators**: Status signaling for young users
   - Consistent visual language for connection status
   - Simple patterns indicating "working" vs "waiting"
   - Age-appropriate error indicators

## 12. Hub Implementation Details

### 12.1 Message Routing

Hub maintains routing tables for module-to-module communication:

1. **Direct Routing**: For modules in same group or under 20 total modules
2. **Group Routing**: Through group leaders for larger deployments
3. **Broadcast Optimization**: Selective broadcasting to relevant groups only

### 12.2 Queue Management

Priority-based message processing to handle traffic spikes:

1. **Priority Levels**:
   - System critical (highest): Reset, emergency commands
   - Configuration: Rule updates, group assignments
   - Status: Battery reports, sensor data
   - Routine: Regular status updates (lowest)

2. **Queue Processing**: Round-robin with priority preemption
3. **Overflow Handling**: Merge similar messages, drop oldest lower priority

### 12.3 BLE-ESP-NOW Translation

The hub bridges between BLE (tablet) and ESP-NOW (modules):

1. **Protocol Translation**:
   - Message format conversion
   - Fragmentation/reassembly for large messages
   - Metadata preservation across protocols

2. **State Synchronization**:
   - Periodic module state updates to tablet
   - Cached responses for frequent queries
   - Background state collection while tablet disconnected

3. **Error Handling**:
   - Protocol-specific error recovery
   - Cross-protocol error translation
   - Fallback modes when one interface is down

## 13. Implementation Guidelines

### 13.1 ESP-NOW Setup

```c
// Initialize ESP-NOW
if (esp_now_init() != ESP_OK) {
  ESP_LOGE(TAG, "Error initializing ESP-NOW");
  return;
}

// Register callback
esp_now_register_recv_cb(on_data_received);

// Add peer (broadcast)
esp_now_peer_info_t peer_info = {};
memset(&peer_info, 0, sizeof(peer_info));
memcpy(peer_info.peer_addr, broadcast_mac, ESP_NOW_ETH_ALEN);
peer_info.channel = 1;
peer_info.encrypt = false;
esp_now_add_peer(&peer_info);
```

### 13.2 Message Handling

```c
void on_data_received(const uint8_t *mac_addr, const uint8_t *data, int len) {
  // Validate header
  if (len < 5 || data[0] != 0xED) {
    return; // Invalid message
  }
  
  uint8_t msg_type = data[1];
  uint16_t source_id = (data[2] << 8) | data[3];
  uint8_t payload_len = data[4];
  
  // Validate length
  if (len != 5 + payload_len) {
    return; // Invalid length
  }
  
  // Process message based on type
  switch (msg_type) {
    case 0x00: // ANNOUNCE
      handle_announce(mac_addr, source_id, &data[5], payload_len);
      break;
    case 0x20: // TRIGGER
      handle_trigger(mac_addr, source_id, &data[5], payload_len);
      break;
    // ... other message types
  }
}
```

### 13.3 MicroPython Example

```python
import network
import espnow
import time
import struct
import json

# Initialize ESP-NOW
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()  # Disconnect from any AP

e = espnow.ESPNow()
e.active(True)

# Add broadcast peer
broadcast = b'\xff\xff\xff\xff\xff\xff'
e.add_peer(broadcast)

def send_message(dest_mac, msg_type, payload):
    """Send a message using the educational protocol format."""
    # Get this module's ID
    source_id = 0x1234  # Example ID, should be unique per module
    
    # Convert payload to bytes
    if isinstance(payload, dict):
        payload_bytes = json.dumps(payload).encode()
    elif isinstance(payload, str):
        payload_bytes = payload.encode()
    else:
        payload_bytes = payload
    
    # Create message header
    header = struct.pack("!BBHB", 
                        0xED,       # Protocol header
                        msg_type,   # Message type
                        source_id,  # Source ID
                        len(payload_bytes))  # Payload length
    
    # Complete message
    message = header + payload_bytes
    
    # Send via ESP-NOW
    return e.send(dest_mac, message)

def handle_message(mac, message):
    """Process a received message."""
    if len(message) < 5 or message[0] != 0xED:
        return  # Invalid message
    
    # Parse header
    msg_type = message[1]
    source_id = (message[2] << 8) | message[3]
    payload_len = message[4]
    payload = message[5:5+payload_len]
    
    # Handle message based on type
    if msg_type == 0x00:  # ANNOUNCE
        try:
            data = json.loads(payload)
            print(f"Module announced: {data['name']}")
            # Process capabilities, etc.
        except:
            print("Invalid ANNOUNCE payload")
            
    elif msg_type == 0x21:  # ACTION
        try:
            data = json.loads(payload)
            action_type = data["action_type"]
            parameters = data["parameters"]
            
            # Execute action based on type
            if action_type == "LED_COLOR":
                # Set LED color
                color = parameters["color"]
                # ... implementation
            
        except:
            print("Invalid ACTION payload")

# Set up message reception callback
def msg_cb(e):
    while e.any():
        mac, msg = e.recv()
        handle_message(mac, msg)

e.irq(msg_cb)

# Example: Announce this module
announce_data = {
    "name": "Module-5",
    "capabilities": ["button", "leds", "accelerometer", "vibration", "buzzer"],
    "battery": 85,
    "version": "1.0.0"
}
send_message(broadcast, 0x00, announce_data)
```

## 14. Error Handling Protocol

### 14.1 Error Categories and Codes

| Category | Code | Description | Recovery |
|----------|------|-------------|----------|
| Hardware | 0x10 | Battery critical | Force sleep, notify teacher |
| Hardware | 0x11 | Sensor failure | Disable sensor rules |
| Communication | 0x20 | Hub unreachable | Local operation only |
| Communication | 0x21 | Peer unreachable | Queue messages, retry |
| Rule Engine | 0x30 | Rule evaluation timeout | Skip rule temporarily |
| Rule Engine | 0x31 | Invalid rule data | Disable specific rule |
| Storage | 0x40 | Storage corruption | Reset to defaults |
| System | 0x50 | Watchdog reset | Report to hub |

### 14.2 Error Reporting Format

```json
{
  "error": {
    "category": "rule_engine",
    "code": "0x30",
    "description": "Rule evaluation timeout",
    "affected_rule": "12345",
    "timestamp": 1234567890,
    "recovery_action": "rule_disabled"
  },
  "module_state": {
    "battery": 45,
    "uptime": 3600,
    "free_memory": 25000
  }
}
```

### 14.3 Teacher-Friendly Error Messages

| Error | Technical Message | Teacher Message |
|-------|-------------------|-----------------|
| 0x10 | Battery critical | "Module 5 needs charging soon" |
| 0x20 | Hub unreachable | "Module 7 lost connection" |
| 0x30 | Rule evaluation timeout | "Activity too complex for Module 3" |
| 0x40 | Storage corruption | "Module 2 needs reset" |

## 15. Testing and Performance Benchmarks

### 15.1 Communication Performance Targets

- **Message Latency**: <50ms module-to-module
- **Throughput**: >10 messages per second per module
- **Reliability**: >99% delivery success rate
- **Range**: >15m indoor, >50m outdoor

### 15.2 Test Scenarios

1. **Full Classroom Test**: 30 modules simultaneously active
2. **Distance Test**: Modules at varying distances from hub
3. **Interference Test**: Operation with WiFi and Bluetooth active
4. **Scalability Test**: Progressive addition of modules
5. **Recovery Test**: Intentional connection failures and recovery

### 15.3 Performance Monitoring

Built-in diagnostics accessible through hub:

1. **Message Statistics**: Sent, received, failed, retried
2. **Timing Analysis**: Average and maximum latencies
3. **Peer Quality**: Signal strength and reliability per peer
4. **Power Impact**: Battery drain during communication scenarios
