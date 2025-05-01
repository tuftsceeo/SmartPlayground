"""
Educational Module System - Rule Engine
--------------------------------------
This module implements the rule engine for the Educational Module System.

>>>> This file contains the methods that need to be added to the existing rule_engine.py
file to support remote rule functionality.

"""

import json
import os
import time
import uasyncio as asyncio

# Input types
class InputTypes:
    # Button inputs
    BUTTON_PRESS = "BUTTON_PRESS"
    BUTTON_RELEASE = "BUTTON_RELEASE"
    BUTTON_HOLD = "BUTTON_HOLD"
    BUTTON_DOUBLE_TAP = "BUTTON_DOUBLE_TAP"
    
    # Accelerometer inputs
    ORIENTATION = "ORIENTATION"
    SHAKE = "SHAKE"
    MOVEMENT = "MOVEMENT"
    TILT_ANGLE_X = "TILT_ANGLE_X"
    TILT_ANGLE_Y = "TILT_ANGLE_Y"
    TILT_ANGLE_Z = "TILT_ANGLE_Z"
    
    # Grove sensor inputs
    DISTANCE = "DISTANCE"
    DISTANCE_ZONE = "DISTANCE_ZONE"
    TEMPERATURE = "TEMPERATURE"
    TEMPERATURE_ZONE = "TEMPERATURE_ZONE"
    POTENTIOMETER = "POTENTIOMETER"
    
    # System state inputs
    BATTERY_LEVEL = "BATTERY_LEVEL"
    BATTERY_STATE = "BATTERY_STATE"
    
# Output types
class OutputTypes:
    # LED outputs
    LED_COLOR = "LED_COLOR"
    LED_BRIGHTNESS = "LED_BRIGHTNESS"
    LED_COUNT = "LED_COUNT"
    LED_PATTERN = "LED_PATTERN"
    
    # Vibration outputs
    VIBRATION = "VIBRATION"
    VIBRATION_PATTERN = "VIBRATION_PATTERN"
    
    # Buzzer outputs
    BUZZER_FREQUENCY = "BUZZER_FREQUENCY"
    BUZZER_NOTE = "BUZZER_NOTE"
    BUZZER_PATTERN = "BUZZER_PATTERN"

# Mapping types
class MappingTypes:
    DIRECT = "DIRECT"
    THRESHOLD = "THRESHOLD"
    PROPORTIONAL = "PROPORTIONAL"

class Rule:
    """
    Represents a rule in the educational module system.
    
    A rule has an if-then structure:
    - id: Unique identifier
    - name: Human-readable name
    - enabled: Whether the rule is active
    - source: Input trigger specification (the "if" part)
    - target: Output action specification (the "then" part)
    - mapping: How to transform the input to output
    """
    
    def __init__(self, rule_dict):
        """Initialize a rule from a dictionary."""
        self.id = rule_dict.get('id')
        self.name = rule_dict.get('name', 'Unnamed Rule')
        self.enabled = rule_dict.get('enabled', True)
        self.source = rule_dict.get('source', {})
        self.target = rule_dict.get('target', {})
        self.mapping = rule_dict.get('mapping', {'type': MappingTypes.DIRECT})
        self.created = rule_dict.get('created')
        self.modified = rule_dict.get('modified')
    
    def to_dict(self):
        """Convert rule to dictionary for storage."""
        return {
            'id': self.id,
            'name': self.name,
            'enabled': self.enabled,
            'source': self.source,
            'target': self.target,
            'mapping': self.mapping,
            'created': self.created,
            'modified': self.modified
        }
    
    def __str__(self):
        """String representation of the rule."""
        return f"Rule({self.id}): {self.name}"

