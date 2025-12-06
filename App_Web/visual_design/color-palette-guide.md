# Color Palette Guide

## Overview
This guide documents the color palette decisions for the Playground Control App, focusing on creating a calming, pastel rainbow aesthetic similar to children's toys while maintaining excellent contrast and readability.

## Design Philosophy

### Core Principles
1. **Skip Yellow/Orange Tones** - Desaturated yellows and oranges are difficult to make look good and tend to appear muddy or dull
2. **Rainbow Gradient Flow** - Colors should flow in spectrum order from warm to cool
3. **Sufficient Contrast** - All colors must have strong enough contrast with white icons
4. **Pastel but Saturated** - Light enough to feel calm and friendly, but saturated enough to be vibrant and clear

## Command Icon Colors

The command buttons flow in a rainbow spectrum from coral through to green, skipping problematic yellow/orange tones:

| Command | Color | Hex | Description |
|---------|-------|-----|-------------|
| Notes | Warm Coral | `#e88a82` | Orangey-red pink, the warmest tone |
| Shake | Rich Pink | `#d57aae` | Saturated pink with good contrast |
| Hot/Cold | Magenta | `#bf75c9` | Purple-pink, bright and clear |
| Jump | Lavender | `#a082cf` | Soft purple-blue |
| Clap | Blue | `#6397b5` | Sky blue, calming |
| Rainbow | Turquoise | `#8fd3c9` | Blue-green, fresh |
| Off | Green | `#93d5a8` | Soft green, the coolest tone |

## Color Selection Guidelines

### What Works
- **-0 and -1 levels** from the base palette provide good balance of lightness and saturation
- **Custom blended colors** when palette colors don't quite fit the spectrum flow
- **Coral to green range** creates a harmonious rainbow without problematic tones

### What to Avoid
- **Pure yellows and oranges** - Become muddy, especially at pastel saturation levels
- **Too pale (-0 level alone)** - May lack sufficient contrast with white icons
- **Too dark (-2 or -3 levels)** - Feels heavy, not calming or toy-like
- **Random color order** - Breaks the rainbow gradient visual flow

## Implementation Notes

### Icon Contrast
All background colors must have sufficient contrast ratio with white (`#ffffff`) icons to meet accessibility standards and ensure clarity.

### Visual Flow
The buttons are arranged in a fixed order on screen. Colors are assigned to create a smooth visual gradient:
- **Warm end**: Coral, Pink
- **Middle**: Magenta, Lavender, Blue
- **Cool end**: Turquoise, Green

This creates a natural left-to-right or top-to-bottom rainbow gradient depending on layout.

## System Status Colors

### Connection Status (Bluetooth/USB)

The app uses a green/amber system to indicate connection status. These colors should remain consistent across the app for clarity:

#### Connected State (Green)
```css
--status-connected-dot: #22c55e;    /* green-500 - pulsing indicator */
--status-connected-icon: #16a34a;   /* green-600 - icon color */
--status-connected-text: #4b5563;   /* gray-600 - status text */
```

**Usage**: Connected status button, success indicators

#### Disconnected/Warning State (Amber)
```css
--status-warning-bg: #fef3c7;       /* amber-100 - button background */
--status-warning-bg-hover: #fde68a; /* amber-200 - button hover */
--status-warning-flash-bg: #fffbeb; /* amber-50 - flash animation background */
--status-warning-flash-ring: #fbbf24; /* amber-400 - flash ring/border */
--status-warning-dot: #f59e0b;      /* amber-500 - status dot */
--status-warning-primary: #d97706;  /* amber-600 - primary action buttons */
--status-warning-primary-hover: #b45309; /* amber-700 - button hover, icons */
--status-warning-text: #92400e;     /* amber-800 - warning text */
```

**Usage**: Disconnected status, connection prompts, warning modals, alert states

**Design Note**: Amber was chosen over red to feel less alarming and more informational. It fits within the friendly, toy-like aesthetic while still being attention-grabbing.

### Neutral Color Scale

The gray scale provides structure and hierarchy without competing with the colorful command palette:

```css
--gray-50: #f9fafb;     /* subtle backgrounds */
--gray-100: #f3f4f6;    /* input backgrounds, hover states */
--gray-200: #e5e7eb;    /* borders, dividers */
--gray-300: #d1d5db;    /* placeholder icons, disabled states */
--gray-400: #9ca3af;    /* secondary icons, muted elements */
--gray-500: #6b7280;    /* secondary text, device icons */
--gray-600: #4b5563;    /* primary text, active icons */
--gray-700: #374151;    /* text hover states, emphasis */
--gray-900: #111827;    /* headings, high emphasis text */
```

**Usage Guidelines**:
- Use grays for UI structure (borders, backgrounds, text)
- Reserve colors for interactive command elements
- Maintain clear hierarchy: darker = more important
- Gray-600 is the default text color for readability

## Reference Palette

The following colors from the original palette serve as good reference points:

```css
/* Warm tones - use sparingly */
--cerise-0: #e6b9d4;    /* soft pink */
--cerise-1: #ca74aa;    /* medium pink */

/* Mid-spectrum - versatile */
--heliotrope-1: #bf75c9;  /* magenta */
--blue-violet-1: #a082cf; /* lavender */

/* Cool tones - calming */
--cornflower-blue-1: #6397b5; /* blue */
--opal-0: #8fd3c9;            /* turquoise */
--sea-green-0: #93d5a8;       /* green */
```

