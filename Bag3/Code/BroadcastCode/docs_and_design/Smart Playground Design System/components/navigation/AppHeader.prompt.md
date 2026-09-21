One-line: the shared header — identical on every screen, with status chips pushed to the right edge.

```jsx
<AppHeader tabs={[{id:'home',label:'Home'},{id:'saved',label:'Saved'},{id:'examples',label:'Examples'}]} active="examples">
  <ModePill tone="serve" icon="modeServe">Code Server</ModePill>
  <Button variant="connect" icon="cable">Connect</Button>
</AppHeader>
```

Tabs are Home / Saved / Examples. Never more than three.
