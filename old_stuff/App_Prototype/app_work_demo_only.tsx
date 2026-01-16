import React, { useState, useEffect } from 'react';
import { Activity, BarChart, CircleDot, ChevronLeft, Circle, Edit, Palette, Save, Plus, Play, Sliders, Volume2, RotateCw, Vibrate, Trash, X, Wifi, WifiOff, ZapOff, Zap, HelpCircle, RefreshCw, AlertCircle } from 'lucide-react';

// ==================================================================================
// CONSTANTS: Based on the actual code from the project's rules_engine.py file
// ==================================================================================

/**
 * Input trigger types that modules can detect
 * These match the exact definitions in rules_engine.py InputTypes class
 */
const InputTypes = {
  // Button inputs
  BUTTON_PRESS: "BUTTON_PRESS",
  BUTTON_RELEASE: "BUTTON_RELEASE",
  BUTTON_HOLD: "BUTTON_HOLD",
  BUTTON_DOUBLE_TAP: "BUTTON_DOUBLE_TAP",
  
  // Accelerometer inputs
  ORIENTATION: "ORIENTATION",
  SHAKE: "SHAKE",
  MOVEMENT: "MOVEMENT",
  TILT_ANGLE_X: "TILT_ANGLE_X",
  TILT_ANGLE_Y: "TILT_ANGLE_Y",
  TILT_ANGLE_Z: "TILT_ANGLE_Z"
};

/**
 * Output action types that modules can perform
 * These match the exact definitions in rules_engine.py OutputTypes class
 */
const OutputTypes = {
  // LED outputs
  LED_COLOR: "LED_COLOR",
  LED_BRIGHTNESS: "LED_BRIGHTNESS",
  LED_COUNT: "LED_COUNT",
  LED_PATTERN: "LED_PATTERN",
  
  // Vibration outputs
  VIBRATION: "VIBRATION",
  VIBRATION_PATTERN: "VIBRATION_PATTERN",
  
  // Buzzer outputs
  BUZZER_FREQUENCY: "BUZZER_FREQUENCY",
  BUZZER_NOTE: "BUZZER_NOTE",
  BUZZER_PATTERN: "BUZZER_PATTERN"
};

/**
 * Mapping types for transforming input values to output values
 * These match the exact definitions in rules_engine.py MappingTypes class
 */
const MappingTypes = {
  DIRECT: "DIRECT",
  THRESHOLD: "THRESHOLD",
  PROPORTIONAL: "PROPORTIONAL"
};

/**
 * Main component for the Smart Playground MVP Prototype
 * This is a React functional component that uses hooks for state management
 */
