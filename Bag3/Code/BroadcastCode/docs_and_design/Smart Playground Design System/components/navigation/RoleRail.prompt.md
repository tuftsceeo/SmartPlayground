One-line: the 88px advanced-mode rail (Wands / Stations) and the thin draggable pane divider.

```jsx
<RoleRail active="wands" items={[
  { id: 'wands', label: 'Wands', icon: 'wand' },
  { id: 'stations', label: 'Stations', icon: 'gamepad', disabled: true },
]} />
```

The rail is hidden in simple mode. Stations is permanently disabled with the tooltip "Coming later".
