#include "Dht11Sensor.h"

Dht11Sensor::Dht11Sensor(uint8_t pin) : _dht(pin) {}

int Dht11Sensor::readTemperature() {
  return _dht.readTemperature();
}

int Dht11Sensor::readHumidity() {
  return _dht.readHumidity();
}

bool Dht11Sensor::readBoth(int &temperature, int &humidity) {
  int result = _dht.readTemperatureHumidity(temperature, humidity);
  return !isError(result);
}

bool Dht11Sensor::isError(int value) {
  return value == DHT11::ERROR_TIMEOUT || value == DHT11::ERROR_CHECKSUM;
}
