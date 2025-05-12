# Educational Module Rule System: Complete Specification

## 1. Introduction

This document specifies the rule system for the educational playground modules, designed for kindergarten students (age 5) to learn computational thinking and if-else concepts. It defines the inputs ("if" conditions), outputs ("then" actions), rule structures, storage mechanisms, and execution flow.

## 2. Rule System Overview

The rule system follows a simple "If This Then That" paradigm:
- When an input condition occurs on one module
- An output action is triggered on the same or another module
- With optional transformations between input and output

Rules support varying levels of complexity:
- **Simple Rules**: Direct mapping between trigger and action
- **Proportional Rules**: Scaling between input and output values
- **Historical Rules**: Actions based on patterns of past inputs
- **Change-Based Rules**: Actions triggered by rate of change

## 3. Input Conditions ("If" Part)

### 3.1 Button Inputs

| Input Type | Data Type | Range/Values | Description |
|------------|-----------|--------------|-------------|
| `BUTTON_PRESS` | Boolean | true/false | Single button press detected |
| `BUTTON_RELEASE` | Boolean | true/false | Button release detected |
| `BUTTON_HOLD` | Numeric | 0-5000 ms | Duration button is held down |
| `BUTTON_PRESS_COUNT` | Numeric | 0-255 | Number of presses within time window |
| `BUTTON_DOUBLE_TAP` | Boolean | true/false | Two quick presses detected |

### 3.2 Accelerometer Inputs

| Input Type | Data Type | Range/Values | Description |
|------------|-----------|--------------|-------------|
| `ORIENTATION` | Enumeration | UP, DOWN, LEFT, RIGHT, FRONT, BACK | Current module orientation |
| `SHAKE` | Numeric | 0-100 (intensity) | Shake intensity detected |
| `MOVEMENT` | Numeric | 0-100 (intensity) | General movement intensity |
| `TILT_ANGLE_X` | Numeric | -90 to 90 degrees | Tilt angle along X axis |
| `TILT_ANGLE_Y` | Numeric | -90 to 90 degrees | Tilt angle along Y axis |
| `TILT_ANGLE_Z` | Numeric | -90 to 90 degrees | Tilt angle along Z axis |

### 3.3 Grove Sensor Inputs

| Input Type | Data Type | Range/Values | Description |
|------------|-----------|--------------|-------------|
| `DISTANCE` | Numeric | 2-400 cm | Distance from ultrasonic sensor |
| `DISTANCE_ZONE` | Enumeration | NEAR, MEDIUM, FAR | Categorized distance zones |
| `TEMPERATURE` | Numeric | -20 to 80 °C | Temperature reading |
| `TEMPERATURE_ZONE` | Enumeration | COLD, COOL, NORMAL, WARM, HOT | Categorized temperature |
| `POTENTIOMETER` | Numeric | 0-100 % | Slider/dial position |

### 3.4 System State Inputs

| Input Type | Data Type | Range/Values | Description |
|------------|-----------|--------------|-------------|
| `BATTERY_LEVEL` | Numeric | 0-100 % | Current battery percentage |
| `BATTERY_STATE` | Enumeration | LOW, MEDIUM, HIGH | Categorized battery level |
| `TIME_ELAPSED` | Numeric | 0-65535 ms | Time since system event |
| `MODULE_ID` | Numeric | 1-30 | Specific module identifier |

### 3.5 Advanced Input Conditions

| Input Type | Data Type | Range/Values | Description |
|------------|-----------|--------------|-------------|
| `INPUT_DELTA` | Numeric | Varies by input | Change rate of any numeric input |
| `INPUT_AVERAGE` | Numeric | Varies by input | Rolling average of numeric input |
| `INPUT_MAX` | Numeric | Varies by input | Maximum value in time window |
| `INPUT_FREQUENCY` | Numeric | 0-100 Hz | Frequency of boolean input changes |
| `CUMULATIVE_COUNT` | Numeric | 0-65535 | Accumulated count of events |

## 4. Output Actions ("Then" Part)

### 4.1 LED Outputs