const SmartPlaygroundMVP = () => {
  // ==================================================================================
  // STATE MANAGEMENT: Define React state hooks for the application
  // ==================================================================================
  
  // Main application state
  const [activeScreen, setActiveScreen] = useState('modules'); // 'modules', 'ruleEditor', 'deployment'
  const [selectedModule, setSelectedModule] = useState(null);
  const [rules, setRules] = useState([]);
  const [currentRule, setCurrentRule] = useState(null);
  const [showNotification, setShowNotification] = useState(false);
  const [notification, setNotification] = useState({ message: '', type: 'info' });
  const [remoteRuleMode, setRemoteRuleMode] = useState('target'); // 'target' or 'source'

  // ==================================================================================
  // MOCK DATA: This would be replaced with real API calls in a production app
  // ==================================================================================
  
  /**
   * Mock modules data with RSSI instead of battery
   * In a real implementation, this would come from an API connected to the Hub
   * which communicates with modules through ESP-NOW
   */
  const [modules, setModules] = useState([
    { 
      id: 1, 
      name: 'Plushie 1', 
      type: 'plushie', 
      macAddress: 'e4:b3:23:b5:73:74', // Real MAC address format from the project
      rssi: -55, // Good signal (RSSI is measured in dBm, closer to 0 is better)
      connected: true,
      lastSeen: Date.now(),
      selected: false 
    },
    { 
      id: 2, 
      name: 'Plushie 2', 
      type: 'plushie', 
      macAddress: 'e4:b3:23:b4:84:2c', 
      rssi: -70, // Medium signal
      connected: true,
      lastSeen: Date.now(),
      selected: false 
    },
    { 
      id: 3, 
      name: 'Button 1', 
      type: 'button', 
      macAddress: 'e4:b3:23:b7:12:55', 
      rssi: -45, // Excellent signal
      connected: true,
      lastSeen: Date.now(),
      selected: false 
    },
    { 
      id: 4, 
      name: 'Plushie 3', 
      type: 'plushie', 
      macAddress: 'e4:b3:23:b8:33:92', 
      rssi: -90, // Poor signal
      connected: false,
      lastSeen: Date.now() - 3600000, // 1 hour ago
      selected: false 
    },
    { 
      id: 5, 
      name: 'Button 2', 
      type: 'button', 
      macAddress: 'e4:b3:23:b9:44:11', 
      rssi: -65, // Good signal
      connected: true,
      lastSeen: Date.now(),
      selected: false 
    }
  ]);

  // ==================================================================================
  // RULE MANAGEMENT: Functions for creating, editing, saving, and deploying rules
  // ==================================================================================
  
  /**
   * Initialize a new rule based on selected modules
   * @implementation This is a prototype implementation. In a real app:
   * - It would validate more thoroughly
   * - It would get defaults from a configuration file
   * - The structure would match the rule_engine.py Rule class exactly
   */
  const initNewRule = () => {
    // Get all selected and connected modules
    const selectedModuleIds = modules
      .filter(module => module.selected && module.connected)
      .map(module => module.macAddress);
    
    // Must have at least one module selected
    if (selectedModuleIds.length === 0) {
      showNotify('Please select at least one connected module first', 'error');
      return;
    }

    // Create a new rule with default values
    const newRule = {
      id: `rule_${Date.now()}`,
      name: 'New Rule',
      enabled: true,
      source: {
        module_id: "self", // Default to local rule
        type: InputTypes.BUTTON_PRESS,
        parameters: {}
      },
      target: {
        module_id: "self", // Default to local rule
        type: OutputTypes.LED_COLOR,
        parameters: {
          hue: 0 // Red in hue color wheel (0-360)
        }
      },
      mapping: {
        type: MappingTypes.DIRECT,
        parameters: {}
      },
      created: Date.now(),
      modified: Date.now(),
      
      // UI-specific properties (not part of the actual rule format in Python)
      remoteMode: false,
      remoteRuleType: 'target', // Default to target mode
      targetModules: [...selectedModuleIds], // Copy to avoid reference issues
      sourceModules: [...selectedModuleIds]  // Copy to avoid reference issues
    };

    setCurrentRule(newRule);
    setActiveScreen('ruleEditor');
  };

  /**
   * Save current rule(s) to the rules array
   * @implementation For remote rules, this creates multiple rules in the background
   * In a real app:
   * - Rules would be sent to the hub via API
   * - The hub would deploy the rules to the modules
   * - Actual rule deployment would happen via ESP-NOW
   */
  const saveRule = () => {
    if (!currentRule) return;

    let rulesToSave = [];
    
    // For remote rules with multiple targets/sources
    if (currentRule.remoteMode) {
      if (currentRule.remoteRuleType === 'target') {
        // One source to multiple targets
        const targetModule = currentRule.target.module_id;
        
        // Fix: When selecting the source modules for a remote target rule
        // we use all selected modules EXCEPT the one we chose as target
        const sourceModules = modules
          .filter(m => m.selected && m.connected && m.macAddress !== targetModule)
          .map(m => m.macAddress);
        
        // Generate a rule for each source module pointing to the target
        sourceModules.forEach(sourceModule => {
          const newRule = {
            ...currentRule,
            id: `rule_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
            source: {
              ...currentRule.source,
              module_id: sourceModule
            },
            target: {
              ...currentRule.target,
              module_id: targetModule
            }
          };
          rulesToSave.push(newRule);
        });
      } else {
        // Multiple sources to one target
        const sourceModule = currentRule.source.module_id;
        
        // Fix: When selecting the target modules for a remote source rule
        // we use all selected modules EXCEPT the one we chose as source
        const targetModules = modules
          .filter(m => m.selected && m.connected && m.macAddress !== sourceModule)
          .map(m => m.macAddress);
        
        // Generate a rule for each target module from the source
        targetModules.forEach(targetModule => {
          const newRule = {
            ...currentRule,
            id: `rule_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
            source: {
              ...currentRule.source,
              module_id: sourceModule
            },
            target: {
              ...currentRule.target,
              module_id: targetModule
            }
          };
          rulesToSave.push(newRule);
        });
      }
    } else {
      // Local rule - just save as is
      rulesToSave = [currentRule];
    }

    // Add or update the rules
    const newRules = [...rules];
    rulesToSave.forEach(rule => {
      const existingIndex = newRules.findIndex(r => r.id === rule.id);
      if (existingIndex >= 0) {
        newRules[existingIndex] = rule;
      } else {
        newRules.push(rule);
      }
    });
    
    setRules(newRules);
    showNotify(`${rulesToSave.length} rule(s) saved successfully`, 'success');
    setActiveScreen('modules');
  };

  /**
   * Delete a rule
   * @param {string} ruleId - The ID of the rule to delete
   */
  const deleteRule = (ruleId) => {
    setRules(rules.filter(rule => rule.id !== ruleId));
    showNotify('Rule deleted', 'info');
  };

  /**
   * Edit an existing rule
   * @param {Object} rule - The rule to edit
   * @implementation This adds UI-specific properties to the rule
   * In a real implementation:
   * - The rule would be loaded from the hub/module
   * - More validation would be performed
   */
  const editRule = (rule) => {
    // Create a deep copy to avoid reference issues
    const ruleCopy = JSON.parse(JSON.stringify(rule));
    
    // Add UI properties if not present
    if (ruleCopy.source.module_id !== "self" || ruleCopy.target.module_id !== "self") {
      ruleCopy.remoteMode = true;
      
      if (ruleCopy.source.module_id !== "self" && ruleCopy.target.module_id !== "self") {
        // If both are set, determine the mode based on which one is in the selected modules
        const selectedMacs = modules
          .filter(m => m.selected)
          .map(m => m.macAddress);
          
        if (selectedMacs.includes(ruleCopy.source.module_id)) {
          ruleCopy.remoteRuleType = 'source';
        } else {
          ruleCopy.remoteRuleType = 'target';
        }
      } else if (ruleCopy.source.module_id !== "self") {
        ruleCopy.remoteRuleType = 'source';
      } else {
        ruleCopy.remoteRuleType = 'target';
      }
      
      // Initialize source/target modules arrays
      const allMacs = modules
        .filter(m => m.connected)
        .map(m => m.macAddress);
        
      ruleCopy.sourceModules = ruleCopy.remoteRuleType === 'source' 
        ? [ruleCopy.source.module_id] 
        : [...allMacs];
        
      ruleCopy.targetModules = ruleCopy.remoteRuleType === 'target' 
        ? [ruleCopy.target.module_id] 
        : [...allMacs];
    }
    
    setCurrentRule(ruleCopy);
    setActiveScreen('ruleEditor');
  };

  /**
   * Deploy rules to modules
   * @implementation This is a placeholder function that simulates deployment
   * In a real implementation:
   * - This would call an API to send rules to the hub
   * - The hub would then distribute rules to modules via ESP-NOW
   * - Status updates would come back through the API
   */
  const deployRules = () => {
    const selectedModuleIds = modules
      .filter(module => module.selected && module.connected)
      .map(module => module.id);
    
    if (selectedModuleIds.length === 0) {
      showNotify('Please select at least one connected module first', 'error');
      return;
    }

    if (rules.length === 0) {
      showNotify('No rules to deploy', 'error');
      return;
    }

    // In a real app, we would initiate the deployment process here
    // For the prototype, we just switch to the deployment screen
    setActiveScreen('deployment');
  };

  /**
   * Simulate completing the deployment process
   * @implementation This is a placeholder function for the prototype
   */
  const completeDeployment = () => {
    // In a real app, this would be triggered by a completed deployment event from the API
    showNotify('Rules deployed successfully to selected modules', 'success');
    setActiveScreen('modules');
  };

  /**
   * Toggle selection state of a module
   * @param {number} moduleId - The ID of the module to toggle
   */
  const toggleModuleSelection = (moduleId) => {
    setModules(modules.map(module => 
      module.id === moduleId 
        ? {...module, selected: !module.selected}
        : module
    ));
  };

  /**
   * Display a notification message
   * @param {string} message - The message to display
   * @param {string} type - The type of notification ('info', 'success', or 'error')
   */
  const showNotify = (message, type = 'info') => {
    setNotification({ message, type });
    setShowNotification(true);
    setTimeout(() => setShowNotification(false), 3000);
  };

  // ==================================================================================
  // FORM HANDLERS: Functions for handling form input changes
  // ==================================================================================

  /**
   * Handle rule name change
   * @param {Object} e - The event object
   */
  const handleRuleNameChange = (e) => {
    setCurrentRule({
      ...currentRule,
      name: e.target.value
    });
  };

  /**
   * Handle rule source type change (trigger)
   * @param {Object} e - The event object
   */
  const handleSourceTypeChange = (e) => {
    setCurrentRule({
      ...currentRule,
      source: {
        ...currentRule.source,
        type: e.target.value,
        parameters: {} // Reset parameters when type changes
      }
    });
  };

  /**
   * Handle rule target type change (action)
   * @param {Object} e - The event object
   */
  const handleTargetTypeChange = (e) => {
    setCurrentRule({
      ...currentRule,
      target: {
        ...currentRule.target,
        type: e.target.value,
        parameters: {} // Reset parameters when type changes
      }
    });
  };

  /**
   * Handle changing between local and remote rule modes
   * @param {boolean} isRemote - Whether to switch to remote mode
   * @param {string} remoteType - The type of remote rule ('target' or 'source')
   * 
   * @implementation This sets up the appropriate source/target relationships
   * - In target mode: One module is the target, all others are sources
   * - In source mode: One module is the source, all others are targets
   */
  const handleRemoteModeChange = (isRemote, remoteType) => {
    if (!isRemote) {
      // Switch to local mode
      setCurrentRule({
        ...currentRule,
        remoteMode: false,
        remoteRuleType: 'target',
        source: {
          ...currentRule.source,
          module_id: "self"
        },
        target: {
          ...currentRule.target,
          module_id: "self"
        }
      });
    } else {
      // Switch to remote mode
      const selectedMacs = modules
        .filter(m => m.selected && m.connected)
        .map(m => m.macAddress);
      
      if (selectedMacs.length === 0) {
        showNotify('No connected modules selected', 'error');
        return;
      }
      
      if (remoteType === 'target') {
        // We're selecting the target module and all other modules are sources
        // Fix: Make sure we include ALL selected modules except the target
        const targetModule = selectedMacs[0];
        const sourceMacs = selectedMacs.filter(mac => mac !== targetModule);
        
        setCurrentRule({
          ...currentRule,
          remoteMode: true,
          remoteRuleType: 'target',
          source: {
            ...currentRule.source,
            module_id: sourceMacs[0] || "self" // Default to first source or self
          },
          target: {
            ...currentRule.target,
            module_id: targetModule // Default to first selected module
          },
          targetModules: [targetModule], // Just the target module
          sourceModules: sourceMacs // All other modules
        });
      } else {
        // We're selecting the source module and all other modules are targets
        // Fix: Make sure we include ALL selected modules except the source
        const sourceModule = selectedMacs[0];
        const targetMacs = selectedMacs.filter(mac => mac !== sourceModule);
        
        setCurrentRule({
          ...currentRule,
          remoteMode: true,
          remoteRuleType: 'source',
          source: {
            ...currentRule.source,
            module_id: sourceModule // Default to first selected module
          },
          target: {
            ...currentRule.target,
            module_id: targetMacs[0] || "self" // Default to first target or self
          },
          sourceModules: [sourceModule], // Just the source module
          targetModules: targetMacs // All other modules
        });
      }
    }
  };

  /**
   * Handle selecting a specific module for remote rules
   * @param {string} moduleId - The MAC address of the selected module
   * @param {boolean} isSource - Whether this is a source or target selection
   */
  const handleRemoteModuleSelect = (moduleId, isSource) => {
    if (isSource) {
      // Update source module
      setCurrentRule({
        ...currentRule,
        source: {
          ...currentRule.source,
          module_id: moduleId
        },
        sourceModules: [moduleId]
      });
    } else {
      // Update target module
      setCurrentRule({
        ...currentRule,
        target: {
          ...currentRule.target,
          module_id: moduleId
        },
        targetModules: [moduleId]
      });
    }
  };

  /**
   * Handle target parameter changes
   * @param {string} paramName - The name of the parameter
   * @param {any} value - The new value
   */
  const handleTargetParameterChange = (paramName, value) => {
    setCurrentRule({
      ...currentRule,
      target: {
        ...currentRule.target,
        parameters: {
          ...currentRule.target.parameters,
          [paramName]: value
        }
      }
    });
  };

  /**
   * Refresh modules list
   * @implementation This is a placeholder function for the prototype
   * In a real implementation:
   * - This would trigger an ESP-NOW scan on the hub
   * - New modules would be returned via API
   */
  const refreshModules = () => {
    // In a real app, this would scan for new modules via an API
    // For the prototype, we just simulate finding a new module
    
    const newModule = { 
      id: modules.length + 1, 
      name: `New Module ${modules.length + 1}`, 
      type: Math.random() > 0.5 ? 'plushie' : 'button', 
      macAddress: `e4:b3:23:${Math.floor(Math.random() * 100)}:${Math.floor(Math.random() * 100)}:${Math.floor(Math.random() * 100)}`, 
      rssi: -Math.floor(Math.random() * 50) - 40, // Random RSSI between -40 and -90
      connected: true,
      lastSeen: Date.now(),
      selected: false 
    };
    
    setModules([...modules, newModule]);
    showNotify(`Found new module: ${newModule.name}`, 'success');
  };

  /**
   * Test the current rule on selected modules
   * @implementation This is a placeholder function for the prototype
   * In a real implementation:
   * - This would send a test message to the hub
   * - The hub would send a temporary rule to the module
   * - The module would execute the rule once
   */
  const testRule = () => {
    if (!currentRule) return;
    
    // In a real implementation, this would send the rule to the selected module
    // For this prototype, we just show a notification
    showNotify(`Testing rule "${currentRule.name}" on selected module(s)`, 'info');
    
    // Simulate a response after a delay
    setTimeout(() => {
      showNotify('Rule test executed successfully', 'success');
    }, 1500);
  };

  // ==================================================================================
  // UI HELPER FUNCTIONS: Functions for rendering UI elements
  // ==================================================================================

  /**
   * Render signal strength indicator based on RSSI value
   * @param {number} rssi - The RSSI value in dBm
   * @return {JSX.Element} The signal strength indicator
   */
  const renderSignalStrength = (rssi) => {
    // RSSI ranges:
    // Excellent: -30 to -60 dBm
    // Good: -60 to -70 dBm
    // Fair: -70 to -80 dBm
    // Poor: -80 to -90 dBm
    // No Signal: < -90 dBm
    
    let color = "";
    let label = "";
    
    if (rssi >= -60) {
      color = "text-green-500";
      label = "Excellent";
    } else if (rssi >= -70) {
      color = "text-green-400";
      label = "Good";
    } else if (rssi >= -80) {
      color = "text-yellow-500";
      label = "Fair";
    } else {
      color = "text-red-500";
      label = "Poor";
    }
    
    return (
      <div className="flex items-center">
        <BarChart size={16} className={`${color} mr-1`} />
        <span className={`text-sm ${color}`}>
          {label} ({rssi} dBm)
        </span>
      </div>
    );
  };

  // ==================================================================================
  // UI RENDERING: Functions for rendering the UI screens
  // ==================================================================================

  /**
   * Render the header bar
   * @return {JSX.Element} The header bar
   */
  const renderHeader = () => {
    let title = 'Smart Playground';
    let backAction = null;
    
    if (activeScreen === 'ruleEditor') {
      title = currentRule ? `Edit Rule: ${currentRule.name}` : 'Create Rule';
      backAction = () => setActiveScreen('modules');
    } else if (activeScreen === 'deployment') {
      title = 'Deploy Rules';
      backAction = () => setActiveScreen('modules');
    }
    
    return (
      <div className="bg-blue-600 text-white p-4 flex items-center justify-between shadow-md">
        <div className="flex items-center">
          {backAction && (
            <button onClick={backAction} className="mr-3 p-1 hover:bg-blue-700 rounded-full">
              <ChevronLeft size={24} />
            </button>
          )}
          <h1 className="text-xl font-bold">{title}</h1>
        </div>
        <div className="flex items-center space-x-3">
          {activeScreen === 'modules' && (
            <button 
              onClick={refreshModules}
              className="p-2 hover:bg-blue-700 rounded-full"
              title="Refresh Modules"
            >
              <RefreshCw size={20} />
            </button>
          )}
          <button className="p-2 hover:bg-blue-700 rounded-full" title="Help">
            <HelpCircle size={20} />
          </button>
        </div>
      </div>
    );
  };

  /**
   * Render the modules list screen
   * @return {JSX.Element} The modules list screen
   */
  const renderModules = () => {
    return (
      <div className="flex flex-col h-full bg-gray-50">
        <div className="p-4 flex justify-between items-center border-b bg-white">
          <h2 className="text-lg font-semibold">Module Management</h2>
          <div className="flex space-x-2">
            <button 
              className="px-3 py-2 rounded-lg border border-gray-300 text-gray-700 flex items-center hover:bg-gray-100"
              onClick={() => {
                const newModules = modules.map(module => ({...module, selected: true}));
                setModules(newModules);
              }}
            >
              <span>Select All</span>
            </button>
            <button 
              className="px-3 py-2 rounded-lg border border-gray-300 text-gray-700 flex items-center hover:bg-gray-100"
              onClick={() => {
                const newModules = modules.map(module => ({...module, selected: false}));
                setModules(newModules);
              }}
            >
              <span>Clear</span>
            </button>
          </div>
        </div>
        
        <div className="flex-1 overflow-auto p-4">
          {/* Module List */}
          <div className="grid grid-cols-1 gap-4 mb-4">
            {modules.map(module => (
              <div 
                key={module.id} 
                className={`border rounded-lg p-4 ${module.selected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'} ${!module.connected ? 'opacity-60' : ''}`}
                onClick={() => toggleModuleSelection(module.id)}
              >
                <div className="flex justify-between items-start">
                  <div className="flex items-center">
                    <div className={`w-4 h-4 rounded-full mr-3 ${module.selected ? 'bg-blue-500' : 'border border-gray-300'}`}></div>
                    <div>
                      <h3 className="font-semibold">{module.name}</h3>
                      <p className="text-sm text-gray-500 capitalize">{module.type} Module</p>
                      <p className="text-xs text-gray-400">{module.macAddress}</p>
                    </div>
                  </div>
                  <div className="flex flex-col items-end">
                    {/* Display RSSI instead of battery */}
                    <div className="mb-1">
                      {renderSignalStrength(module.rssi)}
                    </div>
                    {module.connected ? (
                      <span className="text-green-500 flex items-center text-xs">
                        <Wifi size={14} className="mr-1" />
                        Connected
                      </span>
                    ) : (
                      <span className="text-red-500 flex items-center text-xs">
                        <WifiOff size={14} className="mr-1" />
                        Disconnected
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
          
          {/* Rules List */}
          <div className="mt-6 space-y-4">
            <h3 className="font-semibold text-lg">Rules</h3>
            
            {rules.length > 0 ? (
              <div className="space-y-3">
                {rules.map(rule => (
                  <div key={rule.id} className="border rounded-lg p-4 bg-white">
                    <div className="flex justify-between items-center mb-2">
                      <h4 className="font-medium">{rule.name}</h4>
                      <div className="flex space-x-2">
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            editRule(rule);
                          }}
                          className="p-1.5 text-gray-600 hover:bg-gray-100 rounded-full"
                        >
                          <Edit size={16} />
                        </button>
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteRule(rule.id);
                          }}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded-full"
                        >
                          <Trash size={16} />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center text-sm">
                      <div className="bg-blue-50 px-2 py-1 rounded-md">
                        <span className="text-blue-700 font-medium">When:</span> {rule.source.type.replace(/_/g, ' ')}
                      </div>
                      <div className="mx-2">→</div>
                      <div className="bg-green-50 px-2 py-1 rounded-md">
                        <span className="text-green-700 font-medium">Then:</span> {rule.target.type.replace(/_/g, ' ')}
                      </div>
                    </div>
                    {rule.source.module_id !== "self" && (
                      <div className="mt-2 text-xs text-purple-600">
                        <span className="font-medium">Remote source:</span> {modules.find(m => m.macAddress === rule.source.module_id)?.name || rule.source.module_id}
                      </div>
                    )}
                    {rule.target.module_id !== "self" && (
                      <div className="mt-2 text-xs text-purple-600">
                        <span className="font-medium">Remote target:</span> {modules.find(m => m.macAddress === rule.target.module_id)?.name || rule.target.module_id}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="border rounded-lg p-6 bg-white text-center">
                <p className="text-gray-500">No rules created yet</p>
                <p className="text-sm text-gray-400 mt-1">Create a rule by clicking the button below</p>
              </div>
            )}
            
            {/* Action Buttons */}
            <div className="flex space-x-3 mt-6">
              <button 
                onClick={initNewRule}
                className="flex-1 py-3 bg-blue-600 text-white rounded-lg flex items-center justify-center hover:bg-blue-700"
              >
                <Plus size={18} className="mr-2" />
                Create New Rule
              </button>
              
              <button 
                onClick={deployRules}
                className={`flex-1 py-3 rounded-lg flex items-center justify-center ${rules.length > 0 ? 'bg-green-600 hover:bg-green-700 text-white' : 'bg-gray-200 text-gray-500 cursor-not-allowed'}`}
                disabled={rules.length === 0}
              >
                <Zap size={18} className="mr-2" />
                Deploy Rules
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  /**
   * Render the rule editor screen
   * @return {JSX.Element} The rule editor screen
   */
  const renderRuleEditor = () => {
    if (!currentRule) return null;
    
    // Helper function to get module names by MAC address
    const getModuleName = (macAddress) => {
      if (macAddress === "self") return "Self (Same Module)";
      const module = modules.find(m => m.macAddress === macAddress);
      return module ? module.name : macAddress;
    };
    
    return (
      <div className="flex flex-col h-full bg-gray-50">
        <div className="p-4 border-b bg-white">
          <input
            type="text"
            value={currentRule.name}
            onChange={handleRuleNameChange}
            className="w-full text-lg font-medium border-b border-dashed border-gray-300 pb-1 focus:outline-none focus:border-blue-500"
            placeholder="Rule Name"
          />
          
          {/* Remote Rule Mode Selector */}
          <div className="flex mt-3">
            <div className="flex space-x-3">
              <button 
                onClick={() => handleRemoteModeChange(false)}
                className={`px-3 py-1 rounded-md flex items-center text-sm ${!currentRule.remoteMode ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}
              >
                Local Rule
              </button>
              <button 
                onClick={() => handleRemoteModeChange(true, 'target')}
                className={`px-3 py-1 rounded-md flex items-center text-sm ${currentRule.remoteMode && currentRule.remoteRuleType === 'target' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-700'}`}
              >
                Remote Target
              </button>
              <button 
                onClick={() => handleRemoteModeChange(true, 'source')}
                className={`px-3 py-1 rounded-md flex items-center text-sm ${currentRule.remoteMode && currentRule.remoteRuleType === 'source' ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-700'}`}
              >
                Remote Source
              </button>
            </div>
          </div>
        </div>
        
        <div className="flex-1 overflow-auto p-4">
          {/* Remote Module Selection */}
          {currentRule.remoteMode && (
            <div className="bg-white rounded-lg border p-4 mb-4">
              <h3 className="font-semibold text-purple-700 flex items-center mb-4">
                <span className="bg-purple-100 text-purple-700 w-6 h-6 rounded-full flex items-center justify-center mr-2">R</span>
                {currentRule.remoteRuleType === 'target' ? 'TARGET MODULE' : 'SOURCE MODULE'}
              </h3>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Select {currentRule.remoteRuleType === 'target' ? 'Target' : 'Source'} Module
                </label>
                <select 
                  className="w-full border rounded-lg p-2"
                  value={currentRule.remoteRuleType === 'target' ? currentRule.target.module_id : currentRule.source.module_id}
                  onChange={(e) => handleRemoteModuleSelect(e.target.value, currentRule.remoteRuleType === 'source')}
                >
                  {/* Show all connected, selected modules */}
                  {modules
                    .filter(module => module.selected && module.connected)
                    .map(module => (
                      <option key={module.id} value={module.macAddress}>
                        {module.name} ({module.macAddress})
                      </option>
                    ))}
                </select>
              </div>
              
              {/* Explanation of the rule flow */}
              <div className="p-3 bg-gray-50 rounded-lg mb-3">
                <p className="text-sm text-gray-600">
                  {currentRule.remoteRuleType === 'target' ? (
                    <>This rule will trigger when any selected source module detects a {currentRule.source.type.toLowerCase().replace(/_/g, ' ')} and send the action to <strong>{getModuleName(currentRule.target.module_id)}</strong></>
                  ) : (
                    <>This rule will trigger when <strong>{getModuleName(currentRule.source.module_id)}</strong> detects a {currentRule.source.type.toLowerCase().replace(/_/g, ' ')} and send the action to all selected target modules</>
                  )}
                </p>
              </div>
            </div>
          )}
          
          {/* Trigger (When) Section */}
          <div className="bg-white rounded-lg border p-4 mb-4">
            <h3 className="font-semibold text-blue-700 flex items-center mb-4">
              <span className="bg-blue-100 text-blue-700 w-6 h-6 rounded-full flex items-center justify-center mr-2">1</span>
              WHEN (Trigger)
            </h3>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Trigger Type</label>
              <select 
                className="w-full border rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                value={currentRule.source.type}
                onChange={handleSourceTypeChange}
              >
                <optgroup label="Button Inputs">
                  <option value={InputTypes.BUTTON_PRESS}>Button Press</option>
                  <option value={InputTypes.BUTTON_RELEASE}>Button Release</option>
                  <option value={InputTypes.BUTTON_HOLD}>Button Hold</option>
                  <option value={InputTypes.BUTTON_DOUBLE_TAP}>Double Tap</option>
                </optgroup>
                <optgroup label="Accelerometer Inputs">
                  <option value={InputTypes.ORIENTATION}>Orientation</option>
                  <option value={InputTypes.SHAKE}>Shake</option>
                  <option value={InputTypes.MOVEMENT}>Movement</option>
                </optgroup>
              </select>
            </div>
            
            {/* Orientation parameters */}
            {currentRule.source.type === InputTypes.ORIENTATION && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Orientation</label>
                <div className="grid grid-cols-2 gap-2">
                  {['UP', 'DOWN', 'LEFT', 'RIGHT', 'FRONT', 'BACK'].map((orientation) => (
                    <div 
                      key={orientation}
                      className={`border p-3 rounded-lg cursor-pointer flex items-center ${currentRule.source.parameters.orientation === orientation ? 'bg-blue-50 border-blue-500' : 'hover:bg-gray-50'}`}
                      onClick={() => setCurrentRule({
                        ...currentRule,
                        source: {
                          ...currentRule.source,
                          parameters: { orientation }
                        }
                      })}
                    >
                      <RotateCw size={16} className="mr-2" />
                      {orientation}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Button Hold parameters */}
            {currentRule.source.type === InputTypes.BUTTON_HOLD && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Hold Duration (ms)</label>
                <div className="flex items-center">
                  <input 
                    type="range" 
                    min="100" 
                    max="3000" 
                    step="100"
                    value={currentRule.source.parameters.duration_ms || 500} 
                    onChange={(e) => setCurrentRule({
                      ...currentRule,
                      source: {
                        ...currentRule.source,
                        parameters: { 
                          ...currentRule.source.parameters,
                          duration_ms: parseInt(e.target.value) 
                        }
                      }
                    })}
                    className="flex-1"
                  />
                  <div className="ml-2 text-sm">{(currentRule.source.parameters.duration_ms || 500)/1000}s</div>
                </div>
              </div>
            )}
            
            {/* Shake parameters */}
            {currentRule.source.type === InputTypes.SHAKE && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Shake Intensity</label>
                <div className="flex items-center">
                  <input 
                    type="range" 
                    min="10" 
                    max="100" 
                    step="10"
                    value={currentRule.source.parameters.intensity || 50} 
                    onChange={(e) => setCurrentRule({
                      ...currentRule,
                      source: {
                        ...currentRule.source,
                        parameters: { 
                          ...currentRule.source.parameters,
                          intensity: parseInt(e.target.value) 
                        }
                      }
                    })}
                    className="flex-1"
                  />
                  <div className="ml-2 text-sm">{currentRule.source.parameters.intensity || 50}%</div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {[20, 50, 80].map((intensity) => (
                    <div 
                      key={intensity}
                      className={`border p-2 rounded-lg cursor-pointer text-center ${currentRule.source.parameters.intensity === intensity ? 'bg-blue-50 border-blue-500' : 'hover:bg-gray-50'}`}
                      onClick={() => setCurrentRule({
                        ...currentRule,
                        source: {
                          ...currentRule.source,
                          parameters: { 
                            ...currentRule.source.parameters,
                            intensity
                          }
                        }
                      })}
                    >
                      {intensity < 30 ? 'Gentle' : intensity < 70 ? 'Medium' : 'Strong'}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Movement parameters */}
            {currentRule.source.type === InputTypes.MOVEMENT && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Movement Sensitivity</label>
                <div className="flex items-center">
                  <input 
                    type="range" 
                    min="10" 
                    max="100" 
                    step="10"
                    value={currentRule.source.parameters.sensitivity || 50} 
                    onChange={(e) => setCurrentRule({
                      ...currentRule,
                      source: {
                        ...currentRule.source,
                        parameters: { 
                          ...currentRule.source.parameters,
                          sensitivity: parseInt(e.target.value) 
                        }
                      }
                    })}
                    className="flex-1"
                  />
                  <div className="ml-2 text-sm">{currentRule.source.parameters.sensitivity || 50}%</div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {[20, 50, 80].map((sensitivity) => (
                    <div 
                      key={sensitivity}
                      className={`border p-2 rounded-lg cursor-pointer text-center ${currentRule.source.parameters.sensitivity === sensitivity ? 'bg-blue-50 border-blue-500' : 'hover:bg-gray-50'}`}
                      onClick={() => setCurrentRule({
                        ...currentRule,
                        source: {
                          ...currentRule.source,
                          parameters: { 
                            ...currentRule.source.parameters,
                            sensitivity
                          }
                        }
                      })}
                    >
                      {sensitivity < 30 ? 'Low' : sensitivity < 70 ? 'Medium' : 'High'}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          {/* Action (Then) Section */}
          <div className="bg-white rounded-lg border p-4 mb-4">
            <h3 className="font-semibold text-green-700 flex items-center mb-4">
              <span className="bg-green-100 text-green-700 w-6 h-6 rounded-full flex items-center justify-center mr-2">2</span>
              THEN (Action)
            </h3>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Action Type</label>
              <select 
                className="w-full border rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500"
                value={currentRule.target.type}
                onChange={handleTargetTypeChange}
              >
                <optgroup label="LED Outputs">
                  <option value={OutputTypes.LED_COLOR}>LED Color</option>
                  <option value={OutputTypes.LED_BRIGHTNESS}>LED Brightness</option>
                  <option value={OutputTypes.LED_PATTERN}>LED Pattern</option>
                  <option value={OutputTypes.LED_COUNT}>LED Count</option>
                </optgroup>
                <optgroup label="Vibration Outputs">
                  <option value={OutputTypes.VIBRATION}>Vibration</option>
                  <option value={OutputTypes.VIBRATION_PATTERN}>Vibration Pattern</option>
                </optgroup>
                <optgroup label="Buzzer Outputs">
                  <option value={OutputTypes.BUZZER_NOTE}>Buzzer Note</option>
                  <option value={OutputTypes.BUZZER_PATTERN}>Buzzer Pattern</option>
                </optgroup>
              </select>
            </div>
            
            {/* LED Color parameters */}
            {currentRule.target.type === OutputTypes.LED_COLOR && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Color</label>
                <div className="flex items-center mb-2">
                  <input 
                    type="range" 
                    min="0" 
                    max="360" 
                    value={currentRule.target.parameters.hue || 0} 
                    onChange={(e) => handleTargetParameterChange('hue', parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="ml-4 text-sm">{currentRule.target.parameters.hue || 0}°</div>
                </div>
                <div className="grid grid-cols-6 gap-2 mt-4">
                  {[0, 30, 60, 120, 180, 240, 270, 300, 330].map((hue) => (
                    <div 
                      key={hue}
                      className={`h-10 rounded-lg cursor-pointer border ${currentRule.target.parameters.hue === hue ? 'border-2 border-blue-500' : 'border-gray-200'}`}
                      style={{ backgroundColor: `hsl(${hue}, 100%, 50%)` }}
                      onClick={() => handleTargetParameterChange('hue', hue)}
                    ></div>
                  ))}
                </div>
                
                <div className="mt-4 border rounded-lg p-4 flex items-center justify-center bg-gray-50">
                  <div className="w-16 h-16 rounded-full flex items-center justify-center shadow-md" style={{ backgroundColor: `hsl(${currentRule.target.parameters.hue || 0}, 100%, 50%)` }}>
                    <Palette size={24} className="text-white" />
                  </div>
                </div>
              </div>
            )}
            
            {/* LED Brightness parameters */}
            {currentRule.target.type === OutputTypes.LED_BRIGHTNESS && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Brightness</label>
                <div className="flex items-center mb-2">
                  <input 
                    type="range" 
                    min="0" 
                    max="255" 
                    value={currentRule.target.parameters.brightness || 127} 
                    onChange={(e) => handleTargetParameterChange('brightness', parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="ml-4 text-sm">{Math.round(((currentRule.target.parameters.brightness || 127) / 255) * 100)}%</div>
                </div>
                
                <div className="grid grid-cols-5 gap-2 mt-4">
                  {[0, 63, 127, 191, 255].map((brightness) => (
                    <div 
                      key={brightness}
                      className={`h-12 rounded-lg cursor-pointer border flex items-center justify-center ${currentRule.target.parameters.brightness === brightness ? 'border-2 border-blue-500' : 'border-gray-200'}`}
                      style={{ backgroundColor: `rgba(100, 100, 100, ${brightness/255})` }}
                      onClick={() => handleTargetParameterChange('brightness', brightness)}
                    >
                      {Math.round((brightness / 255) * 100)}%
                    </div>
                  ))}
                </div>
                
                <div className="mt-4 border rounded-lg p-4 flex items-center justify-center bg-gray-50">
                  <div 
                    className="w-16 h-16 rounded-full flex items-center justify-center shadow-md bg-blue-500"
                    style={{ opacity: (currentRule.target.parameters.brightness || 127) / 255 }}
                  >
                    <CircleDot size={24} className="text-white" />
                  </div>
                </div>
              </div>
            )}
            
            {/* LED Count parameters */}
            {currentRule.target.type === OutputTypes.LED_COUNT && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">LED Count</label>
                <div className="flex items-center mb-2">
                  <input 
                    type="range" 
                    min="0" 
                    max="12" 
                    value={currentRule.target.parameters.count || 6} 
                    onChange={(e) => handleTargetParameterChange('count', parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="ml-4 text-sm">{currentRule.target.parameters.count || 6} LEDs</div>
                </div>
                
                <div className="grid grid-cols-4 gap-2 mt-4">
                  {[1, 3, 6, 12].map((count) => (
                    <div 
                      key={count}
                      className={`rounded-lg cursor-pointer border p-2 flex items-center justify-center ${currentRule.target.parameters.count === count ? 'bg-blue-50 border-blue-500' : 'border-gray-200'}`}
                      onClick={() => handleTargetParameterChange('count', count)}
                    >
                      {count} {count === 1 ? 'LED' : 'LEDs'}
                    </div>
                  ))}
                </div>
                
                {/* Visual representation of the LED ring */}
                <div className="mt-4 border rounded-lg p-4 flex items-center justify-center bg-gray-50">
                  <div className="relative w-24 h-24">
                    {Array.from({ length: 12 }).map((_, i) => (
                      <div 
                        key={i}
                        className="absolute w-4 h-4 rounded-full transform -translate-x-1/2 -translate-y-1/2"
                        style={{ 
                          left: '50%', 
                          top: '50%', 
                          backgroundColor: i < (currentRule.target.parameters.count || 6) ? 'rgb(59, 130, 246)' : 'rgb(229, 231, 235)',
                          transform: `translate(${Math.cos(i * Math.PI / 6) * 40}px, ${Math.sin(i * Math.PI / 6) * 40}px)`
                        }}
                      ></div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            
            {/* LED Pattern parameters */}
            {currentRule.target.type === OutputTypes.LED_PATTERN && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Pattern</label>
                <div className="grid grid-cols-2 gap-2">
                  {['SOLID', 'BLINK', 'BREATHE', 'CHASE', 'RAINBOW', 'ALTERNATE'].map((pattern) => (
                    <div 
                      key={pattern}
                      className={`border p-3 rounded-lg cursor-pointer flex items-center ${currentRule.target.parameters.pattern === pattern ? 'bg-blue-50 border-blue-500' : 'hover:bg-gray-50'}`}
                      onClick={() => handleTargetParameterChange('pattern', pattern)}
                    >
                      <Circle size={16} className="mr-2" />
                      {pattern}
                    </div>
                  ))}
                </div>
                
                {currentRule.target.parameters.pattern && (
                  <div>
                    <div className="flex items-center mt-4">
                      <label className="text-sm font-medium text-gray-700 mr-2">Speed:</label>
                      <input 
                        type="range" 
                        min="1" 
                        max="10" 
                        step="1"
                        value={currentRule.target.parameters.speed || 5} 
                        onChange={(e) => handleTargetParameterChange('speed', parseInt(e.target.value))}
                        className="flex-1"
                      />
                      <div className="ml-2 text-sm">{currentRule.target.parameters.speed || 5}/10</div>
                    </div>
                    
                    <div className="flex items-center mt-4">
                      <label className="text-sm font-medium text-gray-700 mr-2">Duration:</label>
                      <input 
                        type="range" 
                        min="500" 
                        max="5000" 
                        step="500"
                        value={currentRule.target.parameters.duration_ms || 1000} 
                        onChange={(e) => handleTargetParameterChange('duration_ms', parseInt(e.target.value))}
                        className="flex-1"
                      />
                      <div className="ml-2 text-sm">{(currentRule.target.parameters.duration_ms || 1000)/1000}s</div>
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {/* Buzzer Note parameters */}
            {currentRule.target.type === OutputTypes.BUZZER_NOTE && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Note</label>
                <div className="grid grid-cols-2 gap-2">
                  {['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5'].map((note) => (
                    <div 
                      key={note}
                      className={`border p-3 rounded-lg cursor-pointer flex items-center ${currentRule.target.parameters.note === note ? 'bg-blue-50 border-blue-500' : 'hover:bg-gray-50'}`}
                      onClick={() => handleTargetParameterChange('note', note)}
                    >
                      <Volume2 size={16} className="mr-2" />
                      {note}
                    </div>
                  ))}
                </div>
                
                <div className="flex items-center mt-4">
                  <label className="text-sm font-medium text-gray-700 mr-2">Duration:</label>
                  <input 
                    type="range" 
                    min="100" 
                    max="2000" 
                    step="100"
                    value={currentRule.target.parameters.duration_ms || 500} 
                    onChange={(e) => handleTargetParameterChange('duration_ms', parseInt(e.target.value))}
                    className="flex-1"
                  />
                  <div className="ml-2 text-sm">{(currentRule.target.parameters.duration_ms || 500)/1000}s</div>
                </div>
              </div>
            )}
            
            {/* Buzzer Pattern parameters */}
            {currentRule.target.type === OutputTypes.BUZZER_PATTERN && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Pattern</label>
                <div className="grid grid-cols-2 gap-2">
                  {['ASCENDING', 'DESCENDING', 'DOUBLE', 'TRIPLE', 'SOS', 'DING', 'ATTENTION'].map((pattern) => (
                    <div 
                      key={pattern}
                      className={`border p-3 rounded-lg cursor-pointer flex items-center ${currentRule.target.parameters.pattern === pattern ? 'bg-blue-50 border-blue-500' : 'hover:bg-gray-50'}`}
                      onClick={() => handleTargetParameterChange('pattern', pattern)}
                    >
                      <Volume2 size={16} className="mr-2" />
                      {pattern}
                    </div>
                  ))}
                </div>
                
                {currentRule.target.parameters.pattern && (
                  <div className="flex items-center mt-4">
                    <label className="text-sm font-medium text-gray-700 mr-2">Base Frequency:</label>
                    <input 
                      type="range" 
                      min="220" 
                      max="880" 
                      step="110"
                      value={currentRule.target.parameters.base_frequency || 440} 
                      onChange={(e) => handleTargetParameterChange('base_frequency', parseInt(e.target.value))}
                      className="flex-1"
                    />
                    <div className="ml-2 text-sm">{currentRule.target.parameters.base_frequency || 440} Hz</div>
                  </div>
                )}
              </div>
            )}
            
            {/* Vibration parameters */}
            {currentRule.target.type === OutputTypes.VIBRATION && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Duration</label>
                <div className="flex items-center">
                  <input 
                    type="range" 
                    min="100" 
                    max="2000" 
                    step="100"
                    value={currentRule.target.parameters.duration_ms || 500} 
                    onChange={(e) => handleTargetParameterChange('duration_ms', parseInt(e.target.value))}
                    className="flex-1"
                  />
                  <div className="ml-2 text-sm">{(currentRule.target.parameters.duration_ms || 500)/1000}s</div>
                </div>
                
                <div className="grid grid-cols-3 gap-2 mt-4">
                  {[200, 500, 1000].map((duration) => (
                    <div 
                      key={duration}
                      className={`border p-2 rounded-lg cursor-pointer text-center ${currentRule.target.parameters.duration_ms === duration ? 'bg-blue-50 border-blue-500' : 'hover:bg-gray-50'}`}
                      onClick={() => handleTargetParameterChange('duration_ms', duration)}
                    >
                      {duration < 300 ? 'Short' : duration < 800 ? 'Medium' : 'Long'}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Vibration Pattern parameters */}
            {currentRule.target.type === OutputTypes.VIBRATION_PATTERN && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Pattern</label>
                <div className="grid grid-cols-2 gap-2">
                  {['CONTINUOUS', 'PULSE', 'DOUBLE', 'TRIPLE', 'LONG_SHORT'].map((pattern) => (
                    <div 
                      key={pattern}
                      className={`border p-3 rounded-lg cursor-pointer flex items-center ${currentRule.target.parameters.pattern === pattern ? 'bg-blue-50 border-blue-500' : 'hover:bg-gray-50'}`}
                      onClick={() => handleTargetParameterChange('pattern', pattern)}
                    >
                      <Vibrate size={16} className="mr-2" />
                      {pattern.replace(/_/g, ' ')}
                    </div>
                  ))}
                </div>
                
                <div className="flex items-center mt-4">
                  <label className="text-sm font-medium text-gray-700 mr-2">Repeat:</label>
                  <input 
                    type="range" 
                    min="1" 
                    max="5" 
                    step="1"
                    value={currentRule.target.parameters.repeat || 1} 
                    onChange={(e) => handleTargetParameterChange('repeat', parseInt(e.target.value))}
                    className="flex-1"
                  />
                  <div className="ml-2 text-sm">{currentRule.target.parameters.repeat || 1}x</div>
                </div>
              </div>
            )}
          </div>
          
          {/* Test & Save Section */}
          <div className="bg-white rounded-lg border p-4 mb-4">
            <h3 className="font-semibold text-purple-700 flex items-center mb-4">
              <span className="bg-purple-100 text-purple-700 w-6 h-6 rounded-full flex items-center justify-center mr-2">3</span>
              TEST & SAVE
            </h3>
            
            <div className="mb-4 text-center">
              <p className="text-sm text-gray-600 mb-3">Test this rule on selected modules before saving</p>
              <button 
                onClick={testRule}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 mb-4"
              >
                Test Rule Now
              </button>
              
              <div className="border-t pt-4">
                <button 
                  onClick={saveRule}
                  className="w-full py-3 bg-green-600 text-white rounded-lg flex items-center justify-center hover:bg-green-700"
                >
                  <Save size={18} className="mr-2" />
                  Save Rule
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  /**
   * Render the deployment screen
   * @return {JSX.Element} The deployment screen
   * @implementation This is a placeholder visualization of the deployment process
   * In a real implementation:
   * - This would show real-time progress from the API
   * - It would handle errors and retries
   * - It would provide more detailed status updates
   */
  const renderDeployment = () => {
    const selectedModules = modules.filter(module => module.selected && module.connected);
    
    return (
      <div className="flex flex-col h-full bg-gray-50">
        <div className="p-4 border-b bg-white">
          <h2 className="text-lg font-semibold">Deploying Rules</h2>
          <p className="text-sm text-gray-600 mt-1">Sending rules to selected modules</p>
        </div>
        
        <div className="flex-1 overflow-auto p-4">
          <div className="bg-white rounded-lg border p-4 mb-4">
            <h3 className="font-medium mb-3">Deployment Progress</h3>
            
            <div className="mb-6">
              <div className="flex justify-between mb-1 text-sm">
                <span>Overall Progress</span>
                <span>75%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div className="bg-green-600 h-2.5 rounded-full" style={{ width: '75%' }}></div>
              </div>
            </div>
            
            <div className="space-y-4">
              {selectedModules.map((module, index) => (
                <div key={module.id} className="border rounded-lg p-3">
                  <div className="flex justify-between items-center mb-2">
                    <div className="flex items-center">
                      {index < 2 ? (
                        <div className="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center mr-2">
                          <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                        </div>
                      ) : index === 2 ? (
                        <div className="w-5 h-5 bg-blue-100 rounded-full flex items-center justify-center mr-2 animate-pulse">
                          <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                        </div>
                      ) : (
                        <div className="w-5 h-5 bg-gray-100 rounded-full flex items-center justify-center mr-2">
                          <div className="w-3 h-3 bg-gray-300 rounded-full"></div>
                        </div>
                      )}
                      <span className="font-medium">{module.name}</span>
                    </div>
                    <div className="text-sm">
                      {index < 2 ? (
                        <span className="text-green-600">Completed</span>
                      ) : index === 2 ? (
                        <span className="text-blue-600">In Progress...</span>
                      ) : (
                        <span className="text-gray-400">Waiting</span>
                      )}
                    </div>
                  </div>
                  
                  {index < 2 && (
                    <div className="text-sm text-gray-600">
                      Deployed {rules.length} rules successfully
                    </div>
                  )}
                  
                  {index === 2 && (
                    <div>
                      <div className="flex justify-between mb-1 text-xs">
                        <span>Deploying rules...</span>
                        <span>45%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1.5">
                        <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: '45%' }}></div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
          
          <button 
            onClick={completeDeployment}
            className="w-full py-3 bg-green-600 text-white rounded-lg flex items-center justify-center hover:bg-green-700"
          >
            <Zap size={18} className="mr-2" />
            Complete Deployment
          </button>
        </div>
      </div>
    );
  };

  /**
   * Render notification toast
   * @return {JSX.Element|null} The notification component or null if hidden
   */
  const renderNotification = () => {
    if (!showNotification) return null;
    
    let bgColor = 'bg-blue-500';
    let icon = <AlertCircle size={20} />;
    
    if (notification.type === 'success') {
      bgColor = 'bg-green-500';
      icon = <Zap size={20} />;
    } else if (notification.type === 'error') {
      bgColor = 'bg-red-500';
      icon = <ZapOff size={20} />;
    } else if (notification.type === 'info') {
      bgColor = 'bg-blue-500';
      icon = <AlertCircle size={20} />;
    }
    
    return (
      <div className={`fixed bottom-5 left-1/2 transform -translate-x-1/2 ${bgColor} text-white px-4 py-3 rounded-lg shadow-lg flex items-center max-w-md`}>
        <div className="mr-3">{icon}</div>
        <div>{notification.message}</div>
        <button 
          onClick={() => setShowNotification(false)}
          className="ml-3 text-white/80 hover:text-white"
        >
          <X size={16} />
        </button>
      </div>
    );
  };

  /**
   * Main render function
   * @return {JSX.Element} The main application component
   */
  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {renderHeader()}
      
      <div className="flex-1 overflow-hidden">
        {activeScreen === 'modules' && renderModules()}
        {activeScreen === 'ruleEditor' && renderRuleEditor()}
        {activeScreen === 'deployment' && renderDeployment()}
      </div>
      
      <div className="bg-gray-800 text-white p-2 flex justify-center items-center space-x-6">
        <button 
          className={`p-2 rounded-lg flex flex-col items-center ${activeScreen === 'modules' ? 'bg-gray-700' : ''}`}
          onClick={() => setActiveScreen('modules')}
        >
          <Activity size={20} />
          <span className="text-xs mt-1">Modules</span>
        </button>
        
        <button 
          className={`p-2 rounded-lg flex flex-col items-center`}
          onClick={refreshModules}
        >
          <RefreshCw size={20} />
          <span className="text-xs mt-1">Refresh</span>
        </button>
        
        <button className="p-2 rounded-lg flex flex-col items-center">
          <Sliders size={20} />
          <span className="text-xs mt-1">Settings</span>
        </button>
      </div>
      
      {renderNotification()}
    </div>
  );
};

// ==================================================================================
// IMPLEMENTATION REQUIREMENTS FOR WORKING PROTOTYPE
// ==================================================================================

/**
 * TO IMPLEMENT A WORKING PROTOTYPE:
 * 
 * 1. Backend API Development
 *    - Create a Node.js Express server (or similar) that acts as the Hub API
 *    - Implement endpoints for:
 *      - GET /modules - List all modules
 *      - POST /modules/scan - Scan for new modules
 *      - GET /rules - List all rules
 *      - POST /rules - Create a new rule
 *      - PUT /rules/:id - Update a rule
 *      - DELETE /rules/:id - Delete a rule
 *      - POST /deploy - Deploy rules to modules
 *      - GET /status - Get deployment status
 *      - POST /test - Test a rule
 *    - The API would communicate with the ESP32 Hub using a serial connection
 *      or by hosting the API directly on the ESP32
 * 
 * 2. Hub Software Development
 *    - Implement a service to manage the ESP-NOW communication
 *    - Create methods to convert between API requests and ESP-NOW messages
 *    - Implement a rule deployment protocol that sends rules to modules
 *    - Set up status tracking for modules (RSSI, connectivity, etc.)
 * 
 * 3. Module Firmware Updates
 *    - Ensure the module firmware has the proper rule engine implementation
 *    - Add support for remote rule deployment via ESP-NOW
 *    - Implement all input and output types
 *    - Set up status reporting back to the hub
 * 
 * 4. Frontend Improvements
 *    - Replace the mock data with real API calls
 *    - Add proper error handling for all operations
 *    - Implement real-time updates using WebSockets or Server-Sent Events
 *    - Add authentication for teacher accounts
 *    - Create activity templates and library
 *    - Add detailed module configuration options
 * 
 * 5. Testing & Deployment
 *    - Test with actual hardware
 *    - Create a deployment process for the hub software
 *    - Set up firmware update mechanisms for modules
 *    - Document the system for teachers and administrators
 */

export default SmartPlaygroundMVP;
