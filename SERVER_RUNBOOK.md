# BettingMaster Server Runbook

Use this when the server is already set up and you just need to run, restart, update, or check the app.

Server IP:

```bash
188.245.79.101
```

Project folder on the server:

```bash
/opt/bettingmaster
```

## 1. Connect to the server

From your computer terminal:

```bash
ssh root@188.245.79.101
```

If it asks whether you trust the server, type:

```text
yes
```

## 2. Go to the project folder

After you log in:

```bash
cd /opt/bettingmaster
```

Always run the Docker commands from this folder.

## 3. Check if everything is running

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner ps
```

You want to see these services running:

- `db`
- `backend`
- `frontend`
- `worker`

Healthy/good signs:

- `db` says `healthy`
- `backend` says `healthy`
- `frontend` says `Up`
- `worker` says `Up`

## 4. Start everything again

Use this if the server restarted, or containers are stopped:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d
```

Then check status:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner ps
```

## 5. Restart everything

Use this if the site is acting weird but you did not update code:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner restart
```

## 6. Update the server after I push new code

Use this most often:

```bash
cd /opt/bettingmaster
git pull
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d --build
```

This rebuilds and restarts the app with the latest GitHub code.

## 7. Update only the frontend

Use this after UI-only changes:

```bash
cd /opt/bettingmaster
git pull
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d --build frontend
```

## 8. Update backend and worker

Use this after scraper, API, database, or odds logic changes:

```bash
cd /opt/bettingmaster
git pull
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d --build backend worker
```

## 9. Watch scraper progress

Quick worker log check:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs worker --tail=100
```

Live worker logs:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs -f worker
```

To exit live logs, press:

```text
Ctrl+C
```

This only stops the log view. It does not stop the scraper.

## 10. Force a scrape manually

Run this if you do not want to wait for the worker schedule. This uses the
match-first order: discover matches, then scrape the same match across all
selected bookmakers before moving to the next match.

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner exec worker python -m bettingmaster.cli scrape-cycle --bookmaker fortuna --bookmaker nike --bookmaker doxxbet --bookmaker polymarket
```

Optional scrapers can be added too:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner exec worker python -m bettingmaster.cli scrape-cycle --bookmaker fortuna --bookmaker nike --bookmaker doxxbet --bookmaker polymarket --bookmaker tipsport --bookmaker tipos
```

Note: `tipsport` and `tipos` may fail or return no data more often than the others.

The older command also still exists for debugging one bookmaker only:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner exec worker python -m bettingmaster.cli scrape doxxbet
```

## 11. Check API health

From the server:

```bash
curl http://127.0.0.1:8000/api/health
```

From your browser:

```text
http://188.245.79.101:8000/api/health
```

Good response looks like this:

```json
{
  "status": "ok",
  "db": "connected",
  "scrapers": {
    "fortuna": "2026-04-21 12:00:00"
  }
}
```

The `scrapers` object fills in after successful scrapes.

## 12. Check if matches exist

From the server:

```bash
curl http://127.0.0.1:8000/api/matches
```

Check best-odds board data:

```bash
curl "http://127.0.0.1:8000/api/matches/best-odds"
```

If `/api/matches` has data but `/api/matches/best-odds` is empty, it usually means only one bookmaker has scraped so far. The homepage needs overlapping bookmaker data.

## 12.1. If only some scrapers appear

If `/api/health` only shows some bookmakers with a timestamp, it means only those bookmakers have saved odds recently.

Check the worker logs:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs worker --tail=300
```

Look for lines containing:

```text
[nike]
[doxxbet]
[fortuna]
[polymarket]
Round-robin scrape cycle
```

You can also filter logs for one scraper:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs worker --tail=500 | grep nike
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs worker --tail=500 | grep doxxbet
```

Force missing scrapers:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner exec worker python -m bettingmaster.cli scrape-cycle --bookmaker nike --bookmaker doxxbet
```

Then check health again:

```bash
curl http://127.0.0.1:8000/api/health
```

If a forced scraper finishes but still does not show in health, it found no odds to save or failed before saving. Check worker logs immediately after forcing it.

## 13. Useful browser links

Main site:

```text
http://188.245.79.101:3000
```

Surebets:

```text
http://188.245.79.101:3000/surebets
```

API health:

```text
http://188.245.79.101:8000/api/health
```

API docs:

```text
http://188.245.79.101:8000/docs
```

## 14. If the worker is restarting or broken

Check logs:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs worker --tail=150
```

Then rebuild worker and backend:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d --build backend worker
```

Check status again:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner ps
```

## 15. If the frontend says API did not answer

Rebuild frontend:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d --build frontend
```

Check frontend logs:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs frontend --tail=100
```

Check backend health:

```bash
curl http://127.0.0.1:8000/api/health
```

## 16. Full clean restart

Use this only when normal restart does not help:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner down
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d --build
```

This keeps the PostgreSQL data volume. It does not delete your database.

## 17. Do not run this unless you want to delete data

Do not run this casually:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner down -v
```

The `-v` deletes Docker volumes, including the database.
