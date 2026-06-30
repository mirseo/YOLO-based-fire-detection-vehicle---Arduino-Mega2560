#ifndef DHT11_SENSOR_H
#define DHT11_SENSOR_H

#include <Arduino.h>
#include <DHT11.h>

class Dht11Sensor {
public:
  Dht11Sensor(uint8_t pin);
  int readTemperature();
  int readHumidity();
  bool readBoth(int &temperature, int &humidity);
  static bool isError(int value);

private:
  DHT11 _dht;
};

#endif
