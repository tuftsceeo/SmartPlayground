import React, { useState } from 'react';
import { Send, Radio, Smartphone, Box, ArrowLeft, RefreshCw, Wifi, WifiOff, Battery, BatteryLow, BatteryMedium, BatteryFull, Power, PowerOff, X, Pencil, CircleDot, Pause, Sparkles, Bluetooth, BluetoothOff, Settings } from 'lucide-react';

export default function PlaygroundControlApp() {
  const [range, setRange] = useState(2); // Index for range options
  const [messageHistory, setMessageHistory] = useState([
    { 
      id: 1, 
      command: 'Unpause', 
      modules: ['M-A3F821', 'M-B4C932'], 
      timestamp: new Date(Date.now() - 15 * 60000), // 15 minutes ago
      displayTime: '2:15 PM'
    },
    { 
      id: 2, 
      command: 'Win', 
      modules: ['M-A3F821', 'M-B4C932', 'E-D6E154'], 
      timestamp: new Date(Date.now() - 3 * 60000), // 3 minutes ago
      displayTime: '2:18 PM'
    }
  ]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [selectedModules, setSelectedModules] = useState([]);
  const [showContactDetails, setShowContactDetails] = useState(false);
  const [showStickers, setShowStickers] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [viewingMessage, setViewingMessage] = useState(null);
  const [editingModule, setEditingModule] = useState(null);
  const [moduleNicknames, setModuleNicknames] = useState({});
  const [isBluetoothConnected, setIsBluetoothConnected] = useState(false); // Mock BLE connection state
  const [showSettings, setShowSettings] = useState(false);
  const [showConnectionWarning, setShowConnectionWarning] = useState(false);
  const [flashMessageBox, setFlashMessageBox] = useState(false);

  // Range options with RSSI cutoff values
  const rangeOptions = [
    { label: 'Here', rssi: -30 },
    { label: 'Near', rssi: -45 },
    { label: 'Close', rssi: -60 },
    { label: 'Distant', rssi: -75 },
    { label: 'Far', rssi: -90 },
    { label: 'All', rssi: -999 } // All modules
  ];

  // Simulated modules with RSSI values instead of distances
  const allModules = [
    { id: 'M-A3F821', name: 'M-A3F821', type: 'module', rssi: -25, signal: 3, battery: 'full' },
    { id: 'M-B4C932', name: 'M-B4C932', type: 'module', rssi: -40, signal: 3, battery: 'high' },
    { id: 'M-C5D043', name: 'M-C5D043', type: 'module', rssi: -58, signal: 2, battery: 'medium' },
    { id: 'E-D6E154', name: 'E-D6E154', type: 'extension', rssi: -48, signal: 2, battery: 'high' },
    { id: 'E-E7F265', name: 'E-E7F265', type: 'extension', rssi: -78, signal: 1, battery: 'low' },
    { id: 'B-F8G376', name: 'B-F8G376', type: 'button', rssi: -85, signal: 1, battery: 'medium' },
  ];

  const currentRangeOption = rangeOptions[range];
  const availableModules = isBluetoothConnected 
    ? allModules.filter(m => m.rssi >= currentRangeOption.rssi)
    : []; // No devices available when Bluetooth disconnected

  const commands = [
    { id: 'unpause', label: 'Unpause', bgColor: '#7eb09b', icon: 'power', textColor: 'white' },
    { id: 'pause', label: 'Pause', bgColor: '#d4a574', icon: 'pause', textColor: 'white' },
    { id: 'win', label: 'Win', bgColor: '#b084cc', icon: 'rainbow', textColor: 'white' },
    { id: 'game1', label: 'Game 1', bgColor: '#658ea9', icon: '1', textColor: 'white' },
    { id: 'game2', label: 'Game 2', bgColor: '#d7a449', icon: '2', textColor: 'white' },
    { id: 'off', label: 'Off', bgColor: '#e98973', icon: 'poweroff', textColor: 'white' }
  ];

  const handleCommandClick = (command) => {
    setCurrentMessage(command.label);
  };

  const handleSendMessage = () => {
    // Bluetooth not connected - always show warning first
    if (!isBluetoothConnected) {
      setShowConnectionWarning(true);
      return;
    }
    
    // No message selected - provide feedback
    if (!currentMessage) {
      if (!showStickers) {
        // Drawer closed - open it
        setShowStickers(true);
      } else {
        // Drawer already open - flash the message box
        setFlashMessageBox(true);
        setTimeout(() => setFlashMessageBox(false), 500);
      }
      return;
    }
    
    // Send message
    if (availableModules.length > 0) {
      const now = new Date();
      const newMessage = {
        id: Date.now(),
        command: currentMessage,
        modules: availableModules.map(m => m.name),
        timestamp: now,
        displayTime: now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
      };
      setMessageHistory([...messageHistory, newMessage]);
      setCurrentMessage('');
      setShowStickers(false);
    }
  };

  const handleRepeatMessage = (message) => {
    setCurrentMessage(message.command);
    setShowStickers(true);
  };

  const handleViewMessage = (message) => {
    setViewingMessage(message);
  };

  const handleBluetoothToggle = () => {
    // Mock BLE connection toggle
    setIsBluetoothConnected(!isBluetoothConnected);
  };

  const getRelativeTime = (timestamp) => {
    const now = new Date();
    const diffMs = now - timestamp;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
    
    const diffHours = Math.round(diffMins / 60);
    return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  };

  const getRecipientIcons = (modules) => {
    const moduleCount = modules.filter(m => m.startsWith('Module') || m.startsWith('M-')).length;
    const extensionCount = modules.filter(m => m.startsWith('Extension') || m.startsWith('E-')).length;
    const buttonCount = modules.filter(m => m.startsWith('B-')).length;
    
    return (
      <div className="flex items-center gap-1">
        {moduleCount > 0 && (
          <div className="flex items-center gap-0.5">
            <div className="w-4 h-4 rounded-full bg-gray-500 flex items-center justify-center">
              <Smartphone className="w-2.5 h-2.5 text-white" />
            </div>
            <span className="text-xs">×{moduleCount}</span>
          </div>
        )}
        {extensionCount > 0 && (
          <div className="flex items-center gap-0.5">
            <div className="w-4 h-4 rounded-full bg-gray-600 flex items-center justify-center">
              <Box className="w-2.5 h-2.5 text-white" />
            </div>
            <span className="text-xs">×{extensionCount}</span>
          </div>
        )}
        {buttonCount > 0 && (
          <div className="flex items-center gap-0.5">
            <div className="w-4 h-4 rounded-full bg-gray-500 flex items-center justify-center">
              <CircleDot className="w-2.5 h-2.5 text-white" />
            </div>
            <span className="text-xs">×{buttonCount}</span>
          </div>
        )}
      </div>
    );
  };

  const getDisplayName = (moduleId) => {
    return moduleNicknames[moduleId] || moduleId;
  };

  const handleSaveNickname = (moduleId, nickname) => {
    setModuleNicknames(prev => ({
      ...prev,
      [moduleId]: nickname.trim() || undefined
    }));
    setEditingModule(null);
  };

  const handleRecipientsClick = () => {
    setShowContactDetails(true);
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    // Simulate ping-echo refresh
    setTimeout(() => {
      setIsRefreshing(false);
    }, 1000);
  };

  const handleMessageInputClick = () => {
    if (!showStickers) {
      setShowStickers(true);
    }
  };

  const handleClickAway = (e) => {
    // Close stickers when clicking outside the command palette area
    if (showStickers && !e.target.closest('.command-palette') && !e.target.closest('.message-input-area')) {
      setShowStickers(false);
    }
  };

  const handleClearMessage = () => {
    setCurrentMessage('');
    setShowStickers(false);
  };

  const getCommandIcon = (commandLabel) => {
    const command = commands.find(c => c.label === commandLabel);
    if (!command) return null;
    
    return (
      <div 
        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: command.bgColor }}
      >
        {command.icon === 'power' && <Power className="w-4 h-4 text-white" />}
        {command.icon === 'poweroff' && <PowerOff className="w-4 h-4 text-white" />}
        {command.icon === 'pause' && <Pause className="w-4 h-4 text-white" />}
        {command.icon === 'rainbow' && <Sparkles className="w-4 h-4 text-white" />}
        {command.icon === '1' && <span className="text-lg font-bold text-white">1</span>}
        {command.icon === '2' && <span className="text-lg font-bold text-white">2</span>}
      </div>
    );
  };

  const getSignalIcon = (signal) => {
    if (signal === 0) return <WifiOff className="w-4 h-4 text-gray-400" />;
    const bars = [];
    for (let i = 0; i < 3; i++) {
      bars.push(
        <div
          key={i}
          className={`w-1 ${i === 0 ? 'h-2' : i === 1 ? 'h-3' : 'h-4'} rounded-sm ${
            i < signal ? 'bg-gray-600' : 'bg-gray-300'
          }`}
        />
      );
    }
    return <div className="flex items-end gap-0.5">{bars}</div>;
  };

  const getBatteryIcon = (battery) => {
    switch (battery) {
      case 'full':
        return <BatteryFull className="w-4 h-4 text-green-700" />;
      case 'high':
        return <BatteryMedium className="w-4 h-4 text-green-500" />;
      case 'medium':
        return <BatteryLow className="w-4 h-4 text-amber-600" />;
      case 'low':
        return <Battery className="w-4 h-4 text-red-700" />;
      default:
        return <Battery className="w-4 h-4 text-gray-400" />;
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto bg-white relative" onClick={handleClickAway}>
      {/* To: Section - Module Selection with integrated Bluetooth status */}
      <div className="bg-white border-b border-gray-200 px-4 py-2" onClick={handleRecipientsClick}>
        <div className="flex items-center gap-3 mb-2">
          <span className="text-gray-500 text-sm">To:</span>
          <span className="text-gray-700 text-sm font-medium">
            {availableModules.length} devices
          </span>
          <div className="flex items-center gap-1 ml-auto">
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleBluetoothToggle();
              }}
              className={`px-2 py-1 rounded-lg flex items-center gap-1.5 transition-colors ${
                isBluetoothConnected
                  ? 'hover:bg-gray-100'
                  : 'bg-amber-100 hover:bg-amber-200'
              }`}
              style={{ width: '130px' }}
              title={isBluetoothConnected ? "Disconnect Bluetooth" : "Connect Bluetooth"}
            >
              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                isBluetoothConnected ? 'bg-green-500 animate-pulse' : 'bg-amber-500'
              }`}></div>
              <span className={`text-xs flex-shrink-0 ${
                isBluetoothConnected ? 'text-gray-600' : 'text-amber-800 font-medium'
              }`}>
                {isBluetoothConnected ? 'Connected' : 'Disconnected'}
              </span>
              <div className="flex-1"></div>
              <Bluetooth className={`w-3.5 h-3.5 flex-shrink-0 ${
                isBluetoothConnected ? 'text-green-600' : 'text-amber-700'
              }`} />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowSettings(true);
              }}
              className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors flex-shrink-0"
              title="Settings"
            >
              <Settings className="w-4 h-4 text-gray-600" />
            </button>
          </div>
        </div>
        
        {/* Module Profile Images - Always show area to prevent layout shift */}
        <div className="flex items-center -space-x-2 mb-2" style={{ minHeight: '48px' }}>
          {availableModules.length === 0 ? (
            // Placeholder when no devices - clearly different from active devices
            <div className="w-12 h-12 rounded-full flex items-center justify-center border-2 border-gray-200 bg-white">
              <BluetoothOff className="w-6 h-6 text-gray-300" />
            </div>
          ) : (
            (() => {
              const maxVisible = 5;
              const visibleModules = availableModules.slice(0, maxVisible);
              const remainingModules = availableModules.slice(maxVisible);
              const remainingModuleCount = remainingModules.filter(m => m.type === 'module').length;
              const remainingExtensionCount = remainingModules.filter(m => m.type === 'extension').length;
              const remainingButtonCount = remainingModules.filter(m => m.type === 'button').length;
              
              return (
                <>
                  {visibleModules.map(module => (
                    <div
                      key={module.id}
                      className={`w-12 h-12 rounded-full flex items-center justify-center border-2 border-white ${
                        module.type === 'extension' ? 'bg-gray-600' : 'bg-gray-500'
                      }`}
                    >
                      {module.type === 'module' && <Smartphone className="w-6 h-6 text-white" />}
                      {module.type === 'extension' && <Box className="w-6 h-6 text-white" />}
                      {module.type === 'button' && <CircleDot className="w-6 h-6 text-white" />}
                    </div>
                  ))}
                  
                  {remainingModuleCount > 0 && (
                    <div className="w-12 h-12 rounded-full flex flex-col items-center justify-center bg-gray-500 border-2 border-white">
                      <Smartphone className="w-4 h-4 text-white" />
                      <span className="text-xs text-white font-medium">+{remainingModuleCount}</span>
                    </div>
                  )}
                  
                  {remainingExtensionCount > 0 && (
                    <div className="w-12 h-12 rounded-full flex flex-col items-center justify-center bg-gray-600 border-2 border-white">
                      <Box className="w-4 h-4 text-white" />
                      <span className="text-xs text-white font-medium">+{remainingExtensionCount}</span>
                    </div>
                  )}
                  
                  {remainingButtonCount > 0 && (
                    <div className="w-12 h-12 rounded-full flex flex-col items-center justify-center bg-gray-500 border-2 border-white">
                      <CircleDot className="w-4 h-4 text-white" />
                      <span className="text-xs text-white font-medium">+{remainingButtonCount}</span>
                    </div>
                  )}
                </>
              );
            })()
          )}
        </div>

        {/* Range Slider */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500 whitespace-nowrap">Near</span>
          <input
            type="range"
            min="0"
            max="5"
            step="1"
            value={range}
            onChange={(e) => setRange(parseInt(e.target.value))}
            onClick={(e) => e.stopPropagation()}
            className="flex-1 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-gray-600"
          />
          <span className="text-xs text-gray-500 whitespace-nowrap">Far</span>
          <span className="text-xs font-medium text-gray-700 text-right whitespace-nowrap" style={{ width: '40px' }}>
            {currentRangeOption.label}
          </span>
        </div>
      </div>

      {/* Message History */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-gray-50 message-history">
        {messageHistory.length === 0 ? (
          <div className="text-center text-gray-400 py-12 text-sm">
            No messages sent yet
          </div>
        ) : (
          messageHistory.map(message => (
            <div
              key={message.id}
              onClick={() => handleViewMessage(message)}
              className="bg-gray-200 text-gray-900 rounded-2xl rounded-br-sm p-3 ml-auto max-w-[85%] cursor-pointer hover:bg-gray-300 transition-colors flex items-start gap-2"
            >
              {getCommandIcon(message.command)}
              <div className="flex-1 min-w-0">
                <div className="font-medium mb-1">{message.command}</div>
                <div className="flex items-center justify-between gap-2">
                  {getRecipientIcons(message.modules)}
                  <div className="text-xs opacity-60">{getRelativeTime(message.timestamp)}</div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Current Message Area */}
      <div className="bg-white border-t border-gray-200">
        <div className="flex items-center gap-2 p-3 message-input-area">
          <div 
            className={`flex-1 bg-gray-100 rounded-full px-4 py-2.5 flex items-center gap-2 cursor-text transition-all ${
              flashMessageBox ? 'ring-2 ring-amber-400 bg-amber-50' : ''
            }`}
            onClick={handleMessageInputClick}
          >
            {currentMessage ? (
              <>
                {getCommandIcon(currentMessage)}
                <span className="text-gray-800 text-sm flex-1">{currentMessage}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClearMessage();
                  }}
                  className="w-5 h-5 rounded-full bg-gray-300 hover:bg-gray-400 flex items-center justify-center transition-colors flex-shrink-0"
                >
                  <X className="w-3 h-3 text-gray-600" />
                </button>
              </>
            ) : (
              <span className="text-gray-400 text-sm">Select a command...</span>
            )}
          </div>
          <button
            onClick={handleSendMessage}
            className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
              currentMessage
                ? 'bg-blue-500 hover:bg-blue-600 text-white cursor-pointer'
                : 'bg-gray-300 text-gray-500 cursor-pointer'
            }`}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        {/* Command Palette - Slides up when active */}
        <div 
          className={`command-palette transition-all duration-300 ease-out ${
            showStickers ? 'max-h-80 opacity-100' : 'max-h-0 opacity-0 overflow-hidden'
          }`}
        >
          <div className="flex flex-wrap gap-3 p-3 pt-0 max-h-80 overflow-y-auto">
            {commands.map(command => (
              <button
                key={command.id}
                onClick={() => handleCommandClick(command)}
                className="bg-gray-100 rounded-2xl p-3 flex-shrink-0 hover:bg-gray-200 transition-all active:scale-95 flex flex-col items-center gap-2"
              >
                <div 
                  className="w-16 h-16 rounded-xl flex items-center justify-center shadow-sm"
                  style={{ backgroundColor: command.bgColor }}
                >
                  {command.icon === 'power' && <Power className="w-8 h-8 text-white" />}
                  {command.icon === 'poweroff' && <PowerOff className="w-8 h-8 text-white" />}
                  {command.icon === 'pause' && <Pause className="w-8 h-8" style={{ color: command.textColor }} />}
                  {command.icon === 'rainbow' && <Sparkles className="w-8 h-8 text-white" />}
                  {command.icon === '1' && <span className="text-3xl font-bold text-white">1</span>}
                  {command.icon === '2' && <span className="text-3xl font-bold text-white">2</span>}
                </div>
                <span className="text-xs text-gray-600 font-medium whitespace-nowrap">{command.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Contact Details Overlay */}
      {showContactDetails && (
        <div className="absolute inset-0 bg-white z-50 flex flex-col">
          {/* Header */}
          <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
            <button
              onClick={() => setShowContactDetails(false)}
              className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-700" />
            </button>
            <h2 className="text-lg font-semibold text-gray-900">Devices</h2>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleRefresh();
              }}
              className={`ml-auto w-9 h-9 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors ${
                isRefreshing ? 'animate-spin' : ''
              }`}
            >
              <RefreshCw className="w-5 h-5 text-gray-700" />
            </button>
          </div>

          {/* Range Slider */}
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
            <div className="flex items-center gap-3 mb-2">
              <span className="text-sm text-gray-700 font-medium">Range</span>
              <div className="flex-1 min-w-2" />
              <span className="text-sm font-semibold text-gray-700 text-right whitespace-nowrap" style={{ width: '60px' }}>
                {currentRangeOption.label}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 whitespace-nowrap">Near</span>
              <input
                type="range"
                min="0"
                max="5"
                step="1"
                value={range}
                onChange={(e) => setRange(parseInt(e.target.value))}
                className="flex-1 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-gray-600"
              />
              <span className="text-xs text-gray-500 whitespace-nowrap">Far</span>
            </div>
          </div>

          {/* Device List */}
          <div className="flex-1 overflow-y-auto">
            {!isBluetoothConnected ? (
              // Bluetooth disconnected state
              <div className="flex flex-col items-center justify-center py-16 px-4">
                <BluetoothOff className="w-12 h-12 text-gray-400 mb-4" />
                <div className="text-sm font-medium text-gray-900 mb-6">Bluetooth Disconnected</div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleBluetoothToggle();
                  }}
                  className="px-6 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
                >
                  <Bluetooth className="w-4 h-4" />
                  Connect
                </button>
              </div>
            ) : (
              <>
                {availableModules.map(module => (
                  <div
                    key={module.id}
                    className="px-4 py-3 border-b border-gray-100 hover:bg-gray-50 flex items-center gap-3"
                  >
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 ${
                      module.type === 'extension' ? 'bg-gray-600' : 'bg-gray-500'
                    }`}>
                      {module.type === 'module' && <Smartphone className="w-6 h-6 text-white" />}
                      {module.type === 'extension' && <Box className="w-6 h-6 text-white" />}
                      {module.type === 'button' && <CircleDot className="w-6 h-6 text-white" />}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      {editingModule === module.id ? (
                        <input
                          type="text"
                          defaultValue={moduleNicknames[module.id] || ''}
                          placeholder={module.id}
                          autoFocus
                          onBlur={(e) => handleSaveNickname(module.id, e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleSaveNickname(module.id, e.target.value);
                            } else if (e.key === 'Escape') {
                              setEditingModule(null);
                            }
                          }}
                          className="w-full px-2 py-1 border border-gray-300 rounded text-sm font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      ) : (
                        <div className="font-medium text-gray-900">{getDisplayName(module.id)}</div>
                      )}
                      <div className="text-xs text-gray-500">
                        {module.type === 'module' ? 'Module' : module.type === 'extension' ? 'Extension' : 'Button'} • {module.id}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      {getSignalIcon(module.signal)}
                      {getBatteryIcon(module.battery)}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingModule(module.id);
                        }}
                        className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-200 transition-colors"
                      >
                        <Pencil className="w-4 h-4 text-gray-500" />
                      </button>
                    </div>
                  </div>
                ))}
                
                {availableModules.length === 0 && (
                  <div className="text-center text-gray-400 py-12 text-sm">
                    No devices in range
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Message Details Overlay */}
      {viewingMessage && (
        <div className="absolute inset-0 bg-white z-50 flex flex-col">
          {/* Header */}
          <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
            <button
              onClick={() => setViewingMessage(null)}
              className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-700" />
            </button>
            <h2 className="text-lg font-semibold text-gray-900">Message Details</h2>
          </div>

          {/* Message Details Content */}
          <div className="flex-1 overflow-y-auto p-4">
            <div className="bg-gray-50 rounded-2xl p-4 space-y-4">
              {/* Command */}
              <div>
                <div className="text-xs text-gray-500 mb-2">Command</div>
                <div className="flex items-center gap-3">
                  {getCommandIcon(viewingMessage.command)}
                  <span className="font-semibold text-lg">{viewingMessage.command}</span>
                </div>
              </div>

              {/* Sent To */}
              <div>
                <div className="text-xs text-gray-500 mb-2">Sent To</div>
                <div className="space-y-2">
                  {viewingMessage.modules.map(moduleName => {
                    const isModule = moduleName.startsWith('Module') || moduleName.startsWith('M-');
                    const isExtension = moduleName.startsWith('Extension') || moduleName.startsWith('E-');
                    const isButton = moduleName.startsWith('B-');
                    return (
                      <div key={moduleName} className="flex items-center gap-2">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                          isExtension ? 'bg-gray-600' : 'bg-gray-500'
                        }`}>
                          {isModule && <Smartphone className="w-4 h-4 text-white" />}
                          {isExtension && <Box className="w-4 h-4 text-white" />}
                          {isButton && <CircleDot className="w-4 h-4 text-white" />}
                        </div>
                        <span className="text-sm font-medium">{getDisplayName(moduleName)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Timestamp */}
              <div>
                <div className="text-xs text-gray-500 mb-2">Time Sent</div>
                <div className="text-sm">
                  <div className="font-medium">{viewingMessage.displayTime}</div>
                  <div className="text-gray-600">{getRelativeTime(viewingMessage.timestamp)}</div>
                </div>
              </div>
            </div>

            {/* Repeat Button */}
            <button
              onClick={() => {
                handleRepeatMessage(viewingMessage);
                setViewingMessage(null);
              }}
              className="w-full mt-4 bg-gray-700 hover:bg-gray-800 text-white rounded-xl py-3 font-medium transition-colors"
            >
              Send Again
            </button>
          </div>
        </div>
      )}

      {/* Settings Overlay */}
      {showSettings && (
        <div className="absolute inset-0 bg-white z-50 flex flex-col">
          {/* Header */}
          <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
            <button
              onClick={() => setShowSettings(false)}
              className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-700" />
            </button>
            <h2 className="text-lg font-semibold text-gray-900">Settings</h2>
          </div>

          {/* Settings Content */}
          <div className="flex-1 overflow-y-auto p-4">
            <div className="text-center text-gray-400 py-12 text-sm">
              Settings placeholder
            </div>
          </div>
        </div>
      )}

      {/* Connection Warning Modal */}
      {showConnectionWarning && (
        <div className="absolute inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center" onClick={() => setShowConnectionWarning(false)}>
          <div className="bg-white rounded-2xl p-8 mx-4 max-w-sm" onClick={(e) => e.stopPropagation()}>
            <div className="flex flex-col items-center">
              <BluetoothOff className="w-12 h-12 text-gray-400 mb-4" />
              <div className="text-lg font-semibold text-gray-900 mb-6">Bluetooth Disconnected</div>
              <button
                onClick={() => {
                  handleBluetoothToggle();
                  setShowConnectionWarning(false);
                }}
                className="w-full px-6 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2 mb-3"
              >
                <Bluetooth className="w-4 h-4" />
                Connect
              </button>
              <button
                onClick={() => setShowConnectionWarning(false)}
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
