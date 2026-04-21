from __future__ import annotations

from pydantic import BaseModel, Field


class ReadingIn(BaseModel):
    device_id: str = Field(min_length=1)
    timestamp: str
    pm25: float | None = None
    pm10: float | None = None
    humidity: float | None = None
    temperature: float | None = None
    status: str = "ok"
    tier_ml: int | None = None
    prob_unhealthy: float | None = None


class ReadingOut(ReadingIn):
    id: int


class DeviceConfig(BaseModel):
    device_id: str = Field(min_length=1)
    caution_pm25: float = 25.0
    alert_pm25: float = 50.0
    humidity_low: float = 20.0
    humidity_high: float = 70.0
    sample_interval_sec: float = 10.0
    alert_cooldown_sec: int = 900
    updated_at: str
    last_applied_at: str | None = None


class AlertEvent(BaseModel):
    id: int
    device_id: str
    timestamp: str
    alert_type: str
    severity: str
    message: str

