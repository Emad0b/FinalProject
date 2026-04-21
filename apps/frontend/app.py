from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

API_BASE = os.getenv("AIRMON_API_BASE", "http://139.222.164.180:8000")
API_KEY = os.getenv("AIRMON_API_KEY", "airmon-secure-key")
DEVICE_ID = os.getenv("AIRMON_DEVICE_ID", "pi-001")
HEADERS = {"x-api-key": API_KEY}

st.set_page_config(page_title="Hyperlocal Air Monitor", layout="wide")
st.title("Hyperlocal Air Monitor Dashboard")


def api_get(path: str):
    return requests.get(f"{API_BASE}{path}", headers=HEADERS, timeout=5).json()


def api_put(path: str, payload: dict):
    return requests.put(f"{API_BASE}{path}", headers=HEADERS, json=payload, timeout=5)


tab_live, tab_history, tab_alerts, tab_config = st.tabs(["Live Overview", "History", "Alerts", "Configuration"])

with tab_live:
    rows = api_get("/api/v1/readings?limit=1")
    latest = rows[0] if rows else None
    if latest is None:
        st.info("No readings yet.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PM2.5", f"{latest.get('pm25') or 0:.1f}")
        c2.metric("PM10", f"{latest.get('pm10') or 0:.1f}")
        c3.metric("Humidity", f"{latest.get('humidity') or 0:.1f}%")
        c4.metric("Temperature", f"{latest.get('temperature') or 0:.1f} C")
        st.success(f"Status: {latest.get('status', 'unknown').upper()}")

with tab_history:
    rows = api_get("/api/v1/readings?limit=300")
    if rows:
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp")
        st.line_chart(df.set_index("timestamp")[["pm25", "humidity", "temperature"]])
    else:
        st.info("No history available.")

with tab_alerts:
    alerts = api_get(f"/api/v1/config/{DEVICE_ID}/alerts")
    if not alerts:
        st.info("No alerts recorded.")
    else:
        adf = pd.DataFrame(alerts)
        st.dataframe(adf, use_container_width=True)

with tab_config:
    cfg = api_get(f"/api/v1/config/{DEVICE_ID}")
    st.caption(f"Last updated: {cfg.get('updated_at', '-')}")
    with st.form("config_form"):
        caution_pm25 = st.number_input("PM2.5 caution threshold", value=float(cfg["caution_pm25"]))
        alert_pm25 = st.number_input("PM2.5 alert threshold", value=float(cfg["alert_pm25"]))
        humidity_low = st.number_input("Humidity low", value=float(cfg["humidity_low"]))
        humidity_high = st.number_input("Humidity high", value=float(cfg["humidity_high"]))
        sample_interval_sec = st.number_input("Sample interval (sec)", value=float(cfg["sample_interval_sec"]))
        alert_cooldown_sec = st.number_input("Alert cooldown (sec)", value=int(cfg["alert_cooldown_sec"]), step=60)
        submit = st.form_submit_button("Save config")

    if submit:
        payload = {
            "device_id": DEVICE_ID,
            "caution_pm25": caution_pm25,
            "alert_pm25": alert_pm25,
            "humidity_low": humidity_low,
            "humidity_high": humidity_high,
            "sample_interval_sec": sample_interval_sec,
            "alert_cooldown_sec": int(alert_cooldown_sec),
            "updated_at": datetime.utcnow().isoformat(),
            "last_applied_at": cfg.get("last_applied_at"),
        }
        resp = api_put(f"/api/v1/config/{DEVICE_ID}", payload)
        if resp.ok:
            st.success("Configuration saved. Pi will apply on next sync.")
        else:
            st.error(f"Failed to save config: {resp.status_code}")

