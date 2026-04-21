from __future__ import annotations

from typing import Any


def evaluate_alert(reading: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, str, str] | None:
    pm25 = reading.get("pm25")
    hum = reading.get("humidity")
    device_id = reading["device_id"]
    if pm25 is not None and pm25 > cfg["alert_pm25"]:
        return ("dust", "alert", f"[{device_id}] High dust detected: PM2.5={pm25:.1f}")
    if pm25 is not None and pm25 > cfg["caution_pm25"]:
        return ("dust", "caution", f"[{device_id}] Elevated dust: PM2.5={pm25:.1f}")
    if hum is not None and (hum < cfg["humidity_low"] or hum > cfg["humidity_high"]):
        return ("humidity", "alert", f"[{device_id}] Humidity out of range: {hum:.1f}%")
    return None

