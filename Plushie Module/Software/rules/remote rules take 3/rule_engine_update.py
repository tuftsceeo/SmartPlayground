"""
Educational Module System - Rule Engine Update
--------------------------------------------
This file contains the methods that need to be added to the existing rule_engine.py
file to support remote rule functionality.
"""

"""
Add these methods to the RuleEngine class in rule_engine.py:
"""

def set_remote_manager(self, remote_manager):
    """Set the remote manager for handling remote rules.
    
    Args:
        remote_manager: RemoteRuleManager instance
    """
    self._remote_manager = remote_manager
    print("Remote manager set in RuleEngine")

def execute_remote_action(self, target_module, action_type, parameters, output_value):
    """Execute a remote action by sending a message to the target module.
    
    Args:
        target_module: Target module MAC address
        action_type: Action type
        parameters: Action parameters
        output_value: Output value from mapping
        
    Returns:
        Success flag
    """
    print(f"Executing remote action: {action_type} on module {target_module}")
    
    # Check if remote manager is available
    if hasattr(self, '_remote_manager'):
        return self._remote_manager.send_action(
            target_module, action_type, parameters, output_value)
    else:
        print("Remote manager not set - cannot execute remote action")
        return False
