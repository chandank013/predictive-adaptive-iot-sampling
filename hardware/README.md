# Hardware Specification & Transition Guide

## Overview

This project is architected with a strict separation between **Simulation Mode** (software-in-the-loop dummy telemetry) and **Physical Hardware Mode** (ESP32 + ADXL345 + INA219).

The system defaults to `SIMULATION` mode, allowing the complete pipeline, policy algorithms, REST API, and React dashboard to run locally without physical hardware.

---

## Hardware Architecture

```
+-------------------------------------------------------------------+
|                        Edge Node (node01)                         |
|                                                                   |
|   +-----------------------+               +-------------------+   |
|   |  ADXL345 (I2C 0x53)   |               |  INA219 (I2C 0x40)|   |
|   |  3-Axis Accelerometer |               |  Current & Power  |   |
|   +-----------+-----------+               +---------+---------+   |
|               |                                     |             |
|               +------------------+------------------+             |
|                                  | I2C (SDA=21, SCL=22)           |
|                       +----------v----------+                     |
|                       |  ESP32 Edge MCU     |                     |
|                       |  Light-Sleep Core   |                     |
|                       +----------+----------+                     |
+----------------------------------|--------------------------------+
                                   | Wi-Fi (802.11 b/g/n)
                                   v MQTT (Port 1883)
                     +---------------------------+
                     | Mosquitto MQTT Broker     |
                     +-------------+-------------+
                                   |
                     +-------------v-------------+
                     | Python Backend & MongoDB  |
                     +-------------+-------------+
                                   |
                     +-------------v-------------+
                     | React Dashboard (Vite)    |
                     +---------------------------+
```

### Components & Default Pinout
| Component | Function | Interface / Pins | I2C Address | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **ESP32 DevKit V1** | Edge Controller & Policy Decision Engine | GPIO 21 (SDA), GPIO 22 (SCL) | Master | Uses light sleep to preserve RAM state across samples |
| **ADXL345** | 3-Axis Digital Accelerometer (±4g range) | I2C shared bus | `0x53` | Measures high-frequency vibration deviation from 1g |
| **INA219** | High-Side DC Current & Power Sensor | I2C shared bus, VIN+/VIN- in series | `0x40` | Measures real current draw (mA) from 3.7V Li-ion battery |
| **18650 Battery** | Power supply (3.7V nominal) | Through INA219 shunt to ESP32 VIN | N/A | Dedicated battery load path |
| **Vibration Inducer** | 12V DC Motor with eccentric weight | Independent power supply (isolated) | N/A | Controlled ground-truth event generator |

---

## Switching from Simulation to Physical Hardware

When physical hardware is assembled and ready to deploy, follow these steps:

### Step 1: Physical Assembly
1. Connect ADXL345 and INA219 to ESP32 I2C pins:
   - `SDA` -> `GPIO 21`
   - `SCL` -> `GPIO 22`
   - `VCC` -> `3.3V`
   - `GND` -> `GND`
2. Wire the INA219 shunt **in series** between the 18650 battery positive terminal and the ESP32 `VIN` pin (see `hardware/wiring_notes.md`).
3. Power the vibration motor inducer from an **independent power supply** so motor current does not pollute sensor energy measurements.

### Step 2: Firmware Configuration & Flashing
1. Open `hardware/firmware/esp32_adaptive_sensing/esp32_adaptive_sensing.ino` in Arduino IDE.
2. Install required Arduino libraries:
   - `PubSubClient` (Nick O'Leary)
   - `Adafruit ADXL345` (+ Adafruit Unified Sensor)
   - `Adafruit INA219`
3. Update Wi-Fi and MQTT broker configuration:
   ```cpp
   const char* WIFI_SSID     = "YOUR_WIFI_SSID";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   const char* MQTT_BROKER   = "192.168.1.100"; // IP of your backend host
   ```
4. Flash the sketch to the ESP32.
5. Open Serial Monitor (`115200` baud) to verify I2C initialization (`ADXL345` and `INA219` found) and Wi-Fi connection.

### Step 3: Configure Environment
In `backend/.env`, set:
```ini
SYSTEM_MODE=HARDWARE
MQTT_BROKER=192.168.1.100
MQTT_PORT=1883
```

### Step 4: Run MQTT Logger
Start the MQTT consumer logger:
```bash
python backend/mqtt_logger.py --broker 192.168.1.100 --node node01 --trial-id hardware_trial_01 --policy predictive
```

---

## Remaining Hardware-Dependent Verification
Before using physical data for experimental publications:
1. **I2C Bus Scan**: Confirm both addresses (`0x53` and `0x40`) respond without signal reflection or bus contention on long breadboard jumpers.
2. **Current Calibration**: Perform a 2-point current measurement calibration on the INA219 using a digital bench multimeter.
3. **Accelerometer Zero-Offset**: Measure resting offset of the ADXL345 in your mechanical mounting rig and adjust resting calibration in firmware.
