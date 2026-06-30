#include "Buzzer.h"

Buzzer::Buzzer(uint8_t pin) : _pin(pin) {}

void Buzzer::begin() {
  pinMode(_pin, OUTPUT);
  analogWrite(_pin, 0);
}

void Buzzer::setLevel(uint8_t level) {
  analogWrite(_pin, level);
}

void Buzzer::off() {
  analogWrite(_pin, 0);
}