class RuleEngine:
    """
    Rule engine for the educational module system.
    
    Handles:
    - Loading and saving rules
    - Evaluating rules based on inputs
    - Executing actions based on rule evaluation
    """
    
    def __init__(self, hardware, storage_path="/rules"):
        """
        Initialize the rule engine.
        
        Args:
            hardware: Hardware interface
            storage_path: Path to store rule files
        """
        self.hardware = hardware
        self.storage_path = storage_path
        self.local_rules = []  # Rules where this module is both source and target
        self.remote_rules = []  # Rules where this module is source but target is remote
        self.incoming_rules = []  # Rules where this module is target but source is remote
        
        # Ensure storage directory exists
        try:
            os.mkdir(storage_path)
        except:
            # Directory might already exist
            pass
        
        # Load rules
        self.load_rules()
        
        # Flag to track if input handlers are registered
        self.handlers_registered = False
        
        print("Rule Engine initialized")
    
    def set_remote_manager(self, remote_manager):
        """Set the remote manager for handling remote rules.
        
        Args:
            remote_manager: RemoteRuleManager instance
        """
        self._remote_manager = remote_manager
        print("Remote manager set in RuleEngine")
        
    def load_rules(self):
        """Load all rules from storage."""
        print("Loading rules...")
        
        # Load local rules
        self._load_rule_file("local.json", self.local_rules)
        
        # Load remote rules
        self._load_rule_file("remote.json", self.remote_rules)
        
        # Load incoming rules
        self._load_rule_file("incoming.json", self.incoming_rules)
    
    def _load_rule_file(self, filename, rule_list):
        """Load rules from a file."""
        filepath = self.storage_path + "/" + filename
        try:
            with open(filepath, 'r') as f:
                rules_data = json.load(f)
            
            # Clear existing rules
            rule_list.clear()
            
            # Add new rules
            for rule_data in rules_data:
                rule_list.append(Rule(rule_data))
            
            print(f"Loaded {len(rule_list)} rules from {filename}")
        except OSError:
            print(f"No rules file found at {filepath}, starting with empty rules")
        except ValueError:
            print(f"Error parsing rules from {filename}, starting with empty rules")
    
    def save_rules(self):
        """Save all rules to storage."""
        print("Saving rules...")
        
        # Save local rules
        self._save_rule_file("local.json", self.local_rules)
        
        # Save remote rules
        self._save_rule_file("remote.json", self.remote_rules)
        
        # Save incoming rules
        self._save_rule_file("incoming.json", self.incoming_rules)
    
    def _save_rule_file(self, filename, rule_list):
        """Save rules to a file."""
        filepath = self.storage_path + "/" + filename
        temp_filepath = self.storage_path + "/temp.new"
        
        try:
            # Convert rules to dictionaries
            rules_data = [rule.to_dict() for rule in rule_list]
            
            # Write to temporary file
            with open(temp_filepath, 'w') as f:
                json.dump(rules_data, f)
            
            # Rename to target file (atomic operation where possible)
            try:
                os.rename(temp_filepath, filepath)
            except:
                # If rename fails, try direct write
                with open(filepath, 'w') as f:
                    json.dump(rules_data, f)
                # Clean up temp file
                try:
                    os.remove(temp_filepath)
                except:
                    pass
            
            print(f"Saved {len(rule_list)} rules to {filename}")
        except Exception as e:
            print(f"Error saving rules to {filename}: {e}")
            # Clean up temporary file if it exists
            try:
                os.remove(temp_filepath)
            except:
                pass
    
    def add_rule(self, rule_data):
        """
        Add a new rule.
        
        Args:
            rule_data: Rule data dictionary
            
        Returns:
            Rule ID
        """
        # Generate a unique ID if not provided
        if 'id' not in rule_data:
            rule_data['id'] = f"rule_{int(time.time())}"
        
        # Set creation and modification timestamps
        current_time = int(time.time())
        rule_data['created'] = current_time
        rule_data['modified'] = current_time
        
        # Create rule object
        rule = Rule(rule_data)
        
        print(f"Adding rule: {rule.name} (ID: {rule.id})")
        
        # Determine rule type and add to appropriate list
        source_module = rule.source.get('module_id')
        target_module = rule.target.get('module_id')
        
        if source_module in ('self', None) and target_module in ('self', None):
            self.local_rules.append(rule)
            print("Added as local rule")
        elif source_module in ('self', None) and target_module not in ('self', None):
            self.remote_rules.append(rule)
            print("Added as remote rule")
        else:
            self.incoming_rules.append(rule)
            print("Added as incoming rule")
        
        # Save rules
        self.save_rules()
        
        # Ensure handlers are registered if we add our first rule
        if not self.handlers_registered:
            self.register_input_handlers()
        
        return rule.id
    
    def update_rule(self, rule_id, updates):
        """
        Update an existing rule.
        
        Args:
            rule_id: Rule ID
            updates: Updates to apply
            
        Returns:
            Success flag
        """
        # Find rule in all lists
        rule = self.get_rule(rule_id)
        if not rule:
            print(f"Rule {rule_id} not found")
            return False
        
        print(f"Updating rule: {rule.name} (ID: {rule.id})")
        
        # Apply updates
        for key, value in updates.items():
            if key != 'id':  # Don't allow changing ID
                setattr(rule, key, value)
        
        # Update modification timestamp
        rule.modified = int(time.time())
        
        # Save rules
        self.save_rules()
        
        return True
    
    def delete_rule(self, rule_id):
        """
        Delete a rule.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            Success flag
        """
        print(f"Deleting rule with ID: {rule_id}")
        
        # Try to remove from all lists
        for rule_list in [self.local_rules, self.remote_rules, self.incoming_rules]:
            for i, rule in enumerate(rule_list):
                if rule.id == rule_id:
                    rule_list.pop(i)
                    print(f"Deleted rule: {rule.name}")
                    # Save rules
                    self.save_rules()
                    return True
        
        print(f"Rule {rule_id} not found")
        return False
    
    def get_rule(self, rule_id):
        """
        Get a rule by ID.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            Rule object or None
        """
        # Search in all lists
        for rule_list in [self.local_rules, self.remote_rules, self.incoming_rules]:
            for rule in rule_list:
                if rule.id == rule_id:
                    return rule
        
        return None
    
    def list_rules(self):
        """
        List all rules.
        
        Returns:
            List of rules
        """
        all_rules = self.local_rules + self.remote_rules + self.incoming_rules
        return all_rules
    
    def clear_all_rules(self):
        """Delete all rules."""
        print("Clearing all rules")
        self.local_rules.clear()
        self.remote_rules.clear()
        self.incoming_rules.clear()
        self.save_rules()
        return True
    
    def evaluate_input(self, input_type, input_value):
        """
        Find rules triggered by a specific input and execute them.
        
        Args:
            input_type: Input type
            input_value: Input value
            
        Returns:
            List of executed rules
        """
        print(f"Evaluating input: {input_type} = {input_value}")
        executed_rules = []
        
        # Check local and remote rules
        for rule in self.local_rules + self.remote_rules:
            if not rule.enabled:
                continue
            
            if rule.source.get('type') == input_type:
                print(f"Rule matched: {rule.name}")
                # Check parameters if any
                params = rule.source.get('parameters', {})
                if params:
                    # Parameter-specific logic could go here
                    # This is where you'd implement checks like "greater than threshold" etc.
                    pass
                
                # Rule matches input type, execute it
                result = self.execute_rule(rule, input_value)
                if result:
                    executed_rules.append(rule)
        
        return executed_rules
    
    def apply_mapping(self, mapping, input_value):
        """
        Apply a mapping transformation to an input value.
        
        Args:
            mapping: Mapping dictionary
            input_value: Input value
            
        Returns:
            Transformed output value
        """
        mapping_type = mapping.get('type', MappingTypes.DIRECT)
        parameters = mapping.get('parameters', {})
        
        print(f"Applying mapping: {mapping_type}")
        
        if mapping_type == MappingTypes.DIRECT:
            return input_value
        
        elif mapping_type == MappingTypes.THRESHOLD:
            thresholds = parameters.get('thresholds', [])
            for threshold in sorted(thresholds, key=lambda x: x['input']):
                if input_value <= threshold['input']:
                    print(f"Threshold matched: {threshold['input']}")
                    return threshold['output']
            # If no threshold matches, return the highest one
            if thresholds:
                print(f"Using highest threshold: {thresholds[-1]['input']}")
                return thresholds[-1]['output']
            return None
        
        elif mapping_type == MappingTypes.PROPORTIONAL:
            input_min = parameters.get('input_min', 0)
            input_max = parameters.get('input_max', 100)
            output_min = parameters.get('output_min', 0)
            output_max = parameters.get('output_max', 100)
            clamp = parameters.get('clamp', True)
            
            # Calculate proportion
            try:
                proportion = (input_value - input_min) / (input_max - input_min)
            except ZeroDivisionError:
                proportion = 0
            
            # Apply proportion to output range
            output_value = output_min + proportion * (output_max - output_min)
            
            # Clamp if needed
            if clamp:
                output_value = max(output_min, min(output_max, output_value))
            
            print(f"Proportional mapping: {input_value} -> {output_value}")
            return output_value
        
        # Default: return input value unchanged
        return input_value
    
    def execute_rule(self, rule, input_value):
        """
        Execute a rule with the given input value.
        
        Args:
            rule: Rule to execute
            input_value: Input value
            
        Returns:
            Success flag
        """
        print(f"Executing rule: {rule.name}")
        
        try:
            # Apply mapping to get output value/parameters
            mapping = rule.mapping
            output_result = self.apply_mapping(mapping, input_value)
            
            # Get target details
            target_module = rule.target.get('module_id')
            target_type = rule.target.get('type')
            target_params = rule.target.get('parameters', {})
            
            # If mapping returned a dict, it's parameters to use
            if isinstance(output_result, dict):
                # Update parameters with mapping result
                for key, value in output_result.items():
                    target_params[key] = value
                output_value = input_value  # Use original input value
            else:
                # Use mapping result as the output value
                output_value = output_result
            
            # Execute action based on target module
            if target_module in ('self', None):
                # Local action
                return self.execute_local_action(target_type, target_params, output_value)
            else:
                # Remote action
                return self.execute_remote_action(target_module, target_type, target_params, output_value)
            
        except Exception as e:
            print(f"Error executing rule {rule.id}: {e}")
            return False
    
    def execute_local_action(self, action_type, parameters, output_value):
        """
        Execute a local action.
        
        Args:
            action_type: Action type
            parameters: Action parameters
            output_value: Output value from mapping
            
        Returns:
            Success flag
        """
        print(f"Executing local action: {action_type}")
        
        # LED actions
        if action_type == OutputTypes.LED_COLOR:
            # Check if we're using the new hue-based color
            if 'hue' in parameters:
                hue = parameters.get('hue', 0)  # 0-360 value
                print(f"Setting LED color to hue {hue}")
                # Use the _hue method from the LED ring to convert hue to RGB
                rgb_color = self.hardware.led_ring._hue(hue, self.hardware.led_ring.current_brightness)
                self.hardware.set_led_color(rgb_color)
            else:
                # Legacy RGB support for backwards compatibility during transition
                color = parameters.get('color', [255, 0, 0])
                print(f"Setting LED color using legacy RGB {color}")
                self.hardware.set_led_color(tuple(color))
            return True
            
        elif action_type == OutputTypes.LED_BRIGHTNESS:
            brightness = output_value if isinstance(output_value, (int, float)) else parameters.get('brightness', 255)
            brightness = int(brightness)  # Ensure it's an integer
            print(f"Setting LED brightness to {brightness}")
            self.hardware.set_led_brightness(brightness)
            return True
            
        elif action_type == OutputTypes.LED_COUNT:
            count = output_value if isinstance(output_value, (int, float)) else parameters.get('count', 12)
            count = int(count)  # Ensure it's an integer
            print(f"Setting LED count to {count}")
            self.hardware.set_led_count(count)
            return True
            
        elif action_type == OutputTypes.LED_PATTERN:
            pattern_name = parameters.get('pattern', 'BLINK')
            
            # Convert pattern name to actual pattern constant
            pattern_attr = getattr(self.hardware.led_ring, pattern_name, None)
            if pattern_attr is None:
                print(f"Unknown pattern: {pattern_name}")
                return False
                
            speed = parameters.get('speed', 5)
            duration_ms = parameters.get('duration_ms', 1000)
            
            print(f"Starting LED pattern: {pattern_name}, speed={speed}, duration={duration_ms}ms")
            self.hardware.start_led_pattern(pattern_attr, speed, duration_ms)
            return True
        
        # Vibration actions
        elif action_type == OutputTypes.VIBRATION:
            duration_ms = parameters.get('duration_ms', 500)
            print(f"Vibrating for {duration_ms}ms")
            self.hardware.vibrate(duration_ms)
            return True
            
        elif action_type == OutputTypes.VIBRATION_PATTERN:
            pattern_name = parameters.get('pattern', 'PULSE')
            
            # Convert pattern name to actual pattern constant
            pattern_attr = getattr(self.hardware.vibration, pattern_name, None)
            if pattern_attr is None:
                print(f"Unknown vibration pattern: {pattern_name}")
                return False
                
            repeat = parameters.get('repeat', 1)
            
            print(f"Starting vibration pattern: {pattern_name}, repeat={repeat}")
            self.hardware.start_vibration_pattern(pattern_attr, repeat)
            return True
        
        # Buzzer actions
        elif action_type == OutputTypes.BUZZER_FREQUENCY:
            frequency = output_value if isinstance(output_value, (int, float)) else parameters.get('frequency', 440)
            duration_ms = parameters.get('duration_ms', 500)
            
            print(f"Playing frequency: {frequency}Hz for {duration_ms}ms")
            self.hardware.play_frequency(frequency, duration_ms)
            return True
            
        elif action_type == OutputTypes.BUZZER_NOTE:
            note = parameters.get('note', 'C4')
            duration_ms = parameters.get('duration_ms', 500)
            
            print(f"Playing note: {note} for {duration_ms}ms")
            self.hardware.play_note(note, duration_ms)
            return True
            
        elif action_type == OutputTypes.BUZZER_PATTERN:
            pattern_name = parameters.get('pattern', 'DOUBLE')
            
            # Convert pattern name to actual pattern constant
            pattern_attr = getattr(self.hardware.buzzer, pattern_name, None)
            if pattern_attr is None:
                print(f"Unknown buzzer pattern: {pattern_name}")
                return False
                
            base_frequency = parameters.get('base_frequency', 440)
            
            print(f"Playing buzzer pattern: {pattern_name}, base_frequency={base_frequency}")
            self.hardware.start_buzzer_pattern(pattern_attr, base_frequency)
            return True
        
        print(f"Unknown action type: {action_type}")
        return False
    
    def execute_remote_action(self, target_module, action_type, parameters, output_value):
        """Execute a remote action by sending a message to the target module.
        
        Args:
            target_module: Target module MAC address
            action_type: Action type
            parameters: Action parameters
            output_value: Output value from mapping
            
        Returns:
            Success flag
        """
        print(f"Executing remote action: {action_type} on module {target_module}")
        
        # Check if remote manager is available
        if hasattr(self, '_remote_manager'):
            return self._remote_manager.send_action(
                target_module, action_type, parameters, output_value)
        else:
            print("Remote manager not set - cannot execute remote action")
            return False
    
    def register_input_handlers(self):
        """Register handlers for different input types."""
        if self.handlers_registered:
            print("Input handlers already registered")
            return
            
        print("Registering input handlers")
        
        # Button handlers
        self.hardware.add_button_callback("press", self._on_button_press)
        self.hardware.add_button_callback("release", self._on_button_release)
        self.hardware.add_button_callback("hold", self._on_button_hold)
        self.hardware.add_button_callback("double_tap", self._on_button_double_tap)
        
        # Register accelerometer handlers if available
        if hasattr(self.hardware.accelerometer, 'available') and self.hardware.accelerometer.available:
            # Start periodic accelerometer checks
            self._start_accelerometer_checks()
        
        self.handlers_registered = True
    
    def _on_button_press(self):
        """Handler for button press."""
        print("Button pressed")
        self.evaluate_input(InputTypes.BUTTON_PRESS, True)
    
    def _on_button_release(self, duration):
        """Handler for button release."""
        print(f"Button released after {duration}ms")
        self.evaluate_input(InputTypes.BUTTON_RELEASE, duration)
    
    def _on_button_hold(self, duration):
        """Handler for button hold."""
        print(f"Button held for {duration}ms")
        self.evaluate_input(InputTypes.BUTTON_HOLD, duration)
    
    def _on_button_double_tap(self):
        """Handler for button double tap."""
        print("Button double tapped")
        self.evaluate_input(InputTypes.BUTTON_DOUBLE_TAP, True)
    
    async def _check_accelerometer_periodically(self):
        """Periodically check accelerometer values."""
        print("Starting accelerometer checks")
        last_orientation = None
        last_shake = 0
        last_movement = 0
        
        while True:
            # Check orientation
            orientation = self.hardware.get_orientation()
            if orientation != last_orientation:
                print(f"Orientation changed to: {orientation}")
                self.evaluate_input(InputTypes.ORIENTATION, orientation)
                last_orientation = orientation
            
            # Check shake
            shake = self.hardware.detect_shake()
            if shake > 20 and shake > last_shake + 10:  # Only trigger on significant changes
                print(f"Shake detected: {shake}")
                self.evaluate_input(InputTypes.SHAKE, shake)
                last_shake = shake
            
            # Check movement
            movement = self.hardware.detect_movement()
            if movement > 20 and movement > last_movement + 10:  # Only trigger on significant changes
                print(f"Movement detected: {movement}")
                self.evaluate_input(InputTypes.MOVEMENT, movement)
                last_movement = movement
            
            # Check tilt angles
            tilt_angles = self.hardware.get_tilt_angles()
            # We don't evaluate these every time to avoid flooding,
            # but they're available when specific rules need them
            
            # Sleep before next check
            await asyncio.sleep(0.2)  # 5 Hz check rate
    
    def _start_accelerometer_checks(self):
        """Start the accelerometer check task."""
        try:
            # Create and schedule the accelerometer check task
            asyncio.create_task(self._check_accelerometer_periodically())
            print("Accelerometer checks scheduled")
        except Exception as e:
            print(f"Error setting up accelerometer checks: {e}")
