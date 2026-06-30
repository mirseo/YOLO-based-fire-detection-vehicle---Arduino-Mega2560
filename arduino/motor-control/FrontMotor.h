#ifndef FRONT_MOTOR_H
#define FRONT_MOTOR_H

#include <Arduino.h>

class FrontMotorController {
public:
  void begin(uint8_t pinFL_IA, uint8_t pinFL_IB,
             uint8_t pinFR_IA, uint8_t pinFR_IB,
             bool invertLeft  = false,
             bool invertRight = true);

  void forward();
  void backward();
  void turnLeft();
  void turnRight();
  void stop();

  String currentMode();

private:
  uint8_t _flIA, _flIB, _frIA, _frIB;
  bool    _invL, _invR;

  void _drive(uint8_t ia, uint8_t ib, int dir, bool invert);
};

extern FrontMotorController FrontMotor;

#endif
