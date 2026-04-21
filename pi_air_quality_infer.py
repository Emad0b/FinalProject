"""
Raspberry Pi–friendly inference: stdlib + json only (copy this file + the JSON artifacts).

Rolling means (pm25_ma7, pm25_ma30) should be updated each reading from a short buffer
of recent PM2.5 values (e.g. collections.deque).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps) or 1.0
    return [e / s for e in exps]


def led_risk_tier(pm25: float) -> int:
    if pm25 <= 25:
        return 0
    if pm25 <= 50:
        return 1
    return 2


def humidity_uncomfortable(humidity: float, low: float = 20.0, high: float = 70.0) -> bool:
    return humidity < low or humidity > high


def build_feature_vector_live(
    pm25: float,
    pm10: float,
    humidity: float,
    temperature: float,
    pm25_ma7: float,
    pm25_ma30: float,
    prev_pm25: float | None,
) -> list[float]:
    d1 = 0.0 if prev_pm25 is None else pm25 - prev_pm25
    ratio = pm10 / (pm25 + 1e-6)
    return [pm25, pm10, humidity, temperature, pm25_ma7, pm25_ma30, d1, ratio]


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


def _scale(x: list[float], mean: list[float], scale: list[float]) -> list[float]:
    return [(xi - mi) / si if si else 0.0 for xi, mi, si in zip(x, mean, scale)]


def load_artifact(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def predict_air_tier_proba(artifact: dict[str, Any], features: list[float]) -> tuple[int, list[float], list[str]]:
    x = _scale(features, artifact["scaler_mean"], artifact["scaler_scale"])
    coef = artifact["coef"]
    intercept = artifact["intercept"]
    logits = [sum(c[j] * x[j] for j in range(len(x))) + b for c, b in zip(coef, intercept)]
    probs = softmax(logits)
    k = int(max(range(len(probs)), key=lambda i: probs[i]))
    names = artifact.get("class_names", [str(i) for i in range(len(probs))])
    return k, probs, names


def predict_proxy_tier_proba(artifact: dict[str, Any], features: list[float]) -> tuple[int, list[float], list[str]]:
    """PM2.5-free model: pass build_proxy_feature_vector_live(...) output."""
    return predict_air_tier_proba(artifact, features)


def predict_humidity_stress(artifact: dict[str, Any], temperature: float, pm25: float, month: int) -> tuple[int, float]:
    feats = [temperature, pm25, float(month)]
    x = _scale(feats, artifact["scaler_mean"], artifact["scaler_scale"])
    w = artifact["coef"]
    b = artifact["intercept"]
    z = sum(wj * xj for wj, xj in zip(w, x)) + b
    p1 = 1.0 / (1.0 + math.exp(-z)) if abs(z) < 30 else (1.0 if z > 0 else 0.0)
    return (1 if p1 >= 0.5 else 0), p1


def recommend_alert(
    pm25: float,
    humidity: float,
    tier_ml: int,
    prob_unhealthy: float,
    hum_stress: bool,
    prob_hum_stress: float | None,
    unhealthy_prob_threshold: float = 0.35,
    tier_proxy: int | None = None,
    proxy_disagree_escalate: bool = True,
) -> str:
    """
    If tier_proxy is set (PM2.5-free model), optional escalation when proxy says worse than raw PM2.5 tier.
    """
    raw = led_risk_tier(pm25)
    eff = raw
    if proxy_disagree_escalate and tier_proxy is not None and tier_proxy > raw:
        eff = tier_proxy
    if eff >= 2 or prob_unhealthy >= unhealthy_prob_threshold:
        return "alert"
    if eff >= 1 or tier_ml >= 1:
        return "caution"
    if hum_stress or (prob_hum_stress is not None and prob_hum_stress >= 0.55):
        return "humidity"
    return "ok"


def demo() -> None:
    root = Path(__file__).resolve().parent
    art_path = root / "output" / "ml_artifacts" / "pi_air_quality_logreg.json"
    if not art_path.exists():
        print("Run single_station_ml.py first; missing", art_path)
        return
    art = load_artifact(art_path)
    fv = build_feature_vector_live(32.0, 48.0, 35.0, 22.0, 18.0, 15.0, 28.0)
    tier, probs, names = predict_air_tier_proba(art, fv)
    print("tier", tier, names[tier], "probs", [round(p, 3) for p in probs])
    hum_path = root / "output" / "ml_artifacts" / "pi_humidity_stress_logreg.json"
    p_hs: float | None = None
    if hum_path.exists():
        ha = load_artifact(hum_path)
        _hs, p_hs = predict_humidity_stress(ha, 22.0, 32.0, 4)
        print("humidity stress model:", _hs, "p(stress)", round(p_hs, 3))
    rec = recommend_alert(
        32.0,
        35.0,
        tier,
        probs[2],
        humidity_uncomfortable(35.0),
        p_hs,
    )
    print("recommend_alert:", rec)


if __name__ == "__main__":
    demo()
