from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_api_key, storage
from ..models.schemas import DeviceConfig

router = APIRouter(prefix="/api/v1/config", tags=["config"])


def _default_cfg(device_id: str) -> dict:
    return {
        "device_id": device_id,
        "caution_pm25": 25.0,
        "alert_pm25": 50.0,
        "humidity_low": 20.0,
        "humidity_high": 70.0,
        "sample_interval_sec": 10.0,
        "alert_cooldown_sec": 900,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_applied_at": None,
    }


@router.get("/{device_id}", dependencies=[Depends(require_api_key)])
def get_config(device_id: str) -> dict:
    cfg = storage.get_config(device_id)
    if cfg is None:
        cfg = _default_cfg(device_id)
        storage.upsert_config(cfg)
    return cfg


@router.put("/{device_id}", dependencies=[Depends(require_api_key)])
def update_config(device_id: str, cfg: DeviceConfig) -> dict[str, str]:
    if cfg.device_id != device_id:
        raise HTTPException(status_code=400, detail="Path device_id mismatch")
    row = cfg.model_dump()
    row["updated_at"] = datetime.now(timezone.utc).isoformat()
    storage.upsert_config(row)
    return {"status": "ok"}


@router.post("/{device_id}/applied", dependencies=[Depends(require_api_key)])
def mark_applied(device_id: str) -> dict[str, str]:
    storage.mark_config_applied(device_id, datetime.now(timezone.utc).isoformat())
    return {"status": "ok"}


@router.get("/{device_id}/alerts")
def list_alerts(device_id: str, limit: int = 100) -> list[dict]:
    alerts = storage.list_alerts(limit=limit)
    return [a for a in alerts if a["device_id"] == device_id]

