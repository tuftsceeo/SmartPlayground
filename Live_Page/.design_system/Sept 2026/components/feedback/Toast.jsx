import React from 'react';
import { Icon } from '../icons/Icon.jsx';

/** Bottom-centre ink toast. `error` turns it red. */
export function Toast({ error, children, style }) {
  return <div style={{
    position: 'absolute', bottom: '24px', left: '50%', transform: 'translateX(-50%)',
    background: error ? '#c0392b' : 'var(--ink)', color: '#fff', padding: '12px 20px',
    borderRadius: '12px', font: "700 13px 'Nunito'", zIndex: 300, maxWidth: '90vw', ...style,
  }}>{children}</div>;
}

/** Top-right transient with a spinner — used while the browser device picker is open. */
export function ConnectToast({ children, style }) {
  return <div style={{
    position: 'absolute', top: '60px', right: '20px', background: 'var(--ink)', color: '#fff',
    font: "700 12px 'Nunito'", padding: '9px 16px', borderRadius: '12px', display: 'flex',
    alignItems: 'center', gap: '8px', zIndex: 310, animation: 'sp-pop 0.15s ease', ...style,
  }}>
    <span style={{ display: 'flex', animation: 'sp-spin 1s linear infinite' }}><Icon name="spinner" size={14} /></span>
    {children}
  </div>;
}

/** Teal success banner pinned to the top of the shell after a successful send. */
export function SentBanner({ children, style }) {
  return <div style={{
    position: 'absolute', top: '24px', left: '50%', transform: 'translateX(-50%)',
    background: 'var(--grad-teal)', color: '#fff', padding: '12px 20px', borderRadius: '14px',
    font: "800 14px 'Nunito'", zIndex: 250, display: 'flex', alignItems: 'center', gap: '8px', ...style,
  }}><Icon name="circle-check" size={16} />{children}</div>;
}

/** Thin teal progress track shown while writing to the Box. */
export function ProgressBar({ value = 0, label, style }) {
  return (
    <div style={{ margin: '12px 0', ...style }}>
      <div style={{ height: '8px', background: '#eee', borderRadius: '5px', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${value}%`, background: 'var(--teal)', transition: 'width 0.2s' }} />
      </div>
      {label ? <p style={{ font: "13px 'Nunito'", color: 'var(--muted)', margin: '6px 0 0' }}>{label}</p> : null}
    </div>
  );
}

/** Segmented bars at the top of the tag checklist — one segment per tag. */
export function TagBars({ total, done, style }) {
  return <div style={{ display: 'flex', gap: '6px', marginBottom: '18px', ...style }}>
    {Array.from({ length: total }).map((_, i) => (
      <div key={i} style={{ flex: 1, height: '8px', borderRadius: '5px', background: i < done ? 'var(--pink)' : '#eee' }} />
    ))}
  </div>;
}

/** One tag in the checklist. next = amber, done = mint. */
export function TagRow({ state = 'idle', name, status, style }) {
  const bg = state === 'next' ? '#fff8e0' : state === 'done' ? '#f7fefb' : '#fafafd';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '10px', padding: '11px 12px', borderRadius: '12px',
      background: bg, marginBottom: '8px', font: "700 13px 'Nunito'", color: 'var(--ink)', ...style,
    }}>
      <Icon name={state === 'done' ? 'check' : 'nfcCard'} size={15} color={state === 'done' ? 'var(--teal)' : 'var(--icon-ink)'} />
      <span style={{ flex: 1 }}>{name}</span>
      <span style={{ font: "700 11px 'Nunito'", color: state === 'done' ? 'var(--teal)' : 'var(--muted)' }}>{status}</span>
    </div>
  );
}

/** Row in the send-confirm "what this game needs" list. */
export function RequirementRow({ icon, children, style }) {
  return <li style={{
    display: 'flex', alignItems: 'center', gap: '9px', padding: '8px 11px', borderRadius: '10px',
    background: '#fafafd', font: "700 12.5px 'Nunito'", color: 'var(--ink)', ...style,
  }}><Icon name={icon} size={15} color="var(--pink)" />{children}</li>;
}
