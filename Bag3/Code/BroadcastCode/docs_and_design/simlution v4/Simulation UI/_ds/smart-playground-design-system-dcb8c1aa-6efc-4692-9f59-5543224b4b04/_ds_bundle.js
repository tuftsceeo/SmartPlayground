/* @ds-bundle: {"format":4,"namespace":"SmartPlaygroundDesignSystem_dcb8c1","components":[{"name":"ChatMessage","sourcePath":"components/chat/ChatMessage.jsx"},{"name":"ThinkingDots","sourcePath":"components/chat/ChatMessage.jsx"},{"name":"CodeBlock","sourcePath":"components/chat/ChatMessage.jsx"},{"name":"BrandMark","sourcePath":"components/core/BrandMark.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Chip","sourcePath":"components/core/Chip.jsx"},{"name":"StarterChip","sourcePath":"components/core/Chip.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"SendButton","sourcePath":"components/core/IconButton.jsx"},{"name":"ModePill","sourcePath":"components/core/ModePill.jsx"},{"name":"ConnChip","sourcePath":"components/core/ModePill.jsx"},{"name":"SsidChip","sourcePath":"components/core/ModePill.jsx"},{"name":"TagBadge","sourcePath":"components/core/ModePill.jsx"},{"name":"Toast","sourcePath":"components/feedback/Toast.jsx"},{"name":"ConnectToast","sourcePath":"components/feedback/Toast.jsx"},{"name":"SentBanner","sourcePath":"components/feedback/Toast.jsx"},{"name":"ProgressBar","sourcePath":"components/feedback/Toast.jsx"},{"name":"TagBars","sourcePath":"components/feedback/Toast.jsx"},{"name":"TagRow","sourcePath":"components/feedback/Toast.jsx"},{"name":"RequirementRow","sourcePath":"components/feedback/Toast.jsx"},{"name":"TextField","sourcePath":"components/forms/TextField.jsx"},{"name":"SearchInput","sourcePath":"components/forms/TextField.jsx"},{"name":"ChatInput","sourcePath":"components/forms/TextField.jsx"},{"name":"ICON_PATHS","sourcePath":"components/icons/Icon.jsx"},{"name":"ICON_NAMES","sourcePath":"components/icons/Icon.jsx"},{"name":"Icon","sourcePath":"components/icons/Icon.jsx"},{"name":"AppHeader","sourcePath":"components/navigation/AppHeader.jsx"},{"name":"TabBar","sourcePath":"components/navigation/AppHeader.jsx"},{"name":"RoleRail","sourcePath":"components/navigation/RoleRail.jsx"},{"name":"PaneResizer","sourcePath":"components/navigation/RoleRail.jsx"},{"name":"ViewPanel","sourcePath":"components/surfaces/ViewPanel.jsx"},{"name":"SplashCard","sourcePath":"components/surfaces/ViewPanel.jsx"},{"name":"ExampleCard","sourcePath":"components/surfaces/ViewPanel.jsx"},{"name":"CardActionButton","sourcePath":"components/surfaces/ViewPanel.jsx"},{"name":"OverlayCard","sourcePath":"components/surfaces/ViewPanel.jsx"},{"name":"OverlayScrim","sourcePath":"components/surfaces/ViewPanel.jsx"}],"sourceHashes":{"components/chat/ChatMessage.jsx":"de6fdaa14a64","components/core/BrandMark.jsx":"7b488b4459fb","components/core/Button.jsx":"66c6c1d4653d","components/core/Chip.jsx":"99ea4f21a0f0","components/core/IconButton.jsx":"24b63c316a4c","components/core/ModePill.jsx":"93f8d4ce31cd","components/feedback/Toast.jsx":"27c8a12df9a9","components/forms/TextField.jsx":"ebf2d7391543","components/icons/Icon.jsx":"1ad27bb15969","components/navigation/AppHeader.jsx":"81f4a4475926","components/navigation/RoleRail.jsx":"24055193eb03","components/surfaces/ViewPanel.jsx":"da4c1b1c37ad","ui_kits/wand-station-coder/App.jsx":"8e8aef9fc8d5","ui_kits/wand-station-coder/Overlays.jsx":"ea6ee815fc4d","ui_kits/wand-station-coder/Screens.jsx":"0478ad87d3af","ui_kits/wand-station-coder/data.js":"68f8cc5c9890"},"inlinedExternals":[],"unexposedExports":[{"name":"categoryIcon","sourcePath":"components/icons/Icon.jsx"}]} */

(() => {

const __ds_ns = (window.SmartPlaygroundDesignSystem_dcb8c1 = window.SmartPlaygroundDesignSystem_dcb8c1 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/chat/ChatMessage.jsx
try { (() => {
const shells = {
  user: {
    alignSelf: 'flex-end',
    background: 'linear-gradient(135deg, #fff0f6, #ffe3f0)',
    color: '#a8265c',
    whiteSpace: 'pre-wrap',
    borderRadius: '14px 14px 3px 14px',
    maxWidth: '88%'
  },
  system: {
    alignSelf: 'flex-start',
    background: '#f4f2fa',
    color: '#5b5468',
    whiteSpace: 'pre-wrap',
    borderRadius: '14px 14px 14px 3px',
    fontSize: '12px',
    maxWidth: '88%'
  },
  bot: {
    alignSelf: 'flex-start',
    background: '#fff',
    color: '#3a3345',
    maxWidth: '95%',
    border: '1px solid var(--border)',
    borderRadius: '14px 14px 14px 3px'
  }
};

/** Chat bubble. Pastel pink gradient for the teacher, white outline for the assistant. */
function ChatMessage({
  role = 'bot',
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      borderRadius: '14px',
      padding: '9px 13px',
      font: "13px/1.45 'Nunito'",
      ...shells[role],
      ...style
    }
  }, children);
}

/** Three pink dots shown while the assistant is composing. */
function ThinkingDots({
  style
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      gap: '3px',
      marginRight: '4px',
      verticalAlign: 'middle',
      ...style
    }
  }, [0, 0.2, 0.4].map((d, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      display: 'inline-block',
      width: '5px',
      height: '5px',
      background: 'var(--pink)',
      borderRadius: '50%',
      animation: `sp-thinking-blink 1.2s infinite ${d}s`
    }
  })));
}

/** Fenced code block with a mono title bar and Copy/Use actions. */
function CodeBlock({
  language = 'python',
  actions,
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--code-bg)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      overflow: 'hidden',
      margin: '0.6em 0',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '6px 10px',
      background: '#f4f2fa',
      borderBottom: '1px solid var(--border)',
      font: '11px ui-monospace, monospace',
      color: 'var(--muted)'
    }
  }, /*#__PURE__*/React.createElement("span", null, language), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      gap: '6px'
    }
  }, actions)), /*#__PURE__*/React.createElement("pre", {
    style: {
      padding: '10px 12px',
      overflowX: 'auto',
      maxHeight: '320px',
      margin: 0,
      fontFamily: '"SF Mono", Consolas, monospace',
      fontSize: '12.5px',
      lineHeight: 1.55,
      color: 'var(--code-text)'
    }
  }, children));
}
Object.assign(__ds_scope, { ChatMessage, ThinkingDots, CodeBlock });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/chat/ChatMessage.jsx", error: String((e && e.message) || e) }); }

// components/core/BrandMark.jsx
try { (() => {
/** The app's identity block: gradient rounded square holding a ✦, then the product name.
 *  There is no logo file in the source — this gradient gem IS the mark. */
function BrandMark({
  size = 'header',
  title = 'Wand & Station Coder',
  showTitle = true,
  style
}) {
  const gem = size === 'splash' ? {
    width: 96,
    height: 96,
    borderRadius: 28,
    fontSize: 44,
    boxShadow: 'var(--shadow-pink-lg)'
  } : {
    width: 30,
    height: 30,
    borderRadius: 9,
    fontSize: 15
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      flex: 'none',
      flexDirection: size === 'splash' ? 'column' : 'row',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      ...gem,
      background: 'var(--grad-gem)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#fff',
      flex: 'none'
    }
  }, "\u2726"), showTitle ? /*#__PURE__*/React.createElement("div", {
    style: size === 'splash' ? {
      font: "900 34px 'Nunito'",
      marginTop: '22px',
      color: 'var(--ink)'
    } : {
      font: "800 14px 'Nunito'",
      color: 'var(--ink)'
    }
  }, title) : null);
}
Object.assign(__ds_scope, { BrandMark });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/BrandMark.jsx", error: String((e && e.message) || e) }); }

