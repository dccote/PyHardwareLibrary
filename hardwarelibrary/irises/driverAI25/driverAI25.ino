/*
 * Uniblitz AI25 Auto Iris driver v1.1
 * for Arduino Uno/Nano/Micro
 *
 * Pin 2 -> AI25 Interrupt (Micro USB3 pin 9)
 * Pin 3 -> AI25 RX (Micro USB3 pin 7)
 * Pin 4 -> AI25 TX (Micro USB3 pin 6)
 */

#include <NeoSWSerial.h>

const byte interruptPin = 2;
NeoSWSerial irisSerial(4, 3); // Driver RX/TX -> AI25 TX/RX
String command; // input buffer

void setup()
{
  Serial.begin(9600);
  irisSerial.begin(9600);
  pinMode(2, OUTPUT);
  while (!Serial); // Wait for serial port to connect; needed for native USB only
  Serial.println("driverAI25 Ready");
}

void loop()
{
  if (Serial.available())
  {
    command = Serial.readStringUntil('\n');

    if (command == "V")
    {
      Serial.println("driverAI25 v1.1");
      return;
    }

    digitalWrite(interruptPin, HIGH);
    delay(2);
    digitalWrite(interruptPin, LOW);

    irisSerial.println(command); // send command
    Serial.println(irisSerial.readStringUntil('\n')); // return reply
  }
}
