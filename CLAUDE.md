# CLAUDE.md

## Project Summary

BettingMaster is a football odds-comparison platform with:

- a `FastAPI` backend
- a `Next.js` frontend
- a background scraper worker
- PostgreSQL on the server, SQLite locally by default

The product goal is to aggregate bookmaker odds, normalize the same match across multiple providers, and show:

- best odds by outcome
- surebets
- match detail pages with bookmaker-by-bookmaker odds
- freshness / scrape-health signals so users know whether prices are trustworthy

This file is a handoff summary of what has been built so far and what decisions were made during development.

## Current Product Scope

Current scope is intentionally narrowed:

- football only for the main product flow
- only `Premier League` and `La Liga` are actively prioritized
- only matches within roughly the next `24 hours` are shown on the main board
- live and upcoming matches are separated in the UI

This narrowing was done to improve scrape quality, reduce noise, and make freshness more realistic.

## Current Bookmakers

Implemented scrapers:

- `fortuna`
- `nike`
- `doxxbet`
- `polymarket`
- `tipsport`
- `tipos`

Real-world status:

- `Fortuna` works and is a core reliable source
- `DOXXbet` works and has been one of the cleaner scrapers
- `Nike` works but is sensitive to rate limiting and must be scraped slowly
- `Polymarket` is integrated through API-style market fetching / reconciliation rather than bookmaker-style scraping
- `Tipsport` exists in code but is currently blocked by upstream anti-bot / IP restrictions
- `Tipos` exists in code but is unreliable and often returns `404` / empty data

Important operational note:

- `Tipsport` likely needs residential or home-network routing to work reliably
- the preferred plan is to route Hetzner traffic through the user’s home PC with `Tailscale exit node`

## Important Product Decisions Already Made

### 1. Match-first scraping order

The worker does **not** scrape an entire bookmaker and then move to the next one.

Instead, round-robin scraping was changed to:

1. discover matches
2. normalize and merge them
3. scrape the same match across due bookmakers
4. then move to the next match

This makes cross-bookmaker comparisons appear faster and helps the homepage fill with usable merged odds sooner.

### 2. Freshness matters more than raw scrape count

We added the concept of:

- `scraped_at`
- `checked_at`
- freshness windows per bookmaker
- on-demand refresh when a user opens a match

This was done because stale prices were causing obvious user-facing inaccuracies, especially with:

- `Polymarket`
- `Nike`

### 3. UI should only show comparable outcomes

On match pages we do **not** show outcomes unless at least `2` bookmakers have data for that same outcome / market.

This avoids low-signal screens filled with single-source markets.

## Major Features Already Implemented

### Main homepage

The homepage now includes:

- best odds board
- live vs upcoming filtering
- sorting
- search
- active bookmakers display
- scrape-health / freshness panel

### Surebets page

The project includes a `/surebets` page showing surebet opportunities from merged latest odds.

### New Polymarket markets page

There is a dedicated subpage:

- `/polymarket-new`

This is for newly opened far-future football Polymarket markets, because early markets can have attractive mispricings.

### Match detail page

The match page was heavily cleaned up and now focuses on usable bookmaker comparisons instead of clutter.

It includes:

- market-by-market odds boards
- focused deep-link opening from homepage cards
- outcome-specific bookmaker links
- freshness labels per bookmaker
- freshness chips in the match header
- live-update websocket badge

### Test subpage

A test/demo subpage exists:

- `/test`

It was used for showing a controlled scraped example such as `Real Madrid vs Bayern Munich` in UCL with a limited number of outcomes.

## Important Matching / Normalization Work

### Team-name reconciliation

A lot of work went into preventing bad cross-site match merges.

This includes:

- fuzzy team matching
- canonical match IDs
- better bookmaker validation
- match identity / reconciliation improvements

This was especially necessary for cases like:

- `Barcelona` vs `Barcelona SC`
- ambiguous team names in Polymarket
- wrong bookmaker outcome links

### Outcome / market mapping fixes

Several bugs were fixed around mapping bookmaker-specific labels into canonical markets, including:

- `BTTS`
- `Draw no bet`
- `Vysledok bez remizy`
- over/under variants
- exact-outcome deep links

## Freshness / Scrape Accuracy Work

### On-demand refresh on open

When a user opens a match, stale bookmaker data can be refreshed on demand.

This behavior now exists for:

- `Fortuna`
- `DOXXbet`
- `Nike`
- `Tipos`
- `Tipsport`
- `Polymarket`

Each bookmaker has its own max-age threshold before an on-open refresh is attempted.

### Homepage scrape-health panel

The homepage now shows bookmaker health with:

- last scrape/check time
- configured cadence
- freshness state:
  - `Fresh`
  - `Aging`
  - `Stale`
  - `Idle`

This was added to make scraper debugging visible without digging through logs.

### Match-page freshness indicators

The match page now shows freshness directly on the odds screen:

- header bookmaker chips include freshness
- each bookmaker row under an outcome includes freshness
- the checked time is still shown for exact context

## Current UI / UX Decisions

### Header / navigation

Main nav items:

- `Best odds`
- `Surebets`
- `New markets`

The header was improved so active routes are clearly highlighted. A homepage button is also present.

### Homepage behavior

The homepage is intended to feel like an operational board:

- quick filters
- live/upcoming split
- best odds first
- visible bookmaker coverage
- visible system health

### Match page behavior

The match page is intended to feel compact and decision-oriented:

- less chart clutter
- more direct bookmaker comparison
- better outcome grouping
- better exact bookmaker links

## Server / Deployment Status

### Laptop deployment (current — Hetzner decommissioned)

