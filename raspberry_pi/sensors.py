"""DHT22 (GPIO4) and PMS5003 (UART) readers."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class PMReading:
    pm10: float
    pm25: float
    pm100: float


class DHTReader:
    """DHT22 on the configured GPIO (data pin)."""

    def __init__(self, pin: int) -> None:
        self._pin = pin
        self._dht: Any = None
        self._last_read = 0.0

    def open(self) -> None:
        import board
        import adafruit_dht

        self._dht = adafruit_dht.DHT22(getattr(board, f"D{self._pin}"))

    def close(self) -> None:
        if self._dht is not None:
            try:
                self._dht.exit()
            except Exception:
                pass
            self._dht = None

    def read(self, min_interval_sec: float = 2.0) -> tuple[float | None, float | None]:
        if self._dht is None:
            return None, None
        now = time.monotonic()
        if now - self._last_read < min_interval_sec:
            time.sleep(min_interval_sec - (now - self._last_read))
        self._last_read = time.monotonic()
        try:
            t = self._dht.temperature
            h = self._dht.humidity
            if t is not None and h is not None:
                return float(t), float(h)
        except RuntimeError as e:
            log.debug("DHT read failed: %s", e)
        return None, None


class PMS5003Reader:
    """
    Plantower PMS5003 via UART (Pi TX→sensor RX, Pi RX←sensor TX through divider).
    """

    def __init__(self) -> None:
        self._pm: Any = None
        self._uart: Any = None

    def open(self) -> None:
        import board
        import busio
        from adafruit_pm25.uart import PM25_UART

        self._uart = busio.UART(board.TX, board.RX, baudrate=9600, timeout=0.25)
        # reset_pin not wired on many breadboard setups
        self._pm = PM25_UART(self._uart, reset_pin=None)

    def close(self) -> None:
        self._pm = None
        if self._uart is not None:
            try:
                self._uart.deinit()
            except Exception:
                pass
            self._uart = None

    def read(self) -> PMReading | None:
        if self._pm is None:
            return None
        try:
            aq = self._pm.read()
            if not aq:
                return None
            return PMReading(
                pm10=float(aq["pm10 standard"]),
                pm25=float(aq["pm25 standard"]),
                pm100=float(aq["pm100 standard"]),
            )
        except Exception as e:
            log.debug("PMS5003 read failed: %s", e)
            return None
