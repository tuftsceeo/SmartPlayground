One-line: every container in the product — the 24px white view shell, the splash choices, gallery game cards, and modal overlays.

```jsx
<ViewPanel><AppHeader … />…</ViewPanel>
<SplashCard icon="library" title="Browse examples" blurb="remix a ready-made game" primary />
<ExampleCard icon="music" name="Melody" description="Tap each note-tag to play a tune." badge="8 NFC tags" />
<OverlayScrim><OverlayCard width={400} align="left">…</OverlayCard></OverlayScrim>
```

Cards inside the shell carry a 1.5px border and no shadow; only the shell and overlays are elevated.
