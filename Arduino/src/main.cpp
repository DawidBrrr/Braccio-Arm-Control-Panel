
/*
  simpleMovements.ino

 This  sketch simpleMovements shows how they move each servo motor of Braccio

 Created on 18 Nov 2015
 by Andrea Martino

 This example is in the public domain.
 */

#include <Braccio.h>
#include <Servo.h>
#include <Arduino.h>

Servo base;
Servo shoulder;
Servo elbow;
Servo wrist_rot;
Servo wrist_ver;
Servo gripper;

int m1 = 90;
int m2 = 45;
int m3 = 180;
int m4 = 180;
int m5 = 90;
int m6 = 10;

int targetM1 = m1;
int targetM2 = m2;
int targetM3 = m3;
int targetM4 = m4;
int targetM5 = m5;
int targetM6 = m6;

struct ServoChannel {
  const char* id;
  Servo* servo;
  int* position;
  int* target;
  int minAngle;
  int maxAngle;
};

ServoChannel channels[] = {
  {"m1", &base, &m1, &targetM1, 0, 270},
  {"m2", &shoulder, &m2, &targetM2, 15, 165},
  {"m3", &elbow, &m3, &targetM3, 0, 180},
  {"m4", &wrist_ver, &m4, &targetM4, 0, 180},
  {"m5", &wrist_rot, &m5, &targetM5, 0, 180},
  {"m6", &gripper, &m6, &targetM6, 10, 110}
};

const size_t SERVO_COUNT = sizeof(channels) / sizeof(channels[0]);
const int SERVO_STEP_DEGREES = 1;
const unsigned long SERVO_STEP_INTERVAL_MS = 15;

String serialLineBuffer;
unsigned long lastServoStepMillis = 0;

void initializePose();
void handleSerialLine(const String& line);
void handleToken(const String& token);
int servoIndexFromId(const String& id);
bool isNumeric(const String& value);
void setServoTarget(int index, int angle);
void stepServosTowardTargets();

void setup() {
  Serial.begin(115200);
  //Initialization functions and set up the initial position for Braccio
  //All the servo motors will be positioned in the "safety" position NOT BEGIN POSITION:
  //Base (M1):90 degrees
  //Shoulder (M2): 45 degrees
  //Elbow (M3): 180 degrees
  //Wrist vertical (M4): 180 degrees
  //Wrist rotation (M5): 90 degrees
  //gripper (M6): 10 degrees
  Braccio.begin();

  base.attach(11);
  shoulder.attach(10);
  elbow.attach(9);
  wrist_rot.attach(6);
  wrist_ver.attach(5);
  gripper.attach(3);

  initializePose();
  Serial.println(F("Braccio ready. Send commands like m1:135 or m1:90;m2:45"));
}

void loop() {

  while (Serial.available() > 0) {
    char incoming = Serial.read();
    if (incoming == '\r') {
      continue;
    }

    if (incoming == '\n') {
      handleSerialLine(serialLineBuffer);
      serialLineBuffer = "";
    } else {
      serialLineBuffer += incoming;
      if (serialLineBuffer.length() > 64) {
        serialLineBuffer = "";  // drop malformed line to keep memory safe
      }
    }
  }

  stepServosTowardTargets();
}

void initializePose() {
  const int safePose[SERVO_COUNT] = {90, 45, 180, 180, 90, 10};
  for (size_t i = 0; i < SERVO_COUNT; ++i) {
    *channels[i].position = safePose[i];
    *channels[i].target = safePose[i];
    channels[i].servo->write(safePose[i]);
  }
}

void handleSerialLine(const String& line) {
  if (line.length() == 0) {
    return;
  }

  int start = 0;
  while (start < line.length()) {
    int end = line.indexOf(';', start);
    if (end == -1) {
      end = line.length();
    }

    String token = line.substring(start, end);
    token.trim();
    handleToken(token);

    start = end + 1;
  }
}

void handleToken(const String& token) {
  if (token.length() == 0) {
    return;
  }

  int colonIndex = token.indexOf(':');
  if (colonIndex == -1) {
    return;
  }

  String id = token.substring(0, colonIndex);
  id.trim();
  id.toLowerCase();
  String value = token.substring(colonIndex + 1);
  value.trim();

  if (!value.length() || !isNumeric(value)) {
    return;
  }

  int index = servoIndexFromId(id);
  if (index < 0) {
    return;
  }

  int angle = value.toInt();
  setServoTarget(index, angle);
}

int servoIndexFromId(const String& id) {
  if (id.length() < 2 || id.charAt(0) != 'm') {
    return -1;
  }

  String numericPart = id.substring(1);
  if (!isNumeric(numericPart)) {
    return -1;
  }

  int servoNumber = numericPart.toInt();
  if (servoNumber < 1 || servoNumber > (int)SERVO_COUNT) {
    return -1;
  }

  return servoNumber - 1;
}

bool isNumeric(const String& value) {
  if (value.length() == 0) {
    return false;
  }

  for (size_t i = 0; i < value.length(); ++i) {
    char c = value.charAt(i);
    if (c < '0' || c > '9') {
      return false;
    }
  }
  return true;
}

void setServoTarget(int index, int angle) {
  ServoChannel& channel = channels[index];
  int clamped = constrain(angle, channel.minAngle, channel.maxAngle);
  *channel.target = clamped;
}

void stepServosTowardTargets() {
  unsigned long now = millis();
  if (now - lastServoStepMillis < SERVO_STEP_INTERVAL_MS) {
    return;
  }

  lastServoStepMillis = now;
  for (size_t i = 0; i < SERVO_COUNT; ++i) {
    ServoChannel& channel = channels[i];
    int diff = *channel.target - *channel.position;
    if (diff == 0) {
      continue;
    }

    int step = SERVO_STEP_DEGREES;
    if (abs(diff) < SERVO_STEP_DEGREES) {
      step = abs(diff);
    }

    if (diff < 0) {
      step = -step;
    }

    *channel.position += step;
    channel.servo->write(*channel.position);
  }
}