// components/icons/Icon.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Stroke-icon set copied verbatim from ChatBroadcast/js/icons.js.
   Mock paths from Box Manager; Lucide (ISC) paths for the rest. Do not redraw these. */
const ICON_PATHS = {
  // Mock-up paths
  wifi: '<path d="M2 8.5a15 15 0 0 1 20 0"/><path d="M5.5 12a10 10 0 0 1 13 0"/><path d="M9 15.5a5 5 0 0 1 6 0"/><circle cx="12" cy="19" r="1" fill="currentColor" stroke="none"/>',
  box: '<path d="M3 8l9-4 9 4-9 4-9-4z"/><path d="M3 8v8l9 4 9-4V8"/><path d="M12 12v8"/>',
  plug: '<path d="M9 2v4M15 2v4"/><path d="M6 6h12v4a6 6 0 0 1-12 0V6z"/><path d="M12 16v6"/>',
  floppy: '<path d="M5 4h11l3 3v13H5V4z"/><path d="M8 4v5h7V4"/><path d="M8 14h8v6H8z"/>',
  wand: '<path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72"/><path d="m14 7 3 3"/><path d="M5 6v4"/><path d="M19 14v4"/><path d="M10 2v2"/><path d="M7 8H3"/><path d="M21 16h-4"/><path d="M11 3H9"/>',
  sparkles: '<path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"/><path d="M20 2v4"/><path d="M22 4h-4"/><circle cx="4" cy="20" r="2"/>',
  "pencil-sparkles": '<path d="M10 3H8"/><path d="m15.007 5.008 3.987 3.986"/><path d="M20 15v4"/><path d="M21.174 6.813a2.82 2.82 0 0 0-3.986-3.987L3.842 16.175a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="M22 17h-4"/><path d="M4 5v4"/><path d="M6 7H2"/><path d="M9 2v2"/>',
  "mop-sparkles": '<path d="M10 22a3 3 0 0 1-3-3"/><path d="M10 22c2.761 0 5-1.79 5-4-4.42 0-4.08-5-8.5-5a4.501 4.501 0 0 0 0 9z"/><path d="M10 3H8"/><path d="M12.5 11.5 22 2"/><path d="M20 13v4"/><path d="M22 15h-4"/><path d="M4 5v4"/><path d="M6 7H2"/><path d="m6.98 13.02 2.665-2.664a1.21 1.21 0 0 1 1.71 0l2.29 2.288a1.21 1.21 0 0 1 0 1.712l-2.088 2.087"/><path d="M9 2v2"/>',
  nfcCard: '<rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="12" cy="12" r="2.5"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  trash: '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/>',
  pencil: '<path d="M4 20l4-1 11-11-3-3L5 16l-1 4z"/>',
  radio: '<circle cx="12" cy="12" r="8"/>',
  radioOn: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5" fill="currentColor" stroke="none"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
  warning: '<path d="M12 3l10 18H2L12 3z"/><path d="M12 9v5"/><circle cx="12" cy="17" r="0.6" fill="currentColor" stroke="none"/>',
  modeServe: '<rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><circle cx="7" cy="7" r="0.6" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="0.6" fill="currentColor" stroke="none"/>',
  shakePhone: '<rect x="7" y="2" width="10" height="20" rx="3"/><path d="M7 7h10M7 17h10"/>',
  spinner: '<circle cx="12" cy="12" r="8" stroke-dasharray="38" stroke-dashoffset="12"/>',
  code: '<path d="M8 6l-5 6 5 6"/><path d="M16 6l5 6-5 6"/>',
  // Lucide (simplified stroke paths, viewBox 0 0 24 24)
  wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  "message-circle": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>',
  library: '<path d="M16 6l4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/>',
  "folder-open": '<path d="M6 14l1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
  shuffle: '<path d="M2 18h1.4a4 4 0 0 0 3.3-1.7l6.6-9.6a4 4 0 0 1 3.3-1.7H22"/><path d="M18 2l4 4-4 4"/><path d="M2 6h1.9a4 4 0 0 1 3.3 1.7l.7 1"/><path d="M22 18h-5.9a4 4 0 0 1-3.3-1.7l-.7-1"/><path d="M18 14l4 4-4 4"/>',
  send: '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="M21.854 2.147l-10.94 10.939"/>',
  download: '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/>',
  cable: '<path d="M17 21v-2a1 1 0 0 1-1-1v-1a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1a1 1 0 0 1-1 1"/><path d="M19 15V6.5a1 1 0 0 0-7 0v11a1 1 0 0 1-7 0V9"/><path d="M21 21v-2h-4"/><path d="M3 5h4V3"/><path d="M7 5a1 1 0 0 1 1 1v1a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a1 1 0 0 1 1-1"/>',
  unplug: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
  gamepad: '<line x1="6" x2="10" y1="12" y2="12"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="15" x2="15.01" y1="13" y2="13"/><line x1="18" x2="18.01" y1="11" y2="11"/><rect width="20" height="12" x="2" y="6" rx="2"/>',
  "square-arrow-out-up-right": '<path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"/><path d="M21 3l-9 9"/><path d="M15 3h6v6"/>',
  "smartphone-nfc": '<rect width="7" height="12" x="2" y="6" rx="1"/><path d="M13 8.32a7.43 7.43 0 0 1 0 7.36"/><path d="M16.46 6.21a11.76 11.76 0 0 1 0 11.58"/><path d="M19.91 4.1a15.91 15.91 0 0 1 .01 15.8"/>',
  vibrate: '<path d="M2 8a2 2 0 0 1 2-2h2v12H4a2 2 0 0 1-2-2Z"/><path d="M18 6h2a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2"/><rect width="8" height="16" x="8" y="4" rx="1"/><path d="m5.5 2.5-.5-.5"/><path d="m5.5 21.5-.5.5"/><path d="m18.5 2.5.5-.5"/><path d="m18.5 21.5.5.5"/>',
  circle: '<circle cx="12" cy="12" r="10"/>',
  chevronDown: '<path d="M6 9l6 6 6-6"/>',
  "volume-2": '<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',
  "grid-3x3": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>',
  music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  palette: '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
  tag: '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
  snowflake: '<path d="M2 12h20"/><path d="M12 2v20"/><path d="m20 16-4-4 4-4"/><path d="m4 8 4 4-4 4"/><path d="m16 4-4 4-4-4"/><path d="m8 20 4-4 4 4"/>',
  rainbow: '<path d="M22 17a10 10 0 0 0-20 0"/><path d="M6 17a6 6 0 0 1 12 0"/><path d="M10 17a2 2 0 0 1 4 0"/>',
  "arrow-up": '<path d="M12 19V5"/><path d="M5 12l7-7 7 7"/>',
  "chef-hat": '<path d="M17 21a1 1 0 0 0 1-1v-5.35c0-.457.316-.844.727-1.041a4 4 0 0 0-2.134-7.589 5 5 0 0 0-9.186 0 4 4 0 0 0-2.134 7.588c.411.198.727.585.727 1.041V20a1 1 0 0 0 1 1Z"/><path d="M6 17h12"/>',
  "circle-check": '<circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/>',
  save: '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
  home: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  "brain-circuit": '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M9 13a4.5 4.5 0 0 0 3-4"/><path d="M12 13h4"/><path d="M12 18h4"/><path d="M12 5h4"/><path d="M16 9h.01"/><path d="M20 9h.01"/><path d="M16 13h.01"/><path d="M20 13h.01"/><path d="M16 17h.01"/><path d="M20 17h.01"/><path d="M17 5a3 3 0 1 1 .5 5.5"/><circle cx="9" cy="9" r="0.5" fill="currentColor"/>'
};
const ICON_NAMES = Object.keys(ICON_PATHS);
function Icon({
  name,
  size = 15,
  strokeWidth = 1.8,
  color,
  title,
  style,
  className,
  ...rest
}) {
  const body = ICON_PATHS[name];
  if (!body) return null;
  return /*#__PURE__*/React.createElement("svg", _extends({
    viewBox: "0 0 24 24",
    width: size,
    height: size,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: strokeWidth,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": title ? undefined : true,
    role: title ? 'img' : undefined,
    className: className,
    style: {
      display: 'block',
      flex: 'none',
      color,
      ...style
    },
    dangerouslySetInnerHTML: {
      __html: (title ? `<title>${title}</title>` : '') + body
    }
  }, rest));
}

