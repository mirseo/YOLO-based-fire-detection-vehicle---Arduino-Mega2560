#include "FrontMotor.h"
#include "BackMotor.h"

const uint8_t FRONT_L_IA = 12, FRONT_L_IB = 13;
const uint8_t FRONT_R_IA = 10, FRONT_R_IB = 11;
const uint8_t BACK_L_IA  = 9,  BACK_L_IB  = 8;
const uint8_t BACK_R_IA  = 7,  BACK_R_IB  = 6;

const uint8_t TURN_SLOW = 120;

unsigned long lastPrint = 0;
const unsigned long PRINT_INTERVAL = 500;

void forward() {
  BackMotor.backward();
  digitalWrite(FRONT_L_IA, HIGH); digitalWrite(FRONT_L_IB, LOW);
  delay(100);
  digitalWrite(FRONT_R_IA, HIGH); digitalWrite(FRONT_R_IB, LOW);
}
void backward() {
  BackMotor.forward();
  digitalWrite(FRONT_L_IA, LOW); digitalWrite(FRONT_L_IB, HIGH);
  digitalWrite(FRONT_R_IA, LOW); digitalWrite(FRONT_R_IB, HIGH);
}
void turnLeft() {
  analogWrite(FRONT_L_IA, TURN_SLOW); digitalWrite(FRONT_L_IB, LOW);
  analogWrite(BACK_L_IB,  TURN_SLOW); digitalWrite(BACK_L_IA,  LOW);
  digitalWrite(FRONT_R_IA, HIGH);     digitalWrite(FRONT_R_IB, LOW);
  digitalWrite(BACK_R_IA,  HIGH);     digitalWrite(BACK_R_IB,  LOW);
}
void turnRight() {
  digitalWrite(FRONT_L_IA, HIGH);     digitalWrite(FRONT_L_IB, LOW);
  digitalWrite(BACK_L_IB,  HIGH);     digitalWrite(BACK_L_IA,  LOW);
  analogWrite(FRONT_R_IA, TURN_SLOW); digitalWrite(FRONT_R_IB, LOW);
  analogWrite(BACK_R_IA,  TURN_SLOW); digitalWrite(BACK_R_IB,  LOW);
}
void stopMotors() { FrontMotor.stop();      BackMotor.stop();      }

void setup() {
  FrontMotor.begin(FRONT_L_IA, FRONT_L_IB, FRONT_R_IA, FRONT_R_IB, true, false);
  BackMotor.begin (BACK_L_IA,  BACK_L_IB,  BACK_R_IA,  BACK_R_IB, false, true);

  Serial.begin(9600);
  Serial.println(F("HG7881 4WD Moter Control Started (Default: STOP)"));
  Serial.println(F("f: Go | b: Back | l: Left | r: Right | s: STOP"));
  // Serial.println(F("Debug - 1: F-L | 2: F-R | 3: B-L | 4: B-R "));
}

void testMotorOnce(uint8_t ia, uint8_t ib, const __FlashStringHelper* label) {
  Serial.print(F("[TEST] "));
  Serial.print(label);
  Serial.print(F(" IA=")); Serial.print(ia);
  Serial.print(F(" IB=")); Serial.print(ib);
  Serial.println(F(" -> HIGH/LOW 1s"));
  digitalWrite(ia, HIGH); digitalWrite(ib, LOW);
  delay(1000);
  digitalWrite(ia, LOW);  digitalWrite(ib, LOW);
  Serial.println(F("[TEST] stop"));
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    switch (cmd) {
      case 'f': case 'F': forward();    break;
      case 'b': case 'B': backward();   break;
      case 'l': case 'L': turnLeft();   break;
      case 'r': case 'R': turnRight();  break;
      case 's': case 'S': stopMotors(); break;
      case '1': testMotorOnce(FRONT_L_IA, FRONT_L_IB, F("FL")); break;
      case '2': testMotorOnce(FRONT_R_IA, FRONT_R_IB, F("FR")); break;
      case '3': testMotorOnce(BACK_L_IA,  BACK_L_IB,  F("BL")); break;
      case '4': testMotorOnce(BACK_R_IA,  BACK_R_IB,  F("BR")); break;
    }
  }

  unsigned long now = millis();
  if (now - lastPrint >= PRINT_INTERVAL) {
    lastPrint = now;
    Serial.print(F("Front "));
    Serial.print(FrontMotor.currentMode());
    Serial.print(F(" | Back "));
    Serial.println(BackMotor.currentMode());
  }
}
