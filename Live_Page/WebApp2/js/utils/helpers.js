/**
 * Utility helpers: time formatting, device type detection.
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

export function formatDisplayTime(date) {
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

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
export function wandNameFromMac(mac) {
  const clean = String(mac || '').replace(/[:-]/g, '').toUpperCase();
  if (clean.length >= 4) {
    return 'W-' + clean.slice(-4);
  }
  return 'W-' + clean;
}

export function rssiToSignalLevel(rssi) {
  if (rssi === null || rssi === undefined || Number.isNaN(Number(rssi))) {
    return null;
  }
  const val = Number(rssi);
  if (val >= -50) return 3;
  if (val >= -70) return 2;
  if (val >= -85) return 1;
  return 0;
}

export function countDevicesByType(deviceIds) {
  return {
    moduleCount: deviceIds.filter(id => id.startsWith('Module') || id.startsWith('M-')).length,
    extensionCount: deviceIds.filter(id => id.startsWith('Extension') || id.startsWith('E-')).length,
    buttonCount: deviceIds.filter(id => id.startsWith('B-')).length
  };
}
