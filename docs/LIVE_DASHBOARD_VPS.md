# Live Dashboard VPS Deployment

This dashboard is research-only. It does not place trades, mutate accounts, or use paid APIs.

## Local Run

Install dependencies:

```powershell
rtk python -m pip install -r requirements.txt
```

Set a password and run:

```powershell
$env:LIVE_DASHBOARD_PASSWORD="change-me"
rtk python -m uvicorn live_app:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000
```

## VPS Workflow

Recommended workflow is GitHub plus SSH:

1. Push this repo to GitHub from your local machine.
2. SSH into the VPS.
3. Clone or pull the repo.
4. Install dependencies in a virtual environment.
5. Run the dashboard with Uvicorn, preferably behind systemd.

Example VPS commands:

```bash
git clone https://github.com/YOUR_USER/YOUR_REPO.git kalshi-weather
cd kalshi-weather
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export LIVE_DASHBOARD_PASSWORD='change-me'
uvicorn live_app:app --host 0.0.0.0 --port 8000
```

## systemd Service

Create `/etc/systemd/system/kalshi-live-dashboard.service`:

```ini
[Unit]
Description=Kalshi Weather Live Dashboard
After=network.target

[Service]
WorkingDirectory=/home/YOUR_USER/kalshi-weather
Environment=LIVE_DASHBOARD_PASSWORD=change-me
ExecStart=/home/YOUR_USER/kalshi-weather/.venv/bin/uvicorn live_app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable kalshi-live-dashboard
sudo systemctl start kalshi-live-dashboard
sudo systemctl status kalshi-live-dashboard
```

To update later:

```bash
cd /home/YOUR_USER/kalshi-weather
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart kalshi-live-dashboard
```

## Optional Nginx Proxy

Use Nginx and HTTPS if exposing the dashboard publicly. Keep the dashboard password enabled.

```nginx
server {
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## What It Shows

The live dashboard tracks only:

- Phoenix
- Las Vegas
- San Antonio

Each city card shows:

- current Kalshi winning bucket and second bucket
- current official-station temperature
- raw and rounded high so far
- NWS forecast high
- critical hour in Eastern time
- heating pace and needed rate
- reachability label
- market/weather alignment
- false-hotter-pump warning

The browser polls every 15 seconds, but the backend refreshes external data no more than once every 60 seconds.
