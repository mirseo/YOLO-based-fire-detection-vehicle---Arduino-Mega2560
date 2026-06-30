#include "MotionSensor.h"

MotionSensor::MotionSensor(uint8_t pin) : _pin(pin) {}

void MotionSensor::begin() {
  pinMode(_pin, INPUT);
}

int MotionSensor::read() {
  return digitalRead(_pin);
}
