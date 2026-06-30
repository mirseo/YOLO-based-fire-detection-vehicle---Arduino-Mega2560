#include "GasSensor.h"

GasSensor::GasSensor(uint8_t analogPin, uint8_t digitalPin)
  : _analogPin(analogPin), _digitalPin(digitalPin) {}

void GasSensor::begin() {
  pinMode(_analogPin, INPUT);
  pinMode(_digitalPin, INPUT);
}

int GasSensor::readAnalog() {
  return analogRead(_analogPin);
}

int GasSensor::readDigital() {
  return digitalRead(_digitalPin);
}
