from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ReadingPayload:
    device_id: str
    timestamp: str
    pm25: float | None
    pm10: float | None
    humidity: float | None
    temperature: float | None
    status: str
    tier_ml: int | None = None
    prob_unhealthy: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceConfigPayload:
    device_id: str
    caution_pm25: float = 25.0
    alert_pm25: float = 50.0
    humidity_low: float = 20.0
    humidity_high: float = 70.0
    sample_interval_sec: float = 10.0
    alert_cooldown_sec: int = 900
    updated_at: str = ""

    def normalized(self) -> "DeviceConfigPayload":
        updated_at = self.updated_at or utc_now_iso()
        return DeviceConfigPayload(
            device_id=self.device_id,
            caution_pm25=float(self.caution_pm25),
            alert_pm25=float(self.alert_pm25),
            humidity_low=float(self.humidity_low),
            humidity_high=float(self.humidity_high),
            sample_interval_sec=max(1.0, float(self.sample_interval_sec)),
            alert_cooldown_sec=max(60, int(self.alert_cooldown_sec)),
            updated_at=updated_at,
        )

