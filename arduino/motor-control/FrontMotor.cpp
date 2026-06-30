#include "FrontMotor.h"

void FrontMotorController::begin(uint8_t pinFL_IA, uint8_t pinFL_IB,
                                 uint8_t pinFR_IA, uint8_t pinFR_IB,
                                 bool invertLeft,
                                 bool invertRight) {
  _flIA = pinFL_IA; _flIB = pinFL_IB;
  _frIA = pinFR_IA; _frIB = pinFR_IB;
  _invL = invertLeft;
  _invR = invertRight;

  pinMode(_flIA, OUTPUT); digitalWrite(_flIA, LOW);
  pinMode(_flIB, OUTPUT); digitalWrite(_flIB, LOW);
  pinMode(_frIA, OUTPUT); digitalWrite(_frIA, LOW);
  pinMode(_frIB, OUTPUT); digitalWrite(_frIB, LOW);
}

void FrontMotorController::_drive(uint8_t ia, uint8_t ib, int dir, bool invert) {
  if (invert) dir = -dir;
  if (dir > 0)      { digitalWrite(ia, HIGH); digitalWrite(ib, LOW);  }
  else if (dir < 0) { digitalWrite(ia, LOW);  digitalWrite(ib, HIGH); }
  else              { digitalWrite(ia, LOW);  digitalWrite(ib, LOW);  }
}

void FrontMotorController::forward()   { _drive(_flIA, _flIB,  1, _invL); _drive(_frIA, _frIB,  1, _invR); }
void FrontMotorController::backward()  { _drive(_flIA, _flIB, -1, _invL); _drive(_frIA, _frIB, -1, _invR); }
void FrontMotorController::turnLeft()  { _drive(_flIA, _flIB, -1, _invL); _drive(_frIA, _frIB,  1, _invR); }
void FrontMotorController::turnRight() { _drive(_flIA, _flIB,  1, _invL); _drive(_frIA, _frIB, -1, _invR); }
void FrontMotorController::stop()      { _drive(_flIA, _flIB,  0, _invL); _drive(_frIA, _frIB,  0, _invR); }

static int decodeDir(int ia, int ib, bool invert) {
  int dir;
  if      (ia == HIGH && ib == LOW)  dir =  1;
  else if (ia == LOW  && ib == HIGH) dir = -1;
  else                                dir =  0;
  return invert ? -dir : dir;
}

String FrontMotorController::currentMode() {
  int flIA = digitalRead(_flIA);
  int flIB = digitalRead(_flIB);
  int frIA = digitalRead(_frIA);
  int frIB = digitalRead(_frIB);

  int lDir = decodeDir(flIA, flIB, _invL);
  int rDir = decodeDir(frIA, frIB, _invR);

  String s = "[FL(";
  s += flIA; s += ","; s += flIB; s += ") FR(";
  s += frIA; s += ","; s += frIB; s += ")] -> ";

  if      (lDir ==  0 && rDir ==  0) s += "Stop";
  else if (lDir ==  1 && rDir ==  1) s += "Go";
  else if (lDir == -1 && rDir == -1) s += "Back";
  else if (lDir == -1 && rDir ==  1) s += "Left";
  else if (lDir ==  1 && rDir == -1) s += "Right";
  else                                s += "Others/Error";

  return s;
}

FrontMotorController FrontMotor;
