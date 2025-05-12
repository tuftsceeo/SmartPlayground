# Smart Playground System: Architecture Specification

## 1. System Overview

This document specifies the architecture for an interactive playground system designed for kindergarten students (age 5) to learn computational thinking and if-else concepts through physical, programmable modules.

### 1.1 System Components

1. **Module Family (15 Plushies + 15 Buttons)**
   - ESP32C6 Xiao microcontrollers
   - 12 NeoPixel LED ring
   - Tactile button input (form varies by module type)
   - 3-axis accelerometer
   - Buzzer
   - Battery-powered

   **Plushie Modules (15)**
   - Compact form integrated into stuffed animal keychains
   - Vibration motor for haptic feedback
   - Standard tactile button
   
   **Button Modules (15)**
   - Large 3-inch arcade-style button housing
   - Audio recording and playback circuit
   - MEMS microphone and 0.5W speaker

2. **Hub**
   - ESP32C6 Xiao microcontroller
   - Dual connectivity (BLE and ESP-NOW)
   - Acts as bridge between tablet app and modules
   - Coordinates network and distributes configuration

3. **Tablet App**
   - Teacher-facing configuration interface
   - Connects to hub via BLE
   - Provides rule creation and activity management
   - Monitors system status

### 1.2 Architecture Philosophy

The system follows a hybrid architecture combining:
- **Centralized Configuration**: Rules and activities defined through tablet app via hub
- **Distributed Execution**: Modules operate independently once configured
- **Direct Communication**: Module-to-module messaging for rule execution

This approach provides resilience (modules continue operating when hub is absent) while maintaining ease of configuration for non-technical teachers.

## 2. Network Architecture

### 2.1 Communication Protocols

1. **Module-to-Module & Module-to-Hub**: ESP-NOW
   - Low-latency communication (~5-10ms)
   - Low power consumption
   - Peer-to-peer without infrastructure
   - Range: ~100m line-of-sight

2. **Hub-to-Tablet**: Bluetooth Low Energy (BLE)
   - Standard tablet connectivity
   - User-friendly connection process
   - Sufficient bandwidth for configuration data

### 2.2 Module Clustering Architecture

To overcome ESP-NOW's 20-peer limitation while supporting up to 30 modules:

1. **Logical Groups**: Modules organized into activity-based groups (<20 modules per group)
2. **Group Leaders**: One module per group serves as communication point to hub
3. **Local Communication**: Modules within a group communicate directly
4. **Cross-Group Messaging**: Messages between groups route through hub

This approach aligns with educational activities naturally organizing into groups and improves power efficiency through localized communication.

### 2.3 Network Topology

