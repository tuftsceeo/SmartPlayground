import React from 'react';
import { Icon } from '../icons/Icon.jsx';

const tones = {
  serve: { background: 'var(--serve-bg)', color: 'var(--serve-fg)' },
  write: { background: 'var(--write-bg)', color: 'var(--write-fg)' },
  muted: { background: '#f4f2fa', color: 'var(--muted)' },
};

/** Box mode pill in the header: "Code Server" / "Tag Writing" / disabled "Box". */
export function ModePill({ tone = 'muted', icon = 'box', children, style, ...rest }) {
  return (
    <button type="button" disabled={tone === 'muted'} style={{
      border: 'none', font: "800 12px 'Nunito'", padding: '7px 12px', borderRadius: '14px',
      cursor: tone === 'muted' ? 'default' : 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
      opacity: tone === 'muted' ? 0.85 : 1, ...tones[tone], ...style,
    }} {...rest}>
      <Icon name={icon} size={14} />{children}
    </button>
  );
}

const connTones = {
  error: { color: '#c0392b', background: '#fdecea' },
  sending: { color: '#b36b00', background: '#fff6e5' },
  repl: { color: 'var(--purple)', background: 'var(--write-bg)' },
};

/** Connection state chip — a filled dot in currentColor, then the state text. */
export function ConnChip({ tone = 'error', children, style, ...rest }) {
  return (
    <span style={{
      font: "700 11px 'Nunito'", borderRadius: '12px', padding: '5px 10px',
      display: 'inline-flex', alignItems: 'center', gap: '6px', ...connTones[tone], ...style,
    }} {...rest}>
      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'currentColor', flex: 'none' }} />
      {children}
    </span>
  );
}

/** Monospace network chip showing which Wi-Fi the wands should join. */
export function SsidChip({ children, style, ...rest }) {
  return (
    <span style={{
      display: 'flex', alignItems: 'center', gap: '5px', background: 'var(--write-bg)',
      color: 'var(--write-fg)', font: '700 11px ui-monospace, monospace',
      padding: '5px 10px', borderRadius: '12px', ...style,
    }} {...rest}><Icon name="wifi" size={12} />{children}</span>
  );
}

/** Amber "needs tags" note under a gallery card. */
export function TagBadge({ children, style, ...rest }) {
  return (
    <span style={{
      font: "700 11px 'Nunito'", color: '#a8781e', background: '#fff8e0',
      borderRadius: '8px', padding: '3px 8px', width: 'fit-content', ...style,
    }} {...rest}>{children}</span>
  );
}