Everything runs on the home Ubuntu laptop, accessible via SSH alias `laptop` over Tailscale.

- laptop path: `/home/adam/projects/bettingmaster`
- Tailscale IP: `100.75.68.42`
- Primary compose: `docker-compose.laptop.yml` with `.env`
- Worker env adds: `.env.laptop` (API tokens, Tipsport/Tipos Playwright settings)

Hetzner (`188.245.79.101`) is decommissioned. The files `docker-compose.hetzner-bettingmaster.yml`
and `.env.hetzner` remain in the repo for reference but should not be deployed to.

### Running services

Expected services (all on laptop):

- `db`
- `backend`
- `frontend`
- `worker`

### Worker behavior

The worker:

- runs migrations
- schedules round-robin scraping
- persists odds snapshots
- powers the main app data

## Important Infrastructure Fixes Already Done

### DB auto-upgrade on startup

A major local-dev bug was fixed where the frontend looked broken because the backend was running against an out-of-date schema.

The app now supports automatic DB upgrade on startup for real runs, while tests disable this behavior to avoid migration collisions.

### Missing Scrapling runtime dependencies

Server deployment issues were fixed around missing dependencies required by Scrapling, including:

- `curl_cffi`
- `browserforge`

### Health endpoint improvements

`/api/health` no longer just says whether the API is alive. It now also exposes scraper freshness metadata.

## Known Operational Problems

### Tipsport blocking

Tipsport is still the biggest unresolved infrastructure issue.

What is already known:

- plain requests get blocked
- browser automation still gets blocked
- this is likely IP / geo / reputation based

Preferred solution:

- route scraper traffic through the user’s home network
- best planned method: `Tailscale exit node`

### Nike rate limiting

Nike is sensitive to `429` responses.

Mitigations already implemented / chosen:

- slow scraping cadence
- cooldown behavior
- accept that Nike refreshes less often than some other bookmakers

### Polymarket reconciliation sensitivity

Polymarket is useful but needs very careful event matching.

Areas that have caused problems:

- ambiguous team names
- wrong event linkage
- odds direction / inversion mistakes
- stale-seeming prices if not refreshed aggressively enough

The codebase already includes reconciliation and validation improvements, but this remains an area to watch closely.

## API / Frontend Capabilities Present

Backend route groups currently include:

- `health`
- `history`
- `matches`
- `polymarket`
- `search`
- `sports`
- `surebets`
- `ws`

Frontend pages currently include:

- `/`
- `/surebets`
- `/polymarket-new`
- `/match/[id]`
- `/league/[id]`
- `/test`

## Important Commands

### Local backend

```bash
python -m uvicorn bettingmaster.api.app:app --host 127.0.0.1 --port 8000
```

### Local frontend

```bash
cd frontend
npm run dev
```

### Tests

```bash
python -m pytest -q
python -m ruff check src tests
cd frontend && npm run lint
cd frontend && npm run build
```

### Server update (laptop — all services)

The full stack runs on the home Ubuntu laptop (SSH alias `laptop`).
Hetzner is decommissioned. Do NOT deploy to Hetzner.

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && git pull && docker compose -f docker-compose.laptop.yml --env-file .env up -d --build"
```

### Server health

```bash
ssh laptop "curl -s http://127.0.0.1:8000/api/health"
ssh laptop "curl -s http://127.0.0.1:8000/api/matches"
```

### Worker logs

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env logs -f worker"
```

### All service logs

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env logs -f"
```

## Files Worth Knowing First

Backend:

- `src/bettingmaster/api/app.py`
- `src/bettingmaster/api/routes/health.py`
- `src/bettingmaster/api/routes/matches.py`
- `src/bettingmaster/scheduler.py`
- `src/bettingmaster/services/odds.py`
- `src/bettingmaster/reconciliation.py`
- `src/bettingmaster/match_identity.py`
- `src/bettingmaster/bookmaker_validation.py`
- `src/bettingmaster/services/on_demand.py`
- `src/bettingmaster/scrapers/*.py`

Frontend:

- `frontend/src/app/page.tsx`
- `frontend/src/app/match/[id]/page.tsx`
- `frontend/src/components/HomeLiveSection.tsx`
- `frontend/src/components/MatchLiveSection.tsx`
- `frontend/src/components/MarketOddsBoard.tsx`
- `frontend/src/components/ScrapeHealthPanel.tsx`
- `frontend/src/components/FreshnessBadge.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/constants.ts`
- `frontend/src/lib/utils.ts`

Ops / deployment:

- `docker-compose.laptop.yml` — unified laptop compose (all 4 services)
- `SERVER_RUNBOOK.md` — day-to-day operations reference

## Recommended Next Steps

Highest-value next work:

1. Verify Tipos odds column order (home/draw/away assumed — cross-check vs Fortuna/Nike for same match).
2. Expand Tipos coverage beyond PL top-bets (GetWebTopBets only returns ~6 events; need category endpoint or different TopOfferType).
3. Add a match-page toggle to hide stale bookmaker rows.
4. Continue tightening Polymarket event matching.
5. Rotate Postgres password (`jozo` → something strong) before any wider exposure.

## Final Note

This project has already gone through a lot of practical product shaping:

- from broad sportsbook scraping to a tighter football scope
- from raw scrape output to user-trust-oriented freshness signals
- from page clutter to comparison-first match screens
- from bookmaker-by-bookmaker crawling to match-first round-robin scraping

If you are continuing development, the most important thing to preserve is this principle:

**fresh, correctly matched, user-trustworthy odds matter more than scraping more pages badly.**
