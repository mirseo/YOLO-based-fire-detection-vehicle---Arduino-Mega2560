#ifndef BACK_MOTOR_H
#define BACK_MOTOR_H

#include <Arduino.h>

class BackMotorController {
public:
  void begin(uint8_t pinBL_IA, uint8_t pinBL_IB,
             uint8_t pinBR_IA, uint8_t pinBR_IB,
             bool invertLeft  = false,
             bool invertRight = true);

  void forward();
  void backward();
  void turnLeft();
  void turnRight();
  void stop();

  String currentMode();

private:
  uint8_t _blIA, _blIB, _brIA, _brIB;
  bool    _invL, _invR;

  void _drive(uint8_t ia, uint8_t ib, int dir, bool invert);
};

extern BackMotorController BackMotor;

#endif
