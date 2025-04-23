"""
Educational Module System - Robust Remote Rules Implementation
-------------------------------------------------------------
This example demonstrates a robust implementation of remote rules using ESP-NOW
that is less sensitive to module startup timing.

Module 1 MAC: e4:b3:23:b5:73:74
Module 2 MAC: e4:b3:23:b4:84:2c

Functionality:
- Each module's button press/release controls the other module's LED color
- Uses periodic status checks and broadcast messages for reliable connection
- Implements retry mechanism for message sending
"""

import time
import uasyncio as asyncio
from machine import Pin, Timer
from hardware import HardwareInterface
from rule_engine import RuleEngine, InputTypes, OutputTypes, MappingTypes
from networking import Networking

# Constants - Update these with your own MAC addresses
MODULE1_MAC = b'\xe4\xb3\x23\xb5\x73\x74'  # Module 1
MODULE2_MAC = b'\xe4\xb3\x23\xb4\x84\x2c'  # Module 2
BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'  # Broadcast address

class RobustRemoteRules:
    def __init__(self, module_number=1):
        """Initialize the remote rules system.
        
        Args:
            module_number: 1 for Module 1, 2 for Module 2
        """
        print("Starting initialization...")
        print("Module number:", module_number)
        
        # Store module information
        self.module_number = module_number
        if module_number == 1:
            self.my_mac = MODULE1_MAC
            self.remote_mac = MODULE2_MAC
        else:
            self.my_mac = MODULE2_MAC
            self.remote_mac = MODULE1_MAC
        
        print("My MAC:", self.my_mac)
        print("Remote MAC:", self.remote_mac)
        
        # Initialize hardware
        print("Initializing hardware...")
        self.hardware = HardwareInterface()
        print("Hardware initialized")
        
        # Initialize rule engine
        print("Initializing rule engine...")
        self.rule_engine = RuleEngine(self.hardware)
        print("Rule engine initialized")
        
        # Clear any existing rules
        print("Clearing existing rules...")
        self.rule_engine.clear_all_rules()
        print("Rules cleared")
        
        # Initialize networking
        print("Initializing networking...")
        self.networking = Networking(True, False, True)  # info_msg=True, debug_msg=False
        print("Networking initialized")
        
        # Add broadcast and remote peer
        print("Adding broadcast peer...")
        self.networking.aen.add_peer(BROADCAST_MAC, "Broadcast")
        print("Broadcast peer added")
        
        print("Adding remote peer...")
        self.networking.aen.add_peer(self.remote_mac, "Remote Module")
        print("Remote peer added")
        
        # Set up callback for message reception
        print("Setting up message callback...")
        self.networking.aen.irq(self.receive_message)
        print("Message callback set")
        
        # Set up button callbacks
        print("Setting up button callbacks...")
        self.hardware.add_button_callback("press", self.on_button_press)
        self.hardware.add_button_callback("release", self.on_button_release)
        print("Button callbacks set")
        
        # Connection status
        self.remote_rssi = None
        self.connected = False
        
        # Set up status check timer (every 3 seconds)
        print("Setting up status timer...")
        self.status_timer = Timer(0)
        self.status_timer.init(period=3000, mode=Timer.PERIODIC, callback=self.check_status)
        print("Status timer set")
        
        # Set initial LED color
        print("Setting initial LED color...")
        self.hardware.set_led_color((0, 0, 255))  # Blue
        print("LED color set")
        
        # Announce our presence
        print("Sending broadcast ping...")
        self.networking.aen.ping(BROADCAST_MAC)
        print("Broadcast ping sent")
        
        print("Module initialization complete")
        print("=== Robust Remote Rules (Module", module_number, ") ===")
        print("Module initialized. Press the button to control remote LED color.")
    
    def check_status(self, timer=None):
        """Check connection status to remote module."""
        print("Checking status...")
        
        # Ping the remote module directly
        print("Pinging remote module:", self.remote_mac)
        self.networking.aen.ping(self.remote_mac)
        print("Ping sent")
        
        # Update RSSI information
        print("Getting RSSI information...")
        rssi_info = self.networking.aen.rssi()
        print("RSSI info:", rssi_info)
        
        if self.remote_mac in rssi_info:
            self.remote_rssi = rssi_info[self.remote_mac][0]
            print("Remote RSSI:", self.remote_rssi)
            
            if self.remote_rssi > -80:  # Good signal strength
                if not self.connected:
                    print("Connected to remote module. RSSI:", self.remote_rssi)
                    self.connected = True
            else:
                print("Signal too weak:", self.remote_rssi)
                self.connected = False
        else:
            print("No RSSI information for remote module")
            self.remote_rssi = None
            self.connected = False
            
        print("Status check complete. Connected:", self.connected)
    
    def on_button_press(self):
        """Handle button press - send message to turn remote LEDs red."""
        print("Button press detected")
        
        # Create message - use a simple consistent format
        message = {
            'event': 'button_action',
            'action': 'press',
            'target': 'led',
            'params': {
                'hue': 0  # Red
            }
        }
        
        print("Sending press message to remote module:", self.remote_mac)
        print("Message content:", message)
        
        # Send message with retry
        self._send_with_retry(message)
    
    def on_button_release(self, duration):
        """Handle button release - send message to turn remote LEDs green."""
        print("Button release detected, duration:", duration, "ms")
        
        # Create message
        message = {
            'event': 'button_action',
            'action': 'release',
            'target': 'led',
            'params': {
                'hue': 120  # Green
            }
        }
        
        print("Sending release message to remote module:", self.remote_mac)
        print("Message content:", message)
        
        # Send message with retry
        self._send_with_retry(message)
    
    def _send_with_retry(self, message, max_retries=3):
        """Send a message with retry mechanism."""
        print("Attempting to send message, max retries:", max_retries)
        
        for attempt in range(max_retries):
            print("Send attempt", attempt + 1, "of", max_retries)
            
            # Removed try-except to expose errors for debugging
            self.networking.aen.send(self.remote_mac, message)
            print("Message sent successfully on attempt", attempt + 1)
            return True
                
        print("Failed to send message after", max_retries, "attempts")
        return False
    
    def receive_message(self):
        """Process received messages."""
        print("Message callback triggered")
        
        # Check if there are any messages
        if not self.networking.aen.check_messages():
            print("No messages in queue")
            return
        
        print("Processing received messages...")
        messages = self.networking.aen.return_messages()
        
        for mac, message, timestamp in messages:
            print("Message from:", mac)
            print("Message content:", message)
            print("Timestamp:", timestamp)
            
            # First check if it's a dictionary message for button actions
            if isinstance(message, dict) and 'event' in message:
                print("Valid event message detected")
                
                if message['event'] == 'button_action' and message['target'] == 'led':
                    print("Button action event for LED detected")
                    
                    # Extract hue value for LED color
                    hue = message['params'].get('hue', 0)
                    print("Hue value:", hue)
                    
                    # Update LED color through rule engine's local action
                    print("Executing LED color change through rule engine")
                    self.rule_engine.execute_local_action(
                        OutputTypes.LED_COLOR,
                        {'hue': hue},
                        None
                    )
                    
                    print("LED color changed successfully")
            else:
                print("Not a valid event message, ignoring")
    
    async def run(self):
        """Run the example until interrupted."""
        print("Example running... Press Ctrl+C to exit")
        
        # Send initial broadcast to help establish connection
        self.networking.aen.ping(BROADCAST_MAC)
        
        # Run indefinitely without try-except to expose errors
        counter = 0
        while True:
            counter += 1
            if counter % 60 == 0:  # Every 6 seconds
                if self.remote_rssi is not None:
                    print("Still running... RSSI: {}".format(self.remote_rssi))
                else:
                    print("Still running... No connection to remote module")
            
            await asyncio.sleep(0.1)  # Short sleep to keep checking button

def main():
    """Main entry point."""


    module_number = 2

    
    # Create and run the example
    example = RobustRemoteRules(module_number)
    
    # Run without try-except to expose errors
    asyncio.run(example.run())

if __name__ == "__main__":
    main()
