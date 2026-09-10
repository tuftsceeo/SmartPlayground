One-line: the four read-only status chips in the app header and gallery — mode, connection, network, tag warning.

```jsx
<ModePill tone="serve" icon="modeServe">Code Server</ModePill>
<ConnChip tone="sending">Sending…</ConnChip>
<SsidChip>playground-2g</SsidChip>
<TagBadge>8 NFC tags</TagBadge>
```

Colour carries the meaning: mint = serving, lilac = writing/REPL, amber = waiting, red = lost.
