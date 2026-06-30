#include "Init.h"
#include "Constants.h"

WaterLevelSensor waterSensor(WATER_LEVEL_PIN);
UltrasonicSensor ultrasonic(TRIG_PIN, ECHO_PIN, ECHO_TIMEOUT_US);
Buzzer buzzer(BUZZER_PIN);
GasSensor gasSensor(GAS_ANALOG_PIN, GAS_DIGITAL_PIN);
MotionSensor motionSensor(MOTION_PIN);
Dht11Sensor dht11Sensor(DHT11_PIN);
Dht11Sensor dht11LeftSensor(DHT11_LEFT_PIN);
Dht11Sensor dht11RightSensor(DHT11_RIGHT_PIN);
Dht11Sensor dht11RearSensor(DHT11_REAR_PIN);
Dht11Sensor dht11TopSensor(DHT11_TOP_PIN);
WarningLed warningLed(WARNING_LED_PIN);

void initSensors() {
  Serial.begin(SERIAL_BAUD_RATE);
  waterSensor.begin();
  ultrasonic.begin();
  buzzer.begin();
  gasSensor.begin();
  motionSensor.begin();
  warningLed.begin();
}
