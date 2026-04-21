# Hyperlocal Air Monitor Architecture

## Components

- `apps/pi_agent`: network sync layer and Pi launcher.
- `raspberry_pi`: hardware sensing runtime (PMS5003, DHT22, OLED, RGB LED).
- `apps/backend`: FastAPI service for ingestion, config, alerts, and storage.
- `apps/frontend`: Streamlit dashboard for live data, history, alerts, and config.
- `shared`: payload contracts shared across modules.

## Data Flow

1. Pi reads sensors in `raspberry_pi/monitor.py`.
2. Each reading is logged locally to CSV and posted to backend `/api/v1/readings`.
3. Backend writes to SQLite (`output/air_monitor.db`) and evaluates alert rules.
4. Alerts are cooldown-limited and persisted in `alert_events`.
5. Streamlit reads backend endpoints and visualizes metrics/alerts.
6. Config updates from frontend are stored via `/api/v1/config/{device_id}`.
7. Pi polls config periodically and applies thresholds/sample interval at runtime.

