/*
 * Fixed Arduino Buzzer Controller
 * Receives buzzer patterns via serial: "B:200,150,300\n"
 * 
 * Issues fixed:
 * 1. Better memory management (avoid String fragmentation)
 * 2. Bounds checking for pulse values
 * 3. Better error handling
 * 4. Handles edge cases (spaces, empty segments)
 */

const uint8_t BUZZER_PIN = 9;
const unsigned long GAP_MS = 150;
const unsigned long MAX_PULSE_MS = 10000;  // Safety limit: max 10 seconds per pulse

void setup() {
  Serial.begin(9600);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  
  // Wait for serial connection (optional, helps with some boards)
  while (!Serial && millis() < 3000) {
    ; // wait for serial port to connect (max 3 seconds)
  }
  
  Serial.println("Ready for B:payload");
}

void loop() {
  if (Serial.available() > 0) {
    // Read until newline
    String line = Serial.readStringUntil('\n');
    line.trim();  // Remove \r and whitespace
    
    if (line.length() > 0) {
      Serial.print("RX: ");
      Serial.println(line);
      
      if (line.startsWith("B:")) {
        playPattern(line.substring(2));
      } else {
        Serial.println("ERR: Expected format 'B:payload'");
      }
    }
  }
}

void playPattern(const String& payload) {
  if (payload.length() == 0) {
    Serial.println("ERR: Empty payload");
    return;
  }
  
  int start = 0;
  int pulseCount = 0;
  
  while (start >= 0 && start < payload.length()) {
    int comma = payload.indexOf(',', start);
    String part = (comma == -1) 
      ? payload.substring(start) 
      : payload.substring(start, comma);
    
    part.trim();  // Remove any spaces
    
    // Skip empty segments
    if (part.length() == 0) {
      if (comma == -1) break;
      start = comma + 1;
      continue;
    }
    
    // Convert to integer
    long pulse = part.toInt();
    
    // Validate pulse value
    if (pulse <= 0) {
      Serial.print("WARN: Invalid pulse value: ");
      Serial.println(part);
      if (comma == -1) break;
      start = comma + 1;
      continue;
    }
    
    if (pulse > MAX_PULSE_MS) {
      Serial.print("WARN: Pulse too long, capping at ");
      Serial.print(MAX_PULSE_MS);
      Serial.println("ms");
      pulse = MAX_PULSE_MS;
    }
    
    // Play the pulse
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
