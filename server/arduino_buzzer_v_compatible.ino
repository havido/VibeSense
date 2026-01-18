/*
 * Arduino Buzzer Controller - V: Protocol Compatible
 * 
 * This version accepts the Python "V:3" format and converts it
 * to buzzer patterns automatically.
 * 
 * Python sends: "V:3\n" (vibration count)
 * Arduino converts: 3 vibrations -> buzzer pattern
 */

const uint8_t BUZZER_PIN = 9;
const unsigned long PULSE_MS = 200;      // Duration of each pulse
const unsigned long GAP_MS = 150;        // Gap between pulses

void setup() {
  Serial.begin(9600);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  
  while (!Serial && millis() < 3000) {
    ; // wait for serial port to connect (max 3 seconds)
  }
  
  Serial.println("Ready for V:count or B:pattern");
}

void loop() {
  if (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    
    if (line.length() > 0) {
      Serial.print("RX: ");
      Serial.println(line);
      
      if (line.startsWith("V:")) {
        // Python format: V:3 means 3 vibrations
        int count = line.substring(2).toInt();
        if (count > 0 && count <= 10) {  // Reasonable limit
          playVibrationCount(count);
        } else {
          Serial.println("ERR: Count must be 1-10");
        }
      } else if (line.startsWith("B:")) {
        // Direct pattern format: B:200,150,300
        playPattern(line.substring(2));
      } else {
        Serial.println("ERR: Expected 'V:count' or 'B:pattern'");
      }
    }
  }
}

void playVibrationCount(int count) {
  // Convert vibration count to buzzer pattern
  // Each vibration = one pulse
  for (int i = 0; i < count; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(PULSE_MS);
    digitalWrite(BUZZER_PIN, LOW);
    if (i < count - 1) {  // No gap after last pulse
      delay(GAP_MS);
    }
  }
  Serial.print("OK: Played ");
  Serial.print(count);
  Serial.println(" vibration(s)");
}

void playPattern(const String& payload) {
  if (payload.length() == 0) {
    Serial.println("ERR: Empty payload");
    return;
  }
  
  int start = 0;
  int pulseCount = 0;
  const unsigned long MAX_PULSE_MS = 10000;
  
  while (start >= 0 && start < payload.length()) {
    int comma = payload.indexOf(',', start);
    String part = (comma == -1) 
      ? payload.substring(start) 
      : payload.substring(start, comma);
    
    part.trim();
    
    if (part.length() == 0) {
      if (comma == -1) break;
      start = comma + 1;
      continue;
    }
    
    long pulse = part.toInt();
    
    if (pulse <= 0) {
      if (comma == -1) break;
      start = comma + 1;
      continue;
    }
    
    if (pulse > MAX_PULSE_MS) {
      pulse = MAX_PULSE_MS;
    }
    
    digitalWrite(BUZZER_PIN, HIGH);
    delay((unsigned long)pulse);
    digitalWrite(BUZZER_PIN, LOW);
    delay(GAP_MS);
    
    pulseCount++;
    
    if (comma == -1) break;
    start = comma + 1;
  }
  
  if (pulseCount > 0) {
    Serial.print("OK: Played ");
    Serial.print(pulseCount);
    Serial.println(" pulse(s)");
  }
}
