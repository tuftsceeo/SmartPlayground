"""
Educational Module System - Rule Engine Example
-----------------------------------------------
This script demonstrates the usage of the rule engine with the hardware interface.
"""

import time
import uasyncio as asyncio
from hardware import HardwareInterface
from rule_engine import RuleEngine, InputTypes, OutputTypes, MappingTypes

async def run_button_example():
    """Run the button-based rule engine example."""
    print("=== Button Example ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Add example rules
    
    # Rule 1: Button press -> Red LED (using hue)
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
                'hue': 0  # 0 = Red in the hue color wheel
            }
        }
    })
    
    # Rule 2: Button release -> Green LED (using hue)
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
                'hue': 120  # 120 = Green in the hue color wheel
            }
        }
    })
    
    # Rule 3: Button hold -> LED brightness proportional to hold duration
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
    
    # Register input handlers
    rule_engine.register_input_handlers()
    
    print("\nButton rules set up successfully!")
    print("Try these interactions:")
    print("1. Press the button -> Red LEDs (hue 0)")
    print("2. Release the button -> Green LEDs (hue 120)")
    print("3. Hold the button -> Brightness changes with hold duration\n")
    
    # Set a starting color to show we're ready
    hardware.set_led_color((0, 0, 255))  # Blue
    
    # Run for 60 seconds
    for i in range(60):
        if i % 10 == 0:  # Every 10 seconds
            remaining = 60 - i
            print(f"Example running... {remaining} seconds remaining")
        await asyncio.sleep(1)
    
    # Clean up
    print("Button example completed")
    hardware.cleanup()

async def run_orientation_example():
    """Run the orientation-based rule engine example."""
    print("=== Orientation Example ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Rule: Orientation change -> different colors using hue
    rule_engine.add_rule({
        'name': 'Orientation -> Different Colors',
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
    
    print("\nOrientation rules set up successfully!")
    print("Try these interactions:")
    print("Hold the module in different orientations to see different colors:")
    print("- UP: Blue (hue 240)")
    print("- DOWN: Yellow (hue 60)")
    print("- LEFT: Cyan (hue 180)")
    print("- RIGHT: Purple (hue 300)")
    print("- FRONT: Green (hue 120)")
    print("- BACK: Red (hue 0)\n")
    
    # Run for 60 seconds
    for i in range(60):
        if i % 10 == 0:  # Every 10 seconds
            remaining = 60 - i
            print(f"Example running... {remaining} seconds remaining")
        await asyncio.sleep(1)
    
    # Clean up
    print("Orientation example completed")
    hardware.cleanup()

async def run_shake_example():
    """Run the shake-based rule engine example."""
    print("=== Shake Example ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Rule: Shake -> Different colors based on intensity using hue
    rule_engine.add_rule({
        'name': 'Shake -> Rainbow Colors',
        'source': {
            'module_id': 'self',
            'type': InputTypes.SHAKE
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR
        },
        'mapping': {
            'type': MappingTypes.PROPORTIONAL,
            'parameters': {
                'input_min': 0,
                'input_max': 100,
                'output_min': 0,
                'output_max': 360,
                'clamp': True
            }
        }
    })
    
    # Register input handlers
    rule_engine.register_input_handlers()
    
    print("\nShake rules set up successfully!")
    print("Try these interactions:")
    print("Shake the module with different intensities to see different colors")
    print("- Gentle shake: Colors toward red/orange (low hue values)")
    print("- Hard shake: Colors toward purple/blue (high hue values)\n")
    
    # Run for 60 seconds
    for i in range(60):
        if i % 10 == 0:  # Every 10 seconds
            remaining = 60 - i
            print(f"Example running... {remaining} seconds remaining")
        await asyncio.sleep(1)
    
    # Clean up
    print("Shake example completed")
    hardware.cleanup()

async def run_sound_example():
    """Run the sound/buzzer rule engine example."""
    print("=== Sound Example ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Rule 1: Double tap -> Play ascending scale
    rule_engine.add_rule({
        'name': 'Double Tap -> Ascending Scale',
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
    
    # Register input handlers
    rule_engine.register_input_handlers()
    
    print("\nSound rules set up successfully!")
    print("Try these interactions:")
    print("Double-tap the button -> Play ascending scale\n")
    
    # Run for 60 seconds
    for i in range(60):
        if i % 10 == 0:  # Every 10 seconds
            remaining = 60 - i
            print(f"Example running... {remaining} seconds remaining")
        await asyncio.sleep(1)
    
    # Clean up
    print("Sound example completed")
    hardware.cleanup()

async def run_multi_example():
    """Run a multi-sensory rule example that demonstrates combined effects."""
    print("=== Multi-Sensory Example ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Rule 1: Button press -> LED color AND vibration
    rule_engine.add_rule({
        'name': 'Button Press -> Blue Color',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_PRESS
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.LED_COLOR,
            'parameters': {
                'hue': 240  # Blue
            }
        }
    })
    
    rule_engine.add_rule({
        'name': 'Button Press -> Vibration',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_PRESS
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.VIBRATION,
            'parameters': {
                'duration_ms': 300
            }
        }
    })
    
    # Register input handlers
    rule_engine.register_input_handlers()
    
    print("\nMulti-sensory rules set up successfully!")
    print("Try these interactions:")
    print("Press the button -> Blue LEDs + vibration\n")
    
    # Run for 60 seconds
    for i in range(60):
        if i % 10 == 0:  # Every 10 seconds
            remaining = 60 - i
            print(f"Example running... {remaining} seconds remaining")
        await asyncio.sleep(1)
    
    # Clean up
    print("Multi-sensory example completed")
    hardware.cleanup()

def main():
    """Main entry point."""
    try:
        # Choose one example to run
        example = input("Choose an example to run (1-5):\n" +
                       "1. Button example\n" +
                       "2. Orientation example\n" +
                       "3. Shake example\n" +
                       "4. Sound example\n" +
                       "5. Multi-sensory example\n" +
                       "Choice: ")
        
        if example == "1":
            asyncio.run(run_button_example())
        elif example == "2":
            asyncio.run(run_orientation_example())
        elif example == "3":
            asyncio.run(run_shake_example())
        elif example == "4":
            asyncio.run(run_sound_example())
        elif example == "5":
            asyncio.run(run_multi_example())
        else:
            print(f"Unknown choice: {example}")
            print("Running button example by default...")
            asyncio.run(run_button_example())
            
    except KeyboardInterrupt:
        print("Example interrupted by user")
    except Exception as e:
        print(f"Error running example: {e}")

if __name__ == "__main__":
    main()
