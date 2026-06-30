#include <Arduino.h>
#include "Loop.h"
#include "Init.h"
#include "MotionOutput.h"
#include "Constants.h"

static unsigned long lastPrint = 0;
static uint8_t dhtIndex = 0;
static int cachedTemp = 0;
static int cachedHumidity = 0;
static int cachedLeftTemp = 0;
static int cachedLeftHumidity = 0;
static int cachedRightTemp = 0;
static int cachedRightHumidity = 0;
static int cachedRearTemp = 0;
static int cachedRearHumidity = 0;
static int cachedTopTemp = 0;
static int cachedTopHumidity = 0;

void runLoop() {
  unsigned long now = millis();
  if (now - lastPrint >= PRINT_INTERVAL) {
    lastPrint = now;
    int water = waterSensor.read();
    ultrasonic.measure();

    float distance = ultrasonic.distanceCm();
    if (distance > 0.0f && distance <= BEEP_MAX_DISTANCE_CM) {
      float ratio = (BEEP_MAX_DISTANCE_CM - distance) / BEEP_MAX_DISTANCE_CM;
      buzzer.setLevel((uint8_t)(ratio * BUZZER_MAX_LEVEL));
    } else {
      buzzer.off();
    }

    int gasAnalog = gasSensor.readAnalog();
    int gasDigital = gasSensor.readDigital();

    Serial.print(F("{'water':"));
    Serial.print(water);
    Serial.print(F(",'distance':"));
    Serial.print(ultrasonic.distanceCm(), 2);
    Serial.print(F(",'distance_raw':"));
    Serial.print(ultrasonic.duration());
    Serial.print(F(",'gas':"));
    Serial.print(gasAnalog);
    Serial.print(F(",'gas_alarm':"));
    Serial.print(gasDigital);
    printMotionField();

    int t, h;
    switch (dhtIndex) {
      case 0: if (dht11Sensor.readBoth(t, h))      { cachedTemp = t;      cachedHumidity = h;      } break;
      case 1: if (dht11LeftSensor.readBoth(t, h))  { cachedLeftTemp = t;  cachedLeftHumidity = h;  } break;
      case 2: if (dht11RightSensor.readBoth(t, h)) { cachedRightTemp = t; cachedRightHumidity = h; } break;
      case 3: if (dht11RearSensor.readBoth(t, h))  { cachedRearTemp = t;  cachedRearHumidity = h;  } break;
      case 4: if (dht11TopSensor.readBoth(t, h))   { cachedTopTemp = t;   cachedTopHumidity = h;   } break;
    }
    dhtIndex = (dhtIndex + 1) % 5;
    Serial.print(F(",'front_temp':"));
    Serial.print(cachedTemp);
    Serial.print(F(",'front_humidity':"));
    Serial.print(cachedHumidity);
    Serial.print(F(",'left_temp':"));
    Serial.print(cachedLeftTemp);
    Serial.print(F(",'left_humidity':"));
    Serial.print(cachedLeftHumidity);
    Serial.print(F(",'right_temp':"));
    Serial.print(cachedRightTemp);
    Serial.print(F(",'right_humidity':"));
    Serial.print(cachedRightHumidity);
    Serial.print(F(",'rear_temp':"));
    Serial.print(cachedRearTemp);
    Serial.print(F(",'rear_humidity':"));
    Serial.print(cachedRearHumidity);
    Serial.print(F(",'top_temp':"));
    Serial.print(cachedTopTemp);
    Serial.print(F(",'top_humidity':"));
    Serial.print(cachedTopHumidity);

    bool gasWarning = gasAnalog > GAS_WARNING_THRESHOLD;
    bool tempWarning = cachedTemp > TEMP_WARNING_THRESHOLD;
    bool distanceWarning = distance > 0.0f && distance <= BEEP_MAX_DISTANCE_CM;
    bool warning = gasWarning || tempWarning || distanceWarning;
    warningLed.set(warning);

    Serial.print(F(",'warning':"));
    Serial.print(warning ? 1 : 0);
    Serial.println(F("}"));
  }
}
