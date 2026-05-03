function OutcomeBars({ match }) {
  const rows = match.rows;
  const cols = [
    { key: 'home', label: match.home, code: '1' },
    { key: 'draw', label: 'Draw',     code: 'X' },
    { key: 'away', label: match.away, code: '2' },
  ];
  // Best PRICE = highest odds in column (best for the bettor)
  const best = {};
  cols.forEach(c => { let b = 0; rows.forEach(r => { const v = r.odds[c.key] ?? 0; if (v > b) b = v; }); best[c.key] = b; });
  const toProb = (d) => d ? Math.round((1/d)*1000)/10 : 0;
  const avgOdds = (k) => { const v = rows.map(r => r.odds[k]).filter(Boolean); return v.reduce((a,b)=>a+b,0)/v.length; };
  const margin = (h,d,a) => ((1/h + 1/d + 1/a) - 1) * 100;

  return (
    <section style={{ border: '1px solid #e2e8f0', background: '#fff', padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 4 }}>
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0f172a', margin: 0, letterSpacing: '-0.01em' }}>Odds for each result</h2>
          <p style={{ fontSize: 12, color: '#64748b', margin: '4px 0 0 0', lineHeight: 1.5, maxWidth: 540 }}>
            Higher odds = bigger payout for you. The <b style={{ color: '#047857' }}>BEST</b> tag marks the bookmaker paying the most per outcome. The bar shows how likely each result is, based on the price.
          </p>
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: '#64748b', textAlign: 'right' }}>
          {rows.length} bookmakers<br/>updated 22:14
        </div>
      </div>

      {/* Column headers */}
      <div style={{ display: 'grid', gridTemplateColumns: '140px repeat(3, 1fr) 80px', gap: 12, marginTop: 16, paddingBottom: 8, borderBottom: '1px solid #e2e8f0' }}>
        <Kicker>Bookmaker</Kicker>
        {cols.map(c => (
          <div key={c.key}>
            <Kicker>{c.code}</Kicker>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#0f172a', marginTop: 2 }}>{c.label}</div>
          </div>
        ))}
        <div style={{ textAlign: 'right' }}><Kicker>Margin</Kicker></div>
      </div>

      {rows.map(r => {
        const m = margin(r.odds.home, r.odds.draw, r.odds.away);
        return (
          <div key={r.bookmaker} style={{ display: 'grid', gridTemplateColumns: '140px repeat(3, 1fr) 80px', gap: 12, alignItems: 'center', padding: '14px 0', borderBottom: '1px solid #f1f5f9' }}>
            <BookmakerName bookmaker={r.bookmaker} />
            {cols.map(c => {
              const v = r.odds[c.key];
              const p = toProb(v);
              const isBest = v && v === best[c.key];
              return (
                <div key={c.key} style={{ position: 'relative' }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: isBest ? '#047857' : '#0f172a', letterSpacing: '-0.01em', lineHeight: 1 }}>{v ? v.toFixed(2) : '—'}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#94a3b8' }}>implied {p}%</span>
                  </div>
                  <div style={{ height: 5, background: '#f1f5f9', marginTop: 6, position: 'relative' }}>
                    <div style={{ position: 'absolute', inset: '0 auto 0 0', width: `${p}%`, background: isBest ? '#047857' : '#cbd5e1' }} />
                  </div>
                  {isBest && (
                    <span style={{ position: 'absolute', top: -2, right: 0, background: '#047857', color: '#fff', fontSize: 8, fontWeight: 700, letterSpacing: '0.08em', padding: '2px 4px' }}>BEST</span>
                  )}
                </div>
              );
            })}
            <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: '#64748b', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>+{m.toFixed(2)}%</div>
          </div>
        );
      })}

      {/* Market average row */}
      <div style={{ background: '#f8fafc', marginTop: 12, padding: '14px 12px', border: '1px solid #e2e8f0' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '128px repeat(3, 1fr) 80px', gap: 12, alignItems: 'center' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: '#475569' }}>
            <span style={{ width: 8, height: 8, background: '#94a3b8', borderRadius: 2 }} />
            Market average
          </span>
          {cols.map(c => {
            const a = avgOdds(c.key);
            const p = toProb(a);
            return (
              <div key={c.key}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 16, fontWeight: 500, fontVariantNumeric: 'tabular-nums', color: '#475569' }}>{a.toFixed(2)}</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#94a3b8' }}>implied {p}%</span>
                </div>
                <div style={{ height: 5, background: '#e2e8f0', marginTop: 6, position: 'relative' }}>
                  <div style={{ position: 'absolute', inset: '0 auto 0 0', width: `${p}%`, background: '#94a3b8' }} />
                </div>
              </div>
            );
          })}
          <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: '#64748b', textAlign: 'right' }}>+{margin(avgOdds('home'), avgOdds('draw'), avgOdds('away')).toFixed(2)}%</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 18, fontSize: 11, color: '#64748b', marginTop: 14, paddingTop: 12, borderTop: '1px dashed #e2e8f0', flexWrap: 'wrap' }}>
        <span><span style={{ display: 'inline-block', width: 14, height: 5, background: '#047857', verticalAlign: 'middle', marginRight: 6 }} /><b style={{ color: '#0f172a', fontWeight: 600 }}>Best</b> — highest odds in this column</span>
        <span><span style={{ display: 'inline-block', width: 14, height: 5, background: '#cbd5e1', verticalAlign: 'middle', marginRight: 6 }} />Other bookmakers</span>
        <span><span style={{ display: 'inline-block', width: 14, height: 5, background: '#94a3b8', verticalAlign: 'middle', marginRight: 6 }} />Market average</span>
      </div>
    </section>
  );
}
window.OutcomeBars = OutcomeBars;
