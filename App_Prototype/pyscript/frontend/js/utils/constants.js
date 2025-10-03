/**
 * Playground Control App - Constants
 */

export const COMMANDS = [
  { id: 'play', label: 'Play', bgColor: '#7eb09b', icon: 'play', textColor: 'white' },
  { id: 'pause', label: 'Pause', bgColor: '#d4a574', icon: 'pause', textColor: 'white' },
  { id: 'win', label: 'Win', bgColor: '#b084cc', icon: 'rainbow', textColor: 'white' },
  { id: 'game1', label: 'Game 1', bgColor: '#658ea9', icon: '1', textColor: 'white' },
  { id: 'game2', label: 'Game 2', bgColor: '#d7a449', icon: '2', textColor: 'white' },
  { id: 'off', label: 'Off', bgColor: '#e98973', icon: 'poweroff', textColor: 'white' }
];

// Get range label for slider position (1-100)
export function getRangeLabel(position) {
  if (position === 100) return 'All';
  if (position >= 84) return 'Far';
  if (position >= 68) return 'Distant';
  if (position >= 51) return 'Close';
  if (position >= 34) return 'Near';
  return 'Here';
}