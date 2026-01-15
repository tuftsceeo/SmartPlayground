# Smart Playground App: MVP Implementation Plan

This document outlines the practical steps to implement a Minimum Viable Product (MVP) of the Smart Playground App based on the interactive prototype. The plan focuses on core functionality, using WebBLE for direct hub communication, and prioritizes features that deliver the most value for early testing.

## 1. Technology Stack

### Frontend & Backend (Combined React App)
- **Framework**: React.js (Create React App or Vite)
- **UI Components**: Tailwind CSS (already used in prototype)
- **State Management**: React Context API or simple Redux setup
- **Communication**: Web Bluetooth API for direct hub connection
- **Build/Deploy**: Standard React build process, deployed as static site

### Hub Integration
- **Communication**: Web Bluetooth API (BLE GATT services)
- **Protocol**: JSON messages over BLE characteristics
- **Persistence**: Local storage for rules/configuration

## 2. Implementation Priorities

### High Priority
1. Module discovery and connection via WebBLE
2. Basic rule creation and management 
3. Rule deployment to modules
4. Module status monitoring (RSSI, connection state)

### Medium Priority
1. Remote rule configuration (source/target)
2. Rule testing functionality
3. Module configuration (naming, grouping)
4. Deployment progress visualization

### Low Priority
1. Activity templates
2. User authentication
3. Advanced rule types
4. Offline functionality

## 3. Implementation Phases

### Phase 1: Web Bluetooth Integration (1-2 weeks)

1. **BLE Connection Management**
   - Implement device scanning and filtering for ESP32 modules
   - Create connection management hooks/context
   - Handle connection/disconnection events and reconnection logic
   - Test basic connectivity with hub device

2. **BLE Service Discovery**
   - Identify and connect to the hub's GATT services
   - Define characteristic UUIDs for different operations
   - Implement read/write/notify operations for characteristics

3. **Protocol Definition**
   - Design JSON message format for operations:
     - Module discovery
     - Rule management
     - Deployment commands
     - Status updates
   - Implement serialization/deserialization utilities

### Phase 2: Module Management (1 week)

1. **Module Discovery Interface**
   - Convert the prototype scanning UI to use real BLE scanning
   - Implement device filtering based on service UUIDs
   - Create module list with live connection status
   - Add RSSI monitoring with signal strength indicators

2. **Module Configuration**
   - Allow renaming modules
   - Implement module grouping functionality
   - Add module detail view with status information
   - Create live update mechanism for status changes

### Phase 3: Rule Builder Implementation (2 weeks)

1. **Rule Data Structure**
   - Finalize rule format based on the ESP32 module's rule_engine.py
   - Create validation functions for rule structure
   - Implement rule serialization for BLE transmission

2. **Rule Builder UI Integration**
   - Connect the prototype rule builder to the BLE backend
   - Implement all input parameter configuration panels
   - Implement all output parameter configuration panels
   - Add validation and error handling

3. **Remote Rule Management**
   - Implement source/target module selection logic
   - Create the rule relationship visualization
   - Add batch rule creation for remote rules
   - Ensure proper rule routing information

### Phase 4: Deployment System (1-2 weeks)

1. **Rule Deployment Protocol**
   - Design deployment message sequence
   - Implement chunked transmission for rules (BLE has packet size limits)
   - Create acknowledgment and verification system
   - Handle error cases and retries

2. **Deployment UI**
   - Connect the prototype deployment UI to actual deployment process
   - Add real-time progress updates 
   - Implement error handling and recovery options
   - Create success/failure feedback mechanisms

3. **Rule Testing**
   - Implement temporary rule deployment for testing
   - Create test result visualization
   - Add basic logging for test outcomes

### Phase 5: Testing & Refinement (1 week)

1. **Integrated Testing**
   - Test complete workflows with real hardware
   - Validate rule execution on modules
   - Measure and optimize BLE performance
   - Document any limitations or edge cases

2. **User Experience Refinement**
   - Improve error messages and recovery flows
   - Enhance visual feedback during operations
   - Optimize UI for tablet use
   - Add helpful tooltips and guidance

## 4. WebBLE Implementation Considerations

### Device Discovery

The Web Bluetooth API requires user interaction to initiate scanning:

```javascript
// Simplified example - not complete code
async function scanForDevices() {
  try {
    // Request device with specific service UUID
    const device = await navigator.bluetooth.requestDevice({
      filters: [{
        services: ['uuid-of-smart-playground-service']
      }]
    });
    
    // Now connect to the device
    await connectToDevice(device);
  } catch (error) {
    