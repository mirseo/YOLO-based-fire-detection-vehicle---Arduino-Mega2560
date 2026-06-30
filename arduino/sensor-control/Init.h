#ifndef INIT_H
#define INIT_H

#include "WaterLevelSensor.h"
#include "UltrasonicSensor.h"
#include "Buzzer.h"
#include "GasSensor.h"
#include "MotionSensor.h"
#include "Dht11Sensor.h"
#include "WarningLed.h"

extern WaterLevelSensor waterSensor;
extern UltrasonicSensor ultrasonic;
extern Buzzer buzzer;
extern GasSensor gasSensor;
extern MotionSensor motionSensor;
extern Dht11Sensor dht11Sensor;
extern Dht11Sensor dht11LeftSensor;
extern Dht11Sensor dht11RightSensor;
extern Dht11Sensor dht11RearSensor;
extern Dht11Sensor dht11TopSensor;
extern WarningLed warningLed;

void initSensors();

#endif
