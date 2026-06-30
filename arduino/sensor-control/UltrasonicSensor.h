#ifndef ULTRASONIC_SENSOR_H
#define ULTRASONIC_SENSOR_H

#include <Arduino.h>

class UltrasonicSensor {
public:
  UltrasonicSensor(uint8_t trigPin, uint8_t echoPin, unsigned long timeoutUs = 30000UL);
  void begin();
  void measure();
  unsigned long duration() const;
  float distanceCm() const;

private:
  uint8_t _trigPin;
  uint8_t _echoPin;
  unsigned long _timeoutUs;
  unsigned long _duration;
};

#endif
