function SurebetBanner({ count, bestProfit, onOpen }) {
  if (!count) return null;
  return (
    <a onClick={onOpen} style={{ display: 'block', textDecoration: 'none', cursor: 'pointer' }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        border: '1px solid #a7f3d0', borderLeft: '3px solid #047857',
        background: '#ecfdf5', padding: '12px 16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Kicker style={{ color: '#047857' }}>OPPORTUNITY</Kicker>
          <span style={{ fontSize: 13, color: '#0f172a', fontWeight: 500 }}>
            {count} live {count === 1 ? 'surebet' : 'surebets'} on the board
          </span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: '#047857', fontVariantNumeric: 'tabular-nums' }}>
            best profit +{bestProfit.toFixed(2)}%
          </span>
        </div>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#047857', fontSize: 12, fontWeight: 500 }}>
          View all <ArrowRight size={12} />
        </span>
      </div>
    </a>
  );
}
window.SurebetBanner = SurebetBanner;

function OddsTable({ match }) {
  const selections = ['home','draw','away'];
  const labels = { home: match.home, draw: 'Draw', away: match.away };
  const oddsMap = {};
  match.rows.forEach(r => { oddsMap[r.bookmaker] = r.odds; });
  const active = BOOKMAKER_ORDER.filter(b => oddsMap[b]);
  const best = {};
  selections.forEach(sel => {
    let b = 0; active.forEach(bm => { const v = oddsMap[bm]?.[sel] ?? 0; if (v > b) b = v; });
    best[sel] = b;
  });
  const th = { padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#64748b', fontFamily: 'var(--mono)' };
  return (
    <div style={{ border: '1px solid #e2e8f0', background: '#fff' }}>
      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
        <thead><tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
          <th style={th}>Bookmaker</th>
          {selections.map(s => <th key={s} style={{ ...th, textAlign: 'right' }}>{labels[s]}</th>)}
        </tr></thead>
        <tbody>
          {active.map(bm => (
            <tr key={bm} style={{ borderBottom: '1px solid #f1f5f9' }}>
              <td style={{ padding: '10px 14px' }}>
                <BookmakerName bookmaker={bm} />
              </td>
              {selections.map(sel => {
                const v = oddsMap[bm]?.[sel];
                const isBest = v && v === best[sel];
                return (
                  <td key={sel} style={{ padding: '10px 14px', textAlign: 'right' }}>
                    {v ? (
                      <span style={{
                        fontFamily: 'var(--mono)', fontVariantNumeric: 'tabular-nums',
                        fontWeight: isBest ? 600 : 400,
                        color: isBest ? '#047857' : '#0f172a',
                      }}>
                        {v.toFixed(2)}
                        {isBest && <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 700, color: '#fff', background: '#047857', padding: '1px 4px', letterSpacing: '0.08em' }}>BEST</span>}
                      </span>
                    ) : <span style={{ color: '#cbd5e1' }}>—</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
        <tfoot><tr style={{ borderTop: '1px solid #047857', background: '#f0fdf4' }}>
          <td style={{ padding: '12px 14px', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#047857', fontFamily: 'var(--mono)' }}>Best per outcome</td>
          {selections.map(sel => {
            const bm = active.find(b => oddsMap[b]?.[sel] === best[sel]);
            return (
              <td key={sel} style={{ padding: '12px 14px', textAlign: 'right' }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#047857', fontFamily: 'var(--mono)', fontVariantNumeric: 'tabular-nums' }}>{best[sel].toFixed(2)}</div>
                {bm && <div style={{ marginTop: 2, fontSize: 10, color: '#64748b', fontFamily: 'var(--mono)' }}>{BOOKMAKERS[bm].displayName}</div>}
              </td>
            );
          })}
        </tr></tfoot>
      </table>
    </div>
  );
}
window.OddsTable = OddsTable;
