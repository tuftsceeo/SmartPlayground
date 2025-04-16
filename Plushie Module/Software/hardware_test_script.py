"""
Educational Module System - Hardware Test Script
-----------------------------------------------
This script tests all the hardware components on the educational module.
"""
import time
import gc
from machine import Pin, SoftI2C, Timer

# Import the hardware interface
from hardware_interface import Hardware, H3LIS331DL_SCALE_FS

def test_button(hardware):
    """Test the button functionality"""
    print("\n===== Button Test =====")
    print("Press the button within the next 5 seconds...")
    
    # Setup counters and flags
    press_count = 0
    release_count = 0
    hold_count = 0
    double_tap_count = 0
    
    # Define callback functions
    def on_press():
        nonlocal press_count
        press_count += 1
        print(f"Button pressed! (Count: {press_count})")
        hardware.led_ring.set_color((255, 0, 0))  # Red when pressed
    
    def on_release(duration):
        nonlocal release_count
        release_count += 1
        print(f"Button released after {duration}ms (Count: {release_count})")
        hardware.led_ring.set_color((0, 0, 0))  # Off when released
    
    def on_hold(duration):
        nonlocal hold_count
        hold_count += 1
        print(f"Button held for {duration}ms (Count: {hold_count})")
        hardware.led_ring.set_color((0, 255, 0))  # Green when held
    
    def on_double_tap():
        nonlocal double_tap_count
        double_tap_count += 1
        print(f"Double tap detected! (Count: {double_tap_count})")
        hardware.led_ring.set_pattern(hardware.led_ring.PATTERN_BLINK, 5, 1000)
    
    # Register callbacks
    hardware.button.add_callback("press", on_press)
    hardware.button.add_callback("release", on_release)
    hardware.button.add_callback("hold", on_hold)
    hardware.button.add_callback("double_tap", on_double_tap)
    
    # Wait for button events
    start_time = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start_time) < 10000:
        # Just wait for callbacks
        time.sleep(0.1)
    
    # Clean up
    hardware.button.remove_callback("press", on_press)
    hardware.button.remove_callback("release", on_release)
    hardware.button.remove_callback("hold", on_hold)
    hardware.button.remove_callback("double_tap", on_double_tap)
    
    print("Button test complete:")
    print(f"- Presses: {press_count}")
    print(f"- Releases: {release_count}")
    print(f"- Holds: {hold_count}")
    print(f"- Double taps: {double_tap_count}")

def test_led_ring(hardware):
    """Test the LED ring"""
    print("\n===== LED Ring Test =====")
    
    # Test colors
    colors = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (255, 255, 0),  # Yellow
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Cyan
        (255, 255, 255) # White
    ]
    
    print("Testing colors...")
    for color in colors:
        print(f"Setting color to {color}")
        hardware.led_ring.set_color(color)
        time.sleep(0.5)
    
    # Test patterns
    patterns = [
        hardware.led_ring.PATTERN_BLINK,
        hardware.led_ring.PATTERN_BREATHE,
        hardware.led_ring.PATTERN_CHASE,
        hardware.led_ring.PATTERN_RAINBOW,
        hardware.led_ring.PATTERN_ALTERNATE
    ]
    
    print("Testing patterns...")
    for i in range(len(patterns)):
        print(f"Pattern: {patterns[i]}")
        hardware.led_ring.set_color(colors[i])
        hardware.led_ring.set_pattern(patterns[i], speed=5, duration_ms=5000)
        time.sleep(1)  # Wait for pattern to complete
    
    # Clear LEDs
    hardware.led_ring.clear()
    print("LED ring test complete")

def test_buzzer(hardware):
    """Test the buzzer (sound)"""
    print("\n===== Buzzer Test =====")
    
    # Test different tones
    print("Testing different tones...")
    for freq in [262, 330, 392, 440, 523]:
        print(f"Playing {freq}Hz")
        hardware.buzzer.play(freq, 300)
        time.sleep(0.1)
    
    # Test musical notes
    print("Testing musical notes...")
    for note in ["C4", "E4", "G4", "A4", "C5"]:
        print(f"Playing {note}")
        hardware.buzzer.note(note, 300)
        time.sleep(0.1)
    
    print("Buzzer test complete")

def test_vibration(hardware):
    """Test the vibration motor"""
    print("\n===== Vibration Test =====")
    
    # Test simple vibration
    print("Testing simple vibration (500ms)...")
    hardware.vibration.vibrate(500)
    time.sleep(0.5)
    
    # Test patterns
    patterns = [
        hardware.vibration.PATTERN_PULSE,
        hardware.vibration.PATTERN_DOUBLE,
        hardware.vibration.PATTERN_TRIPLE,
        hardware.vibration.PATTERN_LONG_SHORT
    ]
    
    print("Testing vibration patterns...")
    for pattern in patterns:
        print(f"Pattern: {pattern}")
        hardware.vibration.pattern(pattern)
        time.sleep(1)
    
    print("Vibration test complete")

def test_accelerometer(hardware):
    """Test the accelerometer"""
    print("\n===== Accelerometer Test =====")
    
    if not hardware.accelerometer.available:
        print("Accelerometer not detected!")
        return
    
    # Read raw and G values
    print("Reading accelerometer values...")
    for i in range(25):
        raw = hardware.accelerometer.read_raw()
        g_values = hardware.accelerometer.read_g()
        
        print(f"Raw: X={raw['x']}, Y={raw['y']}, Z={raw['z']}")
        print(f"G:   X={g_values['x']:.3f}g, Y={g_values['y']:.3f}g, Z={g_values['z']:.3f}g")
        
        # Get orientation
        orientation = hardware.accelerometer.get_orientation()
        print(f"Orientation: {orientation}")
        
        # Detect motion and shake
        movement = hardware.accelerometer.detect_movement()
        shake = hardware.accelerometer.detect_shake()
        print(f"Movement: {movement}, Shake: {shake}")
        
        time.sleep(0.5)
    
    print("Accelerometer test complete")

def test_power_management(hardware):
    """Test power management features"""
    print("\n===== Power Management Test =====")
    
    # Get battery status
    voltage = hardware.power.get_battery_voltage()
    percentage = hardware.power.get_battery_percentage()
    state = hardware.power.get_battery_state()
    
    print(f"Battery voltage: {voltage:.2f}V")
    print(f"Battery percentage: {percentage}%")
    print(f"Battery state: {state}")
    
    # Test activity registration
    print("Testing activity registration...")
    hardware.power.register_activity()
    print("Activity registered, sleep timers reset")
    
    print("Power management test complete")

def main():
    """Main test function"""
    print("Starting Educational Module Hardware Test")
    print("========================================")
    
    # Initialize hardware
    hardware = Hardware()
    
    try:
        # Run individual component tests
        test_led_ring(hardware)
        test_button(hardware)
        test_buzzer(hardware)
        test_vibration(hardware)
        test_accelerometer(hardware)
        test_power_management(hardware)
        
        print("\nAll hardware tests completed successfully!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import sys
        sys.print_exception(e)
    finally:
        # Clean up hardware state
        hardware.led_ring.clear()
        hardware.buzzer.stop()
        
        # Run garbage collection
        gc.collect()
        print(f"Free memory: {gc.mem_free()} bytes")

# Run the test when the script is executed
if __name__ == "__main__":
    main()
