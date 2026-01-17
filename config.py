"""
Configuration for Emotion-to-Vibration Mapping
Modify these values to customize the haptic feedback patterns.
"""

# Map each emotion to a vibration count
# Your teammate will receive these numbers to trigger the hardware
EMOTION_TO_VIBRATION = {
    'happy': 1,      # 1 vibration  - positive emotion
    'angry': 2,      # 2 vibrations - negative/intense emotion
    'sad': 3,        # 3 vibrations - negative emotion
    'surprise': 4,   # 4 vibrations - sudden emotion
    'fear': 5,       # 5 vibrations - alert/danger emotion
    'disgust': 6,    # 6 vibrations - negative reaction
    'neutral': 0     # no vibration - no strong emotion detected
}

# How often to check for emotions (in seconds)
# Lower = more responsive but uses more CPU
# Higher = less responsive but saves battery
DETECTION_INTERVAL = 0.5

# Minimum confidence threshold (0.0 to 1.0)
# Only report emotions with confidence above this value
CONFIDENCE_THRESHOLD = 0.3

# Camera settings
CAMERA_INDEX = 0  # Usually 0 for built-in webcam, 1 for external

# Hardware communication settings
# Your teammate can modify these for their setup
SERIAL_PORT = 'COM3'  # Windows COM port for Arduino
SERIAL_BAUD_RATE = 9600

# Output modes (can enable multiple)
OUTPUT_TO_CONSOLE = True      # Print to terminal
OUTPUT_TO_FILE = True         # Write to output.txt
OUTPUT_TO_SERIAL = False      # Send to Arduino (enable when hardware ready)

# Sustained detection and cooldown settings
# Emotion must be sustained within a sliding window to trigger output
SUSTAIN_WINDOW_SECONDS = 1.5        # Analyze consistency over this window
SUSTAIN_RATIO = 0.8                 # 80% of samples must match the same emotion
STRONG_CONFIDENCE_THRESHOLD = 0.8   # Only count samples with >=80% confidence
SIGNAL_COOLDOWN_SECONDS = 5.0       # After signal, mute further signals for 5s