/** Category → icon name, as the gallery chips map them. */
function categoryIcon(category) {
  if (category === 'sound') return 'music';
  if (category === 'color') return 'palette';
  if (category === 'multi') return 'tag';
  return 'wand';
}
Object.assign(__ds_scope, { ICON_PATHS, ICON_NAMES, Icon, categoryIcon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/icons/Icon.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const base = {
  border: 'none',
  cursor: 'pointer',
  textAlign: 'center',
  fontFamily: "'Nunito', sans-serif",
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '8px'
};
const variants = {
  primary: {
    padding: '12px',
    borderRadius: '14px',
    background: 'var(--grad-pink)',
    color: '#fff',
    font: "800 14px 'Nunito'"
  },
  secondary: {
    padding: '11px',
    borderRadius: '14px',
    border: '1.5px solid var(--border)',
    background: '#fff',
    font: "700 13px 'Nunito'",
    color: 'var(--icon-ink)'
  },
  teal: {
    padding: '12px',
    borderRadius: '14px',
    background: 'var(--grad-teal)',
    color: '#fff',
    font: "800 14px 'Nunito'"
  },
  connect: {
    padding: '7px 14px',
    borderRadius: '14px',
    background: 'var(--grad-teal)',
    color: '#fff',
    font: "800 12px 'Nunito'"
  },
  send: {
    padding: '9px 20px',
    borderRadius: '16px',
    background: 'var(--grad-pink)',
    color: '#fff',
    font: "800 13px 'Nunito'"
  }
};
const compact = {
  width: 'auto',
  padding: '7px 12px',
  borderRadius: '12px',
  font: "700 11px 'Nunito'"
};

/** The product's filled/outline actions. Full-width by default inside overlays. */
function Button({
  variant = 'primary',
  size = 'default',
  icon,
  iconAfter,
  fullWidth,
  disabled,
  connected,
  children,
  style,
  ...rest
}) {
  const s = {
    ...base,
    ...variants[variant]
  };
  if (size === 'compact') Object.assign(s, compact);
  if (fullWidth) s.width = '100%';
  if (variant === 'connect' && connected) s.background = 'var(--grad-muted)';
  if (disabled) {
    s.cursor = 'not-allowed';
    if (variant === 'primary' || variant === 'send') {
      s.background = 'var(--disabled-fill)';
      s.color = '#fff';
      s.boxShadow = 'none';
    } else {
      s.opacity = 0.7;
    }
  }
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    disabled: disabled,
    style: {
      ...s,
      ...style
    }
  }, rest), icon ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: variant === 'connect' || variant === 'send' ? 14 : 16
  }) : null, children, iconAfter ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: iconAfter,
    size: 16
  }) : null);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Chip.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Gallery filter chip. Active state is solid ink, not a tint. */
function Chip({
  icon,
  active,
  children,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    style: {
      font: "700 13px 'Nunito'",
      padding: '7px 16px',
      borderRadius: '20px',
      cursor: 'pointer',
      border: 'none',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      background: active ? 'var(--ink)' : '#f4f2fa',
      color: active ? '#fff' : 'var(--ink)',
      ...style
    }
  }, rest), icon ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 14
  }) : null, children);
}

/** Suggestion chip offered above the empty chat composer. */
function StarterChip({
  icon,
  children,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    style: {
      font: "700 12px 'Nunito'",
      padding: '8px 12px',
      borderRadius: '14px',
      border: '1.5px solid var(--border)',
      background: '#fff',
      color: 'var(--ink)',
      cursor: 'pointer',
      textAlign: 'left',
      maxWidth: '100%',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      ...style
    }
  }, rest), icon ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 14
  }) : null, children);
}
Object.assign(__ds_scope, { Chip, StarterChip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Chip.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Square outline button holding a single glyph — the workspace footer tools. */
function IconButton({
  icon,
  glyph,
  active,
  size = 15,
  title,
  style,
  ...rest
}) {
  const s = {
    border: '1.5px solid var(--border)',
    background: '#fff',
    borderRadius: '14px',
    padding: '8px 10px',
    cursor: 'pointer',
    color: 'var(--icon-ink)',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center'
  };
  if (active) Object.assign(s, {
    background: 'var(--tab-active-bg)',
    color: 'var(--tab-active-fg)',
    borderColor: 'transparent'
  });
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    title: title,
    style: {
      ...s,
      ...style
    }
  }, rest), glyph ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: "800 12px ui-monospace, monospace",
      lineHeight: 1
    }
  }, glyph) : /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: size
  }));
}

/** The round pink send button in the chat composer. */
function SendButton({
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    title: "Send",
    style: {
      width: '38px',
      height: '38px',
      borderRadius: '50%',
      background: 'var(--pink)',
      color: '#fff',
      border: 'none',
      cursor: 'pointer',
      flex: 'none',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "send",
    size: 16
  }));
}
Object.assign(__ds_scope, { IconButton, SendButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/core/ModePill.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const tones = {
  serve: {
    background: 'var(--serve-bg)',
    color: 'var(--serve-fg)'
  },
  write: {
    background: 'var(--write-bg)',
    color: 'var(--write-fg)'
  },
  muted: {
    background: '#f4f2fa',
    color: 'var(--muted)'
  }
};

/** Box mode pill in the header: "Code Server" / "Tag Writing" / disabled "Box". */
function ModePill({
  tone = 'muted',
  icon = 'box',
  children,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    disabled: tone === 'muted',
    style: {
      border: 'none',
      font: "800 12px 'Nunito'",
      padding: '7px 12px',
      borderRadius: '14px',
      cursor: tone === 'muted' ? 'default' : 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      opacity: tone === 'muted' ? 0.85 : 1,
      ...tones[tone],
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 14
  }), children);
}
const connTones = {
  error: {
    color: '#c0392b',
    background: '#fdecea'
  },
  sending: {
    color: '#b36b00',
    background: '#fff6e5'
  },
  repl: {
    color: 'var(--purple)',
    background: 'var(--write-bg)'
  }
};

/** Connection state chip — a filled dot in currentColor, then the state text. */
function ConnChip({
  tone = 'error',
  children,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      font: "700 11px 'Nunito'",
      borderRadius: '12px',
      padding: '5px 10px',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      ...connTones[tone],
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      width: '8px',
      height: '8px',
      borderRadius: '50%',
      background: 'currentColor',
      flex: 'none'
    }
  }), children);
}

/** Monospace network chip showing which Wi-Fi the wands should join. */
function SsidChip({
  children,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '5px',
      background: 'var(--write-bg)',
      color: 'var(--write-fg)',
      font: '700 11px ui-monospace, monospace',
      padding: '5px 10px',
      borderRadius: '12px',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "wifi",
    size: 12
  }), children);
}

/** Amber "needs tags" note under a gallery card. */
function TagBadge({
  children,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      font: "700 11px 'Nunito'",
      color: '#a8781e',
      background: '#fff8e0',
      borderRadius: '8px',
      padding: '3px 8px',
      width: 'fit-content',
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { ModePill, ConnChip, SsidChip, TagBadge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/ModePill.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Toast.jsx
try { (() => {
/** Bottom-centre ink toast. `error` turns it red. */
function Toast({
  error,
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      bottom: '24px',
      left: '50%',
      transform: 'translateX(-50%)',
      background: error ? '#c0392b' : 'var(--ink)',
      color: '#fff',
      padding: '12px 20px',
      borderRadius: '12px',
      font: "700 13px 'Nunito'",
      zIndex: 300,
      maxWidth: '90vw',
      ...style
    }
  }, children);
}

/** Top-right transient with a spinner — used while the browser device picker is open. */
function ConnectToast({
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: '60px',
      right: '20px',
      background: 'var(--ink)',
      color: '#fff',
      font: "700 12px 'Nunito'",
      padding: '9px 16px',
      borderRadius: '12px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      zIndex: 310,
      animation: 'sp-pop 0.15s ease',
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      animation: 'sp-spin 1s linear infinite'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "spinner",
    size: 14
  })), children);
}

/** Teal success banner pinned to the top of the shell after a successful send. */
function SentBanner({
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: '24px',
      left: '50%',
      transform: 'translateX(-50%)',
      background: 'var(--grad-teal)',
      color: '#fff',
      padding: '12px 20px',
      borderRadius: '14px',
      font: "800 14px 'Nunito'",
      zIndex: 250,
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      ...style
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "circle-check",
    size: 16
  }), children);
}

