# Hardware Wiring Notes
### Energy-Aware Adaptive IoT Sensing Using Edge Intelligence

## Pinout / I2C Bus

| Signal | Connects to |
|---|---|
| ADXL345 SDA | ESP32 GPIO21 (I2C SDA) |
| ADXL345 SCL | ESP32 GPIO22 (I2C SCL) |
| ADXL345 VCC / GND | 3.3V / GND |
| INA219 SDA / SCL | Same I2C bus as ADXL345 (shared, different address) |
| INA219 VIN+ / VIN- | In series with the battery-to-load current path |
| Battery (18650) | Through INA219 shunt, to ESP32 VIN / load |

Both sensors share the same two I2C lines (GPIO21/22). They do not
conflict because they sit at different I2C addresses:

| Device | Default I2C Address |
|---|---|
| ADXL345 | `0x53` |
| INA219 | `0x40` |

**Before doing anything else on a new board:** run an I2C scanner
sketch and confirm both addresses show up. If one or both are missing,
stop and recheck wiring/power before touching firmware — this is the
most common early failure at this build scale.

## Power Path

The INA219 must sit **in series** between the battery and everything it
powers (ESP32 + ADXL345), not just tapped in parallel — it measures
current by sensing a tiny voltage drop across a shunt resistor that
the actual load current has to pass through. Wiring it in parallel
will read near-zero current and tell you nothing useful.

```
18650 Battery (+) -> INA219 VIN+ -> INA219 VIN- -> ESP32 VIN -> (ESP32 + ADXL345 share 3.3V rail)
18650 Battery (-) -> common GND
```

## Event Inducer

A small 12V DC motor mounted near (not touching) the accelerometer,
powered independently (not through the INA219 path, so it doesn't
pollute the node's own energy measurement). Running it briefly creates
a repeatable vibration "event" for ground-truth timing.

## Sleep Mode Design Decision

The firmware (`firmware/esp32_adaptive_sensing/esp32_adaptive_sensing.ino`)
uses **light sleep**, not deep sleep, between samples. Light sleep
preserves RAM — including the predictive policy's trend buffer and the
active Wi-Fi/MQTT connection — across every cycle, keeping the
implementation simple and avoiding reconnection overhead on every wake.

Deep sleep would save more idle power but requires persisting policy
state in RTC memory and re-establishing the MQTT connection on every
wake. This is a documented, deferred optimization — worth revisiting
once baseline energy numbers from light sleep are collected and you can
judge whether deep sleep's lower idle draw is worth its reconnection
cost for this specific workload.

## Photos

_(Add photos of the assembled breadboard/rig here once built, for
reproducibility per the course guideline's dataset/reproducibility
requirements.)_
