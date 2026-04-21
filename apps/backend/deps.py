from __future__ import annotations

import os
from pathlib import Path

from fastapi import Header, HTTPException

from .services.notifier import Notifier
from .services.storage import Storage

API_KEY = os.getenv("AIRMON_API_KEY", "airmon-secure-key")
DB_PATH = Path(os.getenv("AIRMON_DB_PATH", "output/air_monitor.db"))

storage = Storage(DB_PATH)
notifier = Notifier()


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

