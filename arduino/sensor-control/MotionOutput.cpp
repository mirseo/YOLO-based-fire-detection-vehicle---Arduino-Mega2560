#include <Arduino.h>
#include "MotionOutput.h"
#include "Init.h"

void printMotionField() {
  int motion = motionSensor.read();
  Serial.print(F(",'motion':"));
  Serial.print(motion);
}
