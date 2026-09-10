One-line: every push action in the app — pink gradient for the main move, white outline for the alternative, teal for connect/confirm.

```jsx
<Button variant="primary" icon="shuffle" fullWidth>Remix this in chat</Button>
<Button variant="secondary" fullWidth>Use as-is → send</Button>
<Button variant="teal" fullWidth>Connect via USB</Button>
<Button variant="send" disabled>Send to Box →</Button>
```

Only one pink gradient button per view. Disabled primary/send fill flat `--disabled-fill` (never faded pink).
