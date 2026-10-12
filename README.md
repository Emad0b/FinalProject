# Hyperlocal Air Monitor

An IoT air-monitoring project combining Raspberry Pi sensor readings, a FastAPI backend, a Streamlit dashboard, and offline air-quality data analysis. The repository is named `FinalProject`; its application is the Hyperlocal Air Monitor.

## Components

- **Pi runtime:** PMS5003 particulate sensing, DHT22 temperature/humidity, OLED display, status LEDs, local CSV logging, and an offline upload queue.
- **Backend:** authenticated reading ingestion, SQLite persistence, device configuration, and cooldown-limited alerts.
- **Dashboard:** live measurements, historical charts, recorded alerts, and configuration updates.
- **Analysis:** EcoCity archive processing, feature preparation, single-station model training, and exported JSON models for on-device inference.

## Run the backend and dashboard

Use Python and run the following from the repository root. A virtual environment is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-backend.txt -r requirements-frontend.txt
$env:AIRMON_API_KEY = "replace-with-your-local-key"
python -m uvicorn apps.backend.app:app --host 127.0.0.1 --port 8000
```

In a second terminal, activate the same environment and set matching configuration:

```powershell
$env:AIRMON_API_BASE = "http://127.0.0.1:8000"
$env:AIRMON_API_KEY = "replace-with-your-local-key"
$env:AIRMON_DEVICE_ID = "pi-001"
streamlit run apps/frontend/app.py
```

Open the Streamlit URL printed in the terminal. Backend health is available at `http://127.0.0.1:8000/health`; interactive API documentation is at `/docs`. The dashboard needs readings from the Pi agent or a mock producer before charts populate.

The existing launcher scripts contain a fixed remote backend address and a default API key. The commands above explicitly configure a local backend instead. `AIRMON_DB_PATH` can override the default `output/air_monitor.db` database location.

## Raspberry Pi and mock mode

See [Pi setup and supported flags](raspberry_pi/README.md) and the [wiring guide](raspberry_pi/WIRING_GUIDE.md). The Pi documentation includes a `--mock` mode for testing without physical sensors and `--no-ml` for threshold-only operation.

Pi rolling-window features operate over sensor samples; the offline EcoCity analysis uses different time windows. Model transfer therefore requires checking feature alignment rather than assuming equivalent measurements.

## Repository layout

- `apps/backend/`: FastAPI service, routes, storage, alerts, and notification support.
- `apps/frontend/`: Streamlit application.
- `apps/pi_agent/` and `raspberry_pi/`: sensing, network synchronization, and device runtime.
- `shared/`: shared reading contracts.
- `Dataset/`: included archive CSV.
- `output/`: processed data, plots, summaries, and model exports.
- Root Python scripts: archive processing, feature engineering, model training, and inference.

## Further documentation

[Architecture](docs/ARCHITECTURE.md) explains the sensor-to-dashboard data flow. [Deployment and validation](docs/DEPLOYMENT.md) covers connectivity, configuration synchronization, and alert checks. Review dataset provenance and permissions before redistributing the included archive or derived data.
