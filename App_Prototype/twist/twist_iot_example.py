"""
IoT System Controller Example
Uses Qwiic Twist for mode selection and status indication
"""
import qwiic_twist
from twist_iot import TwistIOT
import time
import asyncio

class IoTController:
    def __init__(self):
        self.twist_iot = TwistIOT()
        self.system_state = "initializing"
        self.wifi_connected = False
        self.sensor_value = 0
        
        # Define system modes
        modes = [
            ("WiFi Setup", 255, 0, 255),    # Magenta
            ("Sensor Monitor", 0, 255, 0),  # Green
            ("Configuration", 255, 255, 0), # Yellow
            ("Sleep Mode", 0, 0, 255)       # Blue
        ]
        self.twist_iot.setup_modes(modes)
        
    async def setup(self):
        """Initialize system"""
        print("System starting...")
        self.twist_iot.show_connection_status(False)  # Red = not connected
        
        # Simulate WiFi connection
        for i in range(5):
            self.twist_iot.show_progress(i * 20)  # 0-100%
            await asyncio.sleep_ms(500)
            
        self.wifi_connected = True
        self.twist_iot.success_flash()  # Green flash
        await asyncio.sleep_ms(1000)
        
        self.twist_iot.show_mode()  # Show current mode
        print("System ready")
        
    async def handle_mode_0_wifi(self):
        """WiFi Setup Mode - Continuous red/blue blink"""
        if not self.twist_iot.blink_state['active']:
            self.twist_iot.start_blink((255, 0, 0), times=50, interval=400)  # Slow red blink
            
        delta = self.twist_iot.get_rotation_delta()
        if delta != 0:
            print(f"WiFi Channel: {delta}")
            
    async def handle_mode_1_sensor(self):
        """Sensor Monitor Mode - Continuous green breathing"""
        if not self.twist_iot.breathe_state['active']:
            self.twist_iot.start_breathe((0, 255, 0), duration=10000)  # 10 sec green breathe
            
        delta = self.twist_iot.get_rotation_delta()
        if delta != 0:
            self.sensor_value += delta * 5
            self.sensor_value = max(0, min(100, self.sensor_value))
            print(f"Sensor threshold: {self.sensor_value}")
            
    async def handle_mode_2_config(self):
        """Configuration Mode - Continuous orange blink"""
        if not self.twist_iot.blink_state['active']:
            self.twist_iot.start_blink((255, 100, 0), times=50, interval=300)  # Fast orange blink
            
        delta = self.twist_iot.get_rotation_delta()
        if delta != 0:
            print(f"Config parameter: {delta}")
            
    async def handle_mode_3_sleep(self):
        """Sleep Mode"""
        # Dim the LED
        mode_color = self.twist_iot.get_current_mode_color()
        r, g, b = [int(c * 0.1) for c in mode_color]  # 10% brightness
        self.twist_iot.twist.set_color(r, g, b)
        
    async def main_loop(self):
        """Main system loop"""
        mode_handlers = [
            self.handle_mode_0_wifi,
            self.handle_mode_1_sensor,
            self.handle_mode_2_config,
            self.handle_mode_3_sleep
        ]
        
        while True:
            # Check for mode changes
            if self.twist_iot.cycle_mode_on_click():
                mode_name = self.twist_iot.modes[self.twist_iot.current_mode][0]
                print(f"Switched to: {mode_name}")
                
            # Update animations
            self.twist_iot.update_animations()
            
            # Handle current mode
            current_handler = mode_handlers[self.twist_iot.current_mode]
            await current_handler()
            
            # Simulate other async tasks
            await asyncio.sleep_ms(50)
            
    async def run(self):
        """Main entry point"""
        await self.setup()
        await self.main_loop()

# Non-async version for systems without asyncio
def simple_main():
    """Simple synchronous version"""
    controller = IoTController()
    
    print("Simple IoT Controller")
    print("Rotate: adjust values | Click: change mode")
    
    while True:
        # Handle mode changes
        if controller.twist_iot.cycle_mode_on_click():
            mode_name = controller.twist_iot.modes[controller.twist_iot.current_mode][0]
            print(f"Mode: {mode_name}")
            
        # Handle rotation
        delta = controller.twist_iot.get_rotation_delta()
        if delta != 0:
            print(f"Adjustment: {delta}")
            
        # Update animations
        controller.twist_iot.update_animations()
        
        # Small delay
        time.sleep_ms(50)

if __name__ == "__main__":
    # Use async version if available
    try:
        controller = IoTController()
        asyncio.run(controller.run())
    except:
        # Fallback to simple version
        simple_main()