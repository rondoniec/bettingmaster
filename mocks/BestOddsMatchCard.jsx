function BestOddsMatchCard({ match, onOpen }) {
  const isLive = match.status === 'live';
  const isSurebet = match.combined_margin < 0;
  const tone = marginTone(match.combined_margin);
  // Flag only the single outcome with the biggest edge — highest odds = strongest payout.
  // (All three are technically the "best price across books"; the BEST tag should mean
  //  "this is the standout bet on the card", not just "we found a price".)
  const bestIdx = match.selections.reduce((best, s, i, arr) =>
    s.odds > arr[best].odds ? i : best, 0);
  return (
    <article style={{
      border: '1px solid #e2e8f0', background: '#ffffff',
      borderLeft: isSurebet ? '3px solid #047857' : '1px solid #e2e8f0',
    }}>
      {/* Header row */}
      <div style={{ borderBottom: '1px solid #f1f5f9', padding: '16px 20px', display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Kicker>{match.league}</Kicker>
            {isLive && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: 'var(--mono)', fontSize: 10, color: '#dc2626', letterSpacing: '0.1em' }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#dc2626', animation: 'bmPulse 2s ease-in-out infinite' }} />
                LIVE
              </span>
            )}
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: '#64748b' }}>{match.time}</span>
          </div>
          <h2 style={{ marginTop: 8, fontSize: 18, fontWeight: 600, letterSpacing: '-0.015em', color: '#0f172a', margin: '8px 0 0 0' }}>
            {match.home}<span style={{ margin: '0 8px', color: '#94a3b8', fontWeight: 400 }}>vs</span>{match.away}
          </h2>
          <p style={{ marginTop: 6, fontSize: 12, color: '#64748b', fontFamily: 'var(--mono)' }}>
            {match.bookmakers.length} bookmakers compared
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{
            background: tone.bg, color: tone.fg, border: `1px solid ${tone.border}`,
            padding: '4px 10px', fontSize: 11, fontFamily: 'var(--mono)',
            letterSpacing: '0.04em',
          }}>
            MARGIN {formatMargin(match.combined_margin)}
          </span>
          <button onClick={onOpen} style={{
            background: '#0f172a', color: '#fff',
            padding: '7px 14px', fontSize: 12, fontWeight: 500,
            border: 'none', cursor: 'pointer', fontFamily: 'inherit',
            display: 'inline-flex', alignItems: 'center', gap: 4,
          }}>Open <ChevronRight size={12} /></button>
        </div>
      </div>

      {/* Three best-odds cells */}
      <div style={{ padding: 16, display: 'grid', gap: 1, gridTemplateColumns: 'repeat(3, 1fr)', background: '#e2e8f0', border: '1px solid #e2e8f0', margin: 16 }}>
        {match.selections.map((s, i) => {
          const isTop = i === bestIdx;
          return (
            <div key={s.label} style={{ background: '#ffffff', padding: 16, position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Kicker>{s.label}</Kicker>
                {isTop && (
                  <span style={{
                    fontSize: 9, fontWeight: 700, color: '#fff', background: '#047857',
                    padding: '2px 5px', letterSpacing: '0.08em',
                  }}>TOP PICK</span>
                )}
              </div>
              <div style={{
                marginTop: 10, fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em',
                color: isTop ? '#047857' : '#0f172a',
                fontVariantNumeric: 'tabular-nums', lineHeight: 1,
              }}>{formatOdds(s.odds)}</div>
              <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <BookmakerChip bookmaker={s.bookmaker} />
                <a style={{ color: '#475569', fontSize: 11, fontFamily: 'var(--mono)', display: 'inline-flex', alignItems: 'center', gap: 3, cursor: 'pointer', textDecoration: 'none' }}>
                  VISIT <ExternalLink size={10} />
                </a>
              </div>
            </div>
          );
        })}
      </div>
    </article>
  );
}
window.BestOddsMatchCard = BestOddsMatchCard;
