# Hetzner Challenger Circuit Worker

This project now includes a separate `cc_worker.py` service for ALGS Challenger Circuit lookups.

The main app can call this worker if you set:

- `CC_WORKER_URL`
- `CC_WORKER_TOKEN`

in the environment where `app.py` runs.

## What the worker does

- launches Playwright Chromium on the server
- opens a real Battlefy browser session
- fetches Challenger Circuit stage data from Battlefy endpoints
- returns normalized standings JSON for the extension backend

This keeps the Pro League and Scrims logic in the main backend untouched.

## Deploy on Hetzner With Docker

From the repo root:

```bash
docker compose -f docker-compose.hetzner.yml build
CC_WORKER_TOKEN=your-secret-token docker compose -f docker-compose.hetzner.yml up -d
```

The worker listens on:

```text
http://<your-server>:8787
```

Health check:

```bash
curl http://127.0.0.1:8787/health
```

## Connect the main backend

Where `app.py` runs, set:

```bash
export CC_WORKER_URL=http://<your-server>:8787
export CC_WORKER_TOKEN=your-secret-token
```

Then run the main backend normally:

```bash
python app.py
```

## Current CC config inputs

In config mode, Challenger Circuit currently needs:

- target team name or player name
- Battlefy match URL
- Battlefy stage ID

Optional:

- region label
- round label
- lobby label

## Important limitation

The worker is ready for production-style hosting, but Battlefy stage auto-discovery from only the public URL is still unfinished. Right now the cleanest path is:

1. find the correct Battlefy `stage_id`
2. save it in config
3. let the worker resolve standings from there

Once we solve auto-discovery, that manual `stage_id` field can be removed.
