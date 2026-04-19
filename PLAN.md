# BettingMaster - Slovak Odds Comparison Platform

## Vision
A webapp that scrapes all major Slovak sportsbooks in real-time, normalizes the data, and shows users the best available odds for every match — highlighting where to place each part of a bet for maximum value.

---

## Phase 1: Data Layer (Scrapers)

### Target Sportsbooks

| Sportsbook | Domain | Priority | Scraping Method |
|---|---|---|---|
| **Fortuna** | fortuna.sk | P0 | REST API (has public endpoints for odds) |
| **Tipsport** | tipsport.sk | P0 | REST API (shares infra with Tipsport.cz, known API) |
| **Nike** | nike.sk | P0 | REST API / HTML scraping |
| **Tipos** (Tiposbet) | tipos.sk | P0 | REST API / HTML scraping |
| **DOXXbet** | doxxbet.sk | P1 | REST API / HTML scraping |
| **Synottip** | synottip.sk | P2 | HTML scraping with Playwright |

### Scraper Architecture

```
scrapers/
  base.py              # Abstract scraper class with retry, rate-limit, error handling
  fortuna.py           # Fortuna scraper
  tipsport.py          # Tipsport scraper
  nike.py              # Nike scraper
  tipos.py             # Tipos scraper
  doxxbet.py           # DOXXbet scraper
  synottip.py          # Synottip scraper
  normalizer.py        # Unified data model mapping
  scheduler.py         # Periodic scraping orchestration
```

### Scraping Strategy

1. **API-first approach**: Before writing HTML scrapers, inspect each site's network traffic (XHR/Fetch requests) in DevTools. Most Slovak books load odds via JSON APIs — scrape those directly.
2. **Fallback to Playwright**: For sites that render odds client-side with no clean API, use Playwright (headless Chromium) to render the page and extract data.
3. **Rate limiting**: Respect each site — scrape every 60-120 seconds per sport. Rotate user-agents. Add jitter.
4. **Error resilience**: Each scraper must handle: site down, layout change, rate-limit (429), captcha detection. Log failures, don't crash the pipeline.

### Scraper Discovery Checklist (per sportsbook)

For each sportsbook, before writing code:

- [ ] Open the site, navigate to a live football match
- [ ] Open DevTools > Network tab, filter XHR/Fetch
- [ ] Identify the API endpoint that returns odds data (usually JSON)
- [ ] Document: URL pattern, required headers/cookies, response structure
- [ ] Check if an auth token or session cookie is needed
- [ ] Test if the API works without browser context (curl it)
- [ ] If no clean API: document the HTML structure for Playwright extraction
- [ ] Map the sportsbook's event/team naming to our canonical format

---

## Phase 2: Data Model & Storage

### Canonical Data Model

```python
# Core entities

Sport:
  id: str           # "football", "hockey", "tennis", "basketball"
  name: str

League:
  id: str           # "sk-fortuna-liga", "eng-premier-league"
  sport_id: str
  name: str
  country: str

Match:
  id: str           # Generated canonical ID
  league_id: str
  home_team: str    # Canonical team name
  away_team: str    # Canonical team name
  start_time: datetime
  status: str       # "prematch", "live", "finished"

Odds:
  match_id: str
  bookmaker: str    # "fortuna", "tipsport", "nike", "tipos", "doxxbet"
  market: str       # "1x2", "over_under_2.5", "btts", "double_chance", "handicap"
  selection: str    # "home", "draw", "away", "over", "under", "yes", "no"
  value: float      # The decimal odds (e.g. 2.15)
  scraped_at: datetime
  url: str          # Deep link to this bet on the bookmaker's site
```

### Team Name Normalization

This is the HARDEST part. Each bookmaker uses different names:
- Fortuna: "Sl. Bratislava" / Tipsport: "Slovan Bratislava" / Nike: "SK Slovan Bratislava"

**Solution:**
1. Build a `team_aliases.json` mapping file manually for top leagues
2. Use fuzzy matching (rapidfuzz) as fallback with human review queue
3. Match events by: same league + same date + fuzzy team name similarity > 85%

### Database

**SQLite** for MVP (zero ops), migrate to **PostgreSQL** when scaling.

Tables: `sports`, `leagues`, `matches`, `odds_snapshots`, `team_aliases`

Keep historical odds for trend analysis (odds movement charts).

---

## Phase 3: Comparison Engine

### Best Odds Calculator

```python
def get_best_odds(match_id, market="1x2"):
    """
    For a given match and market, return the best odds
    across all bookmakers for each selection.
    
    Returns:
    {
      "home":  { "odds": 2.45, "bookmaker": "tipsport", "url": "..." },
      "draw":  { "odds": 3.60, "bookmaker": "fortuna", "url": "..." },
      "away":  { "odds": 2.80, "bookmaker": "nike",     "url": "..." },
      "best_combined_margin": 4.2%   # vs typical 8-12% single-book margin
    }
    """
```

