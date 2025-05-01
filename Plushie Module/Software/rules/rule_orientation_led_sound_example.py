"""
Educational Module System - Orientation & Button Hold Example
-----------------------------------------------------------
This example demonstrates:
1. Changing LED color based on orientation
2. Playing different notes based on orientation
3. Controlling number of lit LEDs based on button hold duration
"""

import time
import uasyncio as asyncio
from hardware import HardwareInterface
from rule_engine import RuleEngine, InputTypes, OutputTypes, MappingTypes

async def run_example():
    """Run the orientation and button hold example."""
    print("=== Orientation & Button Hold Example ===")
    
    # Initialize hardware
    hardware = HardwareInterface()
    
    # Initialize rule engine
    rule_engine = RuleEngine(hardware)
    
    # Clear any existing rules
    rule_engine.clear_all_rules()
    
    # Rule 1: Orientation -> LED Color (using hue)
    rule_engine.add_rule({
        'name': 'Orientation -> LED Color',
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
    
    # Rule 2: Orientation -> Sound Note
    rule_engine.add_rule({
        'name': 'Orientation -> Sound Note',
        'source': {
            'module_id': 'self',
            'type': InputTypes.ORIENTATION
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.BUZZER_NOTE,
            'parameters': {
                'duration_ms': 300  # Short duration
            }
        },
        'mapping': {
            'type': MappingTypes.THRESHOLD,
            'parameters': {
                'thresholds': [
                    {'input': 'UP', 'output': {'note': 'C4'}},    # Low C
                    {'input': 'DOWN', 'output': {'note': 'G4'}},  # G
                    {'input': 'LEFT', 'output': {'note': 'E4'}},  # E
                    {'input': 'RIGHT', 'output': {'note': 'A4'}}, # A
                    {'input': 'FRONT', 'output': {'note': 'F4'}}, # F
                    {'input': 'BACK', 'output': {'note': 'B4'}}   # B
                ]
            }
        }
    })
    
    # Rule 3: Button Hold Duration -> Number of LEDs Lit
    rule_engine.add_rule({
        'name': 'Button Hold -> LED Count',
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
                'input_max': 3000,  # 3 seconds for full ring
                'output_min': 1,    # Start with 1 LED
                'output_max': 12,   # Maximum 12 LEDs (full ring)
                'clamp': True
            }
        }
    })
    
    # Rule 4: Button Release -> Play a confirming sound
    rule_engine.add_rule({
        'name': 'Button Release -> Confirmation Sound',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_RELEASE
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.BUZZER_PATTERN,
            'parameters': {
                'pattern': 'DING'  # Short confirming sound
            }
        }
    })
    
    rule_engine.add_rule({
        'name': 'Button Release -> Confirmation Sound',
        'source': {
            'module_id': 'self',
            'type': InputTypes.BUTTON_PRESS
        },
        'target': {
            'module_id': 'self',
            'type': OutputTypes.VIBRATION_PATTERN,
            'parameters': {
                'pattern': 'PULSE'  # Short confirming sound
            }
        }
    })
    
    # Register input handlers
    rule_engine.register_input_handlers()
    
    print("\nRules set up successfully!")
    print("Try these interactions:")
    print("1. Hold the module in different orientations:")
    print("   - UP (blue): plays C4 note")
    print("   - DOWN (yellow): plays G4 note")
    print("   - LEFT (cyan): plays E4 note")
    print("   - RIGHT (purple): plays A4 note")
    print("   - FRONT (green): plays F4 note")
    print("   - BACK (red): plays B4 note")
    print("2. Hold the button for different durations:")
    print("   - Short hold (< 1s): Few LEDs lit")
    print("   - Medium hold (1-2s): More LEDs lit")
    print("   - Long hold (2-3s): Almost full ring")
    print("   - Very long hold (> 3s): Full LED ring")
    print("   - Release button: Confirmation sound\n")
    
    # Set initial color and count
    hardware.set_led_color((0, 0, 255))  # Blue
    hardware.set_led_count(12)  # Start with full ring
    
    # Play a startup sound
    hardware.start_buzzer_pattern(hardware.buzzer.CONNECTED)
    
    # Run continuously until interrupted
    print("Example running... Press Ctrl+C to exit")
    try:
        # Run indefinitely
        counter = 0
        while True:
            # Optional heartbeat message every minute to show it's still running
            counter += 1
            if counter % 60 == 0:
                print(f"Still running... (Press Ctrl+C to exit)")
            await asyncio.sleep(0.1)  # Short sleep to keep checking button
            
    except asyncio.CancelledError:
        print("Example cancelled")
    finally:
        # Clean up on exit
        print("Cleaning up hardware...")
        hardware.cleanup()

def main():
    """Main entry point."""
    print("Starting Rules Demo")
    print("Crtl-C to Stop")
    time.sleep(3)
    try:
        asyncio.run(run_example())
    except KeyboardInterrupt:
        print("Example interrupted by user")
        # Clean up hardware
        hardware = HardwareInterface()
        hardware.cleanup()
    except Exception as e:
        print(f"Error running example: {e}")
        # Clean up hardware
        hardware = HardwareInterface()
        hardware.cleanup()

if __name__ == "__main__":
    main()