| Output Type | Data Type | Range/Values | Description |
|-------------|-----------|--------------|-------------|
| `LED_COLOR` | RGB Tuple | (0-255, 0-255, 0-255) | Color for all LEDs |
| `LED_BRIGHTNESS` | Numeric | 0-255 | Overall brightness level |
| `LED_COUNT` | Numeric | 0-12 | Number of LEDs to illuminate |
| `LED_PATTERN` | Enumeration | SOLID, BLINK, CHASE, RAINBOW, BREATHE, ALTERNATE | Visual pattern to display |
| `LED_DURATION` | Numeric | 0-10000 ms | Duration of LED effect |
| `LED_SPEED` | Numeric | 1-10 | Animation speed for patterns |

### 4.2 Vibration Outputs

| Output Type | Data Type | Range/Values | Description |
|-------------|-----------|--------------|-------------|
| `VIBRATION_INTENSITY` | Numeric | 0-100 % | Strength of vibration |
| `VIBRATION_DURATION` | Numeric | 0-2000 ms | Duration of vibration |
| `VIBRATION_PATTERN` | Enumeration | CONTINUOUS, PULSE, DOUBLE, TRIPLE, LONG_SHORT | Pattern of vibration |
| `VIBRATION_REPEAT` | Numeric | 0-10 | Number of pattern repetitions |

### 4.3 Buzzer Outputs

| Output Type | Data Type | Range/Values | Description |
|-------------|-----------|--------------|-------------|
| `BUZZER_FREQUENCY` | Numeric | 100-10000 Hz | Tone frequency |
| `BUZZER_DURATION` | Numeric | 0-2000 ms | Duration of tone |
| `BUZZER_VOLUME` | Numeric | 0-100 % | Volume level (if adjustable) |
| `BUZZER_NOTE` | Enumeration | C4, D4, E4, F4, G4, A4, B4, C5 | Musical notes |
| `BUZZER_PATTERN` | Enumeration | SINGLE, DOUBLE, TRIPLE, ASCENDING, DESCENDING, SOS | Predefined tone patterns |

### 4.4 System Control Outputs

| Output Type | Data Type | Range/Values | Description |
|-------------|-----------|--------------|-------------|
| `SLEEP_MODE` | Boolean | true/false | Enter low-power mode |
| `MESSAGE_SEND` | JSON | Variable | Send message to another module |
| `STATUS_UPDATE` | JSON | Variable | Send status update to hub |

## 5. Rule Structure

### 5.1 Core Rule Structure

```json
{
  "id": "12345",           // Unique rule identifier
  "name": "Button Light",  // Human-readable name
  "enabled": true,         // Rule active state
  "source": {              // Input trigger specification
    "module_id": "self",   // Source module (self or MAC address)
    "type": "BUTTON_PRESS",// Input type from defined types
    "parameters": {}       // Additional trigger parameters
  },
  "target": {              // Output action specification
    "module_id": "12:34:56:78:9A:BC", // Target module (self or MAC address)
    "type": "LED_COLOR",   // Output type from defined types
    "parameters": {        // Action parameters
      "color": [255, 0, 0] // RGB values for red
    }
  },
  "mapping": {             // Optional input-to-output mapping
    "type": "DIRECT",      // Mapping type: DIRECT, THRESHOLD, PROPORTIONAL, etc.
    "parameters": {}       // Mapping-specific parameters
  },
  "conditions": [],        // Optional additional conditions
  "created": 1712345678,   // Creation timestamp
  "modified": 1712345678   // Last modified timestamp
}
```

### 5.2 Mapping Types

#### 5.2.1 Direct Mapping
```json
"mapping": {
  "type": "DIRECT"
}
```

#### 5.2.2 Threshold Mapping
```json
"mapping": {
  "type": "THRESHOLD",
  "parameters": {
    "thresholds": [
      {"input": 10, "output": {"color": [255, 0, 0]}},
      {"input": 20, "output": {"color": [0, 255, 0]}},
      {"input": 30, "output": {"color": [0, 0, 255]}}
    ]
  }
}
```

#### 5.2.3 Proportional Mapping
```json
"mapping": {
  "type": "PROPORTIONAL",
  "parameters": {
    "input_min": 0,
    "input_max": 100,
    "output_min": 0,
    "output_max": 12,
    "clamp": true
  }
}
```

#### 5.2.4 Historical Mapping
```json
"mapping": {
  "type": "HISTORICAL",
  "parameters": {
    "window_size": 10,     // Number of samples to consider
    "aggregation": "COUNT", // COUNT, AVERAGE, MAX, etc.
    "threshold": 5,         // Threshold for triggering
    "reset_after": true     // Reset after triggering
  }
}
```

