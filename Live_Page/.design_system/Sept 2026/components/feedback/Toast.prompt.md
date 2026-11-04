One-line: every piece of transient or progress feedback — toasts, the teal sent banner, send progress, and the NFC tag checklist rows.

```jsx
<Toast>Sent! Hold a card on the Box to write the pickup tag.</Toast>
<Toast error>Broadcast Box disconnected — check the cable.</Toast>
<TagBars total={8} done={3} />
<TagRow state="next" name="note_c" status="hold it on the Box" />
```

Toast copy is one sentence, sentence case, with an em dash before the fix ("— check the cable").
