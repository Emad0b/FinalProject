"""
Wiring (BCM numbering, T-Cobbler).

Breadboard:
  +5V rail  → PMS5003 VCC, DHT22 VCC (pin 1)
  3.3V rail → OLED VCC, DHT22 pull-up (10 kΩ to DATA)
  GND rail  → PMS5003 GND, DHT22 GND (pin 4), OLED GND, RGB common cathode

Signals:
  GPIO4  (D4)  — DHT22 DATA (with pull-up to 3.3V)
  GPIO17       — 220 Ω → HEALTH LED anode
  GPIO18       — 220 Ω → EVENT LED anode
  I2C (SDA/SCL default) — OLED (GPIO2 / GPIO3 on Pi)
  UART GPIO14 TX → PMS5003 RX
  UART GPIO15 RX ← voltage divider from PMS5003 TX (5 V → 3.3 V logic)

Enable serial UART in raspi-config; disable login shell on serial.
"""

from pathlib import Path

# --- GPIO (BCM) ---
DHT22_PIN = 4
HEALTH_LED_PIN = 17
EVENT_LED_PIN = 18

# --- I2C OLED (SSD1306) ---
OLED_I2C_PORT = 1
OLED_I2C_ADDRESS = 0x3C

# --- Timing ---
SAMPLE_INTERVAL_SEC = 10.0
DHT_MIN_INTERVAL_SEC = 2.0

# Rolling means for on-device features (at SAMPLE_INTERVAL_SEC).
# Not identical to daily EcoCity training windows; optional ML is indicative only.
ROLL_PM25_SHORT_SAMPLES = 7
ROLL_PM25_LONG_SAMPLES = 30

# --- Paths ---
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
DEFAULT_LOG_PATH = PACKAGE_DIR / "data" / "air_log.csv"
ML_LOGREG_PATH = PROJECT_ROOT / "output" / "ml_artifacts" / "pi_air_quality_logreg.json"
ML_HUMIDITY_PATH = PROJECT_ROOT / "output" / "ml_artifacts" / "pi_humidity_stress_logreg.json"

# --- Network sync (Pi -> laptop backend) ---
DEFAULT_DEVICE_ID = "pi-001"
DEFAULT_BACKEND_URL = "http://139.222.164.180:8000"
DEFAULT_API_KEY = "airmon-secure-key"
DEFAULT_CONFIG_SYNC_SEC = 60.0
DEFAULT_OFFLINE_QUEUE_PATH = PACKAGE_DIR / "data" / "outbox.json"
