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
    """Test basic LED rules."""
    print("\n=== Testing LED Rules ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add a test rule: button press -> red LED
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
                'color': [255, 0, 0]  # Red
            }
        }
    })
    
    # Manually trigger the rule
    print("Manually triggering button press rule...")
    rule_engine.evaluate_input(InputTypes.BUTTON_PRESS, True)
    
    # Wait to see the effect
    await asyncio.sleep(2)
    
    # Update the rule to change color
    print("Updating rule to use blue color...")
    rule_engine.update_rule(rule_id, {
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR,
            'parameters': {
                'color': [0, 0, 255]  # Blue
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
    """Test threshold mapping functionality."""
    print("\n=== Testing Threshold Mapping ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add a rule with threshold mapping
    rule_engine.add_rule({
        'name': 'Test: Threshold -> LED Colors',
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
                    {'input': 25, 'output': {'color': [0, 0, 255]}},  # Blue for low values
                    {'input': 50, 'output': {'color': [0, 255, 0]}},  # Green for medium values
                    {'input': 75, 'output': {'color': [255, 255, 0]}},  # Yellow for higher values
                    {'input': 100, 'output': {'color': [255, 0, 0]}}   # Red for highest values
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
    
    # Add a rule with proportional mapping for LED count
    rule_engine.add_rule({
        'name': 'Test: Proportional -> LED Count',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_HOLD
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COUNT
        },
        'mapping': {
            'type': MappingTypes.PROPORTIONAL,
            'parameters': {
                'input_min': 0,
                'input_max': 1000,  # 1 second
                'output_min': 0,
                'output_max': 12,   # Full ring
                'clamp': True
            }
        }
    })
    
    # Set a color so we can see the LEDs
    hardware.set_led_color((255, 255, 255))
    
    # Test with different values
    test_values = [0, 250, 500, 750, 1000, 1500]
    
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
    
    # Add a rule for playing a pattern
    rule_engine.add_rule({
        'name': 'Test: Play Pattern',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_DOUBLE_TAP
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.BUZZER_PATTERN,
            'parameters': {
                'pattern': 'ASCENDING'
            }
        }
    })
    
    # Test with double tap
    print("Testing pattern playing...")
    rule_engine.evaluate_input(InputTypes.BUTTON_DOUBLE_TAP, True)
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
    
    # Add a rule for vibration pattern
    rule_engine.add_rule({
        'name': 'Test: Vibration Pattern',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_DOUBLE_TAP
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
    
    # Test with double tap
    print("Testing vibration pattern...")
    rule_engine.evaluate_input(InputTypes.BUTTON_DOUBLE_TAP, True)
    await asyncio.sleep(3)
    
    print("Vibration rules test complete")
    return True

async def test_interactive_rules():
    """Test interactive rules with actual button presses."""
    print("\n=== Testing Interactive Rules ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add interactive rules
    rule_engine.add_rule({
        'name': 'Interactive: Button Press -> LED + Sound',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_PRESS
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR,
            'parameters': {
                'color': [255, 0, 0]  # Red
            }
        }
    })
    
    rule_engine.add_rule({
        'name': 'Interactive: Button Press -> Sound',
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
    
    rule_engine.add_rule({
        'name': 'Interactive: Button Double Tap -> Rainbow',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_DOUBLE_TAP
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_PATTERN,
            'parameters': {
                'pattern': 'RAINBOW',
                'speed': 5,
                'duration_ms': 3000
            }
        }
    })
    
    # Register input handlers
    rule_engine.register_input_handlers()
    
    print("Interactive test ready!")
    print("Try these interactions:")
    print("1. Press the button -> Red LEDs + sound")
    print("2. Double-tap the button -> Rainbow pattern")
    print("Test will run for 30 seconds...")
    
    # Run for 30 seconds to allow manual testing
    for i in range(30):
        await asyncio.sleep(1)
        if i % 5 == 0:
            print(f"{30 - i} seconds remaining...")
    
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
    await test_interactive_rules()
    
    print("\nAll tests completed!")

def main():
    """Main entry point."""
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("Tests interrupted by user")
    except Exception as e:
        print(f"Error running tests: {e}")
        import sys
        sys.print_exception(e)

if __name__ == "__main__":
    main()
