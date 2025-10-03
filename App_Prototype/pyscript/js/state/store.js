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
  lastUpdateTime: null,
  
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

// Batch state updates
let updatesPending = null;
let renderScheduled = false;

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
  console.log('setState called with:', updates);
  
  // Check if ONLY isRefreshing is being updated
  const keys = Object.keys(updates);
  const isRefreshingOnly = keys.length === 1 && keys[0] === 'isRefreshing';
  
  Object.assign(state, updates);
  console.log('State updated, new state:', state);
  
  // Don't re-render for isRefreshing only - just update button
  if (isRefreshingOnly) {
    console.log('isRefreshing only - NO RENDER, just update button');
    const btn = document.getElementById('refreshBtn');
    if (btn) {
      if (state.isRefreshing) {
        btn.classList.add('animate-spin');
      } else {
        btn.classList.remove('animate-spin');
      }
    }
    return; // EXIT - don't schedule render
  }
  
  // Always trigger render for other changes
  if (!renderScheduled) {
    renderScheduled = true;
    console.log('Scheduling render...');
    requestAnimationFrame(() => {
      console.log('Executing scheduled render, callbacks:', renderCallbacks.size);
      renderCallbacks.forEach(cb => {
        console.log('Calling render callback');
        cb(state);
      });
      renderScheduled = false;
    });
  } else {
    console.log('Render already scheduled, skipping');
  }
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