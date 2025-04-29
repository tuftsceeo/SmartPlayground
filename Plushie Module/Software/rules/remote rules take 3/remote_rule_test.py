"""
Educational Module System - Remote Rule Test
-------------------------------------------
This script tests the remote rule functionality by setting up two modules
that can control each other's LEDs via button presses.
"""

import time
import uasyncio as asyncio
from machine import Pin, Timer
from hardware import HardwareInterface
from rule_engine import RuleEngine, InputTypes, OutputTypes, MappingTypes
from networking import Networking
from remote_rule_manager import RemoteRuleManager

# Constants - Update these with your own MAC addresses
MODULE1_MAC = b'\xe4\xb3\x23\xb5\x73\x74'  # Module 1
MODULE2_MAC = b'\xe4\xb3\x23\xb4\x84\x2c'  # Module 2
BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'  # Broadcast address

class RemoteRuleTest:
    def __init__(self, module_number=1):
        """Initialize the remote rule test.
        
        Args:
            module_number: 1 for Module 1, 2 for Module 2
        """
        print("\n===============================")
        print(f"Remote Rule Test (Module {module_number})")
        print("===============================\n")
        
        # Store module information
        self.module_number = module_number
        if module_number == 1:
            self.my_mac = MODULE1_MAC
            self.remote_mac = MODULE2_MAC
        else:
            self.my_mac = MODULE2_MAC
            self.remote_mac = MODULE1_MAC
        
        print(f"My MAC: {self.my_mac}")
        print(f"Remote MAC: {self.remote_mac}")
        
        # Initialize components
        print("\nInitializing hardware...")
        self.hardware = HardwareInterface()
        
        print("Initializing rule engine...")
        self.rule_engine = RuleEngine(self.hardware)
        
        print("Initializing networking...")
        self.networking = Networking(True, False, True)  # info_msg=True, debug_msg=False
        
        # Clear any existing rules
        print("Clearing existing rules...")
        self.rule_engine.clear_all_rules()
        
        # Set up the remote manager
        print("Setting up remote rule manager...")
        self.remote_manager = RemoteRuleManager(self.rule_engine, self.networking)
        
        # Add peers
        print("Adding remote peer...")
        self.networking.aen.add_peer(self.remote_mac, f"Module {3-module_number}")
        print("Adding broadcast peer...")
        self.networking.aen.add_peer(BROADCAST_MAC, "Broadcast")
        
        # Set initial LED color based on module number
        if module_number == 1:
            self.hardware.set_led_color((0, 0, 255))  # Blue for Module 1
        else:
            self.hardware.set_led_color((255, 0, 0))  # Red for Module 2
        
        # Set up status check timer
        self.status_timer = Timer(0)
        self.status_timer.init(period=5000, mode=Timer.PERIODIC, callback=self.check_status)
        
        print("Initialization complete!\n")
    
    def check_status(self, timer=None):
        """Check connection status to remote module."""
        print("Checking connection status...")
        
        # Ping the remote module
        self.networking.aen.ping(self.remote_mac)
        
        # Check RSSI information
        rssi_info = self.networking.aen.rssi()
        
        if self.remote_mac in rssi_info:
            remote_rssi = rssi_info[self.remote_mac][0]
            print(f"Remote RSSI: {remote_rssi}")
            
            if remote_rssi > -80:  # Good signal strength
                print("Connected to remote module")
            else:
                print(f"Weak signal: {remote_rssi}")
        else:
            print("No connection to remote module")
    
    def setup_test_rules(self):
        """Set up test rules for remote control."""
        print("Setting up test rules...")
        
        # Local rule: Button press -> changes local LED color
        local_color = (0, 255, 0) if self.module_number == 1 else (0, 0, 255)
        local_hue = 120 if self.module_number == 1 else 240  # Green for Module 1, Blue for Module 2
        
        self.rule_engine.add_rule({
            'name': 'Button Press -> Local LED',
            'source': {
                'module_id': 'self',
                'type': InputTypes.BUTTON_PRESS
            },
            'target': {
                'module_id': 'self',
                'type': OutputTypes.LED_COLOR,
                'parameters': {
                    'hue': local_hue
                }
            }
        })
        print(f"Added local rule: Button Press -> Local LED (hue: {local_hue})")
        
        # Remote rule: Button release -> changes remote LED color
        remote_hue = 0 if self.module_number == 1 else 60  # Red for remote if Module 1, Yellow for remote if Module 2
        
        self.rule_engine.add_rule({
            'name': 'Button Release -> Remote LED',
            'source': {
                'module_id': 'self',
                'type': InputTypes.BUTTON_RELEASE
            },
            'target': {
                'module_id': self.remote_mac,
                'type': OutputTypes.LED_COLOR,
                'parameters': {
                    'hue': remote_hue
                }
            }
        })
        print(f"Added remote rule: Button Release -> Remote LED (hue: {remote_hue})")
        
        # Add a rule for double-tap to play a sound pattern
        self.rule_engine.add_rule({
            'name': 'Double Tap -> Sound Pattern',
            'source': {
                'module_id': 'self',
                'type': InputTypes.BUTTON_DOUBLE_TAP
            },
            'target': {
                'module_id': 'self',
                'type': OutputTypes.BUZZER_PATTERN,
                'parameters': {
                    'pattern': 'DING'
                }
            }
        })
        print("Added local rule: Double Tap -> Sound Pattern")
        
        # Register input handlers
        print("Registering input handlers...")
        self.rule_engine.register_input_handlers()
        
        print("Test rules setup complete!\n")
    
    async def run(self):
        """Run the test."""
        print("Running remote rule test...")
        print("Try these interactions:")
        print("- Button Press: Change your own LED color")
        print("- Button Release: Change the remote module's LED color")
        print("- Double Tap: Play a confirmation sound")
        print("Press Ctrl+C to exit")
        
        # Send initial ping to help establish connection
        print("\nSending initial ping...")
        self.networking.aen.ping(self.remote_mac)
        
        # Run indefinitely
        counter = 0
        while True:
            counter += 1
            if counter % 100 == 0:  # Every 10 seconds (100 * 0.1s)
                print(f"\nTest still running... ({counter//100}0s)")
                # Send periodic ping to maintain connection
                self.networking.aen.ping(self.remote_mac)
            
            await asyncio.sleep(0.1)  # Short sleep to keep responsive

def main():
    """Main entry point."""

    module_number = 1
    print("CURRENT MODULE NUMBER:", module_number)
    
    # Create and run the test
    test = RemoteRuleTest(module_number)
    test.setup_test_rules()
    
    asyncio.run(test.run())


if __name__ == "__main__":
    main()
