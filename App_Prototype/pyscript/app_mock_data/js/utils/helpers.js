/**
 * Smart Playground Control - Utility Helper Functions
 * 
 * This module provides common utility functions used throughout the application
 * for data formatting, time calculations, device type detection, and other
 * shared functionality that doesn't belong to specific components.
 * 
 * Key Functions:
 * - Time formatting: Convert timestamps to user-friendly relative times
 * - Device type detection: Parse device IDs to determine module types
 * - Device counting: Aggregate device counts by type for display
 * - Data formatting: Consistent formatting for UI display
 * 
 * Usage:
 * - Import specific functions as needed by components
 * - Pure functions with no side effects for easy testing
 * - Consistent return formats for reliable UI rendering
 * 
 * Device ID Conventions:
 * - M-XXXXXX: Module devices (main playground modules)
 * - E-XXXXXX: Extension devices (add-on modules)
 * - B-XXXXXX: Button devices (input modules)
 * - Note: XXXXXX is the last 6 digits of the device MAC address
 * 
 */

/**
 * Convert timestamp to human-readable relative time string.
 * 
 * @param {Date} timestamp - The timestamp to convert
 * @returns {string} Human-readable relative time (e.g., "2 minutes ago", "just now")
 * 
 * Time Ranges:
 * - < 1 minute: "just now"
 * - 1-59 minutes: "X minute(s) ago"
 * - 60+ minutes: "X hour(s) ago" (rounded)
 */
export function getRelativeTime(timestamp) {
  const now = new Date();
  const diffMs = now - timestamp;
  const diffMins = Math.floor(diffMs / 60000);
  
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
  
  const diffHours = Math.round(diffMins / 60);
  return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
}

/**
 * Format date object to display time in user's locale.
 * 
 * @param {Date} date - Date object to format
 * @returns {string} Formatted time string (e.g., "2:30 PM", "14:30")
 * 
 * Format: Uses user's locale with hour and minute display
 */
export function formatDisplayTime(date) {
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

/**
 * Determine device type from device ID string.
 * 
 * @param {string} deviceId - Device identifier (e.g., "M-A3F821", "E-B4C932")
 * @returns {string} Device type: "module", "extension", or "button"
 * 
 * ID Conventions:
 * - M-XXXXXX or Module*: Main playground modules
 * - E-XXXXXX or Extension*: Extension/add-on modules  
 * - B-XXXXXX: Button/input modules
 * - Note: XXXXXX is the last 6 digits of the device MAC address
 * - Default: "module" for unrecognized patterns
 */
export function getDeviceType(deviceId) {
  if (deviceId.startsWith('M-') || deviceId.startsWith('Module')) return 'module';
  if (deviceId.startsWith('E-') || deviceId.startsWith('Extension')) return 'extension';
  if (deviceId.startsWith('B-')) return 'button';
  return 'module';
}

/**
 * Count devices by type for display purposes.
 * 
 * @param {string[]} deviceIds - Array of device ID strings
 * @returns {Object} Object with counts: {moduleCount, extensionCount, buttonCount}
 * 
 * Usage: For displaying device type summaries in UI components
 */
export function countDevicesByType(deviceIds) {
  return {
    moduleCount: deviceIds.filter(id => id.startsWith('Module') || id.startsWith('M-')).length,
    extensionCount: deviceIds.filter(id => id.startsWith('Extension') || id.startsWith('E-')).length,
    buttonCount: deviceIds.filter(id => id.startsWith('B-')).length
  };
}