/** Thin teal progress track shown while writing to the Box. */
function ProgressBar({
  value = 0,
  label,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      margin: '12px 0',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '8px',
      background: '#eee',
      borderRadius: '5px',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      width: `${value}%`,
      background: 'var(--teal)',
      transition: 'width 0.2s'
    }
  })), label ? /*#__PURE__*/React.createElement("p", {
    style: {
      font: "13px 'Nunito'",
      color: 'var(--muted)',
      margin: '6px 0 0'
    }
  }, label) : null);
}

/** Segmented bars at the top of the tag checklist — one segment per tag. */
function TagBars({
  total,
  done,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: '6px',
      marginBottom: '18px',
      ...style
    }
  }, Array.from({
    length: total
  }).map((_, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      flex: 1,
      height: '8px',
      borderRadius: '5px',
      background: i < done ? 'var(--pink)' : '#eee'
    }
  })));
}

/** One tag in the checklist. next = amber, done = mint. */
function TagRow({
  state = 'idle',
  name,
  status,
  style
}) {
  const bg = state === 'next' ? '#fff8e0' : state === 'done' ? '#f7fefb' : '#fafafd';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '11px 12px',
      borderRadius: '12px',
      background: bg,
      marginBottom: '8px',
      font: "700 13px 'Nunito'",
      color: 'var(--ink)',
      ...style
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: state === 'done' ? 'check' : 'nfcCard',
    size: 15,
    color: state === 'done' ? 'var(--teal)' : 'var(--icon-ink)'
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }, name), /*#__PURE__*/React.createElement("span", {
    style: {
      font: "700 11px 'Nunito'",
      color: state === 'done' ? 'var(--teal)' : 'var(--muted)'
    }
  }, status));
}

/** Row in the send-confirm "what this game needs" list. */
function RequirementRow({
  icon,
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("li", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '9px',
      padding: '8px 11px',
      borderRadius: '10px',
      background: '#fafafd',
      font: "700 12.5px 'Nunito'",
      color: 'var(--ink)',
      ...style
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 15,
    color: "var(--pink)"
  }), children);
}
Object.assign(__ds_scope, { Toast, ConnectToast, SentBanner, ProgressBar, TagBars, TagRow, RequirementRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Toast.jsx", error: String((e && e.message) || e) }); }

// components/forms/TextField.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Labelled text input as used in the send-confirm overlay (centred, pencil affordance). */
function TextField({
  label,
  pencil,
  error,
  centered = true,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'left',
      ...style
    }
  }, label ? /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'block',
      font: "700 11px 'Nunito'",
      letterSpacing: '.04em',
      textTransform: 'uppercase',
      color: 'var(--muted)',
      marginBottom: '6px'
    }
  }, label) : null, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      marginBottom: '12px'
    }
  }, /*#__PURE__*/React.createElement("input", _extends({
    style: {
      width: '100%',
      boxSizing: 'border-box',
      padding: pencil ? '10px 34px 10px 12px' : '10px 12px',
      border: '1.5px solid var(--border)',
      borderRadius: '10px',
      background: '#fafafd',
      font: "700 15px 'Nunito'",
      textAlign: centered ? 'center' : 'left'
    }
  }, rest)), pencil ? /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      right: '10px',
      top: '50%',
      transform: 'translateY(-50%)',
      color: 'var(--muted)',
      pointerEvents: 'none'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "pencil",
    size: 15
  })) : null), error ? /*#__PURE__*/React.createElement("p", {
    style: {
      color: '#c0392b',
      font: "13px 'Nunito'",
      minHeight: '1.2em',
      margin: 0
    }
  }, error) : null);
}

/** Gallery search box. */
function SearchInput({
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("input", _extends({
    type: "search",
    style: {
      border: '1.5px solid var(--border)',
      borderRadius: '10px',
      padding: '9px 14px',
      font: "14px 'Nunito'",
      width: '220px',
      ...style
    }
  }, rest));
}

/** Auto-height chat composer field. */
function ChatInput({
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("textarea", _extends({
    rows: 1,
    style: {
      flex: 1,
      border: '1.5px solid var(--border)',
      borderRadius: '20px',
      padding: '8px 14px',
      font: "13px 'Nunito'",
      resize: 'none',
      height: '38px',
      ...style
    }
  }, rest));
}
Object.assign(__ds_scope, { TextField, SearchInput, ChatInput });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/TextField.jsx", error: String((e && e.message) || e) }); }

// components/navigation/AppHeader.jsx
try { (() => {
/** Top bar of every view: brand, pill tabs, then right-aligned status + connect. */
function AppHeader({
  title,
  tabs,
  active,
  onTab,
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '14px 20px',
      borderBottom: '1px solid var(--border)',
      flex: 'none',
      ...style
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.BrandMark, {
    title: title
  }), tabs ? /*#__PURE__*/React.createElement(TabBar, {
    tabs: tabs,
    active: active,
    onSelect: onTab
  }) : null, /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    }
  }, children));
}

/** Pill tabs. Active is a pink tint, never an underline. */
function TabBar({
  tabs,
  active,
  onSelect,
  style
}) {
  return /*#__PURE__*/React.createElement("nav", {
    "aria-label": "Main",
    style: {
      display: 'flex',
      gap: '6px',
      marginLeft: '10px',
      ...style
    }
  }, tabs.map(t => {
    const on = t.id === active;
    return /*#__PURE__*/React.createElement("button", {
      key: t.id,
      type: "button",
      onClick: () => onSelect && onSelect(t.id),
      style: {
        border: 'none',
        font: "700 12px 'Nunito'",
        padding: '6px 12px',
        borderRadius: '20px',
        cursor: 'pointer',
        background: on ? 'var(--tab-active-bg)' : 'transparent',
        color: on ? 'var(--tab-active-fg)' : 'var(--muted)'
      }
    }, t.label);
  }));
}
Object.assign(__ds_scope, { AppHeader, TabBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/AppHeader.jsx", error: String((e && e.message) || e) }); }

// components/navigation/RoleRail.jsx
try { (() => {
/** Left rail in advanced mode: which device you are coding for. */
function RoleRail({
  items,
  active,
  onSelect,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: '88px',
      borderRight: '1px solid var(--border)',
      padding: '14px 8px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      flex: 'none',
      ...style
    }
  }, items.map(it => {
    const on = it.id === active;
    return /*#__PURE__*/React.createElement("div", {
      key: it.id,
      role: "button",
      onClick: () => !it.disabled && onSelect && onSelect(it.id),
      title: it.disabled ? 'Coming later' : it.label,
      style: {
        borderRadius: '10px',
        padding: '10px 6px',
        textAlign: 'center',
        font: "700 11px 'Nunito'",
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '4px',
        cursor: it.disabled ? 'default' : 'pointer',
        ...(on ? {
          background: '#fff0f6',
          borderLeft: '3px solid var(--pink)',
          color: 'var(--pink-dark)'
        } : {
          color: 'var(--ink)'
        }),
        ...(it.disabled ? {
          color: '#a8a4b5',
          opacity: 0.7
        } : null)
      }
    }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
      name: it.icon,
      size: 18
    }), it.label);
  }));
}

/** Draggable column divider between chat and preview. */
function PaneResizer({
  vertical = true,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    role: "separator",
    "aria-orientation": vertical ? 'vertical' : 'horizontal',
    tabIndex: 0,
    style: {
      flex: 'none',
      width: '10px',
      margin: '0 -5px',
      position: 'relative',
      zIndex: 1,
      cursor: 'col-resize',
      background: 'transparent',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 0,
      bottom: 0,
      left: '4px',
      width: '2px',
      background: 'var(--border)',
      borderRadius: '2px'
    }
  }));
}
Object.assign(__ds_scope, { RoleRail, PaneResizer });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/RoleRail.jsx", error: String((e && e.message) || e) }); }

// components/surfaces/ViewPanel.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** The white rounded shell every full view sits inside. */
function ViewPanel({
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: '#fff',
      borderRadius: '24px',
      boxShadow: 'var(--shadow-shell)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      flex: 1,
      minHeight: 0,
      position: 'relative',
      ...style
    }
  }, children);
}

