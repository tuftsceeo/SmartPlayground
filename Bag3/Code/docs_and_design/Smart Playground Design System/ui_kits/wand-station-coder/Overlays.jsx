const { Button, IconButton, SendButton, Chip, StarterChip, ModePill, ConnChip, SsidChip, TagBadge, BrandMark, Icon, TextField, SearchInput, ChatInput, ViewPanel, SplashCard, ExampleCard, CardActionButton, OverlayCard, OverlayScrim, ChatMessage, ThinkingDots, CodeBlock, Toast, ConnectToast, SentBanner, ProgressBar, TagBars, TagRow, RequirementRow, AppHeader, TabBar, RoleRail, PaneResizer } = window.SmartPlaygroundDesignSystem_dcb8c1;
const { useState, useEffect } = React;

function ConnectOverlay({ onConnect, onCancel }) {
  return (
    <OverlayScrim>
      <OverlayCard width={380}>
        <div style={{ display: 'flex', justifyContent: 'center', color: 'var(--teal)', marginBottom: 12 }}><Icon name="cable" size={40} /></div>
        <h2 style={{ font: "800 18px 'Nunito'", margin: '0 0 8px' }}>Connect to Broadcast Box</h2>
        <p style={{ font: "14px 'Nunito'", color: 'var(--muted)', margin: '0 0 12px' }}>Plug it in, then pick it from the browser's list</p>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 14, marginBottom: 18 }}>
          {[['wand', 'Wand', 'var(--purple)'], ['nfcCard', 'Tags', 'var(--pink)'], ['shakePhone', 'Shake', 'var(--teal)']].map(([ic, l, c]) => (
            <span key={l} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, font: "700 11px 'Nunito'", color: c }}>
              <Icon name={ic} size={22} />{l}
            </span>
          ))}
        </div>
        <Button variant="teal" fullWidth onClick={onConnect}>Connect via USB</Button>
        <Button variant="secondary" fullWidth onClick={onCancel} style={{ marginTop: 8 }}>Cancel</Button>
      </OverlayCard>
    </OverlayScrim>
  );
}

function SendOverlay({ example, onCancel, onDone }) {
  const [name, setName] = useState(example ? example.name : 'Shake game');
  const [progress, setProgress] = useState(null);
  useEffect(() => {
    if (progress === null) return;
    if (progress >= 100) { const t = setTimeout(onDone, 400); return () => clearTimeout(t); }
    const t = setTimeout(() => setProgress((p) => Math.min(100, p + 20)), 220);
    return () => clearTimeout(t);
  }, [progress]);
  const tags = example ? example.tags : ['shakegame'];
  return (
    <OverlayScrim>
      <OverlayCard width={380}>
        <TextField label="Name this game" pencil value={name} maxLength={48} onChange={(e) => setName(e.target.value)} />
        <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 18px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <RequirementRow icon="wand">1 wand</RequirementRow>
          <RequirementRow icon="nfcCard">{tags.length} tag{tags.length > 1 ? 's' : ''} to write</RequirementRow>
          <RequirementRow icon="shakePhone">shake &amp; button</RequirementRow>
        </ul>
        {progress !== null ? <ProgressBar value={progress} label="Writing to the Box…" /> : null}
        <Button variant="primary" fullWidth disabled={progress !== null} onClick={() => setProgress(0)}>Send</Button>
        <Button variant="secondary" fullWidth onClick={onCancel} style={{ marginTop: 8 }}>Not yet</Button>
      </OverlayCard>
    </OverlayScrim>
  );
}

function TagChecklistOverlay({ tags, onDone }) {
  const [done, setDone] = useState(1);
  return (
    <OverlayScrim>
      <OverlayCard width={400} align="left">
        <h2 style={{ font: "800 18px 'Nunito'", margin: '0 0 8px' }}>Now write {tags.length} tags on the Box</h2>
        <p style={{ font: "14px 'Nunito'", color: 'var(--muted)', margin: '0 0 12px' }}>Hold each card on the Box in turn — you can unplug it first.</p>
        <TagBars total={tags.length} done={done} />
        <div style={{ maxHeight: 190, overflow: 'auto' }}>
          {tags.map((t, i) => (
            <TagRow key={t} name={t} state={i < done ? 'done' : i === done ? 'next' : 'idle'}
              status={i < done ? 'written' : i === done ? 'hold it on the Box' : 'waiting'} />
          ))}
        </div>
        <Button variant="primary" fullWidth style={{ marginTop: 8 }}
          onClick={() => (done >= tags.length ? onDone() : setDone(done + 1))}>{done >= tags.length ? 'Done' : 'Mark written'}</Button>
      </OverlayCard>
    </OverlayScrim>
  );
}

function BoxLibraryOverlay({ onClose }) {
  const [active, setActive] = useState('melody');
  return (
    <OverlayScrim>
      <OverlayCard width={400} align="left" style={{ maxHeight: 520, overflow: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
          <ModePill tone="serve" icon="modeServe">Code Server</ModePill>
          <button onClick={onClose} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', display: 'inline-flex' }}><Icon name="close" size={18} /></button>
        </div>
        <div style={{ display: 'flex', gap: 16, marginBottom: 16, alignItems: 'center' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--teal)' }}><Icon name="nfcCard" size={15} /><Icon name="check" size={12} /></span>
          <span style={{ font: '700 11px ui-monospace, monospace', color: 'var(--muted)' }}>v1.4.2</span>
        </div>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, borderTop: '1px solid var(--border)' }}>
          {window.WSC_EXAMPLES.slice(0, 4).map((e) => (
            <li key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '9px 0', borderBottom: '1px solid #f4f2fa', font: "700 13px 'Nunito'" }}>
              <button onClick={() => setActive(e.id)} style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0, color: active === e.id ? 'var(--pink)' : '#c2b8d6', display: 'inline-flex' }}>
                <Icon name={active === e.id ? 'radioOn' : 'radio'} size={16} />
              </button>
              <span style={{ flex: 1, color: 'var(--ink)' }}>{e.name}</span>
              <span style={{ font: "11px 'Nunito'", color: 'var(--muted)' }}>{e.tags.length}×</span>
              <button style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#c2b8d6', padding: 2, display: 'inline-flex' }}><Icon name="trash" size={15} /></button>
            </li>
          ))}
        </ul>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14 }}>
          <Button variant="secondary" size="compact">Clear all</Button>
        </div>
      </OverlayCard>
    </OverlayScrim>
  );
}

Object.assign(window, { ConnectOverlay, SendOverlay, TagChecklistOverlay, BoxLibraryOverlay });
