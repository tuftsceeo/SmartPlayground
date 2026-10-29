import React from 'react';
import { Icon } from '../icons/Icon.jsx';

/** Gallery filter chip. Active state is solid ink, not a tint. */
export function Chip({ icon, active, children, style, ...rest }) {
  return (
    <button type="button" style={{
      font: "700 13px 'Nunito'", padding: '7px 16px', borderRadius: '20px',
      cursor: 'pointer', border: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px',
      background: active ? 'var(--ink)' : '#f4f2fa',
      color: active ? '#fff' : 'var(--ink)', ...style,
    }} {...rest}>
      {icon ? <Icon name={icon} size={14} /> : null}{children}
    </button>
  );
}

/** Suggestion chip offered above the empty chat composer. */
export function StarterChip({ icon, children, style, ...rest }) {
  return (
    <button type="button" style={{
      font: "700 12px 'Nunito'", padding: '8px 12px', borderRadius: '14px',
      border: '1.5px solid var(--border)', background: '#fff', color: 'var(--ink)',
      cursor: 'pointer', textAlign: 'left', maxWidth: '100%',
      display: 'inline-flex', alignItems: 'center', gap: '6px', ...style,
    }} {...rest}>
      {icon ? <Icon name={icon} size={14} /> : null}{children}
    </button>
  );
}
