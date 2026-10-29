const { Button, IconButton, SendButton, Chip, StarterChip, ModePill, ConnChip, SsidChip, TagBadge, BrandMark, Icon, TextField, SearchInput, ChatInput, ViewPanel, SplashCard, ExampleCard, CardActionButton, OverlayCard, OverlayScrim, ChatMessage, ThinkingDots, CodeBlock, Toast, ConnectToast, SentBanner, ProgressBar, TagBars, TagRow, RequirementRow, AppHeader, TabBar, RoleRail, PaneResizer } = window.SmartPlaygroundDesignSystem_dcb8c1;
const { useState } = React;

function Shell({ children }) {
  return <div style={{ maxWidth: 1100, margin: '0 auto', height: 'min(760px, calc(100vh - 48px))', padding: '24px 16px', display: 'flex', flexDirection: 'column' }}>{children}</div>;
}

function HeaderBar({ tab, go, connected, onConnect }) {
  return (
    <AppHeader tabs={[{id:'home',label:'Home'},{id:'saved',label:'Saved'},{id:'examples',label:'Examples'}]} active={tab} onTab={go}>
      {connected ? <SsidChip>playground-2g</SsidChip> : null}
      <ModePill tone={connected ? 'serve' : 'muted'} icon={connected ? 'modeServe' : 'box'}>{connected ? 'Code Server' : 'Box'}</ModePill>
      <Button variant="connect" icon="cable" connected={connected} onClick={onConnect}>{connected ? 'Connected' : 'Connect'}</Button>
    </AppHeader>
  );
}

function SplashScreen({ onScratch, onGallery, onSaved }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 24px' }}>
      <BrandMark size="splash" showTitle={false} />
      <div style={{ font: "900 34px 'Nunito'", marginTop: 22 }}>Wand &amp; Station Coder</div>
      <div style={{ font: "20px 'Patrick Hand'", color: '#5b5468', marginTop: 6 }}>make magic for your playground</div>
      <div style={{ display: 'flex', gap: 16, marginTop: 40, flexWrap: 'wrap', justifyContent: 'center' }}>
        <SplashCard icon="message-circle" title="Start from scratch" blurb="chat your idea into code" onClick={onScratch} />
        <SplashCard icon="library" title="Browse examples" blurb="remix a ready-made game" primary onClick={onGallery} />
        <SplashCard icon="folder-open" title="My saved games" blurb="pick up where you left off" onClick={onSaved} />
      </div>
    </div>
  );
}

function GalleryScreen({ mode, onOpen }) {
  const [cat, setCat] = useState('all');
  const [q, setQ] = useState('');
  const saved = mode === 'saved';
  const list = (saved ? window.WSC_EXAMPLES.slice(0, 3) : window.WSC_EXAMPLES)
    .filter((e) => (cat === 'all' || e.category === cat) && e.name.toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px 0' }}>
        <h1 style={{ font: "800 16px 'Nunito'", margin: 0 }}>{saved ? 'My saved games' : 'Example games'}</h1>
        <SearchInput placeholder="search games…" value={q} onChange={(e) => setQ(e.target.value)} style={{ marginLeft: 'auto' }} />
      </div>
      <div style={{ display: 'flex', gap: 8, padding: '12px 20px 4px', flexWrap: 'wrap' }}>
        {window.WSC_CATEGORIES.map((c) => <Chip key={c.id} icon={c.icon} active={c.id === cat} onClick={() => setCat(c.id)}>{c.label}</Chip>)}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px 20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 14, alignContent: 'start' }}>
        {list.map((e) => (
          <ExampleCard key={e.id} icon={e.icon} name={e.name} description={e.description} badge={e.tagNote || undefined}
            onOpen={() => onOpen(e)}
            actions={saved ? <><CardActionButton icon="pencil" /><CardActionButton icon="trash" danger>Delete</CardActionButton></> : undefined} />
        ))}
        {list.length === 0 ? <p style={{ gridColumn: '1/-1', color: '#8b859a', padding: 24, font: "13px 'Nunito'" }}>No saved games yet — open a workspace and tap Save.</p> : null}
      </div>
    </>
  );
}

