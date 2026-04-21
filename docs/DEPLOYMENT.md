# Deployment and Validation

## Install

1. Backend deps:
   - `pip install -r requirements-backend.txt`
2. Frontend deps:
   - `pip install -r requirements-frontend.txt`
3. Pi deps:
   - existing `raspberry_pi/requirements.txt`

## Run Locally (Laptop)

1. Start backend:
   - `powershell -ExecutionPolicy Bypass -File scripts/start_backend.ps1`
2. Start frontend:
   - `powershell -ExecutionPolicy Bypass -File scripts/start_frontend.ps1`

## Run Pi Agent

- `powershell -ExecutionPolicy Bypass -File scripts/start_pi_agent.ps1`
- Optional flags:
  - `--config-sync-sec 30`
  - `--queue-path raspberry_pi/data/outbox.json`

## Internet/LAN Connectivity

- Use laptop LAN IP for `--backend-url` when Pi and laptop are on same Wi-Fi.
- For internet access, use VPN/tunnel or secure reverse proxy.
- Rotate `AIRMON_API_KEY` in production and avoid default key.

## Validation Checklist

- Backend health:
  - `GET /health` returns `{"status":"ok"}`
- Ingestion:
  - Pi/mock posts readings to `/api/v1/readings` and data appears in dashboard.
- Config sync:
  - Change thresholds in Streamlit Configuration page, verify Pi applies within sync interval.
- Alerts:
  - Force PM2.5/humidity out-of-range values and verify alert event appears once per cooldown window.

