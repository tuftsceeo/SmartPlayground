const { Button, IconButton, SendButton, Chip, StarterChip, ModePill, ConnChip, SsidChip, TagBadge, BrandMark, Icon, TextField, SearchInput, ChatInput, ViewPanel, SplashCard, ExampleCard, CardActionButton, OverlayCard, OverlayScrim, ChatMessage, ThinkingDots, CodeBlock, Toast, ConnectToast, SentBanner, ProgressBar, TagBars, TagRow, RequirementRow, AppHeader, TabBar, RoleRail, PaneResizer } = window.SmartPlaygroundDesignSystem_dcb8c1;
const { useState } = React;

function App() {
  const [view, setView] = useState('splash');
  const [galleryMode, setGalleryMode] = useState('examples');
  const [example, setExample] = useState(null);
  const [connected, setConnected] = useState(false);
  const [overlay, setOverlay] = useState(null);
  const [advanced, setAdvanced] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [banner, setBanner] = useState(false);
  const [messages, setMessages] = useState([{ role: 'system', text: 'Try one of these ideas — tap a chip to fill the box, then edit and send:' }]);

  const send = (text) => {
    setMessages((m) => [...m, { role: 'user', text }, { role: 'bot', pending: true }]);
    setTimeout(() => setMessages((m) => m.slice(0, -1).concat({
      role: 'bot',
      text: "Here's a shake game — every shake fills more of the LED matrix, and the button resets it. Tap Show code to read it, or send it straight to the Box.",
    })), 900);
  };

  const go = (id) => {
    if (id === 'home') setView('workspace');
    else { setGalleryMode(id === 'saved' ? 'saved' : 'examples'); setView('gallery'); }
  };

  const tab = view === 'workspace' ? 'home' : galleryMode === 'saved' ? 'saved' : 'examples';
  const hasCode = messages.some((m) => m.role === 'bot' && !m.pending);

  return (
    <Shell>
      <ViewPanel>
        {view !== 'splash' ? (
          <HeaderBar tab={tab} go={go} connected={connected}
            onConnect={() => (connected ? setOverlay('boxlib') : setOverlay('connect'))} />
        ) : null}

        {view === 'splash' ? (
          <SplashScreen
            onScratch={() => setView('workspace')}
            onGallery={() => { setGalleryMode('examples'); setView('gallery'); }}
            onSaved={() => { setGalleryMode('saved'); setView('gallery'); }} />
        ) : null}

        {view === 'gallery' ? (
          <GalleryScreen mode={galleryMode} onOpen={(e) => { setExample(e); setView('detail'); }} />
        ) : null}

        {view === 'detail' && example ? (
          <DetailScreen example={example} onBack={() => setView('gallery')}
            onRemix={() => { setView('workspace'); send('Start from ' + example.name + ' — ' + example.description.toLowerCase()); }}
            onSend={() => setOverlay(connected ? 'send' : 'connect')} />
        ) : null}

        {view === 'workspace' ? (
          <WorkspaceScreen messages={messages} onSend={send} example={example}
            advanced={advanced} onToggleAdvanced={() => setAdvanced(!advanced)}
            showCode={showCode} onToggleCode={() => setShowCode(!showCode)}
            canSend={hasCode} onSendBox={() => setOverlay(connected ? 'send' : 'connect')} />
        ) : null}

        {overlay === 'connect' ? <ConnectOverlay onConnect={() => { setConnected(true); setOverlay(null); }} onCancel={() => setOverlay(null)} /> : null}
        {overlay === 'send' ? <SendOverlay example={example} onCancel={() => setOverlay(null)} onDone={() => setOverlay('tags')} /> : null}
        {overlay === 'tags' ? <TagChecklistOverlay tags={(example && example.tags) || ['shakegame']} onDone={() => { setOverlay(null); setBanner(true); setTimeout(() => setBanner(false), 2600); }} /> : null}
        {overlay === 'boxlib' ? <BoxLibraryOverlay onClose={() => setOverlay(null)} /> : null}
        {banner ? <SentBanner>Sent! Hold a card on the Box to write it.</SentBanner> : null}
      </ViewPanel>
    </Shell>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
