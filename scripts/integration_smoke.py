from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone

BASE = os.getenv("AIRMON_API_BASE", "http://139.222.164.180:8000")
KEY = os.getenv("AIRMON_API_KEY", "airmon-secure-key")
DEVICE = os.getenv("AIRMON_DEVICE_ID", "pi-001")


def request_json(method: str, path: str, payload: dict | None = None) -> dict | list:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        method=method,
        headers={"x-api-key": KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read().decode("utf-8"))


if __name__ == "__main__":
    print(request_json("GET", "/health"))
    reading = {
        "device_id": DEVICE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pm25": 61.0,
        "pm10": 88.0,
        "humidity": 75.0,
        "temperature": 30.0,
        "status": "alert",
        "tier_ml": 2,
        "prob_unhealthy": 0.91,
    }
    print("Insert:", request_json("POST", "/api/v1/readings", reading))
    print("Config:", request_json("GET", f"/api/v1/config/{DEVICE}"))
    print("Readings:", len(request_json("GET", "/api/v1/readings?limit=10")))
    print("Alerts:", len(request_json("GET", f"/api/v1/config/{DEVICE}/alerts")))