/** Big choice card on the splash screen. One card per screen may be `primary`. */
function SplashCard({
  icon,
  title,
  blurb,
  primary,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "button",
    tabIndex: 0,
    style: {
      width: '220px',
      padding: '20px 16px',
      borderRadius: '16px',
      textAlign: 'center',
      cursor: 'pointer',
      ...(primary ? {
        border: 'none',
        background: 'var(--grad-pink)',
        color: '#fff',
        boxShadow: 'var(--shadow-pink)'
      } : {
        border: '2px solid var(--border)',
        background: '#fff'
      }),
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'center',
      color: primary ? '#fff' : 'var(--pink)'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 26
  })), /*#__PURE__*/React.createElement("h3", {
    style: {
      font: "800 15px 'Nunito'",
      margin: '8px 0 2px'
    }
  }, title), /*#__PURE__*/React.createElement("p", {
    style: {
      font: "12px 'Nunito'",
      margin: 0,
      opacity: 0.85
    }
  }, blurb));
}

/** Game card in the gallery grid. */
function ExampleCard({
  icon,
  name,
  description,
  badge,
  actions,
  onOpen,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    onClick: onOpen,
    style: {
      border: '1.5px solid var(--border)',
      borderRadius: '16px',
      padding: '14px',
      cursor: 'pointer',
      position: 'relative',
      background: '#fff',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '64px',
      borderRadius: '10px',
      background: '#fff0f6',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#e9a9c6',
      marginBottom: '10px'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 28
  })), /*#__PURE__*/React.createElement("h3", {
    style: {
      font: "800 13px 'Nunito'",
      margin: '0 0 2px',
      color: 'var(--ink)'
    }
  }, name), /*#__PURE__*/React.createElement("p", {
    style: {
      font: "11px 'Nunito'",
      color: 'var(--muted)',
      margin: '0 0 10px'
    }
  }, description), actions ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: '6px'
    }
  }, actions) : null, badge ? /*#__PURE__*/React.createElement("div", {
    style: {
      font: "700 11px 'Nunito'",
      color: '#a8781e',
      background: '#fff8e0',
      borderRadius: '8px',
      padding: '3px 8px',
      width: 'fit-content',
      marginTop: '8px'
    }
  }, badge) : null);
}

/** Small outline action inside a gallery card (rename, delete, open). */
function CardActionButton({
  icon,
  danger,
  children,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    style: {
      borderRadius: '9px',
      padding: '6px 9px',
      cursor: 'pointer',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      ...(danger ? {
        border: 'none',
        background: '#fdecea',
        color: '#c0392b',
        font: "700 11px 'Nunito'"
      } : {
        border: '1.5px solid var(--border)',
        background: '#fff',
        color: 'var(--icon-ink)'
      }),
      ...style
    }
  }, rest), icon ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 13
  }) : null, children);
}

/** Modal card floating over the scrim. */
function OverlayCard({
  width = 380,
  align = 'center',
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: '#fff',
      borderRadius: '20px',
      padding: '24px',
      width: '100%',
      maxWidth: width + 'px',
      boxShadow: 'var(--shadow-overlay)',
      textAlign: align,
      ...style
    }
  }, children);
}

