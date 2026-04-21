#!/usr/bin/env python3
"""
Air quality monitor for Raspberry Pi — wiring matches `config.py` / README.

Reads PMS5003 (UART), DHT22 (GPIO4), updates SSD1306 OLED (I2C), two status LEDs,
logs CSV, optionally runs exported logistic-regression JSON from the PC training pipeline.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PKG = Path(__file__).resolve().parent
# Allow `python3 monitor.py` from this folder
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))
# Repo root: pi_air_quality_infer.py
_ROOT = _PKG.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
from hardware import OledDisplay, StatusLeds
from sensors import DHTReader, PMReading, PMS5003Reader
from apps.pi_agent.network import PiApiClient
from apps.pi_agent.runtime_config import RuntimeConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("monitor")


def _mean(values: deque[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def append_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)


def update_status_leds(leds: StatusLeds, status: str) -> None:
    """Healthy LED stays on; event LED lights for non-ok states."""
    leds.set_healthy(True)
    leds.set_event(status in {"alert", "caution", "humidity"})


def run_mock_loop(interval: float) -> None:
    """Desktop test without hardware or Blinka."""
    log.warning("Mock mode: no GPIO/UART/I2C (Ctrl+C to stop)")
    pm25_hist: deque[float] = deque(maxlen=config.ROLL_PM25_LONG_SAMPLES)
    try:
        i = 0
        while True:
            pm25 = 12.0 + (i % 17) * 2.0
            pm10 = pm25 * 1.4
            pm25_hist.append(pm25)
            ma7 = _mean(deque(list(pm25_hist)[-config.ROLL_PM25_SHORT_SAMPLES :]))
            ma30 = _mean(pm25_hist)
            log.info(
                "mock PM2.5=%.1f PM10=%.1f ma7=%.1f ma30=%.1f",
                pm25,
                pm10,
                ma7,
                ma30,
            )
            i += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Mock stopped")


def main() -> None:
    ap = argparse.ArgumentParser(description="Hyperlocal air monitor (Pi)")
    ap.add_argument("--mock", action="store_true", help="No hardware; print fake loop")
    ap.add_argument("--interval", type=float, default=config.SAMPLE_INTERVAL_SEC)
    ap.add_argument("--log", type=Path, default=config.DEFAULT_LOG_PATH)
    ap.add_argument("--no-ml", action="store_true", help="Skip JSON logistic regression")
    ap.add_argument("--backend-url", default=config.DEFAULT_BACKEND_URL)
    ap.add_argument("--api-key", default=config.DEFAULT_API_KEY)
    ap.add_argument("--device-id", default=config.DEFAULT_DEVICE_ID)
    ap.add_argument("--config-sync-sec", type=float, default=config.DEFAULT_CONFIG_SYNC_SEC)
    ap.add_argument(
        "--queue-path",
        type=Path,
        default=config.DEFAULT_OFFLINE_QUEUE_PATH,
        help="Offline queue for unsent readings",
    )
    args = ap.parse_args()

    if args.mock:
        run_mock_loop(args.interval)
        return

    try:
        import pi_air_quality_infer as infer
    except ImportError:
        infer = None  # type: ignore[assignment]

    ml_air: dict[str, Any] | None = None
    ml_hum: dict[str, Any] | None = None
    if infer and not args.no_ml:
        if config.ML_LOGREG_PATH.is_file():
            ml_air = infer.load_artifact(config.ML_LOGREG_PATH)
            log.info("Loaded ML air model %s", config.ML_LOGREG_PATH)
        else:
            log.warning("No %s — threshold-only mode for fusion", config.ML_LOGREG_PATH)
        if config.ML_HUMIDITY_PATH.is_file():
            ml_hum = infer.load_artifact(config.ML_HUMIDITY_PATH)

    dht = DHTReader(config.DHT22_PIN)
    pms = PMS5003Reader()
    leds = StatusLeds(config.HEALTH_LED_PIN, config.EVENT_LED_PIN)
    oled = OledDisplay(config.OLED_I2C_PORT, config.OLED_I2C_ADDRESS)

    dht.open()
    pms.open()
    leds.open()
    oled.open()

    pm_hist: deque[float] = deque(maxlen=config.ROLL_PM25_LONG_SAMPLES)
    prev_pm25: float | None = None
    last_temp: float | None = None
    last_hum: float | None = None
    last_config_sync = 0.0
    runtime = RuntimeConfig(sample_interval_sec=args.interval)
    api_client = PiApiClient(args.backend_url, args.api_key, args.device_id, args.queue_path)

    try:
        while True:
            ts = datetime.now(timezone.utc).isoformat()
            pm: PMReading | None = None
            for _ in range(3):
                pm = pms.read()
                if pm is not None:
                    break
                time.sleep(0.05)

            t_c, h_pct = dht.read(min_interval_sec=config.DHT_MIN_INTERVAL_SEC)
            if t_c is not None:
                last_temp = t_c
            if h_pct is not None:
                last_hum = h_pct

            pm25 = pm.pm25 if pm else None
            pm10 = pm.pm10 if pm else None
            if pm25 is not None:
                pm25 = max(0.0, min(pm25, 500.0))
                pm_hist.append(pm25)
            if pm10 is not None:
                pm10 = max(0.0, min(pm10, 600.0))

            ma7 = _mean(deque(list(pm_hist)[-config.ROLL_PM25_SHORT_SAMPLES :]))
            ma30 = _mean(pm_hist)

            tier_ml = 0
            probs: list[float] = [1.0, 0.0, 0.0]
            p_hum_stress: float | None = None

            if (
                infer
                and ml_air
                and pm25 is not None
                and pm10 is not None
                and last_hum is not None
                and last_temp is not None
            ):
                fv = infer.build_feature_vector_live(
                    pm25,
                    pm10,
                    last_hum,
                    last_temp,
                    ma7,
                    ma30,
                    prev_pm25,
                )
                tier_ml, probs, _names = infer.predict_air_tier_proba(ml_air, fv)

            if infer and ml_hum and last_temp is not None and pm25 is not None:
                _hs, p_hum_stress = infer.predict_humidity_stress(
                    ml_hum, last_temp, pm25, datetime.now().month
                )

            hum_stress = False
            if last_hum is not None:
                if infer is not None:
                    hum_stress = infer.humidity_uncomfortable(last_hum)
                else:
                    hum_stress = last_hum < 20 or last_hum > 70

            status = "ok"
            if infer is not None and pm25 is not None and last_hum is not None:
                status = infer.recommend_alert(
                    pm25,
                    last_hum,
                    tier_ml,
                    probs[2] if len(probs) > 2 else 0.0,
                    hum_stress,
                    p_hum_stress,
                )
            elif pm25 is not None:
                status = (
                    "alert"
                    if pm25 > runtime.alert_pm25
                    else "caution"
                    if pm25 > runtime.caution_pm25
                    else "humidity"
                    if last_hum is not None and (last_hum < runtime.humidity_low or last_hum > runtime.humidity_high)
                    else "ok"
                )

            update_status_leds(leds, status)

            trend = ""
            if pm25 is not None and prev_pm25 is not None:
                trend = "^" if pm25 > prev_pm25 + 1 else "v" if pm25 < prev_pm25 - 1 else "-"
            line5 = f"{'ML' if ml_air else 'TH'} {status.upper()} {trend}"
            line6 = f"ma7={ma7:.0f} ma30={ma30:.0f}" if pm_hist else "warming up..."

            oled.render(pm25, pm10, last_temp, last_hum, line5, line6)

            row = {
                "timestamp": ts,
                "pm25": pm25,
                "pm10": pm10,
                "pm100": pm.pm100 if pm else None,
                "humidity": last_hum,
                "temperature": last_temp,
                "status": status,
                "tier_ml": tier_ml,
                "prob_unhealthy": probs[2] if len(probs) > 2 else None,
            }
            append_csv(args.log, row)
            api_client.send_reading(row)

            now = time.time()
            if now - last_config_sync >= args.config_sync_sec:
                cfg = api_client.fetch_config()
                if cfg:
                    runtime.apply_dict(cfg)
                    args.interval = runtime.sample_interval_sec
                    api_client.mark_applied()
                last_config_sync = now

            if pm25 is not None:
                prev_pm25 = pm25

            time.sleep(max(1.0, args.interval))
    except KeyboardInterrupt:
        log.info("Stopping")
    finally:
        leds.close()
        oled.close()
        pms.close()
        dht.close()


if __name__ == "__main__":
    main()
