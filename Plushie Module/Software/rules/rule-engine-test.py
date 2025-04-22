"""
Educational Module System - Rule Engine Test
-------------------------------------------
This script tests the rule engine with basic functionality.
"""

import time
import uasyncio as asyncio
from hardware import HardwareInterface
from rule_engine import RuleEngine, InputTypes, OutputTypes, MappingTypes

async def test_led_rules():
    """Test basic LED rules with hue-based colors."""
    print("\n=== Testing LED Rules ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add a test rule: button press -> red LED (hue 0)
    rule_id = rule_engine.add_rule({
        'name': 'Test: Button Press -> Red LED',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_PRESS
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR,
            'parameters': {
                'hue': 0  # Red
            }
        }
    })
    
    # Manually trigger the rule
    print("Manually triggering button press rule (should set red hue)...")
    rule_engine.evaluate_input(InputTypes.BUTTON_PRESS, True)
    
    # Wait to see the effect
    await asyncio.sleep(2)
    
    # Update the rule to change color
    print("Updating rule to use blue hue...")
    rule_engine.update_rule(rule_id, {
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR,
            'parameters': {
                'hue': 240  # Blue
            }
        }
    })
    
    # Trigger the updated rule
    print("Triggering updated rule...")
    rule_engine.evaluate_input(InputTypes.BUTTON_PRESS, True)
    
    # Wait to see the effect
    await asyncio.sleep(2)
    
    # Clear LEDs for next test
    hardware.set_led_color((0, 0, 0))
    
    print("LED rules test complete")
    return True

async def test_threshold_mapping():
    """Test threshold mapping functionality with hue colors."""
    print("\n=== Testing Threshold Mapping ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add a rule with threshold mapping
    rule_engine.add_rule({
        'name': 'Test: Threshold -> LED Hues',
        'source': {
            'module_id': 'self',
            'type': InputTypes.MOVEMENT
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR
        },
        'mapping': {
            'type': MappingTypes.THRESHOLD,
            'parameters': {
                'thresholds': [
                    {'input': 25, 'output': {'hue': 240}},  # Blue for low values
                    {'input': 50, 'output': {'hue': 120}},  # Green for medium values
                    {'input': 75, 'output': {'hue': 60}},   # Yellow for higher values
                    {'input': 100, 'output': {'hue': 0}}    # Red for highest values
                ]
            }
        }
    })
    
    # Test with different values
    test_values = [10, 30, 60, 80, 120]
    
    for value in test_values:
        print(f"Testing threshold mapping with value: {value}")
        rule_engine.evaluate_input(InputTypes.MOVEMENT, value)
        await asyncio.sleep(1.5)
    
    # Clear LEDs for next test
    hardware.set_led_color((0, 0, 0))
    
    print("Threshold mapping test complete")
    return True

async def test_proportional_mapping():
    """Test proportional mapping functionality."""
    print("\n=== Testing Proportional Mapping ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add a rule with proportional mapping for hue value
    rule_engine.add_rule({
        'name': 'Test: Proportional -> Hue Value',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_HOLD
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR
        },
        'mapping': {
            'type': MappingTypes.PROPORTIONAL,
            'parameters': {
                'input_min': 0,
                'input_max': 1000,  # 1 second
                'output_min': 0,    # Red
                'output_max': 360,  # Full hue circle
                'clamp': True
            }
        }
    })
    
    # Test with different values
    test_values = [0, 250, 500, 750, 1000]
    
    for value in test_values:
        print(f"Testing proportional mapping with value: {value}")
        rule_engine.evaluate_input(InputTypes.BUTTON_HOLD, value)
        await asyncio.sleep(1.5)
    
    # Clear LEDs for next test
    hardware.set_led_color((0, 0, 0))
    
    print("Proportional mapping test complete")
    return True

async def test_buzzer_rules():
    """Test buzzer rules."""
    print("\n=== Testing Buzzer Rules ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add a rule for playing notes
    rule_engine.add_rule({
        'name': 'Test: Play Different Notes',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_PRESS
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.BUZZER_NOTE,
            'parameters': {
                'note': 'C4',
                'duration_ms': 300
            }
        }
    })
    
    # Test with button press
    print("Testing note playing...")
    rule_engine.evaluate_input(InputTypes.BUTTON_PRESS, True)
    await asyncio.sleep(1)
    
    # Update to a rule for playing a pattern
    rule_engine.clear_all_rules()
    rule_engine.add_rule({
        'name': 'Test: Play Pattern',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_PRESS
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.BUZZER_PATTERN,
            'parameters': {
                'pattern': 'ASCENDING'
            }
        }
    })
    
    # Test pattern
    print("Testing pattern playing...")
    rule_engine.evaluate_input(InputTypes.BUTTON_PRESS, True)
    await asyncio.sleep(3)
    
    print("Buzzer rules test complete")
    return True

async def test_vibration_rules():
    """Test vibration rules."""
    print("\n=== Testing Vibration Rules ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add a rule for simple vibration
    rule_engine.add_rule({
        'name': 'Test: Simple Vibration',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_PRESS
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.VIBRATION,
            'parameters': {
                'duration_ms': 500
            }
        }
    })
    
    # Test with button press
    print("Testing simple vibration...")
    rule_engine.evaluate_input(InputTypes.BUTTON_PRESS, True)
    await asyncio.sleep(1)
    
    # Update to a vibration pattern rule
    rule_engine.clear_all_rules()
    rule_engine.add_rule({
        'name': 'Test: Vibration Pattern',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_PRESS
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.VIBRATION_PATTERN,
            'parameters': {
                'pattern': 'DOUBLE',
                'repeat': 2
            }
        }
    })
    
    # Test pattern
    print("Testing vibration pattern...")
    rule_engine.evaluate_input(InputTypes.BUTTON_PRESS, True)
    await asyncio.sleep(3)
    
    print("Vibration rules test complete")
    return True