/** Fixed full-bleed scrim with blur-free 35% ink wash. */
function OverlayScrim({
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      background: 'var(--scrim)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 200,
      padding: '16px',
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { ViewPanel, SplashCard, ExampleCard, CardActionButton, OverlayCard, OverlayScrim });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/surfaces/ViewPanel.jsx", error: String((e && e.message) || e) }); }

// ui_kits/wand-station-coder/App.jsx
try { (() => {
const {
  Button,
  IconButton,
  SendButton,
  Chip,
  StarterChip,
  ModePill,
  ConnChip,
  SsidChip,
  TagBadge,
  BrandMark,
  Icon,
  TextField,
  SearchInput,
  ChatInput,
  ViewPanel,
  SplashCard,
  ExampleCard,
  CardActionButton,
  OverlayCard,
  OverlayScrim,
  ChatMessage,
  ThinkingDots,
  CodeBlock,
  Toast,
  ConnectToast,
  SentBanner,
  ProgressBar,
  TagBars,
  TagRow,
  RequirementRow,
  AppHeader,
  TabBar,
  RoleRail,
  PaneResizer
} = window.SmartPlaygroundDesignSystem_dcb8c1;
const {
  useState
} = React;
function App() {
  const [view, setView] = useState('splash');
  const [galleryMode, setGalleryMode] = useState('examples');
  const [example, setExample] = useState(null);
  const [connected, setConnected] = useState(false);
  const [overlay, setOverlay] = useState(null);
  const [advanced, setAdvanced] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [banner, setBanner] = useState(false);
  const [messages, setMessages] = useState([{
    role: 'system',
    text: 'Try one of these ideas — tap a chip to fill the box, then edit and send:'
  }]);
  const send = text => {
    setMessages(m => [...m, {
      role: 'user',
      text
    }, {
      role: 'bot',
      pending: true
    }]);
    setTimeout(() => setMessages(m => m.slice(0, -1).concat({
      role: 'bot',
      text: "Here's a shake game — every shake fills more of the LED matrix, and the button resets it. Tap Show code to read it, or send it straight to the Box."
    })), 900);
  };
  const go = id => {
    if (id === 'home') setView('workspace');else {
      setGalleryMode(id === 'saved' ? 'saved' : 'examples');
      setView('gallery');
    }
  };
  const tab = view === 'workspace' ? 'home' : galleryMode === 'saved' ? 'saved' : 'examples';
  const hasCode = messages.some(m => m.role === 'bot' && !m.pending);
  return /*#__PURE__*/React.createElement(Shell, null, /*#__PURE__*/React.createElement(ViewPanel, null, view !== 'splash' ? /*#__PURE__*/React.createElement(HeaderBar, {
    tab: tab,
    go: go,
    connected: connected,
    onConnect: () => connected ? setOverlay('boxlib') : setOverlay('connect')
  }) : null, view === 'splash' ? /*#__PURE__*/React.createElement(SplashScreen, {
    onScratch: () => setView('workspace'),
    onGallery: () => {
      setGalleryMode('examples');
      setView('gallery');
    },
    onSaved: () => {
      setGalleryMode('saved');
      setView('gallery');
    }
  }) : null, view === 'gallery' ? /*#__PURE__*/React.createElement(GalleryScreen, {
    mode: galleryMode,
    onOpen: e => {
      setExample(e);
      setView('detail');
    }
  }) : null, view === 'detail' && example ? /*#__PURE__*/React.createElement(DetailScreen, {
    example: example,
    onBack: () => setView('gallery'),
    onRemix: () => {
      setView('workspace');
      send('Start from ' + example.name + ' — ' + example.description.toLowerCase());
    },
    onSend: () => setOverlay(connected ? 'send' : 'connect')
  }) : null, view === 'workspace' ? /*#__PURE__*/React.createElement(WorkspaceScreen, {
    messages: messages,
    onSend: send,
    example: example,
    advanced: advanced,
    onToggleAdvanced: () => setAdvanced(!advanced),
    showCode: showCode,
    onToggleCode: () => setShowCode(!showCode),
    canSend: hasCode,
    onSendBox: () => setOverlay(connected ? 'send' : 'connect')
  }) : null, overlay === 'connect' ? /*#__PURE__*/React.createElement(ConnectOverlay, {
    onConnect: () => {
      setConnected(true);
      setOverlay(null);
    },
    onCancel: () => setOverlay(null)
  }) : null, overlay === 'send' ? /*#__PURE__*/React.createElement(SendOverlay, {
    example: example,
    onCancel: () => setOverlay(null),
    onDone: () => setOverlay('tags')
  }) : null, overlay === 'tags' ? /*#__PURE__*/React.createElement(TagChecklistOverlay, {
    tags: example && example.tags || ['shakegame'],
    onDone: () => {
      setOverlay(null);
      setBanner(true);
      setTimeout(() => setBanner(false), 2600);
    }
  }) : null, overlay === 'boxlib' ? /*#__PURE__*/React.createElement(BoxLibraryOverlay, {
    onClose: () => setOverlay(null)
  }) : null, banner ? /*#__PURE__*/React.createElement(SentBanner, null, "Sent! Hold a card on the Box to write it.") : null));
}
ReactDOM.createRoot(document.getElementById('root')).render(/*#__PURE__*/React.createElement(App, null));
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/wand-station-coder/App.jsx", error: String((e && e.message) || e) }); }

// ui_kits/wand-station-coder/Overlays.jsx
try { (() => {
const {
  Button,
  IconButton,
  SendButton,
  Chip,
  StarterChip,
  ModePill,
  ConnChip,
  SsidChip,
  TagBadge,
  BrandMark,
  Icon,
  TextField,
  SearchInput,
  ChatInput,
  ViewPanel,
  SplashCard,
  ExampleCard,
  CardActionButton,
  OverlayCard,
  OverlayScrim,
  ChatMessage,
  ThinkingDots,
  CodeBlock,
  Toast,
  ConnectToast,
  SentBanner,
  ProgressBar,
  TagBars,
  TagRow,
  RequirementRow,
  AppHeader,
  TabBar,
  RoleRail,
  PaneResizer
} = window.SmartPlaygroundDesignSystem_dcb8c1;
const {
  useState,
  useEffect
} = React;
function ConnectOverlay({
  onConnect,
  onCancel
}) {
  return /*#__PURE__*/React.createElement(OverlayScrim, null, /*#__PURE__*/React.createElement(OverlayCard, {
    width: 380
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'center',
      color: 'var(--teal)',
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "cable",
    size: 40
  })), /*#__PURE__*/React.createElement("h2", {
    style: {
      font: "800 18px 'Nunito'",
      margin: '0 0 8px'
    }
  }, "Connect to Broadcast Box"), /*#__PURE__*/React.createElement("p", {
    style: {
      font: "14px 'Nunito'",
      color: 'var(--muted)',
      margin: '0 0 12px'
    }
  }, "Plug it in, then pick it from the browser's list"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'center',
      gap: 14,
      marginBottom: 18
    }
  }, [['wand', 'Wand', 'var(--purple)'], ['nfcCard', 'Tags', 'var(--pink)'], ['shakePhone', 'Shake', 'var(--teal)']].map(([ic, l, c]) => /*#__PURE__*/React.createElement("span", {
    key: l,
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 4,
      font: "700 11px 'Nunito'",
      color: c
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: ic,
    size: 22
  }), l))), /*#__PURE__*/React.createElement(Button, {
    variant: "teal",
    fullWidth: true,
    onClick: onConnect
  }, "Connect via USB"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    fullWidth: true,
    onClick: onCancel,
    style: {
      marginTop: 8
    }
  }, "Cancel")));
}
function SendOverlay({
  example,
  onCancel,
  onDone
}) {
  const [name, setName] = useState(example ? example.name : 'Shake game');
  const [progress, setProgress] = useState(null);
  useEffect(() => {
    if (progress === null) return;
    if (progress >= 100) {
      const t = setTimeout(onDone, 400);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setProgress(p => Math.min(100, p + 20)), 220);
    return () => clearTimeout(t);
  }, [progress]);
  const tags = example ? example.tags : ['shakegame'];
  return /*#__PURE__*/React.createElement(OverlayScrim, null, /*#__PURE__*/React.createElement(OverlayCard, {
    width: 380
  }, /*#__PURE__*/React.createElement(TextField, {
    label: "Name this game",
    pencil: true,
    value: name,
    maxLength: 48,
    onChange: e => setName(e.target.value)
  }), /*#__PURE__*/React.createElement("ul", {
    style: {
      listStyle: 'none',
      padding: 0,
      margin: '0 0 18px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement(RequirementRow, {
    icon: "wand"
  }, "1 wand"), /*#__PURE__*/React.createElement(RequirementRow, {
    icon: "nfcCard"
  }, tags.length, " tag", tags.length > 1 ? 's' : '', " to write"), /*#__PURE__*/React.createElement(RequirementRow, {
    icon: "shakePhone"
  }, "shake & button")), progress !== null ? /*#__PURE__*/React.createElement(ProgressBar, {
    value: progress,
    label: "Writing to the Box\u2026"
  }) : null, /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    fullWidth: true,
    disabled: progress !== null,
    onClick: () => setProgress(0)
  }, "Send"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    fullWidth: true,
    onClick: onCancel,
    style: {
      marginTop: 8
    }
  }, "Not yet")));
}
function TagChecklistOverlay({
  tags,
  onDone
}) {
  const [done, setDone] = useState(1);
  return /*#__PURE__*/React.createElement(OverlayScrim, null, /*#__PURE__*/React.createElement(OverlayCard, {
    width: 400,
    align: "left"
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      font: "800 18px 'Nunito'",
      margin: '0 0 8px'
    }
  }, "Now write ", tags.length, " tags on the Box"), /*#__PURE__*/React.createElement("p", {
    style: {
      font: "14px 'Nunito'",
      color: 'var(--muted)',
      margin: '0 0 12px'
    }
  }, "Hold each card on the Box in turn \u2014 you can unplug it first."), /*#__PURE__*/React.createElement(TagBars, {
    total: tags.length,
    done: done
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      maxHeight: 190,
      overflow: 'auto'
    }
  }, tags.map((t, i) => /*#__PURE__*/React.createElement(TagRow, {
    key: t,
    name: t,
    state: i < done ? 'done' : i === done ? 'next' : 'idle',
    status: i < done ? 'written' : i === done ? 'hold it on the Box' : 'waiting'
  }))), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    fullWidth: true,
    style: {
      marginTop: 8
    },
    onClick: () => done >= tags.length ? onDone() : setDone(done + 1)
  }, done >= tags.length ? 'Done' : 'Mark written')));
}
function BoxLibraryOverlay({
  onClose
}) {
  const [active, setActive] = useState('melody');
  return /*#__PURE__*/React.createElement(OverlayScrim, null, /*#__PURE__*/React.createElement(OverlayCard, {
    width: 400,
    align: "left",
    style: {
      maxHeight: 520,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement(ModePill, {
    tone: "serve",
    icon: "modeServe"
  }, "Code Server"), /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    style: {
      marginLeft: 'auto',
      background: 'none',
      border: 'none',
      color: 'var(--muted)',
      cursor: 'pointer',
      display: 'inline-flex'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "close",
    size: 18
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 16,
      marginBottom: 16,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      color: 'var(--teal)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "nfcCard",
    size: 15
  }), /*#__PURE__*/React.createElement(Icon, {
    name: "check",
    size: 12
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      font: '700 11px ui-monospace, monospace',
      color: 'var(--muted)'
    }
  }, "v1.4.2")), /*#__PURE__*/React.createElement("ul", {
    style: {
      listStyle: 'none',
      padding: 0,
      margin: 0,
      borderTop: '1px solid var(--border)'
    }
  }, window.WSC_EXAMPLES.slice(0, 4).map(e => /*#__PURE__*/React.createElement("li", {
    key: e.id,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 9,
      padding: '9px 0',
      borderBottom: '1px solid #f4f2fa',
      font: "700 13px 'Nunito'"
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setActive(e.id),
    style: {
      border: 'none',
      background: 'none',
      cursor: 'pointer',
      padding: 0,
      color: active === e.id ? 'var(--pink)' : '#c2b8d6',
      display: 'inline-flex'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: active === e.id ? 'radioOn' : 'radio',
    size: 16
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      color: 'var(--ink)'
    }
  }, e.name), /*#__PURE__*/React.createElement("span", {
    style: {
      font: "11px 'Nunito'",
      color: 'var(--muted)'
    }
  }, e.tags.length, "\xD7"), /*#__PURE__*/React.createElement("button", {
    style: {
      border: 'none',
      background: 'none',
      cursor: 'pointer',
      color: '#c2b8d6',
      padding: 2,
      display: 'inline-flex'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "trash",
    size: 15
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      marginTop: 14
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "compact"
  }, "Clear all"))));
}
Object.assign(window, {
  ConnectOverlay,
  SendOverlay,
  TagChecklistOverlay,
  BoxLibraryOverlay
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/wand-station-coder/Overlays.jsx", error: String((e && e.message) || e) }); }

// ui_kits/wand-station-coder/Screens.jsx
try { (() => {
const {
  Button,
  IconButton,
  SendButton,
  Chip,
  StarterChip,
  ModePill,
  ConnChip,
  SsidChip,
  TagBadge,
  BrandMark,
  Icon,
  TextField,
  SearchInput,
  ChatInput,
  ViewPanel,
  SplashCard,
  ExampleCard,
  CardActionButton,
  OverlayCard,
  OverlayScrim,
  ChatMessage,
  ThinkingDots,
  CodeBlock,
  Toast,
  ConnectToast,
  SentBanner,
  ProgressBar,
  TagBars,
  TagRow,
  RequirementRow,
  AppHeader,
  TabBar,
  RoleRail,
  PaneResizer
} = window.SmartPlaygroundDesignSystem_dcb8c1;
const {
  useState
} = React;
function Shell({
  children
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1100,
      margin: '0 auto',
      height: 'min(760px, calc(100vh - 48px))',
      padding: '24px 16px',
      display: 'flex',
      flexDirection: 'column'
    }
  }, children);
}
function HeaderBar({
  tab,
  go,
  connected,
  onConnect
}) {
  return /*#__PURE__*/React.createElement(AppHeader, {
    tabs: [{
      id: 'home',
      label: 'Home'
    }, {
      id: 'saved',
      label: 'Saved'
    }, {
      id: 'examples',
      label: 'Examples'
    }],
    active: tab,
    onTab: go
  }, connected ? /*#__PURE__*/React.createElement(SsidChip, null, "playground-2g") : null, /*#__PURE__*/React.createElement(ModePill, {
    tone: connected ? 'serve' : 'muted',
    icon: connected ? 'modeServe' : 'box'
  }, connected ? 'Code Server' : 'Box'), /*#__PURE__*/React.createElement(Button, {
    variant: "connect",
    icon: "cable",
    connected: connected,
    onClick: onConnect
  }, connected ? 'Connected' : 'Connect'));
}
function SplashScreen({
  onScratch,
  onGallery,
  onSaved
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px 24px'
    }
  }, /*#__PURE__*/React.createElement(BrandMark, {
    size: "splash",
    showTitle: false
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "900 34px 'Nunito'",
      marginTop: 22
    }
  }, "Wand & Station Coder"), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "20px 'Patrick Hand'",
      color: '#5b5468',
      marginTop: 6
    }
  }, "make magic for your playground"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 16,
      marginTop: 40,
      flexWrap: 'wrap',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement(SplashCard, {
    icon: "message-circle",
    title: "Start from scratch",
    blurb: "chat your idea into code",
    onClick: onScratch
  }), /*#__PURE__*/React.createElement(SplashCard, {
    icon: "library",
    title: "Browse examples",
    blurb: "remix a ready-made game",
    primary: true,
    onClick: onGallery
  }), /*#__PURE__*/React.createElement(SplashCard, {
    icon: "folder-open",
    title: "My saved games",
    blurb: "pick up where you left off",
    onClick: onSaved
  })));
}
function GalleryScreen({
  mode,
  onOpen
}) {
  const [cat, setCat] = useState('all');
  const [q, setQ] = useState('');
  const saved = mode === 'saved';
  const list = (saved ? window.WSC_EXAMPLES.slice(0, 3) : window.WSC_EXAMPLES).filter(e => (cat === 'all' || e.category === cat) && e.name.toLowerCase().includes(q.toLowerCase()));
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '12px 20px 0'
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      font: "800 16px 'Nunito'",
      margin: 0
    }
  }, saved ? 'My saved games' : 'Example games'), /*#__PURE__*/React.createElement(SearchInput, {
    placeholder: "search games\u2026",
    value: q,
    onChange: e => setQ(e.target.value),
    style: {
      marginLeft: 'auto'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      padding: '12px 20px 4px',
      flexWrap: 'wrap'
    }
  }, window.WSC_CATEGORIES.map(c => /*#__PURE__*/React.createElement(Chip, {
    key: c.id,
    icon: c.icon,
    active: c.id === cat,
    onClick: () => setCat(c.id)
  }, c.label))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: 'auto',
      padding: '16px 20px 20px',
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))',
      gap: 14,
      alignContent: 'start'
    }
  }, list.map(e => /*#__PURE__*/React.createElement(ExampleCard, {
    key: e.id,
    icon: e.icon,
    name: e.name,
    description: e.description,
    badge: e.tagNote || undefined,
    onOpen: () => onOpen(e),
    actions: saved ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(CardActionButton, {
      icon: "pencil"
    }), /*#__PURE__*/React.createElement(CardActionButton, {
      icon: "trash",
      danger: true
    }, "Delete")) : undefined
  })), list.length === 0 ? /*#__PURE__*/React.createElement("p", {
    style: {
      gridColumn: '1/-1',
      color: '#8b859a',
      padding: 24,
      font: "13px 'Nunito'"
    }
  }, "No saved games yet \u2014 open a workspace and tap Save.") : null));
}
function DetailScreen({
  example,
  onBack,
  onRemix,
  onSend
}) {
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '10px 20px 0'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onBack,
    style: {
      font: "16px 'Nunito'",
      color: 'var(--muted)',
      cursor: 'pointer',
      border: 'none',
      background: 'none',
      padding: '4px 8px'
    }
  }, "\u2190"), /*#__PURE__*/React.createElement("h1", {
    style: {
      font: "800 16px 'Nunito'",
      margin: 0
    }
  }, example.name)), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      gap: 28,
      padding: '16px 20px 20px',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0,
      borderRadius: 16,
      background: 'var(--pattern-stripe)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 20,
      padding: 12
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/wand/WAND_FRONT.svg",
    style: {
      height: '78%'
    },
    alt: ""
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/gestures/shake_left_right.svg",
    style: {
      width: 92
    },
    alt: ""
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: '12px ui-monospace, monospace',
      color: '#c9a3bd'
    }
  }, "practice window"))), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 280,
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement("p", {
    style: {
      font: "14px/1.5 'Nunito'",
      color: '#5b5468',
      margin: 0
    }
  }, example.hint), example.tagNote ? /*#__PURE__*/React.createElement(TagBadge, null, example.tagNote) : null, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    icon: "shuffle",
    fullWidth: true,
    onClick: onRemix
  }, "Remix this in chat"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    fullWidth: true,
    onClick: onSend
  }, "Use as-is \u2192 send"))));
}
function WorkspaceScreen({
  messages,
  onSend,
  advanced,
  onToggleAdvanced,
  showCode,
  onToggleCode,
  canSend,
  onSendBox,
  example
}) {
  const [draft, setDraft] = useState('');
  const send = () => {
    if (draft.trim()) {
      onSend(draft.trim());
      setDraft('');
    }
  };
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flex: 1,
      minHeight: 0
    }
  }, advanced ? /*#__PURE__*/React.createElement(RoleRail, {
    active: "wands",
    items: [{
      id: 'wands',
      label: 'Wands',
      icon: 'wand'
    }, {
      id: 'stations',
      label: 'Stations',
      icon: 'gamepad',
      disabled: true
    }]
  }) : null, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: '0 0 auto',
      width: 340,
      minWidth: 260,
      display: 'flex',
      flexDirection: 'column',
      minHeight: 0,
      borderRight: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minHeight: 0,
      overflow: 'auto',
      padding: 14,
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, messages.map((m, i) => /*#__PURE__*/React.createElement(ChatMessage, {
    key: i,
    role: m.role
  }, m.pending ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(ThinkingDots, null), "thinking\u2026") : m.text)), messages.length <= 1 ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 8,
      padding: '4px 0 8px'
    }
  }, /*#__PURE__*/React.createElement(StarterChip, {
    icon: "rainbow",
    onClick: () => onSend('a game where shaking makes a rainbow')
  }, "a game where shaking makes a rainbow"), /*#__PURE__*/React.createElement(StarterChip, {
    icon: "music",
    onClick: () => onSend('tap tags to play a tune')
  }, "tap tags to play a tune")) : null), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      padding: '12px 14px',
      borderTop: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement(ChatInput, {
    placeholder: "type a request\u2026",
    value: draft,
    onChange: e => setDraft(e.target.value),
    onKeyDown: e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    }
  }), /*#__PURE__*/React.createElement(SendButton, {
    onClick: send
  }))), /*#__PURE__*/React.createElement(PaneResizer, null), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      minWidth: 180,
      minHeight: 0,
      background: canSend ? '#fff' : 'var(--pattern-stripe)'
    }
  }, canSend ? /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 12,
      padding: 16,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/wand/WAND_FRONT.svg",
    style: {
      maxHeight: 260
    },
    alt: "Wand simulator"
  }), /*#__PURE__*/React.createElement("p", {
    style: {
      font: "13px 'Nunito'",
      color: 'var(--muted)',
      textAlign: 'center',
      margin: 0,
      maxWidth: 320
    }
  }, example ? example.hint : 'Shake to fill the lights. Press the button to reset.'), /*#__PURE__*/React.createElement("img", {
    src: "../../assets/gestures/shake_left_right.svg",
    style: {
      width: 110
    },
    alt: ""
  })) : /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 14,
      color: '#c9a3bd'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "wand",
    size: 46,
    strokeWidth: 1.3
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      font: '12px ui-monospace, monospace'
    }
  }, "wand preview"))), showCode ? /*#__PURE__*/React.createElement("div", {
    style: {
      width: 380,
      background: '#fff',
      display: 'flex',
      flexDirection: 'column',
      borderLeft: '1px solid var(--border)',
      boxShadow: 'var(--shadow-drawer)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '14px 20px',
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: "800 14px 'Nunito'"
    }
  }, "</> generated code"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: "700 12px 'Nunito'",
      color: 'var(--muted)'
    }
  }, "v2/2"), /*#__PURE__*/React.createElement(IconButton, {
    icon: "download",
    title: "Download"
  }), /*#__PURE__*/React.createElement("button", {
    onClick: onToggleCode,
    style: {
      background: 'none',
      border: 'none',
      color: 'var(--muted)',
      cursor: 'pointer',
      display: 'inline-flex'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "close",
    size: 18
  })))), /*#__PURE__*/React.createElement("pre", {
    style: {
      flex: 1,
      margin: 0,
      overflow: 'auto',
      padding: '12px 16px',
      font: "12.5px/1.55 'SF Mono', Consolas, monospace",
      color: 'var(--code-text)',
      background: 'var(--code-bg)'
    }
  }, window.WSC_SAMPLE_CODE)) : null), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      padding: '12px 20px',
      borderTop: '1px solid var(--border)',
      alignItems: 'center',
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(IconButton, {
    icon: "save",
    title: "Save"
  }), /*#__PURE__*/React.createElement(IconButton, {
    glyph: "</>",
    title: "Show code",
    active: showCode,
    onClick: onToggleCode
  }), /*#__PURE__*/React.createElement(IconButton, {
    icon: "wrench",
    title: "Switch to advanced mode",
    active: advanced,
    onClick: onToggleAdvanced
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto'
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "send",
    disabled: !canSend,
    onClick: onSendBox
  }, "Send to Box \u2192"))));
}
Object.assign(window, {
  Shell,
  HeaderBar,
  SplashScreen,
  GalleryScreen,
  DetailScreen,
  WorkspaceScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/wand-station-coder/Screens.jsx", error: String((e && e.message) || e) }); }

// ui_kits/wand-station-coder/data.js
try { (() => {
/* Content lifted from ChatBroadcast/js/examples.js — real names, descriptions and tag notes. */
window.WSC_EXAMPLES = [{
  id: 'melody',
  name: 'Melody',
  icon: 'music',
  category: 'sound',
  description: 'Tap each note-tag to play a tune.',
  tagNote: '8 NFC tags',
  hint: 'Tap the note tags to build a tune, then press the button to play it back.',
  tags: ['note_c', 'note_d', 'note_e', 'note_f', 'note_g', 'note_a', 'note_b', 'note_c_high']
}, {
  id: 'freezedance',
  name: 'Freeze Dance',
  icon: 'snowflake',
  category: 'color',
  description: 'Move, then freeze when the music stops.',
  tagNote: null,
  hint: 'Shake while the lights dance — freeze when they turn white!',
  tags: ['freezedance']
}, {
  id: 'rainbow',
  name: 'Rainbow',
  icon: 'rainbow',
  category: 'color',
  description: 'Shake for color.',
  tagNote: null,
  hint: 'Shake for a new color. Press the button to reset to white.',
  tags: ['rainbow']
}, {
  id: 'shakerainbow',
  name: 'Shake Rainbow',
  icon: 'rainbow',
  category: 'color',
  description: 'Shake harder to climb through rainbow colors.',
  tagNote: null,
  hint: 'Shake harder to climb to the next color — your best shake sticks. Press the button to reset.',
  tags: ['shakerainbow']
}, {
  id: 'jump',
  name: 'Jump',
  icon: 'arrow-up',
  category: 'color',
  description: 'Jump (freefall) to light more LEDs on the matrix.',
  tagNote: null,
  hint: 'Jump to light one more LED. Press the button to reset.',
  tags: ['jump']
}, {
  id: 'cooking',
  name: 'Cooking',
  icon: 'chef-hat',
  category: 'multi',
  description: 'Recipe steps with ingredient tags.',
  tagNote: 'Multi-tag',
  hint: 'Tap the ingredient tags in recipe order. Press the button to start over.',
  tags: ['flour', 'egg', 'milk', 'butter', 'sugar']
}, {
  id: 'jumpin',
  name: 'Jump In',
  icon: 'brain-circuit',
  category: 'color',
  description: 'Simple jump game — great first project.',
  tagNote: null,
  hint: 'Shake to fill the lights. Press the button to reset.',
  tags: ['jumpin']
}];
window.WSC_CATEGORIES = [{
  id: 'all',
  label: 'All',
  icon: null
}, {
  id: 'sound',
  label: 'Sound',
  icon: 'music'
}, {
  id: 'color',
  label: 'Color',
  icon: 'palette'
}, {
  id: 'multi',
  label: 'Multi-tag',
  icon: 'tag'
}];
window.WSC_SAMPLE_CODE = `"""
Jump In — shake to light the wand
=================================
Shake the wand to fill the LED matrix with color. Press the button to reset.
"""

import time, math
from machine import Pin
from leds import RED, GREEN, BLUE, YELLOW, PURPLE, PINK

SHAKE_THRESHOLD = 1.4
PICK = [RED, GREEN, BLUE, YELLOW, PURPLE, PINK]


def play(nfc, leds, buz, accel, i2c, enow):
    buz.beep(523, 80)
    level = 0
    while True:
        x, y, z = accel.read()
        if math.sqrt(x*x + y*y + z*z) > SHAKE_THRESHOLD:
            level = min(25, level + 1)
            leds.fill(PICK[level % len(PICK)])
            buz.beep(600, 40)
        time.sleep_ms(50)`;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/wand-station-coder/data.js", error: String((e && e.message) || e) }); }

__ds_ns.ChatMessage = __ds_scope.ChatMessage;

__ds_ns.ThinkingDots = __ds_scope.ThinkingDots;

__ds_ns.CodeBlock = __ds_scope.CodeBlock;

__ds_ns.BrandMark = __ds_scope.BrandMark;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Chip = __ds_scope.Chip;

__ds_ns.StarterChip = __ds_scope.StarterChip;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.SendButton = __ds_scope.SendButton;

__ds_ns.ModePill = __ds_scope.ModePill;

__ds_ns.ConnChip = __ds_scope.ConnChip;

__ds_ns.SsidChip = __ds_scope.SsidChip;

__ds_ns.TagBadge = __ds_scope.TagBadge;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.ConnectToast = __ds_scope.ConnectToast;

__ds_ns.SentBanner = __ds_scope.SentBanner;

__ds_ns.ProgressBar = __ds_scope.ProgressBar;

__ds_ns.TagBars = __ds_scope.TagBars;

__ds_ns.TagRow = __ds_scope.TagRow;

__ds_ns.RequirementRow = __ds_scope.RequirementRow;

__ds_ns.TextField = __ds_scope.TextField;

__ds_ns.SearchInput = __ds_scope.SearchInput;

__ds_ns.ChatInput = __ds_scope.ChatInput;

__ds_ns.ICON_PATHS = __ds_scope.ICON_PATHS;

__ds_ns.ICON_NAMES = __ds_scope.ICON_NAMES;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.AppHeader = __ds_scope.AppHeader;

__ds_ns.TabBar = __ds_scope.TabBar;

__ds_ns.RoleRail = __ds_scope.RoleRail;

__ds_ns.PaneResizer = __ds_scope.PaneResizer;

__ds_ns.ViewPanel = __ds_scope.ViewPanel;

__ds_ns.SplashCard = __ds_scope.SplashCard;

__ds_ns.ExampleCard = __ds_scope.ExampleCard;

__ds_ns.CardActionButton = __ds_scope.CardActionButton;

__ds_ns.OverlayCard = __ds_scope.OverlayCard;

__ds_ns.OverlayScrim = __ds_scope.OverlayScrim;

})();
