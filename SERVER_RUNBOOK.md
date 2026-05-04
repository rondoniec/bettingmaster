# BettingMaster Runbook

Everything runs on the home Ubuntu laptop (SSH alias `laptop` over Tailscale).
Hetzner is decommissioned. Do not deploy there.

- Laptop path: `/home/adam/projects/bettingmaster`
- Laptop Tailscale IP: `100.75.68.42`
- Compose file: `docker-compose.laptop.yml`
- Env file: `.env` (worker also loads `.env.laptop`)

---

## Connect

```bash
ssh laptop
```

---

## 1. Check status

```bash
cd /home/adam/projects/bettingmaster
docker compose -f docker-compose.laptop.yml --env-file .env ps
```

All four services should show:

- `db` — `healthy`
- `backend` — `healthy`
- `frontend` — `Up`
- `worker` — `Up`

---

## 2. Deploy after pushing new code

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && git pull && docker compose -f docker-compose.laptop.yml --env-file .env up -d --build"
```

Rebuilds changed images, restarts containers, keeps the DB volume intact.

---

## 3. Rebuild only one service

Frontend (after UI-only change):

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && git pull && docker compose -f docker-compose.laptop.yml --env-file .env up -d --build frontend"
```

Backend + worker (after scraper/API/DB change):

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && git pull && docker compose -f docker-compose.laptop.yml --env-file .env up -d --build backend worker"
```

---

## 4. Restart without rebuilding

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env restart"
```

---

## 5. Worker logs

Tail live:

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env logs -f worker"
```

Last 100 lines:

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env logs worker --tail=100"
```

Filter by scraper:

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env logs worker --tail=500 2>&1 | grep nike"
```

---

## 6. All service logs

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env logs -f"
```

---

## 7. Health check

```bash
ssh laptop "curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool"
```

---

## 8. Force a scrape manually

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env exec worker python -m bettingmaster.cli scrape-cycle --bookmaker fortuna --bookmaker nike --bookmaker doxxbet --bookmaker polymarket --bookmaker tipsport --bookmaker tipos"
```

Single bookmaker for debugging:

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env exec worker python -m bettingmaster.cli scrape doxxbet"
```

---

## 9. Full clean restart

Use when normal restart doesn't help:

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env down && docker compose -f docker-compose.laptop.yml --env-file .env up -d --build"
```

Keeps the PostgreSQL data volume — does not delete the database.

---

## 10. Delete everything including data (DESTRUCTIVE)

Do not run unless you want to wipe the database:

```bash
ssh laptop "cd /home/adam/projects/bettingmaster && docker compose -f docker-compose.laptop.yml --env-file .env down -v"
```

The `-v` flag deletes Docker volumes including PostgreSQL data.

---

## 11. Useful URLs (via Tailscale or LAN)

- Frontend: `http://100.75.68.42:3000`
- API health: `http://100.75.68.42:8000/api/health`
- API docs: `http://100.75.68.42:8000/docs`
- Best odds: `http://100.75.68.42:8000/api/matches/best-odds`

---

## 12. Active scrapers and status

| Scraper | Status | Notes |
|---------|--------|-------|
| fortuna | ✅ working | Core reliable source |
| nike | ✅ working | Adaptive cadence (starts 60s, +5s on 429) |
| doxxbet | ✅ working | Clean API |
| polymarket | ✅ working | Ask price (CLOB SELL side) |
| tipsport | ✅ working | Playwright HTML scraper, patchright + real Chrome + Xvfb |
| tipos | ✅ working | Playwright API scraper, GetWebTopBets + GetWebStandardEventExt |

Tipsport requires residential IP — works on laptop, fails on datacenter IPs.

---

## 13. Worker environment files

| File | Used by | Contains |
|------|---------|----------|
| `.env` | db, backend, frontend, worker | DB creds, CORS, API URLs, Tipsport headless=false |
| `.env.laptop` | worker (merged on top of .env) | football-data.org + API-Football tokens, Tipsport channel |

`.env.laptop` `BM_DATABASE_URL` uses Docker-internal `db:5432` — do not change to Tailscale IP.
