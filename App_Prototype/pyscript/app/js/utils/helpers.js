/**
 * Playground Control App - Utility Helpers
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

export function countDevicesByType(deviceIds) {
  return {
    moduleCount: deviceIds.filter(id => id.startsWith('Module') || id.startsWith('M-')).length,
    extensionCount: deviceIds.filter(id => id.startsWith('Extension') || id.startsWith('E-')).length,
    buttonCount: deviceIds.filter(id => id.startsWith('B-')).length
  };
}