### 5.3 Rule Execution Flow

The standard rule execution flow follows these steps:

1. Input event detection (e.g., button press, accelerometer movement)
2. Input value recording in historical buffer
3. Rule matching based on input type
4. Rule evaluation including mapping transformations
5. Output generation (local or remote)
6. Acknowledgment handling (if required)

## 6. Rule Storage Specification

### 6.1 Storage Organization

Rules are organized into three categories:

1. **Local Rules**: Rules that execute on the module itself
2. **Remote Rules**: Rules that trigger actions on other modules
3. **Incoming Rules**: Rules triggered by other modules

### 6.2 File Structure

```
/rules/
  ├── local.json     # Rules where this module is both source and target
  ├── remote.json    # Rules where this module is source but target is remote
  ├── incoming.json  # Rules where this module is target but source is remote
  └── temp.new       # Temporary file for atomic updates
```

### 6.3 Storage Format

Rules are stored as JSON for:
- Human readability (easier debugging)
- Compatibility with web tooling
- Simpler serialization/deserialization

For extremely constrained environments, a binary format option is provided.

### 6.4 Data Integrity

To ensure rule data isn't corrupted:

1. **Atomic Updates**: Write to temporary file, then rename
2. **Checksums**: JSON files include a checksum field
3. **Backup**: Keep previous version until new one confirmed
4. **Validation**: Schema validation before saving

## 7. Historical Data Management

### 7.1 Data Storage

- **Storage Location**: Circular buffer in RAM
- **Size Limitations**: 
  - Maximum 100 samples per input type
  - Oldest samples dropped when buffer full
- **Persistence**: Historical data not preserved across reboots
- **Sample Rate**: Input-specific (Button: on event, Accelerometer: 10Hz)

### 7.2 Aggregation Functions

| Function | Description | Parameters |
|----------|-------------|------------|
| `COUNT` | Number of samples in window | threshold, window_size |
| `AVERAGE` | Average value in window | threshold, operator, window_size |
| `MAX` | Maximum value in window | threshold, operator, window_size |
| `MIN` | Minimum value in window | threshold, operator, window_size |
| `DELTA` | Change between oldest and newest | threshold, operator, window_size |
| `INCREASING` | Boolean if consistently increasing | required_samples, window_size |
| `DECREASING` | Boolean if consistently decreasing | required_samples, window_size |

### 7.3 Example Historical Rule

Rule that plays ascending tones based on button press count:

```json
{
  "id": "hist123",
  "name": "Count Tones",
  "enabled": true,
  "source": {
    "module_id": "self",
    "type": "BUTTON_PRESS",
    "parameters": {
      "window_ms": 5000
    }
  },
  "target": {
    "module_id": "self",
    "type": "BUZZER_NOTE",
    "parameters": {
      "duration_ms": 300
    }
  },
  "mapping": {
    "type": "HISTORICAL",
    "parameters": {
      "window_size": 5,
      "aggregation": "COUNT",
      "input_min": 1,
      "input_max": 7,
      "output_min": 0,
      "output_max": 7,
      "output_map": [
        {"value": 1, "note": "C4"},
        {"value": 2, "note": "D4"},
        {"value": 3, "note": "E4"},
        {"value": 4, "note": "F4"},
        {"value": 5, "note": "G4"},
        {"value": 6, "note": "A4"},
        {"value": 7, "note": "B4"}
      ]
    }
  }
}
```

## 8. Rule Engine API

### 8.1 Core Functions

```python
def load_rules() -> RuleCollection:
    """Load all rules from storage."""
    
def save_rules(rules: RuleCollection) -> bool:
    """Save all rules to storage."""
    
def add_rule(rule: Rule) -> str:
    """Add a new rule and return its ID."""
    
def update_rule(rule_id: str, updates: dict) -> bool:
    """Update an existing rule."""
    
def delete_rule(rule_id: str) -> bool:
    """Delete a rule by ID."""
    
def get_rule(rule_id: str) -> Rule:
    """Retrieve a specific rule by ID."""
    
def list_rules(filters: dict = None) -> list[Rule]:
    """List rules, optionally filtered."""
```

