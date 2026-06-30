#ifndef BUZZER_H
#define BUZZER_H

#include <Arduino.h>

class Buzzer {
public:
  Buzzer(uint8_t pin);
  void begin();
  void setLevel(uint8_t level);
  void off();

private:
  uint8_t _pin;
};

#endif
