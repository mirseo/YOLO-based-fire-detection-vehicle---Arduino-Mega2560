#include "UltrasonicSensor.h"

UltrasonicSensor::UltrasonicSensor(uint8_t trigPin, uint8_t echoPin, unsigned long timeoutUs)
    : _trigPin(trigPin), _echoPin(echoPin), _timeoutUs(timeoutUs), _duration(0) {}

void UltrasonicSensor::begin() {
  pinMode(_trigPin, OUTPUT);
  pinMode(_echoPin, INPUT);
  digitalWrite(_trigPin, LOW);
}

void UltrasonicSensor::measure() {
  digitalWrite(_trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(_trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(_trigPin, LOW);
  _duration = pulseIn(_echoPin, HIGH, _timeoutUs);
}

unsigned long UltrasonicSensor::duration() const {
  return _duration;
}

float UltrasonicSensor::distanceCm() const {
  return (_duration == 0) ? -1.0f : _duration * 0.0343f / 2.0f;
}
