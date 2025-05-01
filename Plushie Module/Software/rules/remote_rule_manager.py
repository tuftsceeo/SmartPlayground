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
            target_module: Target module MAC address
            action_type: Action type (OutputTypes)
            parameters: Action parameters
            output_value: Output value from mapping
            
        Returns:
            Success flag
        """
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
        # In Phase 1, just log the message
        print(f"Message from {source_mac}: {message} (time: {timestamp})")
        
        # Phase 3 will implement rule matching and execution
