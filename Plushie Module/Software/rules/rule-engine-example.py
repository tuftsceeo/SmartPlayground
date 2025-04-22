"""
Educational Module System - Rule Engine Example
-----------------------------------------------
This script demonstrates the usage of the rule engine with the hardware interface.
"""

import time
import uasyncio as asyncio
from hardware import HardwareInterface
from rule_engine import RuleEngine, InputTypes, OutputTypes, MappingTypes

async def run_example():
    """Run the rule engine example."""
    print("=== Rule Engine Example ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add example rules
    
    # Rule 1: Button press -> Red LED
    rule_engine.add_rule({
        'name': 'Button Press -> Red LED',
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
    
    # Rule 2: Button release -> Green LED
    rule_engine.add_rule({
        'name': 'Button Release -> Green LED',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_RELEASE
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR,
            'parameters': {
                'color': [0, 255, 0]  # Green
            }
        }
    })
    
    # Rule 3: Button double tap -> Rainbow pattern
    rule_engine.add_rule({
        'name': 'Button Double Tap -> Rainbow',
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
    
    # Rule 4: Button hold -> LED brightness proportional to hold duration
    rule_engine.add_rule({
        'name': 'Button Hold -> LED Brightness',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_HOLD
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_BRIGHTNESS
        },
        'mapping': {
            'type': MappingTypes.PROPORTIONAL,
            'parameters': {
                'input_min': 0,
                'input_max': 2000,  # 2 seconds
                'output_min': 0,
                'output_max': 255,
                'clamp': True
            }
        }
    })
    
    # Rule 5: Shake -> Different colors based on intensity
    rule_engine.add_rule({
        'name': 'Shake Intensity -> LED Color',
        'source': {
            'module_id': 'self',
            'type': InputTypes.SHAKE
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR
        },
        'mapping': {
            'type': MappingTypes.THRESHOLD,
            'parameters': {
                'thresholds': [
                    {'input': 30, 'output': {'color': [0, 0, 255]}},  # Low intensity -> Blue
                    {'input': 60, 'output': {'color': [255, 255, 0]}},  # Medium intensity -> Yellow
                    {'input': 100, 'output': {'color': [255, 0, 0]}}  # High intensity -> Red
                ]
            }
        }
    })
    
    # Rule 6: Orientation change -> different sounds
    rule_engine.add_rule({
        'name': 'Orientation -> Different Sounds',
        'source': {
            'module_id': 'self',
            'type': InputTypes.ORIENTATION
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.BUZZER_NOTE,
            'parameters': {
                'duration_ms': 300
            }
        },
        'mapping': {
            'type': MappingTypes.THRESHOLD,
            'parameters': {
                'thresholds': [
                    {'input': 'UP', 'output': {'note': 'C4'}},
                    {'input': 'DOWN', 'output': {'note': 'G4'}},
                    {'input': 'LEFT', 'output': {'note': 'E4'}},
                    {'input': 'RIGHT', 'output': {'note': 'A4'}},
                    {'input': 'FRONT', 'output': {'note': 'F4'}},
                    {'input': 'BACK', 'output': {'note': 'B4'}}
                ]
            }
        }
    })
    
    # Register input handlers (will start monitoring accelerometer too)
    rule_engine.register_input_handlers()
    
    print("\nRules set up successfully!")
    print("Try these interactions:")
    print("1. Press the button -> Red LEDs")
    print("2. Release the button -> Green LEDs")
    print("3. Double-tap the button -> Rainbow pattern")
    print("4. Hold the button -> Brightness changes with hold duration")
    print("5. Shake the module -> Color changes with intensity")
    print("6. Change orientation -> Different notes play\n")
    
    # Set a starting color to show we're ready
    hardware.set_led_color((0, 0, 255))  # Blue
    
    # Run for a few minutes
    runtime = 5 * 60  # 5 minutes in seconds
    for i in range(runtime):
        if i % 30 == 0:  # Every 30 seconds
            remaining = runtime - i
            print(f"Example running... {remaining} seconds remaining")
        await asyncio.sleep(1)
    
    # Clean up
    print("Example completed")
    hardware.cleanup()

def main():
    """Main entry point."""
    try:
        asyncio.run(run_example())
    except KeyboardInterrupt:
        print("Example interrupted by user")
    except Exception as e:
        print(f"Error running example: {e}")

if __name__ == "__main__":
    main()
