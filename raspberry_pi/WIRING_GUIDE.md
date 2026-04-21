# Raspberry Pi Wiring Guide (2 LEDs + PMS5003 Divider)

This guide shows the exact wiring for:
- PMS5003 dust sensor
- DHT22 humidity/temperature
- SSD1306 OLED (I2C)
- 2 status LEDs (healthy + event)
- PMS5003 TX -> Pi RX voltage divider

---

## 1) GPIO map (BCM)

- `GPIO4` -> DHT22 data
- `GPIO17` -> Healthy LED
- `GPIO18` -> Event LED
- `GPIO2 (SDA)` -> OLED SDA
- `GPIO3 (SCL)` -> OLED SCL
- `GPIO14 (TX)` -> PMS5003 RX
- `GPIO15 (RX)` <- PMS5003 TX through divider

---

## 2) Breadboard-style wiring view

```text
+--------------------------------------------------------------+
|                     Raspberry Pi (40-pin)                   |
|                                                              |
| 5V  --------------------------------------------------+      |
| GND --------------------------------------------------+--+   |
| 3V3 ---------------------------------------------+       |   |
| GPIO4 (DHT DATA) -------------------------------+|       |   |
| GPIO17 (HEALTH LED) ----[220R]---->|---- GND ----+       |   |
| GPIO18 (EVENT LED)  ----[220R]---->|---- GND ------------+   |
| GPIO2 SDA ----------------------------------> OLED SDA        |
| GPIO3 SCL ----------------------------------> OLED SCL        |
| GPIO14 TX ----------------------------------> PMS5003 RX      |
| GPIO15 RX <-- divider midpoint ---------------- PMS5003 TX    |
|                                                              |
| DHT22:                                                       |
|   VCC -> 5V (or 3V3 depending on module), GND -> GND        |
|   DATA -> GPIO4                                              |
|   10k pull-up resistor: DATA -> 3V3                          |
|                                                              |
| OLED SSD1306:                                                |
|   VCC -> 3V3, GND -> GND, SDA -> GPIO2, SCL -> GPIO3        |
|                                                              |
| PMS5003:                                                     |
|   VCC -> 5V, GND -> GND, RX <- GPIO14 TX, TX -> divider     |
+--------------------------------------------------------------+
```

---

## 3) PMS5003 TX voltage divider (IMPORTANT)

PMS5003 TX is often 5V logic. Pi RX (`GPIO15`) is 3.3V logic, so use a divider:

```text
PMS5003 TX ---- R1 (10k) ----+----> Pi GPIO15 (RX)
                             |
                           R2 (20k)
                             |
                            GND
```

Output voltage:

`Vout = Vin * (R2 / (R1 + R2)) = 5V * (20k / 30k) = ~3.33V`

That is safe for Pi UART RX.

---

## 4) LED resistor vs voltage divider

For LEDs, **do not use the same divider setup**.

- LED lines need a **series current-limiting resistor** (e.g., 220 ohm to 330 ohm).
- A voltage divider is for reducing a logic voltage level (like 5V UART TX to 3.3V RX), not for driving an LED.

So:
- PMS5003 TX -> Pi RX: use **divider**.
- GPIO -> LED: use **single series resistor**.

---

## 5) Quick checklist

- [ ] All sensor grounds tied to Pi ground
- [ ] PMS5003 TX goes through divider before GPIO15
- [ ] DHT22 has pull-up resistor on data line
- [ ] Each LED has its own series resistor
- [ ] OLED powered from 3.3V, not 5V

