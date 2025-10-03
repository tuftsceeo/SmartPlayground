/**
 * Playground Control App - Main Application
 */

console.log('main.js loading...');

import { state, setState, getAvailableDevices, onStateChange } from './state/store.js';
import { PyBridge } from './utils/pyBridge.js';
import { formatDisplayTime } from './utils/helpers.js';
import { createRecipientBar } from './components/recipientBar.js';
import { createMessageHistory } from './components/messageHistory.js';
import { createMessageInput } from './components/messageInput.js';
import { createDeviceListOverlay } from './components/deviceListOverlay.js';
import { createMessageDetailsOverlay } from './components/messageDetailsOverlay.js';

console.log('All imports loaded');

class App {
  constructor() {
    console.log('App constructor called');
    this.container = document.getElementById('root');
    console.log('Container element:', this.container);
    this.components = {};
    this.init();
  }
  
  async init() {
    console.log('init() called');
    
    // Use mock devices for now (Python call not completing)
    const mockDevices = [
      { id: 'M-A3F821', name: 'M-A3F821', type: 'module', rssi: -25, signal: 3, battery: 'full' },
      { id: 'M-B4C932', name: 'M-B4C932', type: 'module', rssi: -40, signal: 3, battery: 'high' },
      { id: 'M-C5D043', name: 'M-C5D043', type: 'module', rssi: -58, signal: 2, battery: 'medium' },
      { id: 'E-D6E154', name: 'E-D6E154', type: 'extension', rssi: -48, signal: 2, battery: 'high' },
      { id: 'E-E7F265', name: 'E-E7F265', type: 'extension', rssi: -78, signal: 1, battery: 'low' },
      { id: 'B-F8G376', name: 'B-F8G376', type: 'button', rssi: -85, signal: 1, battery: 'medium' }
    ];
    
    setState({ allDevices: mockDevices });
    console.log('Mock devices loaded:', mockDevices);
    
    // Try Python in background (optional)
    PyBridge.call('get_devices').then(devices => {
      if (devices) {
        console.log('Real devices from Python:', devices);
        setState({ allDevices: devices });
      }
    }).catch(e => console.log('Python call failed:', e));
    
    // Listen for device updates
    PyBridge.on('devices-updated', (devices) => setState({ allDevices: devices }));
    PyBridge.on('message-sent', (data) => console.log('Message sent:', data));
    
    // Register for state changes
    onStateChange(() => this.render());
    console.log('Registered state change listener');
    
    // Initial render
    console.log('Calling initial render...');
    this.render();
    console.log('init() complete');
  }
  
  render() {
    console.log('render() called');
    const devices = getAvailableDevices();
    console.log('Available devices:', devices);
    const canSend = state.currentMessage && devices.length > 0;
    
    // Clear container
    this.container.innerHTML = '';
    this.container.className = 'flex flex-col h-screen max-w-2xl mx-auto bg-white relative';
    console.log('Container cleared and styled');
    
    // Create components
    const recipientBar = createRecipientBar(
      devices,
      state.range,
      (range) => setState({ range }),
      () => {
        setState({ showDeviceList: true });
        this.components.deviceListOverlay.style.display = 'flex';
      }
    );
    
    const messageHistory = createMessageHistory(
      state.messageHistory,
      (message) => {
        setState({ viewingMessage: message, showMessageDetails: true });
        this.components.messageDetailsOverlay.style.display = 'flex';
        this.renderMessageDetails();
      }
    );
    
    const messageInput = createMessageInput(
      state.currentMessage,
      state.showCommandPalette,
      canSend,
      () => setState({ showCommandPalette: true }),
      (command) => setState({ currentMessage: command.label }),
      () => setState({ currentMessage: '', showCommandPalette: false }),
      () => this.handleSendMessage()
    );
    
    this.components.deviceListOverlay = createDeviceListOverlay(
      devices,
      state.range,
      state.isRefreshing,
      state.editingDeviceId,
      state.moduleNicknames,
      () => {
        setState({ showDeviceList: false });
        this.components.deviceListOverlay.style.display = 'none';
      },
      (range) => setState({ range }),
      () => this.handleRefreshDevices(),
      (deviceId) => setState({ editingDeviceId: deviceId }),
      (deviceId, nickname) => {
        setState({
          moduleNicknames: {
            ...state.moduleNicknames,
            [deviceId]: nickname.trim() || undefined
          },
          editingDeviceId: null
        });
      }
    );
    
    this.components.messageDetailsOverlay = createMessageDetailsOverlay(
      state.viewingMessage,
      state.moduleNicknames,
      () => {
        setState({ showMessageDetails: false, viewingMessage: null });
        this.components.messageDetailsOverlay.style.display = 'none';
      },
      (message) => setState({ currentMessage: message.command, showCommandPalette: true })
    );
    
    // Append to DOM
    this.container.appendChild(recipientBar);
    this.container.appendChild(messageHistory);
    this.container.appendChild(messageInput);
    this.container.appendChild(this.components.deviceListOverlay);
    this.container.appendChild(this.components.messageDetailsOverlay);
    
    // Initialize Lucide icons
    if (window.lucide) {
      window.lucide.createIcons();
    }
    
    // Handle overlay visibility
    if (state.showDeviceList) {
      this.components.deviceListOverlay.style.display = 'flex';
    }
    if (state.showMessageDetails) {
      this.components.messageDetailsOverlay.style.display = 'flex';
    }
  }
  
  renderMessageDetails() {
    // Re-render message details overlay
    const newOverlay = createMessageDetailsOverlay(
      state.viewingMessage,
      state.moduleNicknames,
      () => {
        setState({ showMessageDetails: false, viewingMessage: null });
        this.components.messageDetailsOverlay.style.display = 'none';
      },
      (message) => setState({ currentMessage: message.command, showCommandPalette: true })
    );
    
    this.components.messageDetailsOverlay.replaceWith(newOverlay);
    this.components.messageDetailsOverlay = newOverlay;
    this.components.messageDetailsOverlay.style.display = 'flex';
    
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }
  
  async handleSendMessage() {
    const devices = getAvailableDevices();
    if (!state.currentMessage || devices.length === 0) return;
    
    const now = new Date();
    const newMessage = {
      id: Date.now(),
      command: state.currentMessage,
      modules: devices.map(d => d.name),
      timestamp: now,
      displayTime: formatDisplayTime(now)
    };
    
    setState({
      messageHistory: [...state.messageHistory, newMessage],
      currentMessage: '',
      showCommandPalette: false
    });
    
    // Send to Python backend
    try {
      await PyBridge.call('send_command', newMessage.command, devices.map(d => d.id));
    } catch (e) {
      console.error('Error sending command:', e);
    }
  }
  
  async handleRefreshDevices() {
    setState({ isRefreshing: true });
    
    try {
      const devices = await PyBridge.call('refresh_devices');
      setState({ allDevices: devices || [] });
    } catch (e) {
      console.error('Error refreshing:', e);
    }
    
    setTimeout(() => setState({ isRefreshing: false }), 1000);
  }
}

// Initialize app
console.log('About to create App instance...');
try {
  const app = new App();
  console.log('App created successfully:', app);
} catch (error) {
  console.error('Error creating App:', error);
}