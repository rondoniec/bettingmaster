// Primitives shared across the kit. Attaches to window so other Babel scripts see them.
const { useState } = React;

// Lucide-ish inline SVG icons
const Icon = ({ d, size = 16, stroke = 'currentColor', className = '', extra }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke}
       strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className={className}>
    {typeof d === 'string' ? <path d={d}/> : d}
    {extra}
  </svg>
);
const TrendingUp = (p) => <Icon {...p} d={<><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></>} />;
const Search = (p) => <Icon {...p} d={<><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></>} />;
const Activity = (p) => <Icon {...p} d="M22 12h-4l-3 9L9 3l-3 9H2"/>;
const ExternalLink = (p) => <Icon {...p} d={<><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></>} />;
const ArrowRight = (p) => <Icon {...p} d={<><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></>} />;
const ChevronRight = (p) => <Icon {...p} d={<><polyline points="9 18 15 12 9 6"/></>} />;

// Slate-only label, no funky colors
const Kicker = ({ children, color = '#64748b', style }) => (
  <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.14em', color, fontFamily: 'var(--mono)', ...style }}>{children}</div>
);

// Plain inline link styled like a menu item
const NavLink = ({ active, children, onClick }) => (
  <a onClick={onClick} style={{
    fontSize: 13, fontWeight: 500, color: active ? '#0f172a' : '#64748b',
    textDecoration: 'none', cursor: 'pointer', padding: '6px 0',
    borderBottom: active ? '2px solid #0f172a' : '2px solid transparent',
  }}>{children}</a>
);

// Underline tab — replaces capsule pills everywhere
const Tab = ({ active, children, onClick, tone = 'slate' }) => {
  const activeColor = tone === 'emerald' ? '#047857' : '#0f172a';
  return (
    <button onClick={onClick} style={{
      background: 'transparent', border: 'none', padding: '8px 0', margin: 0,
      fontFamily: 'inherit', fontSize: 13, fontWeight: active ? 600 : 500,
      color: active ? activeColor : '#64748b', cursor: 'pointer',
      borderBottom: active ? `2px solid ${activeColor}` : '2px solid transparent',
      letterSpacing: '-0.005em',
    }}>{children}</button>
  );
};

// Bookmaker brand map
const BOOKMAKERS = {
  fortuna:    { displayName: 'Fortuna',    color: '#17171b', bgColor: '#ffdb01' },
  nike:       { displayName: 'Niké',       color: '#ff8000', bgColor: '#0d0d0d' },
  doxxbet:    { displayName: 'DOXXbet',    color: '#f31537', bgColor: '#272727' },
  tipsport:   { displayName: 'Tipsport',   color: '#ff8e13', bgColor: '#167be8' },
  tipos:      { displayName: 'Tipos',      color: '#ffffff', bgColor: '#e30613' },
  polymarket: { displayName: 'Polymarket', color: '#2d9cdb', bgColor: '#0d1117' },
};
const BOOKMAKER_ORDER = ['fortuna','nike','doxxbet','tipsport','tipos','polymarket'];

// Bookmaker chip — neutral, with a tiny brand-colored dot. Logos no longer dominate.
const BookmakerChip = ({ bookmaker, size = 'sm' }) => {
  const d = BOOKMAKERS[bookmaker];
  if (!d) return null;
  const padY = size === 'sm' ? 2 : 4;
  const padX = size === 'sm' ? 6 : 10;
  const fs = size === 'sm' ? 10 : 11;
  // Use the brand bg as a small marker dot; main chip is monochrome slate
  const dot = d.bgColor === '#ffffff' ? d.color : d.bgColor;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: '#f8fafc', color: '#334155',
      border: '1px solid #e2e8f0',
      padding: `${padY}px ${padX}px`, borderRadius: 3,
      fontSize: fs, fontWeight: 500, letterSpacing: '0.01em',
      fontFamily: 'var(--sans)',
    }}>
      <span style={{ width: 6, height: 6, background: dot, borderRadius: '50%', display: 'inline-block', flexShrink: 0 }} />
      {d.displayName}
    </span>
  );
};

// Bookmaker text token — for inline mentions in tables
const BookmakerName = ({ bookmaker }) => {
  const d = BOOKMAKERS[bookmaker];
  if (!d) return null;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#0f172a', fontWeight: 500 }}>
      <span style={{ width: 8, height: 8, background: d.bgColor, borderRadius: 2, display: 'inline-block' }} />
      {d.displayName}
    </span>
  );
};

const formatOdds = (n) => (n == null ? '—' : n.toFixed(2));
const formatMargin = (m) => `${m >= 0 ? '+' : ''}${m.toFixed(2)}%`;

// Margin tone — only emerald (negative = surebet) vs neutral
const marginTone = (m) =>
  m < 0 ? { bg: '#ecfdf5', fg: '#047857', border: '#a7f3d0' }
        : { bg: '#f8fafc', fg: '#475569', border: '#e2e8f0' };

Object.assign(window, {
  Icon, TrendingUp, Search, Activity, ExternalLink, ArrowRight, ChevronRight,
  Kicker, NavLink, Tab,
  BOOKMAKERS, BOOKMAKER_ORDER, BookmakerChip, BookmakerName,
  formatOdds, formatMargin, marginTone,
});
