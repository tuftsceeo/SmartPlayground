/**
 * Utility Helper Functions
 * 
 * Time formatting, device type detection, and data formatting utilities.
 * Device IDs: M-*, E-*, B-* (Module, Extension, Button + last 6 MAC digits).
 */

/**
 * Convert timestamp to relative time string.
 * @param {Date} timestamp
 * @returns {string} "just now", "X minute(s) ago", or "X hour(s) ago"
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
 * Format date to locale time string.
 * @param {Date} date
 * @returns {string} Formatted time (e.g., "2:30 PM")
 */
export function formatDisplayTime(date) {
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

/**
 * Get device type from ID.
 * @param {string} deviceId - e.g., "M-A3F821", "E-B4C932"
 * @returns {string} "module", "extension", or "button"
 */
export function getDeviceType(deviceId) {
  if (deviceId.startsWith('M-') || deviceId.startsWith('Module')) return 'module';
  if (deviceId.startsWith('E-') || deviceId.startsWith('Extension')) return 'extension';
  if (deviceId.startsWith('B-')) return 'button';
  return 'module';
}

/**
 * Count devices by type.
 * @param {string[]} deviceIds
 * @returns {Object} {moduleCount, extensionCount, buttonCount}
 */
export function countDevicesByType(deviceIds) {
  return {
    moduleCount: deviceIds.filter(id => id.startsWith('Module') || id.startsWith('M-')).length,
    extensionCount: deviceIds.filter(id => id.startsWith('Extension') || id.startsWith('E-')).length,
    buttonCount: deviceIds.filter(id => id.startsWith('B-')).length
  };
}
