import React from 'react';
import { BrandMark } from '../core/BrandMark.jsx';

/** Top bar of every view: brand, pill tabs, then right-aligned status + connect. */
export function AppHeader({ title, tabs, active, onTab, children, style }) {
  return (
    <header style={{
      display: 'flex', alignItems: 'center', gap: '10px', padding: '14px 20px',
      borderBottom: '1px solid var(--border)', flex: 'none', ...style,
    }}>
      <BrandMark title={title} />
      {tabs ? <TabBar tabs={tabs} active={active} onSelect={onTab} /> : null}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>{children}</div>
    </header>
  );
}

/** Pill tabs. Active is a pink tint, never an underline. */
export function TabBar({ tabs, active, onSelect, style }) {
  return (
    <nav aria-label="Main" style={{ display: 'flex', gap: '6px', marginLeft: '10px', ...style }}>
      {tabs.map((t) => {
        const on = t.id === active;
        return (
          <button key={t.id} type="button" onClick={() => onSelect && onSelect(t.id)} style={{
            border: 'none', font: "700 12px 'Nunito'", padding: '6px 12px', borderRadius: '20px',
            cursor: 'pointer',
            background: on ? 'var(--tab-active-bg)' : 'transparent',
            color: on ? 'var(--tab-active-fg)' : 'var(--muted)',
          }}>{t.label}</button>
        );
      })}
    </nav>
  );
}
