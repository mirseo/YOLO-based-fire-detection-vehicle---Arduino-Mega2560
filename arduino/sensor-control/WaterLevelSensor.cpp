#include "WaterLevelSensor.h"

WaterLevelSensor::WaterLevelSensor(uint8_t pin) : _pin(pin) {}

void WaterLevelSensor::begin() {
  pinMode(_pin, INPUT);
}

int WaterLevelSensor::read() {
  return analogRead(_pin);
}
