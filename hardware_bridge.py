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
    
    # Create data packet
    data = {
        "timestamp": timestamp,
        "emotion": emotion,
        "vibrations": vibration_count,
        "confidence": round(confidence, 2)
    }
    
    # Output to console
    if config.OUTPUT_TO_CONSOLE:
        print(f"[{timestamp}] {emotion.upper()} (confidence: {confidence:.0%}) -> {vibration_count} vibration(s)")
    
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
            # Send format: "V:3\n" means 3 vibrations
            # Modify this format based on what your hardware expects
            message = f"V:{vibration_count}\n"
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
# FOR HARDWARE TEAMMATE: Example Arduino code to receive signals
# =============================================================================
"""
// Arduino code to receive vibration signals
// Upload this to your Arduino

const int VIBRATION_PIN = 9;  // Pin connected to vibration motor

void setup() {
    Serial.begin(9600);
    pinMode(VIBRATION_PIN, OUTPUT);
}

void loop() {
    if (Serial.available() > 0) {
        String data = Serial.readStringUntil('\\n');
        
        if (data.startsWith("V:")) {
            int count = data.substring(2).toInt();
            vibrateMotor(count);
        }
    }
}

void vibrateMotor(int count) {
    for (int i = 0; i < count; i++) {
        digitalWrite(VIBRATION_PIN, HIGH);
        delay(200);  // Vibration duration
        digitalWrite(VIBRATION_PIN, LOW);
        delay(150);  // Pause between vibrations
    }
}
"""
