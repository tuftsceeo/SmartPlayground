import React from 'react';

/** The app's identity block: gradient rounded square holding a ✦, then the product name.
 *  There is no logo file in the source — this gradient gem IS the mark. */
export function BrandMark({ size = 'header', title = 'Wand & Station Coder', showTitle = true, style }) {
  const gem = size === 'splash'
    ? { width: 96, height: 96, borderRadius: 28, fontSize: 44, boxShadow: 'var(--shadow-pink-lg)' }
    : { width: 30, height: 30, borderRadius: 9, fontSize: 15 };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 'none', flexDirection: size === 'splash' ? 'column' : 'row', ...style }}>
      <div style={{
        ...gem, background: 'var(--grad-gem)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', color: '#fff', flex: 'none',
      }}>✦</div>
      {showTitle ? (
        <div style={size === 'splash'
          ? { font: "900 34px 'Nunito'", marginTop: '22px', color: 'var(--ink)' }
          : { font: "800 14px 'Nunito'", color: 'var(--ink)' }}>{title}</div>
      ) : null}
    </div>
  );
}
