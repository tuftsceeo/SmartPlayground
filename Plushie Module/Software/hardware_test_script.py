"""
Educational Module System - Hardware Test Script
----------------------------------------------
This script tests all hardware components of the Educational Module System.
"""
import time
import uasyncio as asyncio
from hardware import HardwareInterface

async def test_accelerometer(hardware):
    """Test accelerometer functionality"""
    print("\nTesting Accelerometer...")
    
    # Test raw readings
    print("Reading raw accelerometer values...")
    raw = hardware.accelerometer.read_raw()
    print(f"Raw values: X={raw['x']}, Y={raw['y']}, Z={raw['z']}")
    
    # Test g readings
    print("Reading g values...")
    g = hardware.accelerometer.read_g()
    print(f"G values: X={g['x']:.2f}g, Y={g['y']:.2f}g, Z={g['z']:.2f}g")
    
    # Test orientation detection
    print("Testing orientation detection...")
    orientation = hardware.accelerometer.get_orientation()
    print(f"Current orientation: {orientation}")
    
    # Test tilt angles
    print("Testing tilt angles...")
    angles = hardware.accelerometer.get_tilt_angles()
    print(f"Tilt angles: X={angles[0]:.1f}°, Y={angles[1]:.1f}°, Z={angles[2]:.1f}°")
    
    # Test shake detection
    print("Testing shake detection (shake the device)...")
    for _ in range(10):
        shake = hardware.accelerometer.detect_shake()
        print(f"Shake intensity: {shake}")
        await asyncio.sleep(0.5)
    
    # Test movement detection
    print("Testing movement detection (move the device)...")
    for _ in range(10):
        movement = hardware.accelerometer.detect_movement()
        print(f"Movement intensity: {movement}")
        await asyncio.sleep(0.5)

async def test_led_ring(hardware):
    """Test LED ring functionality"""
    print("\nTesting LED Ring...")
    
    # Test basic color setting
    print("Testing color setting...")
    hardware.led_ring.set_color((255, 0, 0))  # Red
    await asyncio.sleep(1)
    hardware.led_ring.set_color((0, 255, 0))  # Green
    await asyncio.sleep(1)
    hardware.led_ring.set_color((0, 0, 255))  # Blue
    await asyncio.sleep(1)
    
    # Test brightness control
    print("Testing brightness control...")
    for brightness in range(0, 256, 51):
        hardware.led_ring.set_brightness(brightness)
        print(f"Brightness: {brightness}")
        await asyncio.sleep(0.5)
    
    # Test LED count control
    print("Testing LED count control...")
    for count in range(13):
        hardware.led_ring.set_count(count)
        print(f"Active LEDs: {count}")
        await asyncio.sleep(0.5)
    
    # Test patterns
    print("Testing patterns...")
    patterns = [
        hardware.led_ring.PATTERN_BLINK,
        hardware.led_ring.PATTERN_BREATHE,
        hardware.led_ring.PATTERN_CHASE,
        hardware.led_ring.PATTERN_RAINBOW,
        hardware.led_ring.PATTERN_ALTERNATE
    ]
    
    for pattern in patterns:
        print(f"Running pattern: {pattern}")
        task = hardware.led_ring.start_pattern(pattern, speed=5, duration_ms=2000)
        await task
        await asyncio.sleep(0.5)
    
    # Clear LEDs
    hardware.led_ring.clear()

async def test_button(hardware):
    """Test button functionality"""
    print("\nTesting Button...")
    
    def on_press():
        print("Button pressed!")
    
    def on_release(duration):
        print(f"Button released! Hold duration: {duration}ms")
    
    def on_hold(duration):
        print(f"Button held! Duration: {duration}ms")
    
    def on_double_tap():
        print("Double tap detected!")
    
    # Add callbacks
    hardware.button.add_callback("press", on_press)
    hardware.button.add_callback("release", on_release)
    hardware.button.add_callback("hold", on_hold)
    hardware.button.add_callback("double_tap", on_double_tap)
    
    print("Press the button to test callbacks...")
    print("Try: single press, hold, and double tap")
    await asyncio.sleep(10)
    
    # Remove callbacks
    hardware.button.remove_callback("press", on_press)
    hardware.button.remove_callback("release", on_release)
    hardware.button.remove_callback("hold", on_hold)
    hardware.button.remove_callback("double_tap", on_double_tap)

async def test_buzzer(hardware):
    """Test buzzer functionality"""
    print("\nTesting Buzzer...")
    
    # Test volume control
    print("Testing volume control...")
    hardware.buzzer.set_volume(50)
    
    # Test single frequency
    print("Testing single frequency...")
    task = hardware.buzzer.play_frequency(440, 1000)  # A4 note for 1 second
    await task
    
    # Test musical notes
    print("Testing musical notes...")
    notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
    for note in notes:
        print(f"Playing note: {note}")
        task = hardware.buzzer.play_note(note, 500)
        await task
        await asyncio.sleep(0.1)
    
    # Test patterns
    print("Testing patterns...")
    patterns = [
        hardware.buzzer.PATTERN_DOUBLE,
        hardware.buzzer.PATTERN_TRIPLE,
        hardware.buzzer.PATTERN_ASCENDING,
        hardware.buzzer.PATTERN_DESCENDING,
        hardware.buzzer.PATTERN_SOS
    ]
    
    for pattern in patterns:
        print(f"Playing pattern: {pattern}")
        task = hardware.buzzer.play_pattern(pattern)
        await task
        await asyncio.sleep(0.5)
    
    # Test demo melody
    print("Playing demo melody...")
    task = hardware.buzzer.play_demo()
    await task

async def test_vibration(hardware):
    """Test vibration motor functionality"""
    print("\nTesting Vibration Motor...")
    
    # Test basic vibration
    print("Testing basic vibration...")
    task = hardware.vibration.start_vibration(1000)  # 1 second vibration
    await task
    
    # Test patterns
    print("Testing patterns...")
    patterns = [
        hardware.vibration.PATTERN_CONTINUOUS,
        hardware.vibration.PATTERN_PULSE,
        hardware.vibration.PATTERN_DOUBLE,
        hardware.vibration.PATTERN_TRIPLE,
        hardware.vibration.PATTERN_LONG_SHORT
    ]
    
    for pattern in patterns:
        print(f"Running pattern: {pattern}")
        task = hardware.vibration.start_pattern(pattern, repeat=2)
        await task
        await asyncio.sleep(0.5)

async def test_power_management(hardware):
    """Test power management functionality"""
    print("\nTesting Power Management...")
    
    # Test activity registration
    print("Testing activity registration...")
    hardware.power.register_activity()
    print("Activity registered, sleep timers reset")

async def main():
    """Main test function"""
    print("Starting Hardware Test Script...")
    
    # Initialize hardware interface
    hardware = HardwareInterface()
    
    try:
        # Run tests
        #await test_accelerometer(hardware)
        await test_led_ring(hardware)
        #await test_button(hardware)
        await test_buzzer(hardware)
        #await test_vibration(hardware)
        #await test_power_management(hardware)
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        
    finally:
        # Clean up hardware
        hardware.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
