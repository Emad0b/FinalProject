from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import error, request


class PiApiClient:
    def __init__(self, base_url: str, api_key: str, device_id: str, queue_path: Path) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.device_id = device_id
        self.queue_path = queue_path
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }

    def _post_json(self, path: str, payload: dict[str, Any]) -> None:
        req = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with request.urlopen(req, timeout=5):
            return

    def _get_json(self, path: str) -> dict[str, Any]:
        req = request.Request(
            f"{self.base_url}{path}",
            headers=self._headers(),
            method="GET",
        )
        with request.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode("utf-8"))

    def enqueue(self, reading: dict[str, Any]) -> None:
        queue = self._read_queue()
        queue.append(reading)
        self.queue_path.write_text(json.dumps(queue), encoding="utf-8")

    def _read_queue(self) -> list[dict[str, Any]]:
        if not self.queue_path.exists():
            return []
        try:
            return json.loads(self.queue_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def flush_queue(self) -> None:
        queue = self._read_queue()
        if not queue:
            return
        pending: list[dict[str, Any]] = []
        for row in queue:
            try:
                self._post_json("/api/v1/readings", row)
            except (TimeoutError, OSError, error.URLError):
                pending.append(row)
                break
        self.queue_path.write_text(json.dumps(pending), encoding="utf-8")

    def send_reading(self, reading: dict[str, Any]) -> None:
        reading = dict(reading)
        reading["device_id"] = self.device_id
        try:
            self.flush_queue()
            self._post_json("/api/v1/readings", reading)
        except (TimeoutError, OSError, error.URLError):
            self.enqueue(reading)

    def fetch_config(self) -> dict[str, Any] | None:
        try:
            return self._get_json(f"/api/v1/config/{self.device_id}")
        except (TimeoutError, OSError, error.URLError):
            return None

    def mark_applied(self) -> None:
        try:
            self._post_json(f"/api/v1/config/{self.device_id}/applied", {})
        except (TimeoutError, OSError, error.URLError):
            return

