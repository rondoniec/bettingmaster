function Header({ onSearch }) {
  const [q, setQ] = useState('');
  return (
    <header style={{
      position: 'sticky', top: 0, zIndex: 50,
      borderBottom: '1px solid #e2e8f0', background: '#ffffff',
    }}>
      <div style={{ maxWidth: 1280, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 24, padding: '14px 24px' }}>
        {/* Wordmark — flat, no icon, just the name in slate-950 */}
        <a style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#0f172a', fontSize: 16, fontWeight: 600, letterSpacing: '-0.015em', textDecoration: 'none' }}>
          <span style={{ display: 'inline-block', width: 14, height: 14, background: '#0f172a' }} />
          BettingMaster
        </a>

        {/* Search — minimal, no inner button, no shadow */}
        <form onSubmit={(e) => { e.preventDefault(); onSearch?.(q.trim()); }}
              style={{ flex: 1, display: 'flex', maxWidth: 420 }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }}>
              <Search size={14} />
            </span>
            <input value={q} onChange={(e) => setQ(e.target.value)}
                   placeholder="Search match, team, league…"
                   style={{
                     width: '100%', padding: '7px 12px 7px 32px',
                     border: '1px solid #e2e8f0', background: '#ffffff',
                     borderRadius: 4, fontSize: 13, outline: 'none',
                     fontFamily: 'inherit', color: '#0f172a',
                   }}
                   onFocus={(e) => { e.target.style.borderColor = '#0f172a'; }}
                   onBlur={(e) => { e.target.style.borderColor = '#e2e8f0'; }} />
          </div>
        </form>

        {/* Tabs instead of capsules */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: 24, marginLeft: 'auto' }}>
          <NavLink active>Best odds</NavLink>
          <NavLink>Surebets</NavLink>
          <NavLink>Leagues</NavLink>
          <NavLink>Live</NavLink>
        </nav>

        {/* Live status — inline, not a pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#64748b', fontFamily: 'var(--mono)', borderLeft: '1px solid #e2e8f0', paddingLeft: 16 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', animation: 'bmPulse 2s ease-in-out infinite' }} />
          FEED OK
        </div>
      </div>
    </header>
  );
}
window.Header = Header;
