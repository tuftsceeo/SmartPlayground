import React from 'react';

const shells = {
  user: {
    alignSelf: 'flex-end', background: 'linear-gradient(135deg, #fff0f6, #ffe3f0)',
    color: '#a8265c', whiteSpace: 'pre-wrap', borderRadius: '14px 14px 3px 14px', maxWidth: '88%',
  },
  system: {
    alignSelf: 'flex-start', background: '#f4f2fa', color: '#5b5468', whiteSpace: 'pre-wrap',
    borderRadius: '14px 14px 14px 3px', fontSize: '12px', maxWidth: '88%',
  },
  bot: {
    alignSelf: 'flex-start', background: '#fff', color: '#3a3345', maxWidth: '95%',
    border: '1px solid var(--border)', borderRadius: '14px 14px 14px 3px',
  },
};

/** Chat bubble. Pastel pink gradient for the teacher, white outline for the assistant. */
export function ChatMessage({ role = 'bot', children, style }) {
  return <div style={{
    borderRadius: '14px', padding: '9px 13px', font: "13px/1.45 'Nunito'",
    ...shells[role], ...style,
  }}>{children}</div>;
}

/** Three pink dots shown while the assistant is composing. */
export function ThinkingDots({ style }) {
  return (
    <span style={{ display: 'inline-flex', gap: '3px', marginRight: '4px', verticalAlign: 'middle', ...style }}>
      {[0, 0.2, 0.4].map((d, i) => (
        <span key={i} style={{
          display: 'inline-block', width: '5px', height: '5px', background: 'var(--pink)',
          borderRadius: '50%', animation: `sp-thinking-blink 1.2s infinite ${d}s`,
        }} />
      ))}
    </span>
  );
}

/** Fenced code block with a mono title bar and Copy/Use actions. */
export function CodeBlock({ language = 'python', actions, children, style }) {
  return (
    <div style={{
      background: 'var(--code-bg)', border: '1px solid var(--border)', borderRadius: '12px',
      overflow: 'hidden', margin: '0.6em 0', ...style,
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 10px',
        background: '#f4f2fa', borderBottom: '1px solid var(--border)',
        font: '11px ui-monospace, monospace', color: 'var(--muted)',
      }}><span>{language}</span><span style={{ display: 'flex', gap: '6px' }}>{actions}</span></div>
      <pre style={{
        padding: '10px 12px', overflowX: 'auto', maxHeight: '320px', margin: 0,
        fontFamily: '"SF Mono", Consolas, monospace', fontSize: '12.5px',
        lineHeight: 1.55, color: 'var(--code-text)',
      }}>{children}</pre>
    </div>
  );
}
