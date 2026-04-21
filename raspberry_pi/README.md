# Raspberry Pi air monitor

Python code for the **PMS5003** (UART), **DHT22** (GPIO4), **SSD1306 OLED** (I2C), and **two status LEDs**: healthy (GPIO17) and event (GPIO18), matching the breadboard layout below.

## Wiring summary

```
+------------------------------------------------------+
|                 BREADBOARD                           |
|  (Red line = +5V, Blue line = GND)                  |
|                                                      |
|  T-Cobbler (left)                                   |
|  +----+                                             |
|  | 5V |----+  +5V rail                              |
|  |GND |----+  GND rail                               |
|  |GPIO4|--- DHT22 DATA (+ 10k pull-up to 3.3V)      |
|  |GPIO17|-- 220R -- HEALTH LED anode                |
|  |GPIO18|-- 220R -- EVENT LED anode                 |
|  | SDA |---- OLED SDA (GPIO2)                       |
|  | SCL |---- OLED SCL (GPIO3)                       |
|  | RX  |---- voltage divider <-- PMS5003 TX (5V)   |
|  | TX  |---- PMS5003 RX                             |
|  +----+                                             |
|                                                      |
|  PMS5003                                            |
|  5V / GND to rails; TX->divider->Pi RX; RX<-Pi TX   |
|                                                      |
|  DHT22: VCC +5V, DATA GPIO4, GND                    |
|  OLED:  VCC 3.3V, GND, SCL, SDA                     |
|  LED1:  HEALTH (on when loop is healthy)            |
|  LED2:  EVENT (on for dust/humidity events)         |
+------------------------------------------------------+
```

**BCM pins used in software**

| Signal    | BCM | Physical (typ.) |
|-----------|-----|-----------------|
| DHT22 data | 4  | 7               |
| LED healthy | 17 | 11              |
| LED event   | 18 | 12              |
| I2C SDA    | 2  | 3               |
| I2C SCL    | 3  | 5               |
| UART TX    | 14 | 8               |
| UART RX    | 15 | 10              |

**PMS5003 TX is 5 V logic:** use a **voltage divider** (e.g. 10 kΩ / 20 kΩ) or a level shifter into **GPIO15 (RX)**. Pi **TX (GPIO14)** to sensor **RX** is usually fine.

## Pi setup

1. `sudo raspi-config` → enable **I2C**, **Serial** (UART), disable login shell on serial.
   On **Raspberry Pi 5**, `gpiozero` may need: `sudo apt install python3-lgpio`.
2. Install dependencies (venv recommended):

   ```bash
   cd raspberry_pi
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy ML weights (optional) from your PC:  
   `output/ml_artifacts/pi_air_quality_logreg.json`  
   `output/ml_artifacts/pi_humidity_stress_logreg.json`  
   Place them under the same paths relative to the **project root** (parent of `raspberry_pi/`), or set paths in `config.py`.

## Run

From the `raspberry_pi` folder:

```bash
python3 monitor.py
```

- `--mock` — no hardware (smoke test on a laptop).
- `--no-ml` — thresholds + humidity rules only (no JSON model).
- `--interval 10` — seconds between loop iterations.
- `--log data/air_log.csv` — CSV log path.
- `--backend-url http://<laptop-ip>:8000` — API endpoint for internet/LAN upload.
- `--api-key <key>` — API key for backend authentication.
- `--device-id pi-001` — unique device id for config + alert tracking.
- `--config-sync-sec 60` — how often to fetch remote config.
- `--queue-path data/outbox.json` — offline queue for failed uploads.

## systemd (optional)

See `systemd/air-monitor.service.example` — adjust `User` and `WorkingDirectory`, then:

```bash
sudo cp systemd/air-monitor.service.example /etc/systemd/system/air-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable --now air-monitor.service
```

## Notes

- **DHT22** can miss reads; the code keeps the last good humidity/temperature.
- On-device rolling windows (7 / 30 samples) are **short-term** smoothers at your sample rate; they are **not** the same as 7- / 30-**day** EcoCity features. For strict ML alignment, retrain on Pi-collected logs or use `--no-ml` and threshold-only alerts.
