import React from 'react';
import { Icon } from '../icons/Icon.jsx';

const base = {
  border: 'none', cursor: 'pointer', textAlign: 'center',
  fontFamily: "'Nunito', sans-serif", display: 'inline-flex',
  alignItems: 'center', justifyContent: 'center', gap: '8px',
};

const variants = {
  primary: {
    padding: '12px', borderRadius: '14px', background: 'var(--grad-pink)',
    color: '#fff', font: "800 14px 'Nunito'",
  },
  secondary: {
    padding: '11px', borderRadius: '14px', border: '1.5px solid var(--border)',
    background: '#fff', font: "700 13px 'Nunito'", color: 'var(--icon-ink)',
  },
  teal: {
    padding: '12px', borderRadius: '14px', background: 'var(--grad-teal)',
    color: '#fff', font: "800 14px 'Nunito'",
  },
  connect: {
    padding: '7px 14px', borderRadius: '14px', background: 'var(--grad-teal)',
    color: '#fff', font: "800 12px 'Nunito'",
  },
  send: {
    padding: '9px 20px', borderRadius: '16px', background: 'var(--grad-pink)',
    color: '#fff', font: "800 13px 'Nunito'",
  },
};

const compact = { width: 'auto', padding: '7px 12px', borderRadius: '12px', font: "700 11px 'Nunito'" };

/** The product's filled/outline actions. Full-width by default inside overlays. */
export function Button({
  variant = 'primary', size = 'default', icon, iconAfter, fullWidth,
  disabled, connected, children, style, ...rest
}) {
  const s = { ...base, ...variants[variant] };
  if (size === 'compact') Object.assign(s, compact);
  if (fullWidth) s.width = '100%';
  if (variant === 'connect' && connected) s.background = 'var(--grad-muted)';
  if (disabled) {
    s.cursor = 'not-allowed';
    if (variant === 'primary' || variant === 'send') {
      s.background = 'var(--disabled-fill)'; s.color = '#fff'; s.boxShadow = 'none';
    } else { s.opacity = 0.7; }
  }
  return (
    <button type="button" disabled={disabled} style={{ ...s, ...style }} {...rest}>
      {icon ? <Icon name={icon} size={variant === 'connect' || variant === 'send' ? 14 : 16} /> : null}
      {children}
      {iconAfter ? <Icon name={iconAfter} size={16} /> : null}
    </button>
  );
}
