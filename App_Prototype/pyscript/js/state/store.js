/**
 * Playground Control App - State Management
 * 
 * Centralized state management for the application.
 * All state changes trigger re-renders of affected components.
 */

export const state = {
  // Device state
  range: 40, // 0-100 slider value (40 = "Close")
  allDevices: [],
  moduleNicknames: {},
  
  // Message state
  messageHistory: [],
  currentMessage: '',
  
  // UI state
  showCommandPalette: false,
  showDeviceList: false,
  showMessageDetails: false,
  viewingMessage: null,
  editingDeviceId: null,
  isRefreshing: false
};

// Render callbacks - components register themselves here
const renderCallbacks = new Set();

/**
 * Register a render callback
 */
export function onStateChange(callback) {
  renderCallbacks.add(callback);
  return () => renderCallbacks.delete(callback); // Cleanup function
}

/**
 * Update state and trigger re-renders
 */
export function setState(updates) {
  Object.assign(state, updates);
  renderCallbacks.forEach(cb => cb(state));
}

/**
 * Get computed values
 */
// Convert slider position (1-100) to RSSI threshold
function sliderToRSSI(position) {
  if (position === 100) return -999; // "All" - no cutoff
  // Map 1-99 to RSSI range: -30 (closest) to -90 (farthest)
  // Linear interpolation: position 1 = -30, position 99 = -90
  return -30 - ((position - 1) / 98) * 60;
}

// Get range label for slider position
export function getRangeLabel(position) {
  if (position === 100) return 'All';
  if (position >= 84) return 'Far';
  if (position >= 68) return 'Distant';
  if (position >= 51) return 'Close';
  if (position >= 34) return 'Near';
  return 'Here';
}

export function getAvailableDevices() {
  const rssiThreshold = sliderToRSSI(state.range);
  return state.allDevices.filter(d => d.rssi >= rssiThreshold);
}
