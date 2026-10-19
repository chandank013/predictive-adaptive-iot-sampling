/*
  Predictive Adaptive Sampling — ESP32 Firmware
  Deliverable 4 — Working Prototype

  Implements three interchangeable sensing policies (fixed-rate,
  threshold-adaptive, predictive-adaptive) over an accelerometer,
  publishes readings/events/energy over MQTT, and uses light-sleep
  between samples to reduce power draw while preserving in-RAM state
  (trend buffer, policy flags) across sleep cycles.

  Hardware: ESP32 (or ESP32-S3), ADXL345 accelerometer (I2C),
  INA219 current-sense breakout (I2C).

  Required libraries (Arduino Library Manager):
    - PubSubClient (Nick O'Leary)
    - Adafruit ADXL345 (+ Adafruit Unified Sensor dependency)
    - Adafruit INA219

  Wiring (I2C shared bus):
    ADXL345  SDA/SCL -> ESP32 GPIO21 (SDA) / GPIO22 (SCL)
    INA219   SDA/SCL -> same I2C bus (different I2C address, default 0x40)
    INA219   VIN+/VIN- in series with the battery-to-load current path
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_ADXL345_U.h>
#include <Adafruit_INA219.h>

// ---------------- User configuration ----------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_BROKER   = "192.168.1.100";   // IP of the Raspberry Pi / laptop running Mosquitto
const int   MQTT_PORT     = 1883;
const char* NODE_ID       = "node01";

// Policy selection: can be set here for a controlled trial, or changed at
// runtime via MQTT (publish "fixed" | "threshold" | "predictive" to the
// policy/set topic) so a single flashed firmware can run all three trials.
enum Policy { FIXED_RATE, THRESHOLD_ADAPTIVE, PREDICTIVE_ADAPTIVE };
volatile Policy activePolicy = FIXED_RATE;

// ---------------- Sampling-rate parameters ----------------
const unsigned long FIXED_INTERVAL_MS  = 1000;  // fixed-rate policy: constant 1 Hz
const unsigned long IDLE_INTERVAL_MS   = 800;   // slow rate when nothing interesting is happening
const unsigned long ACTIVE_INTERVAL_MS = 100;   // fast rate during / approaching an event
const float THRESHOLD_G                = 0.35;  // amplitude threshold (g) for the threshold policy
const int   TREND_WINDOW               = 6;     // number of samples in the predictive trend buffer
const float TREND_SLOPE_TRIGGER        = 0.035; // slope (g/sample) that pre-emptively ramps sampling

// ---------------- Topics ----------------
String TOPIC_READING = String("sensor/") + NODE_ID + "/reading";
String TOPIC_EVENT   = String("sensor/") + NODE_ID + "/event";
String TOPIC_ENERGY  = String("sensor/") + NODE_ID + "/energy";
String TOPIC_POLICY  = String("sensor/") + NODE_ID + "/policy/set";

// ---------------- Globals ----------------
Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);
Adafruit_INA219 ina219;
WiFiClient espClient;
PubSubClient mqtt(espClient);

float trendBuffer[TREND_WINDOW];
int   trendIndex  = 0;
bool  trendFilled = false;
bool  lastEventState = false;

// ---------------- Setup ----------------
void setup() {
  Serial.begin(115200);
  Wire.begin();

  if (!accel.begin()) {
    Serial.println("ERROR: ADXL345 not found — check wiring.");
  }
  accel.setRange(ADXL345_RANGE_4_G);

  if (!ina219.begin()) {
    Serial.println("ERROR: INA219 not found — check wiring.");
  }

  connectWiFi();
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  connectMQTT();
}

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? " connected." : " FAILED (continuing offline).");
}

void connectMQTT() {
  int attempts = 0;
  while (!mqtt.connected() && attempts < 5) {
    String clientId = String(NODE_ID) + "-" + String(random(0xffff), HEX);
    if (mqtt.connect(clientId.c_str())) {
      mqtt.subscribe(TOPIC_POLICY.c_str());
      Serial.println("MQTT connected.");
    } else {
      delay(1000);
      attempts++;
    }
  }
}

// Allows switching policy at runtime without reflashing, e.g.:
//   mosquitto_pub -h <broker> -t sensor/node01/policy/set -m "predictive"
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();
  if (msg == "fixed")           activePolicy = FIXED_RATE;
  else if (msg == "threshold")  activePolicy = THRESHOLD_ADAPTIVE;
  else if (msg == "predictive") activePolicy = PREDICTIVE_ADAPTIVE;
  Serial.println("Policy set to: " + msg);
}

// ---------------- Sensor reading ----------------
// Returns deviation from resting 1g magnitude, in g — near 0 at rest,
// growing with vibration amplitude.
float readAccelMagnitude() {
  sensors_event_t event;
  accel.getEvent(&event);
  float x = event.acceleration.x;
  float y = event.acceleration.y;
  float z = event.acceleration.z;
  float mag = sqrt(x * x + y * y + z * z) / 9.80665;
  return mag - 1.0;
}

float readCurrent_mA() {
  return ina219.getCurrent_mA();
}

// ---------------- Policy logic ----------------
// Decides the next sampling interval and publishes the event flag as a
// side effect. This is the on-device analogue of the Python reference
// implementation in simulation/policy_reference.py — keep both in sync.
unsigned long decideNextInterval(float reading) {
  switch (activePolicy) {

    case FIXED_RATE:
      return FIXED_INTERVAL_MS;

    case THRESHOLD_ADAPTIVE: {
      bool eventNow = fabs(reading) > THRESHOLD_G;
      publishEventFlag(eventNow);
      return eventNow ? ACTIVE_INTERVAL_MS : IDLE_INTERVAL_MS;
    }

    case PREDICTIVE_ADAPTIVE: {
      float oldest = trendBuffer[trendIndex];   // about to be overwritten
      trendBuffer[trendIndex] = reading;
      trendIndex = (trendIndex + 1) % TREND_WINDOW;
      if (trendIndex == 0) trendFilled = true;

      float slope = 0.0;
      if (trendFilled) {
        slope = (reading - oldest) / TREND_WINDOW;
      }

      bool eventNow        = fabs(reading) > THRESHOLD_G;
      bool approachingEvent = fabs(slope) > TREND_SLOPE_TRIGGER;
      publishEventFlag(eventNow);

      return (eventNow || approachingEvent) ? ACTIVE_INTERVAL_MS : IDLE_INTERVAL_MS;
    }
  }
  return FIXED_INTERVAL_MS;
}

// ---------------- MQTT publish helpers ----------------
void publishReading(float reading, unsigned long ts) {
  String payload = "{\"t\":" + String(ts) + ",\"value\":" + String(reading, 4) +
                    ",\"policy\":\"" + policyName(activePolicy) + "\"}";
  mqtt.publish(TOPIC_READING.c_str(), payload.c_str());
}

void publishEventFlag(bool eventNow) {
  if (eventNow != lastEventState) {
    String payload = String("{\"event\":") + (eventNow ? "true" : "false") +
                      ",\"t\":" + String(millis()) + "}";
    mqtt.publish(TOPIC_EVENT.c_str(), payload.c_str());
    lastEventState = eventNow;
  }
}

void publishEnergy(float current_mA, unsigned long ts) {
  String payload = "{\"t\":" + String(ts) + ",\"current_mA\":" + String(current_mA, 3) + "}";
  mqtt.publish(TOPIC_ENERGY.c_str(), payload.c_str());
}

String policyName(Policy p) {
  switch (p) {
    case FIXED_RATE:           return "fixed";
    case THRESHOLD_ADAPTIVE:   return "threshold";
    case PREDICTIVE_ADAPTIVE:  return "predictive";
  }
  return "unknown";
}

// ---------------- Main loop ----------------
void loop() {
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  float reading      = readAccelMagnitude();
  float current_mA    = readCurrent_mA();
  unsigned long ts    = millis();

  publishReading(reading, ts);
  publishEnergy(current_mA, ts);

  unsigned long nextInterval = decideNextInterval(reading);

  Serial.printf("[%s] reading=%.4f g  current=%.2f mA  next=%lu ms\n",
                policyName(activePolicy).c_str(), reading, current_mA, nextInterval);

  // Light sleep preserves RAM (trend buffer, policy state, WiFi/MQTT
  // connection context) while still cutting power between samples. For a
  // production deployment, deep sleep + RTC memory persistence of
  // trendBuffer/trendIndex would save more power at the cost of added
  // reconnection overhead on every wake — a documented next step, not
  // implemented in this prototype.
  esp_sleep_enable_timer_wakeup(nextInterval * 1000ULL);
  esp_light_sleep_start();
}
