import React from 'react';
import { Icon } from '../icons/Icon.jsx';

/** Labelled text input as used in the send-confirm overlay (centred, pencil affordance). */
export function TextField({ label, pencil, error, centered = true, style, ...rest }) {
  return (
    <div style={{ textAlign: 'left', ...style }}>
      {label ? (
        <label style={{
          display: 'block', font: "700 11px 'Nunito'", letterSpacing: '.04em',
          textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '6px',
        }}>{label}</label>
      ) : null}
      <div style={{ position: 'relative', marginBottom: '12px' }}>
        <input style={{
          width: '100%', boxSizing: 'border-box', padding: pencil ? '10px 34px 10px 12px' : '10px 12px',
          border: '1.5px solid var(--border)', borderRadius: '10px', background: '#fafafd',
          font: "700 15px 'Nunito'", textAlign: centered ? 'center' : 'left',
        }} {...rest} />
        {pencil ? (
          <span style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)', pointerEvents: 'none' }}>
            <Icon name="pencil" size={15} />
          </span>
        ) : null}
      </div>
      {error ? <p style={{ color: '#c0392b', font: "13px 'Nunito'", minHeight: '1.2em', margin: 0 }}>{error}</p> : null}
    </div>
  );
}

/** Gallery search box. */
export function SearchInput({ style, ...rest }) {
  return (
    <input type="search" style={{
      border: '1.5px solid var(--border)', borderRadius: '10px', padding: '9px 14px',
      font: "14px 'Nunito'", width: '220px', ...style,
    }} {...rest} />
  );
}

/** Auto-height chat composer field. */
export function ChatInput({ style, ...rest }) {
  return (
    <textarea rows={1} style={{
      flex: 1, border: '1.5px solid var(--border)', borderRadius: '20px',
      padding: '8px 14px', font: "13px 'Nunito'", resize: 'none', height: '38px', ...style,
    }} {...rest} />
  );
}
