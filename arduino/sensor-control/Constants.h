#ifndef CONSTANTS_H
#define CONSTANTS_H

#include <Arduino.h>

const uint8_t WATER_LEVEL_PIN = A0;
const uint8_t TRIG_PIN = 3;
const uint8_t ECHO_PIN = 4;
const uint8_t BUZZER_PIN = 2;
const uint8_t GAS_ANALOG_PIN = A1;
const uint8_t GAS_DIGITAL_PIN = 6;
const uint8_t MOTION_PIN = 13;
const uint8_t DHT11_PIN = 12;
const uint8_t DHT11_LEFT_PIN = 9;
const uint8_t DHT11_RIGHT_PIN = 7;
const uint8_t DHT11_REAR_PIN = 11;
const uint8_t DHT11_TOP_PIN = 8;
const uint8_t WARNING_LED_PIN = 10;

const unsigned long ECHO_TIMEOUT_US = 30000UL;
const unsigned long PRINT_INTERVAL = 500;

const float BEEP_MAX_DISTANCE_CM = 5.0f;
const uint8_t BUZZER_MAX_LEVEL = 128;

const int GAS_WARNING_THRESHOLD = 600;
const int TEMP_WARNING_THRESHOLD = 35;

const unsigned long SERIAL_BAUD_RATE = 9600;

#endif
