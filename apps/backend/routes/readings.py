from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ..deps import notifier, require_api_key, storage
from ..models.schemas import ReadingIn
from ..services.alerts import evaluate_alert

router = APIRouter(prefix="/api/v1/readings", tags=["readings"])


@router.post("", dependencies=[Depends(require_api_key)])
def ingest_reading(reading: ReadingIn) -> dict[str, int]:
    row = reading.model_dump()
    row_id = storage.insert_reading(row)

    cfg = storage.get_config(reading.device_id) or {
        "device_id": reading.device_id,
        "caution_pm25": 25.0,
        "alert_pm25": 50.0,
        "humidity_low": 20.0,
        "humidity_high": 70.0,
        "sample_interval_sec": 10.0,
        "alert_cooldown_sec": 900,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_applied_at": None,
    }
    if not storage.get_config(reading.device_id):
        storage.upsert_config(cfg)

    alert = evaluate_alert(row, cfg)
    if alert is not None:
        alert_type, severity, message = alert
        if notifier.should_send(reading.device_id, alert_type, int(cfg["alert_cooldown_sec"])):
            storage.insert_alert(
                {
                    "device_id": reading.device_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "alert_type": alert_type,
                    "severity": severity,
                    "message": message,
                }
            )
            notifier.send(message)
    return {"id": row_id}


@router.get("")
def list_readings(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict]:
    return storage.latest_readings(limit=limit)

