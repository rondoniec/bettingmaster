# BettingMaster Hetzner Setup

This guide is written for the "I just want the exact steps" case.

If you follow it line by line, you will end up with:

- the website running on port `3000`
- the API running on port `8000`
- a dedicated scraper worker running all the time
- PostgreSQL storing the data

This setup uses Docker, so you do not need to install Python, Node, or Playwright manually on the server.

## What you need before starting

You need these 3 things:

1. Your Hetzner server IP address
2. A way to log in to the server with SSH
3. This project available on the server

If the repo is on GitHub, the easiest way is to clone it on the server.

## Step 1: Connect to your server

From your own computer, open a terminal.

If you are on Windows:

```powershell
ssh root@YOUR_SERVER_IP
```

If you are on Mac or Linux:

```bash
ssh root@YOUR_SERVER_IP
```

Replace `YOUR_SERVER_IP` with the real server IP from Hetzner.

The first time, it may ask if you trust the server. Type:

```text
yes
```

If it asks for a password, enter the root password from Hetzner.

When you are connected, your prompt should look something like this:

```bash
root@your-server:~#
```

## Step 2: Update the server

Run these commands on the server:

```bash
apt update
apt upgrade -y
```

This may take a few minutes.

## Step 3: Install Docker and Git

Run:

```bash
apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl enable docker
systemctl start docker
```

Now check that Docker is installed:

```bash
docker --version
docker compose version
```

Both commands should print version numbers.

## Step 4: Put the project on the server

Move into `/opt`, which is a good place for app code:

```bash
cd /opt
```

If your repo is on GitHub, clone it:

```bash
git clone YOUR_GIT_REPO_URL bettingmaster
cd bettingmaster
```

Example:

```bash
git clone https://github.com/yourname/bettingmaster.git bettingmaster
cd bettingmaster
```

If the repo is private and `git clone` does not work, you have 2 options:

- use a GitHub token or SSH key
- upload the project manually to `/opt/bettingmaster`

If you already uploaded the project manually, just do:

```bash
cd /opt/bettingmaster
```

## Step 5: Create the server environment file

Copy the example file:

```bash
cp .env.hetzner.example .env.hetzner
```

Open it for editing:

```bash
nano .env.hetzner
```

You will see this:

```env
POSTGRES_DB=bettingmaster
POSTGRES_USER=bettingmaster
POSTGRES_PASSWORD=change-me

BM_DATABASE_URL=postgresql+psycopg://bettingmaster:change-me@db:5432/bettingmaster
BM_CORS_ORIGINS=http://YOUR_SERVER_IP:3000
BM_LOG_LEVEL=INFO

NEXT_PUBLIC_API_URL=http://YOUR_SERVER_IP:8000
```

Change:

- `change-me` to a real strong password
- `YOUR_SERVER_IP` to your real Hetzner server IP

Example:

```env
POSTGRES_DB=bettingmaster
POSTGRES_USER=bettingmaster
POSTGRES_PASSWORD=my-super-strong-password-123

BM_DATABASE_URL=postgresql+psycopg://bettingmaster:my-super-strong-password-123@db:5432/bettingmaster
BM_CORS_ORIGINS=http://95.217.123.45:3000
BM_LOG_LEVEL=INFO

NEXT_PUBLIC_API_URL=http://95.217.123.45:8000
```

To save in `nano`:

1. Press `Ctrl+O`
2. Press `Enter`
3. Press `Ctrl+X`

## Step 6: Start BettingMaster

Still inside `/opt/bettingmaster`, run:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d --build
```

What this does:

- builds the backend image
- builds the frontend image
- starts PostgreSQL
- starts the API
- starts the scraper worker

The first run can take quite a while because it downloads Docker images and browser dependencies.

## Step 7: Check that everything is running

Run:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner ps
```

You should see services like:

- `db`
- `backend`
- `worker`
- `frontend`

If you want to watch logs:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs -f
```

To stop watching logs, press:

```text
Ctrl+C
```

## Step 8: Open the app in your browser

Open these URLs in your browser:

- frontend: `http://YOUR_SERVER_IP:3000`
- API docs: `http://YOUR_SERVER_IP:8000/docs`
- API health: `http://YOUR_SERVER_IP:8000/api/health`

Replace `YOUR_SERVER_IP` with the real IP.

## Step 9: Understand what is running

This stack has 4 parts:

- `db`: PostgreSQL database
- `backend`: FastAPI server
- `worker`: the always-on scraper process
- `frontend`: the Next.js website

Important:

- the scraper runs in `worker`, not in the website
- that means scraping keeps going in the background
- Docker is set to `restart: unless-stopped`, so services should come back after a reboot
- inside Docker, the frontend talks to the backend using the internal service name `backend`

## Daily commands you will actually use

Go to the project folder first:

```bash
cd /opt/bettingmaster
```

### See if containers are running

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner ps
```

### Watch logs

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs -f
```

### Restart only the scraper

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner restart worker
```

### Restart everything

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner restart
```

### Stop everything

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner down
```

### Start everything again

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d
```

## How to update the app later

If the code changed and you want the server to use the new version:

```bash
cd /opt/bettingmaster
git pull
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d --build
```

## If the site does not open

Check these things in order:

### 1. Are the containers running?

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner ps
```

If one says `Exited`, check logs:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner logs -f
```

### 2. Is the server firewall blocking ports?

You need these ports reachable:

- `22` for SSH
- `3000` for the frontend
- `8000` for the API

If you use a Hetzner firewall, make sure those ports are allowed.

### 3. Did you replace `YOUR_SERVER_IP` in `.env.hetzner`?

Check with:

```bash
cat .env.hetzner
```

If you still see `YOUR_SERVER_IP`, fix the file:

```bash
nano .env.hetzner
```

Then restart:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d --build
```

### 4. Is the API alive?

Run this on the server:

```bash
curl http://127.0.0.1:8000/api/health
```

If it returns JSON, the backend is alive.

### 5. Is the frontend alive?

Run this on the server:

```bash
curl http://127.0.0.1:3000
```

If it returns HTML, the frontend is alive.

## If you reboot the server

After a reboot, Docker should start the containers again automatically.

To check:

```bash
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner ps
```

If they did not come back, start them manually:

```bash
cd /opt/bettingmaster
docker compose -f docker-compose.hetzner-bettingmaster.yml --env-file .env.hetzner up -d
```

## Next improvement after this works

Once this is running, the next smart improvement is:

- attach a real domain
- put Nginx or Caddy in front
- serve the site on normal HTTPS instead of raw ports `3000` and `8000`

But for the first deployment, the steps above are enough to get BettingMaster live and scraping continuously.
