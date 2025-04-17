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
    orientation = hardware.get_orientation()
    print(f"Current orientation: {orientation}")
    
    # Test tilt angles
    print("Testing tilt angles...")
    angles = hardware.get_tilt_angles()
    print(f"Tilt angles: X={angles[0]:.1f}°, Y={angles[1]:.1f}°, Z={angles[2]:.1f}°")
    
    # Test shake detection
    print("Testing shake detection (shake the device)...")
    for _ in range(10):
        shake = hardware.detect_shake()
        print(f"Shake intensity: {shake}")
        await asyncio.sleep(0.5)
    
    # Test movement detection
    print("Testing movement detection (move the device)...")
    for _ in range(10):
        movement = hardware.detect_movement()
        print(f"Movement intensity: {movement}")
        await asyncio.sleep(0.5)

async def test_led_ring(hardware):
    """Test LED ring functionality"""
    print("\nTesting LED Ring...")
    
    # Test basic color setting
    print("Testing color setting...")
    hardware.set_led_color((255, 0, 0))  # Red
    await asyncio.sleep(1)
    hardware.set_led_color((0, 255, 0))  # Green
    await asyncio.sleep(1)
    hardware.set_led_color((0, 0, 255))  # Blue
    await asyncio.sleep(1)
    
    # Test brightness control
    print("Testing brightness control...")
    for brightness in range(0, 256, 51):
        hardware.set_led_brightness(brightness)
        print(f"Brightness: {brightness}")
        await asyncio.sleep(0.5)
    
    # Test LED count control
    print("Testing LED count control...")
    for count in range(13):
        hardware.set_led_count(count)
        print(f"Active LEDs: {count}")
        await asyncio.sleep(0.5)
    
    # Test patterns
    print("Testing patterns...")
    patterns = [
        hardware.led_ring.BLINK,
        hardware.led_ring.BREATHE,
        hardware.led_ring.CHASE,
        hardware.led_ring.RAINBOW,
        hardware.led_ring.ALTERNATE
    ]
    
    for pattern in patterns:
        print(f"Running pattern: {pattern}")
        task = hardware.start_led_pattern(pattern, speed=5, duration_ms=3000)
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
    hardware.add_button_callback("press", on_press)
    hardware.add_button_callback("release", on_release)
    hardware.add_button_callback("hold", on_hold)
    hardware.add_button_callback("double_tap", on_double_tap)
    
    print("Press the button to test callbacks...")
    print("Try: single press, hold, and double tap")
    await asyncio.sleep(10)
    
    # Remove callbacks
    hardware.remove_button_callback("press", on_press)
    hardware.remove_button_callback("release", on_release)
    hardware.remove_button_callback("hold", on_hold)
    hardware.remove_button_callback("double_tap", on_double_tap)

async def test_buzzer(hardware):
    """Test buzzer functionality"""
    print("\nTesting Buzzer...")
    
    # Test volume control
    print("Testing volume control...")
    hardware.set_volume(50)
    
    # Test single frequency
    print("Testing single frequency...")
    task = hardware.play_frequency(440, 1000)  # A4 note for 1 second
    await task
    
    # Test musical notes
    print("Testing musical notes...")
    notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
    for note in notes:
        print(f"Playing note: {note}")
        task = hardware.play_note(note, 500)
        await task
        await asyncio.sleep(0.1)
    
    # Test patterns
    print("Testing patterns...")
    patterns = [
        hardware.buzzer.DOUBLE,
        hardware.buzzer.TRIPLE,
        hardware.buzzer.ASCENDING,
        hardware.buzzer.DESCENDING,
        hardware.buzzer.SOS
    ]
    
    for pattern in patterns:
        print(f"Playing pattern: {pattern}")
        task = hardware.start_buzzer_pattern(pattern)
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
    task = hardware.vibrate(1000)  # 1 second vibration
    await task
    
    # Test patterns
    print("Testing patterns...")
    patterns = [
        hardware.vibration.CONTINUOUS,
        hardware.vibration.PULSE,
        hardware.vibration.DOUBLE,
        hardware.vibration.TRIPLE,
        hardware.vibration.LONG_SHORT
    ]
    
    for pattern in patterns:
        print(f"Running pattern: {pattern}")
        task = hardware.start_vibration_pattern(pattern, repeat=2)
        await task
        await asyncio.sleep(0.5)

async def test_power_management(hardware):
    """Test power management functionality"""
    print("\nTesting Power Management...")
    
    # Test activity registration
    print("Testing activity registration...")
    hardware.register_activity()
    print("Activity registered, sleep timers reset")

async def test_concurrent_components(hardware):
    """Test concurrent operation of buzzer, LED ring, vibration motor, and button"""
    print("\nTesting Concurrent Component Operation...")
    
    # Button press counter
    button_press_count = 0
    
    def on_button_press():
        nonlocal button_press_count
        button_press_count += 1
        print(f"Button pressed! Count: {button_press_count}")
        
        # Change LED color on button press
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
        hardware.set_led_color(colors[button_press_count % len(colors)])
        
        # Play a different note on each press
        notes = ["C4", "E4", "G4", "C5"]
        hardware.play_note(notes[button_press_count % len(notes)], 200)
        
        # Vibrate on button press
        hardware.vibrate(200)
    
    # Add button callback
    hardware.add_button_callback("press", on_button_press)
    
    # Set initial LED color
    hardware.set_led_color((255, 0, 0))  # Red
    
    # Start a pattern that runs for 5 seconds
    print("Starting 5-second pattern with LED, vibration, and buzzer...")
    print("Press the button to see interactive effects!")
    
    # Create tasks for concurrent operation
    led_task = hardware.start_led_pattern(hardware.led_ring.BREATHE, speed=3)
    vib_task = hardware.start_vibration_pattern(hardware.vibration.PULSE, repeat=5)
    buzzer_task = hardware.start_buzzer_pattern(hardware.buzzer.ASCENDING)
    
    # Wait for 5 seconds
    await asyncio.sleep(5)
    
    # Cancel tasks
    led_task.cancel()
    vib_task.cancel()
    buzzer_task.cancel()
    
    # Clear LEDs
    hardware.led_ring.clear()
    
    # Remove button callback
    hardware.remove_button_callback("press", on_button_press)
    
    print(f"Concurrent test completed. Button was pressed {button_press_count} times.")

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
        #await test_buzzer(hardware)
        #await test_vibration(hardware)
        #await test_power_management(hardware)
        #await test_concurrent_components(hardware)
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        
    finally:
        # Clean up hardware
        hardware.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
