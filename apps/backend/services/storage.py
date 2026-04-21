from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    pm25 REAL,
                    pm10 REAL,
                    humidity REAL,
                    temperature REAL,
                    status TEXT NOT NULL,
                    tier_ml INTEGER,
                    prob_unhealthy REAL
                );

                CREATE TABLE IF NOT EXISTS device_config (
                    device_id TEXT PRIMARY KEY,
                    caution_pm25 REAL NOT NULL,
                    alert_pm25 REAL NOT NULL,
                    humidity_low REAL NOT NULL,
                    humidity_high REAL NOT NULL,
                    sample_interval_sec REAL NOT NULL,
                    alert_cooldown_sec INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_applied_at TEXT
                );

                CREATE TABLE IF NOT EXISTS alert_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                """
            )

    def insert_reading(self, payload: dict[str, Any]) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO readings(device_id, timestamp, pm25, pm10, humidity, temperature, status, tier_ml, prob_unhealthy)
                VALUES(:device_id, :timestamp, :pm25, :pm10, :humidity, :temperature, :status, :tier_ml, :prob_unhealthy)
                """,
                payload,
            )
            return int(cur.lastrowid)

    def latest_readings(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM readings ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_config(self, device_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM device_config WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def upsert_config(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_config(device_id, caution_pm25, alert_pm25, humidity_low, humidity_high, sample_interval_sec, alert_cooldown_sec, updated_at, last_applied_at)
                VALUES(:device_id, :caution_pm25, :alert_pm25, :humidity_low, :humidity_high, :sample_interval_sec, :alert_cooldown_sec, :updated_at, :last_applied_at)
                ON CONFLICT(device_id) DO UPDATE SET
                    caution_pm25=excluded.caution_pm25,
                    alert_pm25=excluded.alert_pm25,
                    humidity_low=excluded.humidity_low,
                    humidity_high=excluded.humidity_high,
                    sample_interval_sec=excluded.sample_interval_sec,
                    alert_cooldown_sec=excluded.alert_cooldown_sec,
                    updated_at=excluded.updated_at,
                    last_applied_at=excluded.last_applied_at
                """,
                payload,
            )

    def mark_config_applied(self, device_id: str, applied_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE device_config SET last_applied_at = ? WHERE device_id = ?",
                (applied_at, device_id),
            )

    def insert_alert(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO alert_events(device_id, timestamp, alert_type, severity, message)
                VALUES(:device_id, :timestamp, :alert_type, :severity, :message)
                """,
                payload,
            )

    def list_alerts(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM alert_events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

