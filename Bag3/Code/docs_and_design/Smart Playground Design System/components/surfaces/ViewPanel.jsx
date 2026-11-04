import React from 'react';
import { Icon } from '../icons/Icon.jsx';

/** The white rounded shell every full view sits inside. */
export function ViewPanel({ children, style }) {
  return <div style={{
    background: '#fff', borderRadius: '24px', boxShadow: 'var(--shadow-shell)',
    overflow: 'hidden', display: 'flex', flexDirection: 'column',
    flex: 1, minHeight: 0, position: 'relative', ...style,
  }}>{children}</div>;
}

/** Big choice card on the splash screen. One card per screen may be `primary`. */
export function SplashCard({ icon, title, blurb, primary, style, ...rest }) {
  return (
    <div role="button" tabIndex={0} style={{
      width: '220px', padding: '20px 16px', borderRadius: '16px', textAlign: 'center',
      cursor: 'pointer',
      ...(primary
        ? { border: 'none', background: 'var(--grad-pink)', color: '#fff', boxShadow: 'var(--shadow-pink)' }
        : { border: '2px solid var(--border)', background: '#fff' }),
      ...style,
    }} {...rest}>
      <div style={{ display: 'flex', justifyContent: 'center', color: primary ? '#fff' : 'var(--pink)' }}>
        <Icon name={icon} size={26} />
      </div>
      <h3 style={{ font: "800 15px 'Nunito'", margin: '8px 0 2px' }}>{title}</h3>
      <p style={{ font: "12px 'Nunito'", margin: 0, opacity: 0.85 }}>{blurb}</p>
    </div>
  );
}

/** Game card in the gallery grid. */
export function ExampleCard({ icon, name, description, badge, actions, onOpen, style }) {
  return (
    <div onClick={onOpen} style={{
      border: '1.5px solid var(--border)', borderRadius: '16px', padding: '14px',
      cursor: 'pointer', position: 'relative', background: '#fff', ...style,
    }}>
      <div style={{
        height: '64px', borderRadius: '10px', background: '#fff0f6', display: 'flex',
        alignItems: 'center', justifyContent: 'center', color: '#e9a9c6', marginBottom: '10px',
      }}><Icon name={icon} size={28} /></div>
      <h3 style={{ font: "800 13px 'Nunito'", margin: '0 0 2px', color: 'var(--ink)' }}>{name}</h3>
      <p style={{ font: "11px 'Nunito'", color: 'var(--muted)', margin: '0 0 10px' }}>{description}</p>
      {actions ? <div style={{ display: 'flex', gap: '6px' }}>{actions}</div> : null}
      {badge ? <div style={{
        font: "700 11px 'Nunito'", color: '#a8781e', background: '#fff8e0',
        borderRadius: '8px', padding: '3px 8px', width: 'fit-content', marginTop: '8px',
      }}>{badge}</div> : null}
    </div>
  );
}

/** Small outline action inside a gallery card (rename, delete, open). */
export function CardActionButton({ icon, danger, children, style, ...rest }) {
  return (
    <button type="button" style={{
      borderRadius: '9px', padding: '6px 9px', cursor: 'pointer',
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      ...(danger
        ? { border: 'none', background: '#fdecea', color: '#c0392b', font: "700 11px 'Nunito'" }
        : { border: '1.5px solid var(--border)', background: '#fff', color: 'var(--icon-ink)' }),
      ...style,
    }} {...rest}>{icon ? <Icon name={icon} size={13} /> : null}{children}</button>
  );
}

/** Modal card floating over the scrim. */
export function OverlayCard({ width = 380, align = 'center', children, style }) {
  return (
    <div style={{
      background: '#fff', borderRadius: '20px', padding: '24px', width: '100%',
      maxWidth: width + 'px', boxShadow: 'var(--shadow-overlay)', textAlign: align, ...style,
    }}>{children}</div>
  );
}

/** Fixed full-bleed scrim with blur-free 35% ink wash. */
export function OverlayScrim({ children, style }) {
  return <div style={{
    position: 'absolute', inset: 0, background: 'var(--scrim)', display: 'flex',
    alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: '16px', ...style,
  }}>{children}</div>;
}
