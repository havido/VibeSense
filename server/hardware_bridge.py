"""
Hardware Bridge - Interface for Hardware Team
==============================================
This file handles communication between the emotion detector and the haptic hardware.

FOR THE HARDWARE TEAMMATE:
- Modify the send_vibration() function to match your hardware setup
- The emotion detector will call send_vibration(count) whenever an emotion is detected
- You can also read from the output.txt file if that's easier for your setup
"""

import config
import json
from datetime import datetime

# Try to import serial (for Arduino communication)
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Note: pyserial not installed. Serial output disabled.")

# Global serial connection
serial_connection = None

# Simple buzzer pulse patterns (milliseconds HIGH per pulse)
# Tweak as needed to feel distinct on the active buzzer
BUZZER_PATTERNS = {
    "happy":    [120, 120, 200],        # short, upbeat chirps
    "angry":    [300, 80, 300, 80, 300],# sharp triple blast
    "sad":      [500, 200],             # long low tone with a tail
    "surprise": [80, 80, 80, 400],      # quick triplet then hold
    "fear":     [150, 150, 150, 150, 400],  # steady beeps then hold
    "disgust":  [250, 100, 500],        # medium then long groan
    "neutral":  []                      # no sound
}


def init_serial():
    """Initialize serial connection to Arduino/hardware."""
    global serial_connection
    
    if not SERIAL_AVAILABLE:
        return False
    
    if not config.OUTPUT_TO_SERIAL:
        return False
    
    try:
        serial_connection = serial.Serial(
            port=config.SERIAL_PORT,
            baudrate=config.SERIAL_BAUD_RATE,
            timeout=1
        )
        print(f"[OK] Connected to hardware on {config.SERIAL_PORT}")
        return True
    except Exception as e:
        print(f"[ERROR] Could not connect to hardware: {e}")
        return False


def send_vibration(vibration_count: int, emotion: str, confidence: float):
    """
    Send vibration signal to the hardware.
    
    This is the main function your hardware teammate needs to integrate with.
    
    Parameters:
    -----------
    vibration_count : int
        Number of vibrations to trigger (0-6)
    emotion : str
        The detected emotion name (happy, sad, angry, etc.)
    confidence : float
        How confident the detection is (0.0 to 1.0)
    """
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Pick buzzer pattern; fall back to simple repeated beeps based on count
    pattern = BUZZER_PATTERNS.get(emotion)
    if pattern is None:
        # unknown emotion: reuse count as N quick beeps
        pattern = [150] * max(vibration_count, 1)
    # Flatten to comma-separated millisecond pulses for the Arduino sketch
    pattern_str = ",".join(str(p) for p in pattern if p > 0)

    # Create data packet
    data = {
        "timestamp": timestamp,
        "emotion": emotion,
        "buzzer_pattern": pattern,
        "confidence": round(confidence, 2)
    }
    
    # Output to console
    if config.OUTPUT_TO_CONSOLE:
        beeps = len(pattern)
        print(f"[{timestamp}] {emotion.upper()} (confidence: {confidence:.0%}) -> {beeps} beep(s) [{pattern_str}]")
    
    # Output to file (for hardware team to read)
    if config.OUTPUT_TO_FILE:
        try:
            with open("output.txt", "w") as f:
                f.write(json.dumps(data))
        except Exception as e:
            print(f"Warning: Could not write to file: {e}")
    
    # Output to serial (for Arduino/hardware)
    if config.OUTPUT_TO_SERIAL and serial_connection:
        try:
            # Send format: "B:120,120,200\n" (ms HIGH durations per pulse)
            message = f"B:{pattern_str}\n"
            serial_connection.write(message.encode())
        except Exception as e:
            print(f"Warning: Could not send to serial: {e}")
    
    return data


def cleanup():
    """Clean up connections when program exits."""
    global serial_connection
    if serial_connection:
        serial_connection.close()
        print("Serial connection closed.")


# =============================================================================
# Reference: Arduino code to receive signals
# =============================================================================
"""
// Active Buzzer Receiver for VibeRater (with debug)
const uint8_t BUZZER_PIN = 9;
const unsigned long GAP_MS = 150;

void setup() {
  Serial.begin(9600);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.println("Ready for B:payload");
}

void loop() {
  if (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    line.trim();               // drops \r if present
    Serial.print("RX: ");
    Serial.println(line);
    if (line.startsWith("B:")) {
      playPattern(line.substring(2));
    }
  }
}

void playPattern(const String& payload) {
  if (payload.length() == 0) return;  // ignore empty payloads
  int start = 0;
  while (start >= 0) {
    int comma = payload.indexOf(',', start);
    String part = (comma == -1) ? payload.substring(start) : payload.substring(start, comma);
    part.trim();
    unsigned long pulse = part.toInt();
    if (pulse > 0) {
      digitalWrite(BUZZER_PIN, HIGH);
      delay(pulse);
      digitalWrite(BUZZER_PIN, LOW);
      delay(GAP_MS);
    }
    if (comma == -1) break;
    start = comma + 1;
  }
}
"""
