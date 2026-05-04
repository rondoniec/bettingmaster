# Laptop Scraper Host Setup

Run all commands on Ubuntu laptop via SSH from Mac.

```bash
ssh USERNAME@192.168.1.101
```

---

## 1. Keep laptop awake forever

### Disable sleep/suspend/hibernate

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

### Ignore lid close

```bash
sudo sed -i 's/^#*HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf
sudo sed -i 's/^#*HandleLidSwitchDocked=.*/HandleLidSwitchDocked=ignore/' /etc/systemd/logind.conf
sudo sed -i 's/^#*HandleLidSwitchExternalPower=.*/HandleLidSwitchExternalPower=ignore/' /etc/systemd/logind.conf
sudo systemctl restart systemd-logind
```

### Disable GNOME idle (skip if no desktop)

```bash
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing'
gsettings set org.gnome.desktop.screensaver lock-enabled false
```

### Console screen blank off

```bash
sudo setterm -blank 0 -powerdown 0 2>/dev/null || true
```

### Auto-reboot on kernel panic

```bash
echo 'kernel.panic = 10' | sudo tee /etc/sysctl.d/99-panic.conf
sudo sysctl -p /etc/sysctl.d/99-panic.conf
```

### Verify

```bash
systemctl status sleep.target suspend.target hibernate.target
systemd-inhibit --list
```

Expect `masked` + minimal inhibitors.

### BIOS step (manual)

Reboot, enter BIOS, find:

- `AC Power Recovery` / `Restore on AC Loss` → set **On** / **Last State**

So power blackout = laptop auto power-on.

---

## 2. Install Docker + git

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Logout + login again so docker group take effect:

```bash
exit
```

Then `ssh USERNAME@192.168.1.101` again.

Verify:

```bash
docker run --rm hello-world
```

---

## 3. Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Open URL printed → login Tailscale account (same account use on Hetzner later).

Get laptop tailnet IP:

```bash
tailscale ip -4
```

Note this IP. Looks like `100.x.y.z`.

---

## 4. Clone repo

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/rondoniec/bettingmaster.git
cd bettingmaster
```

(Adjust repo URL if different.)

---

## 5. Start the stack

Copy `.env` and `.env.laptop` to `~/projects/bettingmaster/` (get them from the Mac project).

Then start everything:

```bash
cd ~/projects/bettingmaster
docker compose -f docker-compose.laptop.yml --env-file .env up -d --build
```

Check all four services are up:

```bash
docker compose -f docker-compose.laptop.yml --env-file .env ps
```

Expected: `db` healthy, `backend` healthy, `frontend` up, `worker` up.

---

## Current status

Setup complete as of 2026-05-03. Laptop is the sole production host.

- Tailscale IP: `100.75.68.42`
- All 4 services run on this machine
- Hetzner decommissioned

See `SERVER_RUNBOOK.md` for day-to-day operations.