### 8.2 Rule Evaluation Functions

```python
def evaluate_input(input_type: str, input_value: any) -> list[Rule]:
    """Find rules triggered by a specific input."""
    
def calculate_output(rule: Rule, input_value: any) -> dict:
    """Calculate the output for a rule given an input value."""
    
def apply_mapping(mapping: dict, input_value: any) -> any:
    """Apply a mapping transformation to an input value."""
```

### 8.3 Rule Management Functions

```python
def enable_rule(rule_id: str) -> bool:
    """Enable a specific rule."""
    
def disable_rule(rule_id: str) -> bool:
    """Disable a specific rule."""
    
def backup_rules() -> str:
    """Create a backup of all rules."""
    
def restore_rules(backup_id: str) -> bool:
    """Restore rules from a backup."""
    
def clear_all_rules() -> bool:
    """Delete all rules."""
```

### 8.4 Historical Data Functions

```python
def record_input(input_type: str, value: any) -> None:
    """Record an input value for historical rules."""
    
def get_historical_data(input_type: str, window: int) -> list:
    """Get historical data for an input type."""
```

## 9. Rule Creation Workflow

### 9.1 Tablet App Interface

1. Teacher selects "Create Rule" in tablet app
2. Teacher selects source module and input trigger
3. Teacher selects target module and output action
4. Teacher configures any rule parameters
5. Teacher tests rule with preview function
6. Teacher saves rule to system
7. Hub distributes rule to appropriate modules

### 9.2 Rule Language for Advanced Users

Optional text-based rule definition language:

```
WHEN <module>.<input_condition> THEN <module>.<output_action> [WITH <mapping>]
```

Examples:
```
WHEN Module1.Button.Pressed THEN Module2.LEDs.SetColor(red)
WHEN Module3.Accelerometer.Shaken > 50 THEN Module3.Vibration.Activate(duration:500ms)
WHEN Module5.Button.HeldFor > 2s THEN Module5.LEDs.Illuminate(count:$value/500)
```

## 10. Rule Storage Optimization

### 10.1 Memory Efficiency

1. **Rule Indexing**: Index rules by input type for faster lookup
2. **Lazy Loading**: Load rule details only when needed
3. **Memory Pooling**: Reuse memory for rule evaluation

### 10.2 Storage Efficiency

1. **Incremental Updates**: Only write changed rules
2. **Compression**: Optional compression for rule storage
3. **Deduplication**: Share common parameters across rules

### 10.3 Processing Efficiency

1. **Rule Compilation**: Pre-process rules for faster evaluation
2. **Evaluation Ordering**: Prioritize simpler rules first
3. **Caching**: Cache recent rule evaluations

## 11. Testing and Validation

### 11.1 Rule Validation

Rules are validated against these criteria:
- Input and output types must be valid
- Parameters must have valid values and types
- Mapping must be appropriate for input/output types
- Resource usage must be within module constraints

### 11.2 Rule Testing

Each rule can be tested:
- Direct preview on physical modules
- Simulated execution in tablet app
- Step-by-step execution with value inspection

### 11.3 Performance Benchmarks

- **Rule Storage**: <1KB per rule
- **Rule Evaluation**: <5ms per rule
- **Maximum Rules**: 20 per module
- **Historical Data**: Up to 100 samples per input type

## 12. Educational Considerations

### 12.1 Complexity Progression

Rules are designed to introduce computational thinking concepts progressively:

1. **Level 1**: Simple cause-effect (button press → light)
2. **Level 2**: Different inputs and outputs (shake → sound)
3. **Level 3**: Multiple devices (my button → your light)
4. **Level 4**: Conditional effects (hard shake → bright light)
5. **Level 5**: Proportional relationships (how long → how many)
6. **Level 6**: Historical patterns (count of presses → pattern)

### 12.2 Age-Appropriate Interactions

All rules should consider the abilities of 5-year-old children:
- Immediate feedback (<100ms response)
- Clear cause-effect relationships
- Engaging sensory responses
- Forgiving of unintended inputs
- Self-explanatory behaviors

### 12.3 Teacher Controls

Teachers can:
- Create rule sets for different activities
- Enable/disable rules remotely
- Monitor rule executions
- Reset modules to default state
- Adjust rule parameters without recreation
