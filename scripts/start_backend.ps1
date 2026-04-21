$env:AIRMON_API_KEY = "airmon-secure-key"
python -m uvicorn apps.backend.app:app --host 0.0.0.0 --port 8000 --reload