![Network Topology Diagram](https://placeholder-for-topology-diagram.png)

- **Groups**: Logical clusters of related modules (typically 4-8 per activity)
- **Hub**: Central connection point for tablet and inter-group communication
- **Direct Links**: Peer-to-peer connections between modules within a group

## 3. Module Architecture

### 3.1 Shared Hardware Components

| Component | Specification | Purpose |
|-----------|---------------|---------|
| Microcontroller | ESP32C6 Xiao | Core processing, wireless communication |
| Display | 12 NeoPixel LED ring | Visual feedback and indication |
| Input | Tactile button (varies by type) | User interaction trigger |
| Motion Sensor | LIS2DW12 3-axis accelerometer | Orientation and movement detection |
| Audio | Buzzer | Basic auditory feedback |
| Power | LiPo battery | Portable power source |

### 3.2 Plushie-Specific Components

| Component | Specification | Purpose |
|-----------|---------------|---------|
| Form Factor | Compact, embedded in stuffed animal | Child-friendly, portable interaction |
| Haptic Feedback | Vibration motor | Physical feedback for events |
| Housing | 3D printed casing inside plush body | Protection and integration |

### 3.3 Button-Specific Components

| Component | Specification | Purpose |
|-----------|---------------|---------|
| Form Factor | 3-inch arcade-style button | Large interaction surface for group activities |
| Audio System | MEMS mic + 0.5W speaker | Higher quality sound, recording capability |
| Housing | Durable plastic button housing | Standalone, robust interaction |

### 3.4 Software Architecture

```
+---------------------+      +---------------------+
| Hardware Interface  |      | Communication Layer |
|---------------------|      |---------------------|
| - LED Control       |      | - ESP-NOW Protocol  |
| - Button Input      |      | - Message Handling  |
| - Accelerometer     |<---->| - Peer Management   |
| - Vibration/Audio   |      | - Group Membership  |
| - Buzzer Control    |      | - Reliability       |
+---------------------+      +---------------------+
           ^                           ^
           |                           |
           v                           v
+---------------------+      +---------------------+
| Rule Engine         |      | Power Management    |
|---------------------|      |---------------------|
| - Rule Storage      |      | - Sleep Control     |
| - Rule Evaluation   |<---->| - Battery Monitoring|
| - Action Execution  |      | - Activity Detection|
| - Input Processing  |      | - Wake Mechanisms   |
| - Historical Data   |      |                     |
+---------------------+      +---------------------+
```

#### 3.4.1 Core Software Components

1. **Hardware Interface Layer**
   - Abstracts physical components
   - Handles calibration and configuration
   - Provides consistent APIs for sensors and outputs
   - Implements specialized interfaces for plushie/button variants

2. **Communication Layer**
   - Manages ESP-NOW connections
   - Handles message sending/receiving
   - Implements reliability mechanisms
   - Maintains peer relationships

3. **Rule Engine**
   - Stores and retrieves rules
   - Evaluates input conditions
   - Executes matching actions
   - Processes historical data
   - Manages rule relationships

4. **Power Management**
   - Controls sleep modes
   - Monitors battery levels
   - Optimizes power usage
   - Handles wake conditions

### 3.5 Power Management Strategy

Standardized power management approach across all modules:

1. **Activity Detection**
   - Button presses
   - Accelerometer movement
   - Message reception
   - Rule execution

2. **Power States**
   - **Active**: Full functionality, all sensors active
   - **Deep Sleep**: After 10 minutes of inactivity, wake on button only

3. **Wake Mechanisms**
   - Primary: Button press
   - Secondary: Scheduled wake-ups for critical modules

4. **Battery Monitoring**
   - Regular voltage sampling
   - Low battery warnings
   - Critical battery auto-shutdown

## 4. Hub Architecture

### 4.1 Hardware Components

Same as modules with additional emphasis on reliable power supply (typically wall-powered rather than battery-operated).

### 4.2 Software Architecture

```
+-----------------------+       +------------------------+
| BLE Service Layer     |<----->| ESP-NOW Management     |
|                       |       |                        |
| - GATT Services       |       | - Peer management      |
| - Characteristic      |       | - Message routing      |
|   Handlers            |       | - Reliability control  |
+-----------------------+       +------------------------+
            ^                              ^
            |                              |
            v                              v
+-----------------------+       +------------------------+
| Protocol Translation  |<----->| System State Manager   |
|                       |       |                        |
| - Message conversion  |       | - Module registry      |
| - Format adaptation   |       | - Rule registry        |
| - Queue management    |       | - Group management     |
+-----------------------+       +------------------------+
```

### 4.3 Message Queue Management

Priority-based message processing to handle traffic spikes:

1. **Priority Levels**:
   - System critical (highest): Reset, emergency commands
   - Configuration: Rule updates, group assignments
   - Status: Battery reports, sensor data
   - Routine: Regular status updates (lowest)

2. **Queue Processing**: Round-robin with priority preemption
3. **Overflow Handling**: Merge similar messages, drop oldest lower priority

### 4.4 Connectivity Management

1. **BLE Connection**
   - Authentication and pairing with tablet
   - Service advertisement
   - Connection parameter optimization

2. **ESP-NOW Network**
   - Dynamic peer management for >20 modules
   - Group leader coordination
   - Broadcast message optimization

3. **Recovery Procedures**
   - BLE disconnect: Continue ESP-NOW operations, buffer tablet-bound messages
   - ESP-NOW failures: Implement exponential backoff, try alternative routing

## 5. Tablet App Architecture

### 5.1 Application Structure

```
+---------------------+      +---------------------+
| User Interface      |      | BLE Communication   |
|---------------------|      |---------------------|
| - Rule Builder      |      | - Connection Mgmt   |
| - Activity Designer |<---->| - Service Discovery |
| - Module Monitor    |      | - Data Transfer     |
| - Status Dashboard  |      | - Reliability       |
+---------------------+      +---------------------+
           ^                           ^
           |                           |
           v                           v
+---------------------+      +---------------------+
| Rule Management     |      | Data Storage        |
|---------------------|      |---------------------|
| - Rule Templates    |      | - Activity Library  |
| - Rule Validation   |<---->| - Configuration     |
| - Rule Translation  |      | - Module Database   |
| - Visual Simulation |      | - Usage Analytics   |
+---------------------+      +---------------------+
```

### 5.2 Teacher-Centric Design

Optimized for non-technical kindergarten teachers:

1. **Visual Rule Builder**
   - Drag-and-drop interface for rule creation
   - Visual representation of triggers and actions
   - Real-time preview of rule effects

2. **Pre-built Activities**
   - Ready-to-use educational scenarios
   - Age-appropriate computational thinking exercises
   - Curriculum-aligned challenges

3. **Simple Monitoring**
   - Clear battery status indicators
   - Module health visualization
   - Activity progress tracking
   - Differentiated visualization for plushie vs button modules

### 5.3 Data Synchronization

1. **Configuration Distribution**
   - Rules packaged and sent to hub
   - Confirmation of successful deployment
   - Version tracking for configuration sets

2. **Status Collection**
   - Battery levels aggregation
   - Error reporting and visualization
   - Activity completion tracking

## 6. Interaction Patterns

### 6.1 Configuration Flow

1. Teacher opens tablet app
2. App connects to hub via BLE
3. Teacher selects or creates an activity
4. Teacher assigns modules to groups (can mix plushies and buttons)
5. Hub distributes rules to appropriate modules
6. Modules confirm configuration
7. Teacher starts activity

### 6.2 Rule Execution Flow

1. Module detects input event (e.g., button press)
2. Input value recorded for historical rules
3. Rule engine identifies matching rules
4. Rules evaluated including mappings
5. Actions executed locally or messages sent to target modules
6. Target modules perform actions
7. Optional acknowledgments returned

### 6.3 Module-Specific Interactions

#### 6.3.1 Plushie Module Interactions
1. Physical handling (orientation changes, shaking, tilting)
2. Button press/release/hold
3. Visual feedback via LED ring
4. Haptic feedback via vibration motor
5. Basic sound via buzzer

#### 6.3.2 Button Module Interactions
1. Large button press (more accessible for group activities)
2. Audio recording and playback
3. Visual feedback via LED ring
4. Higher-volume sound output
5. Orientation detection when button is moved

### 6.4 Group Coordination

1. Hub sends synchronization message to group
2. Group leader confirms readiness
3. Hub initiates coordinated activity
4. Modules execute pre-programmed sequences
5. Results reported back to hub
6. Hub aggregates and displays results to teacher

## 7. Error Handling Framework

### 7.1 Error Categories

1. **Hardware Errors**: Battery issues, sensor failures
2. **Communication Errors**: Message failures, disconnections
3. **Rule Engine Errors**: Evaluation failures, invalid rules
4. **Storage Errors**: Corruption, write failures
5. **System Errors**: Crashes, watchdog resets

### 7.2 Recovery Mechanisms

| Error Type | Detection | Recovery | User Notification |
|------------|-----------|----------|-------------------|
| Low Battery | Voltage monitoring | Sleep non-essential functions | Yellow LED pattern |
| Communication Loss | Timeout/ACK failure | Retry, then operate locally | Red blink pattern |
| Rule Execution Failure | Exception/timeout | Skip rule, log error | Brief error indication |
| Storage Corruption | Checksum verification | Restore from backup | Teacher app notification |

### 7.3 Teacher Notifications

Error messages translated to teacher-friendly language:
- Technical: "ESP-NOW peer connection failed"
- Teacher: "Module 5 can't connect to other modules"

## 8. Implementation Considerations

### 8.1 Development Priorities

1. Core module functionality with basic rule execution
2. Hub and communication framework
3. Advanced rule capabilities
4. Tablet app interface
5. Power management optimization
6. Group coordination features
7. Audio recording/playback for button modules

### 8.2 Testing Strategy

1. **Unit Testing**: Individual component validation
2. **Integration Testing**: Combined component verification
3. **System Testing**: End-to-end scenario validation
4. **Field Testing**: Classroom environment validation
5. **User Testing**: Teacher and student experience validation
6. **Module-Specific Testing**: 
   - Plushie: Durability, vibration effectiveness, portability
   - Button: Audio quality, large-button accessibility, group interaction

### 8.3 Performance Targets

- **Rule Evaluation**: <5ms per rule
- **Message Latency**: <50ms module-to-module
- **Battery Life**: >8 hours active use
- **Wake-from-Sleep**: <1 second
- **Maximum Rules**: 20 per module
- **Audio Quality** (Button modules): Clear reproduction at classroom volumes

## 9. Extension Points

### 9.1 Module Extensions

The system architecture allows for future expansion of module capabilities:
- Additional sensors via software updates
- New module types maintaining the same communication protocol
- Enhanced audio capabilities for plushie modules

### 9.2 Advanced Rule Types

Framework supports future enhancement with:
- Time-based rules (scheduled actions)
- Multi-condition rules (AND/OR logic)
- Probabilistic rules (random effects)
- Pattern-recognition rules

### 9.3 Infrastructure Integration

Potential extensions include:
- Cloud connectivity for activity sharing
- Classroom management integration
- Learning analytics collection