## Accessibility Guidelines

### Color Contrast Requirements

All text and icons must meet WCAG 2.1 Level AA contrast requirements:
- **Normal text**: Minimum 4.5:1 contrast ratio
- **Large text** (18pt+): Minimum 3:1 contrast ratio
- **Icons and UI components**: Minimum 3:1 contrast ratio

**Applied to this app**:
- All command icons use white (`#ffffff`) on colored backgrounds
- Each command background color tested to ensure sufficient contrast
- Status text uses appropriate gray values for readability
- Warning states use high-contrast amber shades

### Focus States

All interactive elements must have visible focus indicators for keyboard navigation:

```css
button:focus-visible,
a:focus-visible {
  outline: 2px solid #3b82f6; /* blue-500 */
  outline-offset: 2px;
}
```

**Design Note**: Blue focus rings work well because they don't appear in the command rainbow gradient, making them distinctive.

### ARIA Labels and Semantics

When using colors to convey meaning, always provide text alternatives:
- Connection status button: `aria-label="Connection status: {connected|disconnected}"`
- Status indicators: Include descriptive text, not just colored dots
- Warning modals: Use `role="dialog"` and `aria-modal="true"`
- Icon buttons: Always include `aria-label` describing the action

### Color Blindness Considerations

**Status Indicators**: 
- Don't rely on color alone - use icons + text
- Green/amber status includes both colored dots AND text labels
- Connection modals use icons (Bluetooth/BluetoothOff) in addition to color

**Command Buttons**:
- Each command has a unique icon, not just color
- Visual hierarchy doesn't depend solely on color
- Spacing and layout provide additional cues

## Color Usage Best Practices

### Do's ✅
- Use command colors only for command buttons
- Keep system UI (headers, modals) in neutral grays
- Use green/amber exclusively for connection status
- Maintain consistent color meanings throughout the app
- Test all colors with actual white icons, not in isolation

### Don'ts ❌
- Don't use command colors for other UI elements
- Don't introduce new yellow/orange tones for any purpose
- Don't use color as the only way to convey information
- Don't use too many different color systems simultaneously
- Don't adjust colors without testing contrast ratios

## Future Considerations

If additional commands are added:
- Maintain the rainbow spectrum order
- Consider where the new command fits semantically and assign an appropriate color
- May need to adjust the gradient to accommodate more steps
- Always test contrast with white icons
- Avoid creating color jumps that break the smooth gradient flow

If new status states are needed:
- Consider extending the green/amber system rather than introducing new colors
- Red could be used for error states (distinct from warning amber)
- Blue could be used for info states (avoid conflicting with command palette)

## Testing Recommendations

When evaluating new colors:

### Visual Testing
1. View on actual device screens (not just development monitors)
2. Test in different lighting conditions (bright, dim, outdoor)
3. Ensure colors feel cohesive as a set, not just individually
4. Verify that the rainbow gradient is perceptually smooth
5. Get feedback on whether colors feel "toy-like" and approachable

### Accessibility Testing
1. Run contrast ratio tests for all color combinations
2. Test with color blindness simulators (protanopia, deuteranopia, tritanopia)
3. Navigate the app with keyboard only and verify focus states
4. Use screen reader to verify color information has text alternatives
5. View in grayscale mode to ensure hierarchy works without color

### User Testing
1. Observe whether users understand connection status colors
2. Check if command colors feel distinct and memorable
3. Verify that the rainbow gradient reads as intentional, not random
4. Ensure amber warnings feel informative, not alarming
5. Confirm overall aesthetic feels calm and friendly

---

## Quick Reference: Complete Color Palette

### Command Colors (in display order)
```css
--command-notes: #e88a82;      /* coral */
--command-shake: #d57aae;      /* pink */
--command-hot-cold: #bf75c9;   /* magenta */
--command-jump: #a082cf;       /* lavender */
--command-clap: #6397b5;       /* blue */
--command-rainbow: #8fd3c9;    /* turquoise */
--command-off: #93d5a8;        /* green */
```

### Connection Status
```css
/* Connected (Green) */
--connected-dot: #22c55e;
--connected-icon: #16a34a;
--connected-text: #4b5563;

/* Disconnected/Warning (Amber) */
--warning-bg: #fef3c7;
--warning-bg-hover: #fde68a;
--warning-dot: #f59e0b;
--warning-primary: #d97706;
--warning-primary-hover: #b45309;
--warning-text: #92400e;
--warning-flash-bg: #fffbeb;
--warning-flash-ring: #fbbf24;
```

### Neutral Grays
```css
--gray-50: #f9fafb;
--gray-100: #f3f4f6;
--gray-200: #e5e7eb;
--gray-300: #d1d5db;
--gray-400: #9ca3af;
--gray-500: #6b7280;
--gray-600: #4b5563;
--gray-700: #374151;
--gray-900: #111827;
```

### Accent Colors
```css
--focus-ring: #3b82f6;         /* blue-500 for focus states */
--error-primary: #dc2626;      /* red-600 for error states (if needed) */
--info-primary: #2563eb;       /* blue-600 for info states (if needed) */
```