### Margin Calculation

```
Margin = (1/odds_home + 1/odds_draw + 1/odds_away - 1) * 100

# Single bookmaker margin: typically 8-12%
# Cherry-picked best odds margin: typically 2-5% (this is the value we provide)
```

### Value Bet Detection

Flag when the best available odds imply probability < true probability estimated from market consensus.

### Sure Bet (Arbitrage) Detection

When cherry-picked best odds across bookmakers produce a **negative margin** (guaranteed profit regardless of outcome). This is rare but very valuable to users.

---

## Phase 4: Backend API

### Tech Stack

- **Python 3.12+** with **FastAPI**
- **SQLAlchemy** ORM
- **APScheduler** for scraping cron jobs
- **httpx** for async HTTP requests to bookmaker APIs
- **Playwright** (Python) for JS-rendered sites
- **rapidfuzz** for team name matching

### API Endpoints

```
GET  /api/sports                          # List all sports
GET  /api/sports/{sport}/leagues          # Leagues for a sport
GET  /api/leagues/{league}/matches        # Matches in a league
GET  /api/matches/{match_id}              # Match detail with all odds
GET  /api/matches/{match_id}/best-odds    # Best odds comparison
GET  /api/matches/{match_id}/history      # Odds movement over time
GET  /api/surebets                        # Current arbitrage opportunities
GET  /api/search?q=slovan                 # Search matches/teams

# Filters (query params):
#   ?sport=football
#   ?bookmakers=fortuna,tipsport,nike
#   ?market=1x2,over_under
#   ?date=today|tomorrow|2026-04-15
```

### WebSocket for Live Updates

```
WS /ws/odds-feed
# Pushes real-time odds changes to connected clients
# Client subscribes to specific matches or leagues
```

---

## Phase 5: Frontend

### Tech Stack

- **Next.js 14+** (App Router) with **TypeScript**
- **Tailwind CSS** for styling
- **shadcn/ui** components
- **TanStack Query** for data fetching + caching
- **Recharts** for odds movement graphs

### Pages & Components

```
/                           # Homepage: today's top matches + surebets banner
/sport/football             # All football leagues & matches
/league/sk-fortuna-liga     # All matches in a league
/match/[id]                 # Full odds comparison for a single match
/surebets                   # Arbitrage opportunities
/settings                   # Bookmaker preferences, notifications
```

### Match Comparison View (Core UI)

```
+----------------------------------------------------------+
| Slovan Bratislava vs Spartak Trnava                      |
| Fortuna Liga | 2026-04-12 18:00                          |
+----------------------------------------------------------+
|                                                          |
| 1X2 Market:                                              |
|          HOME (1)    DRAW (X)    AWAY (2)                |
| Fortuna   2.30        3.20        2.90                   |
| Tipsport  2.45*       3.15        2.85                   |
| Nike      2.35        3.60*       2.80                   |
| Tipos     2.25        3.10        3.00*                  |
| DOXXbet   2.40        3.25        2.95                   |
|                                                          |
| BEST:     2.45        3.60        3.00                   |
|           Tipsport    Nike        Tipos                  |
|           [Bet ->]    [Bet ->]    [Bet ->]               |
|                                                          |
| Combined margin: 3.8% (vs avg single-book: 9.2%)        |
+----------------------------------------------------------+
| Over/Under 2.5 | BTTS | Double Chance | Handicap        |
+----------------------------------------------------------+
| Odds Movement Chart [sparkline graph]                    |
+----------------------------------------------------------+

* = best odds (highlighted in green)
[Bet ->] = deep link to bookmaker's betslip
```

### Mobile-First Design

80%+ of sports betting users are on mobile. Design for 375px width first.

---

## Phase 6: Infrastructure & Deployment

### Architecture

```
                    ┌─────────────────┐
                    │   Next.js App    │
                    │   (Vercel/VPS)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   FastAPI        │
                    │   Backend        │
                    │   (VPS/Railway)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───┐  ┌──────▼─────┐  ┌────▼────────┐
     │  SQLite/    │  │  Scraper   │  │  Redis      │
     │  PostgreSQL │  │  Workers   │  │  (cache +   │
     │             │  │  (cron)    │  │   pub/sub)  │
     └─────────────┘  └────────────┘  └─────────────┘
```

### MVP Deployment (Cheapest)

- **Single VPS** (Hetzner CX22, ~4 EUR/mo): runs everything
- SQLite database (no separate DB server needed)
- Caddy as reverse proxy with auto-HTTPS
- Systemd services for backend + scrapers

### Scaling Path

- PostgreSQL on managed DB when data grows
- Redis for caching hot odds data + WebSocket pub/sub
- Separate scraper workers (can run on cheap VPS)
- CDN for frontend (Vercel free tier)

---

## Phase 7: Legal & Compliance Considerations

