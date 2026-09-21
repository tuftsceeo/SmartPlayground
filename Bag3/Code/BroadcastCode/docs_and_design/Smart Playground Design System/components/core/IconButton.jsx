import React from 'react';
import { Icon } from '../icons/Icon.jsx';

/** Square outline button holding a single glyph — the workspace footer tools. */
export function IconButton({ icon, glyph, active, size = 15, title, style, ...rest }) {
  const s = {
    border: '1.5px solid var(--border)', background: '#fff', borderRadius: '14px',
    padding: '8px 10px', cursor: 'pointer', color: 'var(--icon-ink)',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  };
  if (active) Object.assign(s, { background: 'var(--tab-active-bg)', color: 'var(--tab-active-fg)', borderColor: 'transparent' });
  return (
    <button type="button" title={title} style={{ ...s, ...style }} {...rest}>
      {glyph ? <span style={{ font: "800 12px ui-monospace, monospace", lineHeight: 1 }}>{glyph}</span> : <Icon name={icon} size={size} />}
    </button>
  );
}

/** The round pink send button in the chat composer. */
export function SendButton({ style, ...rest }) {
  return (
    <button type="button" title="Send" style={{
      width: '38px', height: '38px', borderRadius: '50%', background: 'var(--pink)',
      color: '#fff', border: 'none', cursor: 'pointer', flex: 'none',
      display: 'flex', alignItems: 'center', justifyContent: 'center', ...style,
    }} {...rest}><Icon name="send" size={16} /></button>
  );
}
