"""
Educational Module System - Remote Rule Manager
----------------------------------------------
This module provides remote rule functionality by connecting the rule engine
with the networking module.
"""
import time

class RemoteRuleManager:
    """
    Manages remote rule execution and reception between modules.
    
    This class acts as a mediator between the RuleEngine and Networking classes,
    handling message translation, sending, and receiving for remote rules.
    """
    
    def __init__(self, rule_engine, networking):
        """Initialize the remote rule manager.
        
        Args:
            rule_engine: RuleEngine instance
            networking: Networking instance
        """
        self.rule_engine = rule_engine
        self.networking = networking
        self.rule_engine.set_remote_manager(self)
        
        # Register for message reception
        self.networking.aen.irq(self._on_message_received)
        
        print("RemoteRuleManager initialized")
    
    def send_action(self, target_module, action_type, parameters, output_value):
        """Send an action message to a remote module.
        
        Args:
            target_module: Target module MAC address (string or bytes)
            action_type: Action type (OutputTypes)
            parameters: Action parameters
            output_value: Output value from mapping
            
        Returns:
            Success flag
        """
        # Ensure target_module is a bytes object
        if isinstance(target_module, str):
            # Convert hex string MAC address to bytes
            target_module = self._hex_string_to_bytes(target_module)
        
        print(f"Sending action to {target_module}: {action_type}")
        
        # Create message
        message = {
            'type': 'ACTION',
            'action_type': action_type,
            'parameters': parameters,
            'value': output_value,
            'timestamp': time.ticks_ms()
        }
        
        # Send message - no retry in Phase 1
        try:
            self.networking.aen.send(target_module, message)
            print(f"Message sent successfully")
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    def _hex_string_to_bytes(self, mac_string):
        """Convert MAC address hex string to bytes for use.
        
        Args:
            mac_string: MAC address as hex string
            
        Returns:
            MAC address as bytes object
        """
        if not isinstance(mac_string, str) or ":" not in mac_string:
            return mac_string  # Return unchanged if not a hex string
        
        # Split by colon and convert each hex to byte
        return bytes([int(x, 16) for x in mac_string.split(':')])
    
    def _on_message_received(self):
        """Handle message reception callback."""
        print("Message received callback triggered")
        
        # Check for messages
        if not self.networking.aen.check_messages():
            print("No messages in queue")
            return
        
        # Get messages
        messages = self.networking.aen.return_messages()
        
        # Process each message
        for mac, message, timestamp in messages:
            if mac is not None and message is not None:
                print(f"Processing message from {mac}: {message}")
                self._process_message(mac, message, timestamp)
    
    def _process_message(self, source_mac, message, timestamp):
        """Process a received message.
        
        Args:
            source_mac: Source module MAC address
            message: Message content
            timestamp: Message timestamp
        """
        print(f"Message from {source_mac}: {message} (time: {timestamp})")
        
        # Only process dictionaries
        if not isinstance(message, dict):
            print("Message is not a dictionary, ignoring")
            return
        
        # Process action messages
        if message.get('type') == 'ACTION':
            self._process_action_message(source_mac, message)
        elif message.get('type') == 'PING':
            self._process_ping_message(source_mac, message)
        # Add other message types as needed
    
    def _process_action_message(self, source_mac, message):
        """Process an action message and execute the corresponding action.
        
        Args:
            source_mac: Source module MAC address
            message: Message content
        """
        action_type = message.get('action_type')
        parameters = message.get('parameters', {})
        output_value = message.get('value')
        
        print(f"Executing action: {action_type} with parameters: {parameters}")
        
        # Execute the action using the rule engine's direct action execution
        self.rule_engine.execute_action_from_message(
            source_mac, action_type, parameters, output_value)
    
    def _process_ping_message(self, source_mac, message):
        """Process a ping message by sending a pong response.
        
        Args:
            source_mac: Source module MAC address
            message: Message content
        """
        print(f"Received ping from {source_mac}")
        
        # Send pong response
        pong_message = {
            'type': 'PONG',
            'timestamp': time.ticks_ms()
        }
        
        try:
            self.networking.aen.send(source_mac, pong_message)
            print(f"Sent pong response to {source_mac}")
        except Exception as e:
            print(f"Error sending pong response: {e}")