- **Terms of Service**: Scraping may violate ToS of bookmakers. This is a legal gray area in Slovakia/EU. Odds comparison sites exist (e.g., oddschecker, oddsportal) and are generally tolerated.
- **No affiliate revenue initially**: but design the deep links to support affiliate parameters later (all major SK books have affiliate programs — this is the monetization path).
- **No user accounts or money handling**: this is purely informational — we never hold funds or place bets.
- **GDPR**: minimal concern since we don't collect user PII in MVP.

---

## Implementation Order (Build Sequence)

### Sprint 1 (Week 1-2): Foundation + First Scraper
1. Set up Python project with FastAPI boilerplate
2. Define SQLAlchemy models (matches, odds)
3. Build Fortuna scraper (most documented API)
4. Manual verification: scraper runs, data looks correct
5. Basic API: `/api/matches`, `/api/matches/{id}`

### Sprint 2 (Week 2-3): More Scrapers + Matching
1. Build Tipsport scraper
2. Build Nike scraper
3. Implement team name normalization + match linking
4. Seed `team_aliases.json` for Slovak Fortuna Liga + top EU leagues

### Sprint 3 (Week 3-4): Comparison Engine + Frontend
1. Best odds comparison logic
2. Margin calculator
3. Sure bet detector
4. Next.js frontend: homepage, match list, match detail with odds table
5. Mobile-responsive design

### Sprint 4 (Week 4-5): Polish + Remaining Scrapers
1. Tipos + DOXXbet scrapers
2. Odds movement history + charts
3. Search functionality
4. WebSocket live updates
5. Deploy to VPS

### Sprint 5 (Week 5-6): Growth Features
1. Surebets page
2. Notifications (Telegram bot for surebets?)
3. More sports beyond football
4. Affiliate link integration
5. SEO optimization

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Bookmaker blocks scraper | High | Rotate IPs, use residential proxies, respect rate limits |
| Site layout changes break scraper | Medium | Monitor scraper health, alert on failures, prefer APIs over HTML |
| Team name matching errors | Medium | Manual review queue, community corrections, start with fewer leagues |
| Legal takedown | Low-Medium | No commercial use initially, respect robots.txt, consider reaching out to books for data partnerships |
| Odds data staleness | Medium | Scrape frequently (60s), show "last updated" timestamps prominently |

---

## Tech Stack Summary

| Layer | Technology |
|---|---|
| Scrapers | Python, httpx, Playwright, APScheduler |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Database | SQLite (MVP) -> PostgreSQL |
| Cache | Redis (post-MVP) |
| Frontend | Next.js, TypeScript, Tailwind, shadcn/ui |
| Deployment | Hetzner VPS, Caddy, systemd |
| Monitoring | Sentry (errors), UptimeRobot (availability) |

---

## Metaprompt: How to Use This Plan with an AI Assistant

When building this project with Claude or another AI, use these prompts in order:

### Prompt 1: Backend Setup
> "Set up a Python FastAPI project in /backend with: project structure, SQLAlchemy models for sports/leagues/matches/odds as defined in the PLAN.md data model, Alembic migrations, basic CRUD API endpoints. Use SQLite. Include a base scraper class with retry logic, rate limiting, and error handling."

### Prompt 2: First Scraper (Fortuna)
> "I've inspected Fortuna.sk's network traffic. The odds API is at [URL]. Here's a sample response: [paste JSON]. Build a Fortuna scraper that: fetches all prematch football matches, parses the response into our canonical Match/Odds models, and stores them in the database. Include a CLI command to run it manually."

### Prompt 3: Team Normalization
> "Build a team name normalizer: 1) Load canonical names from team_aliases.json, 2) When a scraper returns a team name, try exact match first, then fuzzy match (rapidfuzz, threshold 85%), 3) If no match, log it for manual review. Create the initial team_aliases.json for Slovak Fortuna Liga teams."

### Prompt 4: More Scrapers
> "Using the same pattern as the Fortuna scraper, build scrapers for Tipsport and Nike. Here are their API endpoints and sample responses: [paste]. Wire them into the scheduler to run every 90 seconds."

### Prompt 5: Comparison Engine
> "Build the odds comparison engine: for each match, compute best odds per selection across all bookmakers, calculate combined margin vs single-book margin, detect sure bets (negative margin). Expose via API endpoints: /api/matches/{id}/best-odds and /api/surebets."

### Prompt 6: Frontend
> "Build the Next.js frontend with: homepage showing today's matches grouped by league with best odds highlighted, match detail page with full odds comparison table (as shown in PLAN.md wireframe), sure bets page, search. Use Tailwind + shadcn/ui. Mobile-first."

### Prompt 7: Live Updates + Polish
> "Add WebSocket support for live odds updates. Add odds movement sparkline charts using Recharts. Add 'last updated' timestamps. Add deep links to each bookmaker's bet slip."
