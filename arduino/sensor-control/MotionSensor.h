#ifndef MOTION_SENSOR_H
#define MOTION_SENSOR_H

#include <Arduino.h>

class MotionSensor {
public:
  MotionSensor(uint8_t pin);
  void begin();
  int read();

private:
  uint8_t _pin;
};

#endif