async def test_orientation_priority():
    """Test orientation change priority handling."""
    print("\n=== Testing Orientation Priority ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add a rule for orientation changes
    rule_engine.add_rule({
        'name': 'Test: Orientation -> LED Hue',
        'source': {
            'module_id': 'self',
            'type': InputTypes.ORIENTATION
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR
        },
        'mapping': {
            'type': MappingTypes.THRESHOLD,
            'parameters': {
                'thresholds': [
                    {'input': 'UP', 'output': {'hue': 240}},      # Blue
                    {'input': 'DOWN', 'output': {'hue': 60}},     # Yellow
                    {'input': 'LEFT', 'output': {'hue': 180}},    # Cyan
                    {'input': 'RIGHT', 'output': {'hue': 300}},   # Purple
                    {'input': 'FRONT', 'output': {'hue': 120}},   # Green
                    {'input': 'BACK', 'output': {'hue': 0}}       # Red
                ]
            }
        }
    })
    
    # Register input handlers
    rule_engine.register_input_handlers()
    
    print("\nOrientation to hue rule set up.")
    print("Try changing the orientation of the module.")
    print("The LEDs should change color based on orientation.")
    print("This test runs for 30 seconds...")
    
    # Run for 30 seconds
    for i in range(30):
        if i % 5 == 0:
            print(f"{30-i} seconds remaining...")
        await asyncio.sleep(1)
    
    # Clean up
    hardware.set_led_color((0, 0, 0))
    
    print("Orientation priority test complete")
    return True

async def test_interactive():
    """Test simple interactive rules for manual testing."""
    print("\n=== Interactive Test ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add a rule for button press -> rainbow hue based on time held
    rule_engine.add_rule({
        'name': 'Interactive: Button Hold -> Rainbow',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_HOLD
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR
        },
        'mapping': {
            'type': MappingTypes.PROPORTIONAL,
            'parameters': {
                'input_min': 0,
                'input_max': 3000,  # 3 seconds
                'output_min': 0,    # Red
                'output_max': 360,  # Full hue circle
                'clamp': True
            }
        }
    })
    
    # Add a rule for button release -> play note based on hold time
    rule_engine.add_rule({
        'name': 'Interactive: Button Release -> Note',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_RELEASE
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.BUZZER_PATTERN
        },
        'mapping': {
            'type': MappingTypes.THRESHOLD,
            'parameters': {
                'thresholds': [
                    {'input': 500, 'output': {'pattern': 'SINGLE'}},
                    {'input': 1000, 'output': {'pattern': 'DOUBLE'}},
                    {'input': 2000, 'output': {'pattern': 'TRIPLE'}},
                    {'input': 3000, 'output': {'pattern': 'ASCENDING'}}
                ]
            }
        }
    })
    
    # Register input handlers
    rule_engine.register_input_handlers()
    
    print("\nInteractive test ready!")
    print("Try these interactions:")
    print("1. Hold the button to see colors change with hold time (hue rotates through rainbow)")
    print("2. Release after different hold durations to hear different sound patterns")
    print("Test will run for 60 seconds...")
    
    # Run for 60 seconds to allow manual testing
    for i in range(60):
        await asyncio.sleep(1)
        if i % 10 == 0:
            print(f"{60 - i} seconds remaining...")
    
    # Clean up
    hardware.set_led_color((0, 0, 0))
    
    print("Interactive test complete")
    return True

async def run_all_tests():
    """Run all rule engine tests."""
    print("=== Rule Engine Tests ===")
    
    # Run tests
    await test_led_rules()
    await test_threshold_mapping()
    await test_proportional_mapping()
    await test_buzzer_rules()
    await test_vibration_rules()
    await test_orientation_priority()
    await test_interactive()
    
    print("\nAll tests completed!")

def main():
    """Main entry point."""
    try:
        # Allow user to choose specific test or run all
        print("Choose a test to run:")
        print("1. LED rules with hue colors")
        print("2. Threshold mapping test")
        print("3. Proportional mapping test")
        print("4. Buzzer rules test")
        print("5. Vibration rules test")
        print("6. Orientation priority test")
        print("7. Interactive test")
        print("8. Run all tests")
        
        choice = input("Enter choice (1-8): ")
        
        if choice == "1":
            asyncio.run(test_led_rules())
        elif choice == "2":
            asyncio.run(test_threshold_mapping())
        elif choice == "3":
            asyncio.run(test_proportional_mapping())
        elif choice == "4":
            asyncio.run(test_buzzer_rules())
        elif choice == "5":
            asyncio.run(test_vibration_rules())
        elif choice == "6":
            asyncio.run(test_orientation_priority())
        elif choice == "7":
            asyncio.run(test_interactive())
        elif choice == "8":
            asyncio.run(run_all_tests())
        else:
            print("Invalid choice. Running all tests.")
            asyncio.run(run_all_tests())
            
    except KeyboardInterrupt:
        print("Tests interrupted by user")
    except Exception as e:
        print(f"Error running tests: {e}")
        import sys
        sys.print_exception(e)

if __name__ == "__main__":
    main()
