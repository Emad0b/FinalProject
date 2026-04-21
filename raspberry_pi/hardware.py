"""SSD1306 OLED (I2C) and two status LEDs."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


class StatusLeds:
    """
    Two discrete LEDs:
    - healthy LED: on when monitor loop is running
    - event LED: on when any alert/caution/humidity event is active
    """

    def __init__(self, healthy_pin: int, event_pin: int) -> None:
        self._healthy_pin = healthy_pin
        self._event_pin = event_pin
        self._healthy: Any = None
        self._event: Any = None

    def open(self) -> None:
        from gpiozero import LED

        self._healthy = LED(self._healthy_pin)
        self._event = LED(self._event_pin)

    def close(self) -> None:
        if self._healthy is not None:
            self._healthy.off()
            self._healthy.close()
            self._healthy = None
        if self._event is not None:
            self._event.off()
            self._event.close()
            self._event = None

    def set_healthy(self, is_on: bool) -> None:
        if self._healthy is None:
            return
        if is_on:
            self._healthy.on()
        else:
            self._healthy.off()

    def set_event(self, is_on: bool) -> None:
        if self._event is None:
            return
        if is_on:
            self._event.on()
        else:
            self._event.off()


class OledDisplay:
    """128×64 SSD1306 over I2C (luma.oled)."""

    def __init__(self, port: int, address: int) -> None:
        self._port = port
        self._address = address
        self._device: Any = None

    def open(self) -> None:
        from luma.core.interface.serial import i2c
        from luma.oled.device import ssd1306

        serial = i2c(port=self._port, address=self._address)
        self._device = ssd1306(serial)

    def close(self) -> None:
        if self._device is not None:
            try:
                self._device.hide()
            except Exception:
                pass
            self._device = None

    def render(
        self,
        pm25: float | None,
        pm10: float | None,
        temp_c: float | None,
        hum_pct: float | None,
        line5: str,
        line6: str,
    ) -> None:
        if self._device is None:
            return
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("1", self._device.size, "black")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 11)
            font_small = ImageFont.truetype("DejaVuSans.ttf", 10)
        except OSError:
            font = ImageFont.load_default()
            font_small = font

        def fmt(v: float | None, unit: str) -> str:
            if v is None:
                return "--"
            return f"{v:.1f}{unit}"

        y = 0
        lh = 11
        draw.text((0, y), f"PM2.5 {fmt(pm25, '')} ug/m3", font=font, fill="white")
        y += lh
        draw.text((0, y), f"PM10  {fmt(pm10, '')} ug/m3", font=font, fill="white")
        y += lh
        draw.text((0, y), f"RH    {fmt(hum_pct, '%')}  T {fmt(temp_c, 'C')}", font=font, fill="white")
        y += lh
        draw.text((0, y), line5[:21], font=font_small, fill="white")
        y += lh
        draw.text((0, y), line6[:21], font=font_small, fill="white")

        self._device.display(img)
