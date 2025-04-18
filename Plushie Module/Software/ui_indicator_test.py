"""
Educational Module System - UI Indicator Test Script
------------------------------------------------
This script demonstrates the UI indicators for the Educational Module System.
Press the button to cycle through different indicators.
"""
import uasyncio as asyncio
from hardware import HardwareInterface

# List of all indicators to test
INDICATORS = [
    ("Confirmation", "green pulsing light, ascending ding, short vibration", "show_confirmation"),
    ("Error", "red blinking light, descending error tone, double vibration", "show_error"),
    ("Information", "yellow pulsing light, medium tone, single vibration", "show_information"),
    ("Connecting", "blue chasing light, ascending/descending tones, continuous pulsing", "show_connecting"),
    ("Connection Established", "blue rainbow, connection melody, triple pulse", "show_connection_established"),
    ("Attention", "multi-color alternating, attention melody, long-short vibration", "show_attention"),
    ("Calm", "soft blue breathing light, gentle descending tone, no vibration", "show_calm"),
    ("Celebration", "rainbow pattern, celebratory melody, triple pulse", "show_celebration"),
    ("Sleep", "dimming light, soft descending tone, gentle pulse", "show_sleep"),
    ("Help", "purple pulsing light, friendly alternating notes, double gentle pulse", "show_help")
]

class IndicatorTester:
    """Class to manage the UI indicator testing"""
    
    def __init__(self, hardware):
        """Initialize the tester with hardware interface"""
        self.hardware = hardware
        self.current_index = 0
        self.running = False
        self.current_tasks = []
        
        # Set up button callback
        self.hardware.add_button_callback("press", self.button_pressed)
        
        # Print instructions
        print("\nUI Indicator Test Script")
        print("------------------------")
        print("Press the button to cycle through different indicators")
        print("Current indicator: " + INDICATORS[self.current_index][0])
        print("Description: " + INDICATORS[self.current_index][1])
    
    def button_pressed(self):
        """Handle button press to switch to next indicator"""
        # Cancel current tasks
        self.cancel_current_tasks()
        
        # Move to next indicator
        self.current_index = (self.current_index + 1) % len(INDICATORS)
        
        # Show new indicator
        self.show_current_indicator()
    
    def cancel_current_tasks(self):
        """Cancel any running tasks"""
        for task in self.current_tasks:
                task.cancel()
        self.current_tasks = []
        
        # Clear outputs
        self.hardware.led_ring.clear()
        self.hardware.buzzer.stop()
        self.hardware.vibration.cancel_vibration()
    
    def show_current_indicator(self):
        """Show the current indicator"""
        name, description, method_name = INDICATORS[self.current_index]
        
        print(f"\nShowing {name} Indicator...")
        print(f"Description: {description}")
        
        # Get the method from hardware interface
        method = getattr(self.hardware, method_name)
        
        # Call the method and store tasks
        self.current_tasks = method()
    
    async def run(self):
        """Run the indicator tester"""
        self.running = True
        
        # Show initial indicator
        self.show_current_indicator()
        
        # Keep running until stopped
        while self.running:
            await asyncio.sleep(0.1)
    
    def stop(self):
        """Stop the tester"""
        self.running = False
        self.cancel_current_tasks()
        self.hardware.remove_button_callback("press", self.button_pressed)

async def main():
    """Main test function"""
    print("Starting UI Indicator Test Script...")
    
    # Initialize hardware interface
    hardware = HardwareInterface()
    
    try:
        # Create and run the tester
        tester = IndicatorTester(hardware)
        await tester.run()
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        
    finally:
        # Clean up hardware
        hardware.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 