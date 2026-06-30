#include "BackMotor.h"

void BackMotorController::begin(uint8_t pinBL_IA, uint8_t pinBL_IB,
                                uint8_t pinBR_IA, uint8_t pinBR_IB,
                                bool invertLeft,
                                bool invertRight) {
  _blIA = pinBL_IA; _blIB = pinBL_IB;
  _brIA = pinBR_IA; _brIB = pinBR_IB;
  _invL = invertLeft;
  _invR = invertRight;

  pinMode(_blIA, OUTPUT); digitalWrite(_blIA, LOW);
  pinMode(_blIB, OUTPUT); digitalWrite(_blIB, LOW);
  pinMode(_brIA, OUTPUT); digitalWrite(_brIA, LOW);
  pinMode(_brIB, OUTPUT); digitalWrite(_brIB, LOW);
}

void BackMotorController::_drive(uint8_t ia, uint8_t ib, int dir, bool invert) {
  if (invert) dir = -dir;
  if (dir > 0)      { digitalWrite(ia, HIGH); digitalWrite(ib, LOW);  }
  else if (dir < 0) { digitalWrite(ia, LOW);  digitalWrite(ib, HIGH); }
  else              { digitalWrite(ia, LOW);  digitalWrite(ib, LOW);  }
}

void BackMotorController::forward()   { _drive(_blIA, _blIB,  1, _invL); _drive(_brIA, _brIB,  1, _invR); }
void BackMotorController::backward()  { _drive(_blIA, _blIB, -1, _invL); _drive(_brIA, _brIB, -1, _invR); }
void BackMotorController::turnLeft()  { _drive(_blIA, _blIB, -1, _invL); _drive(_brIA, _brIB,  1, _invR); }
void BackMotorController::turnRight() { _drive(_blIA, _blIB,  1, _invL); _drive(_brIA, _brIB, -1, _invR); }
void BackMotorController::stop()      { _drive(_blIA, _blIB,  0, _invL); _drive(_brIA, _brIB,  0, _invR); }

static int decodeDir(int ia, int ib, bool invert) {
  int dir;
  if      (ia == HIGH && ib == LOW)  dir =  1;
  else if (ia == LOW  && ib == HIGH) dir = -1;
  else                                dir =  0;
  return invert ? -dir : dir;
}

String BackMotorController::currentMode() {
  int blIA = digitalRead(_blIA);
  int blIB = digitalRead(_blIB);
  int brIA = digitalRead(_brIA);
  int brIB = digitalRead(_brIB);

  int lDir = decodeDir(blIA, blIB, _invL);
  int rDir = decodeDir(brIA, brIB, _invR);

  String s = "[BL(";
  s += blIA; s += ","; s += blIB; s += ") BR(";
  s += brIA; s += ","; s += brIB; s += ")] -> ";

  if      (lDir ==  0 && rDir ==  0) s += "Stop";
  else if (lDir ==  1 && rDir ==  1) s += "Go";
  else if (lDir == -1 && rDir == -1) s += "Back";
  else if (lDir == -1 && rDir ==  1) s += "Left";
  else if (lDir ==  1 && rDir == -1) s += "Right";
  else                                s += "Others/Error";

  return s;
}

BackMotorController BackMotor;
