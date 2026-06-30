#ifndef WARNING_LED_H
#define WARNING_LED_H

#include <Arduino.h>

class WarningLed {
public:
  WarningLed(uint8_t pin);
  void begin();
  void set(bool on);

private:
  uint8_t _pin;
};

#endif
