# Emotion Detector for Blind Accessibility

This project detects facial emotions from a webcam and converts them to vibration patterns for haptic feedback, helping blind individuals understand how others around them are feeling.

## 🎯 How It Works

1. Camera captures video of people in front of the user
2. AI analyzes faces to detect emotions (happy, sad, angry, etc.)
3. Each emotion maps to a specific vibration pattern
4. Hardware teammate receives the signal and triggers haptic feedback

## 📊 Emotion to Vibration Mapping

| Emotion   | Vibrations | Description |
|-----------|------------|-------------|
| Happy     | 1          | One short pulse |
| Angry     | 2          | Two quick pulses |
| Sad       | 3          | Three pulses |
| Surprise  | 4          | Four pulses |
| Fear      | 5          | Five pulses (alert!) |
| Disgust   | 6          | Six pulses |
| Neutral   | 0          | No vibration |

## 🚀 Quick Start

### Step 1: Install Python
Make sure you have Python 3.8+ installed. Download from: https://www.python.org/downloads/

### Step 2: Install Dependencies
Open a terminal/command prompt in this folder and run:

```bash
pip install -r requirements.txt
```

⚠️ **Note:** First install may take a few minutes (downloads ~500MB of AI models).

### Step 3: Run the Detector
```bash
python main.py
```

### Step 4: Test It
- Point your webcam at your face
- Make different expressions (smile, frown, look surprised)
- Watch the terminal output show detected emotions!

## 📁 Project Files

| File | Purpose |
|------|---------|
| `main.py` | Main program - run this |
| `config.py` | Settings (emotion mapping, camera, etc.) |
| `hardware_bridge.py` | Interface for hardware teammate |
| `output.txt` | Latest emotion data (auto-generated) |
| `requirements.txt` | Python dependencies |

## 🔧 Configuration

Edit `config.py` to customize:

- **EMOTION_TO_VIBRATION**: Change which emotions map to how many vibrations
- **DETECTION_INTERVAL**: How often to check (lower = faster, uses more CPU)
- **CONFIDENCE_THRESHOLD**: Minimum confidence to report an emotion
- **CAMERA_INDEX**: Which camera to use (0 = default webcam)

## 🤝 For Hardware Teammate

The emotion detector outputs data in these ways:

### Option 1: Read from File
Check `output.txt` which contains JSON like:
```json
{"timestamp": "2024-01-14 10:30:45", "emotion": "happy", "vibrations": 1, "confidence": 0.85}
```

### Option 2: Serial Communication (Arduino)
1. Set `OUTPUT_TO_SERIAL = True` in `config.py`
2. Set correct `SERIAL_PORT` (e.g., 'COM3' on Windows)
3. Use the Arduino code example in `hardware_bridge.py`

### Option 3: Custom Integration
Modify the `send_vibration()` function in `hardware_bridge.py` to add your own communication method.

## 🐛 Troubleshooting

**"Could not open camera"**
- Make sure no other app is using your webcam
- Try changing `CAMERA_INDEX` in config.py (try 0, 1, or 2)

**"No face detected"**
- Make sure your face is visible and well-lit
- Face the camera directly

**Slow performance**
- Increase `DETECTION_INTERVAL` in config.py
- Close other applications

**Installation errors**
- Make sure you have Python 3.8+
- Try: `pip install --upgrade pip` first

## 📱 Future Ideas

- [ ] Add support for multiple faces
- [ ] Mobile app version
- [ ] Voice feedback option
- [ ] Emotion history/trends

---
Made with ❤️ for accessibility
