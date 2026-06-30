#ifndef WATER_LEVEL_SENSOR_H
#define WATER_LEVEL_SENSOR_H

#include <Arduino.h>

class WaterLevelSensor {
public:
  WaterLevelSensor(uint8_t pin);
  void begin();
  int read();

private:
  uint8_t _pin;
};

#endif
