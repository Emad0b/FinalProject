"""
Shared feature definitions for training (PC) and inference (Raspberry Pi).

Feature order must match `FEATURE_COLUMNS` when building matrices and the exported JSON.
"""

from __future__ import annotations

import math
from typing import Sequence

import pandas as pd

FEATURE_COLUMNS = [
    "pm25",
    "pm10",
    "humidity",
    "temperature",
    "pm25_ma7",
    "pm25_ma30",
    "pm25_delta1",
    "pm10_pm25_ratio",
]

# No instantaneous PM2.5 — for Pi as a weak sanity check / context-only hint (train on EcoCity).
PROXY_FEATURE_COLUMNS = [
    "pm10",
    "humidity",
    "temperature",
    "pm10_ma7",
    "pm10_ma30",
    "pm10_delta1",
]


def add_engineered_columns(wide: pd.DataFrame) -> pd.DataFrame:
    """Mutates a copy: expects columns pm25, pm10, humidity, temperature."""
    df = wide.copy()
    if "pm25" not in df.columns:
        raise ValueError("pm25 required")
    df["pm25_ma7"] = df["pm25"].rolling(window=7, min_periods=1).mean()
    df["pm25_ma30"] = df["pm25"].rolling(window=30, min_periods=1).mean()
    df["pm25_delta1"] = df["pm25"].diff().fillna(0.0)
    eps = 1e-6
    df["pm10_pm25_ratio"] = df["pm10"] / (df["pm25"] + eps)
    df["pm10_ma7"] = df["pm10"].rolling(window=7, min_periods=1).mean()
    df["pm10_ma30"] = df["pm10"].rolling(window=30, min_periods=1).mean()
    df["pm10_delta1"] = df["pm10"].diff().fillna(0.0)
    return df


def led_risk_tier(pm25: float) -> int:
    """0 = green ≤25, 1 = yellow 25–50, 2 = red >50 µg/m³."""
    if pm25 <= 25:
        return 0
    if pm25 <= 50:
        return 1
    return 2


def humidity_uncomfortable(humidity: float, low: float = 20.0, high: float = 70.0) -> bool:
    return humidity < low or humidity > high


def build_feature_vector_row(row: pd.Series) -> list[float]:
    return [float(row[c]) for c in FEATURE_COLUMNS]


def build_feature_vector_live(
    pm25: float,
    pm10: float,
    humidity: float,
    temperature: float,
    pm25_ma7: float,
    pm25_ma30: float,
    prev_pm25: float | None,
) -> list[float]:
    """For Pi: supply rolling means you maintain in firmware; prev_pm25 for delta (or None → 0)."""
    d1 = 0.0 if prev_pm25 is None else pm25 - prev_pm25
    ratio = pm10 / (pm25 + 1e-6)
    return [
        pm25,
        pm10,
        humidity,
        temperature,
        pm25_ma7,
        pm25_ma30,
        d1,
        ratio,
    ]


def build_proxy_feature_vector_live(
    pm10: float,
    humidity: float,
    temperature: float,
    pm10_ma7: float,
    pm10_ma30: float,
    prev_pm10: float | None,
) -> list[float]:
    d1 = 0.0 if prev_pm10 is None else pm10 - prev_pm10
    return [pm10, humidity, temperature, pm10_ma7, pm10_ma30, d1]


def softmax(logits: Sequence[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps) or 1.0
    return [e / s for e in exps]
