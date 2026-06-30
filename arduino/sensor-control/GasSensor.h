#ifndef GAS_SENSOR_H
#define GAS_SENSOR_H

#include <Arduino.h>

class GasSensor {
public:
  GasSensor(uint8_t analogPin, uint8_t digitalPin);
  void begin();
  int readAnalog();
  int readDigital();

private:
  uint8_t _analogPin;
  uint8_t _digitalPin;
};

#endif
