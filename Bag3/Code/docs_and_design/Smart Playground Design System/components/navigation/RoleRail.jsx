import React from 'react';
import { Icon } from '../icons/Icon.jsx';

/** Left rail in advanced mode: which device you are coding for. */
export function RoleRail({ items, active, onSelect, style }) {
  return (
    <div style={{
      width: '88px', borderRight: '1px solid var(--border)', padding: '14px 8px',
      display: 'flex', flexDirection: 'column', gap: '8px', flex: 'none', ...style,
    }}>
      {items.map((it) => {
        const on = it.id === active;
        return (
          <div key={it.id} role="button" onClick={() => !it.disabled && onSelect && onSelect(it.id)}
            title={it.disabled ? 'Coming later' : it.label}
            style={{
              borderRadius: '10px', padding: '10px 6px', textAlign: 'center',
              font: "700 11px 'Nunito'", display: 'flex', flexDirection: 'column',
              alignItems: 'center', gap: '4px', cursor: it.disabled ? 'default' : 'pointer',
              ...(on ? { background: '#fff0f6', borderLeft: '3px solid var(--pink)', color: 'var(--pink-dark)' } : { color: 'var(--ink)' }),
              ...(it.disabled ? { color: '#a8a4b5', opacity: 0.7 } : null),
            }}>
            <Icon name={it.icon} size={18} />{it.label}
          </div>
        );
      })}
    </div>
  );
}

/** Draggable column divider between chat and preview. */
export function PaneResizer({ vertical = true, style }) {
  return <div role="separator" aria-orientation={vertical ? 'vertical' : 'horizontal'} tabIndex={0} style={{
    flex: 'none', width: '10px', margin: '0 -5px', position: 'relative', zIndex: 1,
    cursor: 'col-resize', background: 'transparent', ...style,
  }}>
    <div style={{ position: 'absolute', top: 0, bottom: 0, left: '4px', width: '2px', background: 'var(--border)', borderRadius: '2px' }} />
  </div>;
}
