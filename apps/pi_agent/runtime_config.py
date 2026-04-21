from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeConfig:
    caution_pm25: float = 25.0
    alert_pm25: float = 50.0
    humidity_low: float = 20.0
    humidity_high: float = 70.0
    sample_interval_sec: float = 10.0
    alert_cooldown_sec: int = 900

    def apply_dict(self, payload: dict) -> None:
        self.caution_pm25 = float(payload.get("caution_pm25", self.caution_pm25))
        self.alert_pm25 = float(payload.get("alert_pm25", self.alert_pm25))
        self.humidity_low = float(payload.get("humidity_low", self.humidity_low))
        self.humidity_high = float(payload.get("humidity_high", self.humidity_high))
        self.sample_interval_sec = float(payload.get("sample_interval_sec", self.sample_interval_sec))
        self.alert_cooldown_sec = int(payload.get("alert_cooldown_sec", self.alert_cooldown_sec))