function DetailScreen({ example, onBack, onRemix, onSend }) {
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 20px 0' }}>
        <button onClick={onBack} style={{ font: "16px 'Nunito'", color: 'var(--muted)', cursor: 'pointer', border: 'none', background: 'none', padding: '4px 8px' }}>←</button>
        <h1 style={{ font: "800 16px 'Nunito'", margin: 0 }}>{example.name}</h1>
      </div>
      <div style={{ flex: 1, display: 'flex', gap: 28, padding: '16px 20px 20px', minHeight: 0 }}>
        <div style={{ flex: 1, minWidth: 0, borderRadius: 16, background: 'var(--pattern-stripe)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20, padding: 12 }}>
          <img src="../../assets/wand/WAND_FRONT.svg" style={{ height: '78%' }} alt="" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center' }}>
            <img src="../../assets/gestures/shake_left_right.svg" style={{ width: 92 }} alt="" />
            <span style={{ font: '12px ui-monospace, monospace', color: '#c9a3bd' }}>practice window</span>
          </div>
        </div>
        <div style={{ width: 280, display: 'flex', flexDirection: 'column', gap: 14, flex: 'none' }}>
          <p style={{ font: "14px/1.5 'Nunito'", color: '#5b5468', margin: 0 }}>{example.hint}</p>
          {example.tagNote ? <TagBadge>{example.tagNote}</TagBadge> : null}
          <div style={{ flex: 1 }} />
          <Button variant="primary" icon="shuffle" fullWidth onClick={onRemix}>Remix this in chat</Button>
          <Button variant="secondary" fullWidth onClick={onSend}>Use as-is → send</Button>
        </div>
      </div>
    </>
  );
}

function WorkspaceScreen({ messages, onSend, advanced, onToggleAdvanced, showCode, onToggleCode, canSend, onSendBox, example }) {
  const [draft, setDraft] = useState('');
  const send = () => { if (draft.trim()) { onSend(draft.trim()); setDraft(''); } };
  return (
    <>
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {advanced ? <RoleRail active="wands" items={[{ id:'wands', label:'Wands', icon:'wand' }, { id:'stations', label:'Stations', icon:'gamepad', disabled:true }]} /> : null}
        <div style={{ flex: '0 0 auto', width: 340, minWidth: 260, display: 'flex', flexDirection: 'column', minHeight: 0, borderRight: '1px solid var(--border)' }}>
          <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {messages.map((m, i) => <ChatMessage key={i} role={m.role}>{m.pending ? <><ThinkingDots />thinking…</> : m.text}</ChatMessage>)}
            {messages.length <= 1 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: '4px 0 8px' }}>
                <StarterChip icon="rainbow" onClick={() => onSend('a game where shaking makes a rainbow')}>a game where shaking makes a rainbow</StarterChip>
                <StarterChip icon="music" onClick={() => onSend('tap tags to play a tune')}>tap tags to play a tune</StarterChip>
              </div>
            ) : null}
          </div>
          <div style={{ display: 'flex', gap: 8, padding: '12px 14px', borderTop: '1px solid var(--border)' }}>
            <ChatInput placeholder="type a request…" value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} />
            <SendButton onClick={send} />
          </div>
        </div>
        <PaneResizer />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 180, minHeight: 0, background: canSend ? '#fff' : 'var(--pattern-stripe)' }}>
          {canSend ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, padding: 16, overflow: 'auto' }}>
              <img src="../../assets/wand/WAND_FRONT.svg" style={{ maxHeight: 260 }} alt="Wand simulator" />
              <p style={{ font: "13px 'Nunito'", color: 'var(--muted)', textAlign: 'center', margin: 0, maxWidth: 320 }}>{example ? example.hint : 'Shake to fill the lights. Press the button to reset.'}</p>
              <img src="../../assets/gestures/shake_left_right.svg" style={{ width: 110 }} alt="" />
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, color: '#c9a3bd' }}>
              <Icon name="wand" size={46} strokeWidth={1.3} />
              <div style={{ font: '12px ui-monospace, monospace' }}>wand preview</div>
            </div>
          )}
        </div>
        {showCode ? (
          <div style={{ width: 380, background: '#fff', display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--border)', boxShadow: 'var(--shadow-drawer)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 20px', borderBottom: '1px solid var(--border)' }}>
              <span style={{ font: "800 14px 'Nunito'" }}>&lt;/&gt; generated code</span>
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ font: "700 12px 'Nunito'", color: 'var(--muted)' }}>v2/2</span>
                <IconButton icon="download" title="Download" />
                <button onClick={onToggleCode} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', display: 'inline-flex' }}><Icon name="close" size={18} /></button>
              </div>
            </div>
            <pre style={{ flex: 1, margin: 0, overflow: 'auto', padding: '12px 16px', font: "12.5px/1.55 'SF Mono', Consolas, monospace", color: 'var(--code-text)', background: 'var(--code-bg)' }}>{window.WSC_SAMPLE_CODE}</pre>
          </div>
        ) : null}
      </div>
      <div style={{ display: 'flex', gap: 10, padding: '12px 20px', borderTop: '1px solid var(--border)', alignItems: 'center', flex: 'none' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <IconButton icon="save" title="Save" />
          <IconButton glyph="</>" title="Show code" active={showCode} onClick={onToggleCode} />
          <IconButton icon="wrench" title="Switch to advanced mode" active={advanced} onClick={onToggleAdvanced} />
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <Button variant="send" disabled={!canSend} onClick={onSendBox}>Send to Box →</Button>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { Shell, HeaderBar, SplashScreen, GalleryScreen, DetailScreen, WorkspaceScreen });
