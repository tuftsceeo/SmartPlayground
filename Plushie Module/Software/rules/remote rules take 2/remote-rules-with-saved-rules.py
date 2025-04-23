"""
Educational Module System - Remote Rules with Explicit Saved Rules
-----------------------------------------------------------------
This example demonstrates remote rules using ESP-NOW with proper rule saving.

Module 1 MAC: e4:b3:23:b5:73:74
Module 2 MAC: e4:b3:23:b4:84:2c

Functionality:
- Each module defines rules for handling remote messages
- Rules are explicitly saved to the rule engine's storage
- Shows status of initialization steps
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

class RemoteRulesExample:
    def __init__(self, module_number=1):
        """Initialize the remote rules system with explicit saved rules.
        
        Args:
            module_number: 1 for Module 1, 2 for Module 2
        """
        print("=== Remote Rules Example (Module {}) ===".format(module_number))
        print("[INIT] Starting initialization")
        
        # Store module information
        self.module_number = module_number
        if module_number == 1:
            self.my_mac = MODULE1_MAC
            self.remote_mac = MODULE2_MAC
            self.module_name = "Module 1"
        else:
            self.my_mac = MODULE2_MAC
            self.remote_mac = MODULE1_MAC
            self.module_name = "Module 2"
        
        print("[INIT] Initializing hardware...")
        # Initialize hardware
        self.hardware = HardwareInterface()
        print("[INIT] Hardware initialized")
        
        print("[INIT] Initializing rule engine...")
        # Initialize rule engine
        self.rule_engine = RuleEngine(self.hardware)
        
        # Clear any existing rules
        self.rule_engine.clear_all_rules()
        print("[INIT] Rule engine initialized, rules cleared")
        
        # Set up initial rules
        self._create_rules()
        
        print("[INIT] Initializing networking...")
        # Initialize networking
        self.networking = Networking(True, False)  # info_msg=True, debug_msg=False
        print("[INIT] Networking initialized")
        
        # Set up networking callback
        self.networking.aen.irq(self.receive_message)
        
        print("[INIT] Adding peers...")
        # Add broadcast and remote peer
        self.networking.aen.add_peer(BROADCAST_MAC, "Broadcast")
        print("[INIT] Broadcast peer added")
        self.networking.aen.add_peer(self.remote_mac, "Remote Module")
        print("[INIT] Remote peer added")
        
        # Connection status
        self.remote_rssi = None
        self.connected = False
        
        print("[INIT] Setting up status check timer...")
        # Set up status check timer (every 3 seconds)
        self.status_timer = Timer(0)
        self.status_timer.init(period=3000, mode=Timer.PERIODIC, callback=self.check_status)
        print("[INIT] Status check timer initialized")
        
        print("[INIT] Setting initial LED color...")
        # Set initial LED color
        self.hardware.set_led_color((0, 0, 255))  # Blue
        print("[INIT] LED color set to blue")
        
        print("[INIT] Announcing presence...")
        # Announce our presence
        self.networking.aen.ping(BROADCAST_MAC)
        print("[INIT] Broadcast ping sent")
        
        # Set up button callbacks
        self.hardware.add_button_callback("press", self.on_button_press)
        self.hardware.add_button_callback("release", self.on_button_release)
        
        print("[INIT] Initialization complete")
        print("Module initialized. Press the button to control remote LED color.")
    
    def _create_rules(self):
        """Create and save rules in the rule engine."""
        print("[RULES] Creating rules...")
        
        # 1. Local rule: Button press -> Local blue LED
        local_button_rule_id = self.rule_engine.add_rule({
            'name': 'Local Button Press -> Local Blue LED',
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
        print("[RULES] Created local button rule: {}".format(local_button_rule_id))
        
        # 2. Remote rule for incoming 'RED' action
        red_action_rule_id = self.rule_engine.add_rule({
            'name': 'Remote RED Action -> Red LED',
            'source': {
                'module_id': self.remote_mac,
                'type': 'NETWORK_ACTION',  # Custom type for network messages
                'parameters': {
                    'action': 'RED'
                }
            },
            'target': {
                'module_id': 'self',
                'type': OutputTypes.LED_COLOR,
                'parameters': {
                    'hue': 0  # Red
                }
            }
        })
        print("[RULES] Created remote RED action rule: {}".format(red_action_rule_id))
        
        # 3. Remote rule for incoming 'GREEN' action
        green_action_rule_id = self.rule_engine.add_rule({
            'name': 'Remote GREEN Action -> Green LED',
            'source': {
                'module_id': self.remote_mac,
                'type': 'NETWORK_ACTION',  # Custom type for network messages
                'parameters': {
                    'action': 'GREEN'
                }
            },
            'target': {
                'module_id': 'self',
                'type': OutputTypes.LED_COLOR,
                'parameters': {
                    'hue': 120  # Green
                }
            }
        })
        print("[RULES] Created remote GREEN action rule: {}".format(green_action_rule_id))
        
        print("[RULES] All rules created and saved.")
    
    def check_status(self, timer=None):
        """Check connection status to remote module."""
        print("[STATUS] Starting status check")
        
        # Ping the remote module directly
        print("[STATUS] Pinging remote module...")
        self.networking.aen.ping(self.remote_mac)
        
        # Update RSSI information
        print("[STATUS] Getting RSSI information...")
        rssi_info = self.networking.aen.rssi()
        print("[STATUS] RSSI info: {}".format(rssi_info))
        
        if self.remote_mac in rssi_info:
            self.remote_rssi = rssi_info[self.remote_mac][0]
            print("[STATUS] Remote RSSI: {}".format(self.remote_rssi))
            
            if self.remote_rssi > -80:  # Good signal strength
                if not self.connected:
                    print("[STATUS] Connected to remote module. RSSI: {}".format(self.remote_rssi))
                    self.connected = True
                    # Send initial connection message
                    self._send_action("CONNECTED")
            else:
                print("[STATUS] Poor signal strength: {}".format(self.remote_rssi))
                self.connected = False
        else:
            print("[STATUS] Remote module not found in RSSI info")
            self.remote_rssi = None
            self.connected = False
            
        print("[STATUS] Status check complete. Connected: {}".format(self.connected))
    
    def on_button_press(self):
        """Handle button press - send RED action to remote module."""
        print("[BUTTON] Button pressed - sending RED action to remote module")
        self._send_action("RED")
        
        # The button press will also trigger the local rule for blue LED
        # through the rule engine's input handler
    
    def on_button_release(self, duration):
        """Handle button release - send GREEN action to remote module."""
        print("[BUTTON] Button released after {}ms - sending GREEN action".format(duration))
        self._send_action("GREEN")
    
    def _send_action(self, action):
        """Send an action message to the remote module."""
        print("[SEND] Sending {} action to remote module".format(action))
        
        # Format the message
        message = {
            'type': 'NETWORK_ACTION',
            'action': action,
            'from': self.module_name,
            'timestamp': time.ticks_ms()
        }
        
        # Send the message
        self.networking.aen.send(self.remote_mac, message)
        print("[SEND] Message sent: {}".format(message))
    
    def receive_message(self):
        """Process received messages."""
        print("[RECEIVE] Checking for messages...")
        
        messages = self.networking.aen.return_messages()
        print("[RECEIVE] Got {} messages".format(len(messages)))
        
        for mac, message, timestamp in messages:
            print("[RECEIVE] Message from {}: {}".format(mac, message))
            
            # Check if it's a network action message
            if isinstance(message, dict) and message.get('type') == 'NETWORK_ACTION':
                action = message.get('action')
                sender = message.get('from', 'unknown')
                
                print("[RECEIVE] Network action '{}' from {}".format(action, sender))
                
                # Evaluate the rule for this network action
                # This is done by creating a virtual input that the rule engine can process
                self.rule_engine.evaluate_input(
                    'NETWORK_ACTION', 
                    {
                        'action': action,
                        'source_module': mac
                    }
                )
    
    async def run(self):
        """Run the example until interrupted."""
        print("[RUN] Starting main loop...")
        
        # Send initial broadcast to help establish connection
        self.networking.aen.ping(BROADCAST_MAC)
        
        # Run indefinitely without try-except to expose errors
        counter = 0
        while True:
            counter += 1
            if counter % 60 == 0:  # Every 6 seconds
                if self.remote_rssi is not None:
                    print("[RUN] Still running... RSSI: {}".format(self.remote_rssi))
                else:
                    print("[RUN] Still running... No connection to remote module")
                
                # Print all rules
                rules = self.rule_engine.list_rules()
                print("[RUN] Current rules ({} total):".format(len(rules)))
                for rule in rules:
                    print("  - {}: {}".format(rule.id, rule.name))
            
            await asyncio.sleep(0.1)  # Short sleep to keep checking button

def main():
    """Main entry point."""
    # Determine which module this is based on MAC comparison
    from network import WLAN, STA_IF
    
    # Get our MAC address
    wlan = WLAN(STA_IF)
    wlan.active(True)
    my_mac = wlan.config('mac')
    
    # Print our MAC for debugging
    print("My MAC address: {}".format(my_mac))
    
    # Determine module number
    if my_mac == MODULE1_MAC:
        module_number = 1
    elif my_mac == MODULE2_MAC:
        module_number = 2
    else:
        print("Warning: MAC address doesn't match either module.")
        print("Assuming this is Module 1")
        module_number = 1
    
    # Create and run the example
    example = RemoteRulesExample(module_number)
    
    # Run without try-except to expose errors
    asyncio.run(example.run())

if __name__ == "__main__":
    main()
