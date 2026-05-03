function HeroBoard({ date, setDate, sport, setSport, sortMode, setSortMode, statusFilter, setStatusFilter, liveCount, upcomingCount, matches, surebets, bestMargin, activeBookmakers }) {
  return (
    <section style={{
      border: '1px solid #e2e8f0', background: '#ffffff', padding: '24px 24px',
    }}>
      {/* Title row — flat, no kicker pill */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 24, flexWrap: 'wrap' }}>
        <div style={{ maxWidth: 720 }}>
          <Kicker>Market view · {date.toUpperCase()}</Kicker>
          <h1 style={{ marginTop: 8, fontSize: 30, fontWeight: 600, letterSpacing: '-0.02em', color: '#0f172a', lineHeight: 1.15, margin: '8px 0 0 0' }}>
            Best price across {activeBookmakers.length} bookmakers, in real time.
          </h1>
          <p style={{ marginTop: 10, fontSize: 13, lineHeight: 1.55, color: '#475569', maxWidth: 560 }}>
            Each card compares the same 1X2 market side-by-side and tags the bookmaker offering the highest payout for each outcome.
          </p>
        </div>

        {/* Right-side stat strip — flat, slate-only, dividers do the work */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, auto)',
          fontFamily: 'var(--mono)', fontVariantNumeric: 'tabular-nums',
          gap: 0,
        }}>
          {[
            { k: 'Merged',      v: matches.length, color: '#0f172a' },
            { k: 'Surebets',    v: surebets.length > 0 ? `+${surebets.length}` : '0', color: surebets.length ? '#047857' : '#0f172a' },
            { k: 'Best margin', v: bestMargin != null ? `${bestMargin.toFixed(2)}%` : '—', color: bestMargin < 0 ? '#047857' : '#0f172a' },
          ].map((s, i, arr) => (
            <div key={s.k} style={{ padding: '4px 24px', borderLeft: i === 0 ? 'none' : '1px solid #e2e8f0', minWidth: 110 }}>
              <div style={{ fontSize: 9, color: '#64748b', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{s.k}</div>
              <div style={{ fontSize: 24, color: s.color, marginTop: 4, fontWeight: 500, letterSpacing: '-0.01em' }}>{s.v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Filter bar — single row of underline tabs + segmented bits */}
      <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 24 }}>
        <FilterGroup label="State">
          <Tab active={statusFilter==='live'} onClick={() => setStatusFilter('live')}>Live ({liveCount})</Tab>
          <Tab active={statusFilter==='upcoming'} onClick={() => setStatusFilter('upcoming')}>Upcoming ({upcomingCount})</Tab>
        </FilterGroup>
        <FilterGroup label="Date">
          <Tab active={date==='today'} onClick={() => setDate('today')}>Today</Tab>
          <Tab active={date==='tomorrow'} onClick={() => setDate('tomorrow')}>Tomorrow</Tab>
        </FilterGroup>
        <FilterGroup label="Sort">
          <Tab active={sortMode==='kickoff'} onClick={() => setSortMode('kickoff')}>Kickoff</Tab>
          <Tab active={sortMode==='edge'} onClick={() => setSortMode('edge')}>Best edge</Tab>
          <Tab active={sortMode==='coverage'} onClick={() => setSortMode('coverage')}>Coverage</Tab>
        </FilterGroup>
        <FilterGroup label="Sport">
          <Tab active={!sport} onClick={() => setSport(null)}>All</Tab>
          {['Football','Tennis','Hockey'].map((s) =>
            <Tab key={s} active={sport===s} onClick={() => setSport(s)}>{s}</Tab>)}
        </FilterGroup>
      </div>

      {/* Bookmaker row — chips show what's compared */}
      <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px dashed #e2e8f0' }}>
        <Kicker style={{ marginBottom: 8 }}>Bookmakers in this view</Kicker>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {activeBookmakers.map((bm) => <BookmakerChip key={bm} bookmaker={bm} />)}
        </div>
      </div>
    </section>
  );
}

function FilterGroup({ label, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <Kicker>{label}</Kicker>
      <div style={{ display: 'flex', gap: 16 }}>{children}</div>
    </div>
  );
}

window.HeroBoard = HeroBoard;
