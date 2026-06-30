#include "WarningLed.h"

WarningLed::WarningLed(uint8_t pin) : _pin(pin) {}

void WarningLed::begin() {
  pinMode(_pin, OUTPUT);
  digitalWrite(_pin, LOW);
}

void WarningLed::set(bool on) {
  digitalWrite(_pin, on ? HIGH : LOW);
}
