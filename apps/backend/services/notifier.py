from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

log = logging.getLogger("notifier")


class Notifier:
    def __init__(self) -> None:
        self._last_sent: dict[tuple[str, str], datetime] = defaultdict(
            lambda: datetime.min.replace(tzinfo=timezone.utc)
        )

    def should_send(self, device_id: str, alert_type: str, cooldown_sec: int) -> bool:
        now = datetime.now(timezone.utc)
        key = (device_id, alert_type)
        delta = (now - self._last_sent[key]).total_seconds()
        if delta >= cooldown_sec:
            self._last_sent[key] = now
            return True
        return False

    def send(self, message: str) -> None:
        # Pluggable point for Pushbullet/Telegram/email/webhook.
        log.warning("ALERT: %s", message)

