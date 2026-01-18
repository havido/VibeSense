"""
Emotion Detector for Blind Accessibility
========================================
This script uses your webcam to detect facial emotions of people in front of you,
converts them to sound patterns, and exposes a
Flask /gemini endpoint that can read the live analysis history (last 5 seconds)
and ask Gemini for a single summarized emotion.

Run with: python server/main.py

Press 'Q' to quit (if display window is open)
Press Ctrl+C in terminal to stop
"""

import os
import cv2
import time
import sys
import threading
from collections import deque, Counter
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from google import genai

# Import our modules
import config
import hardware_bridge

# Make .env variables available (e.g., GOOGLE_API_KEY)
load_dotenv()

# Try to import UI (requires Pillow for PIL)
try:
    from PIL import Image, ImageTk
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    print("Note: UI not available. Install Pillow: pip install Pillow")


# Shared in-memory emotion history for the Flask endpoint to read
analysis_history: deque[tuple[float, str | None, float]] = deque()
analysis_lock = threading.Lock()

# Latest biometrics pushed from clients
latest_biometrics = {
    "pulse_average": None,
    "breathing_average": None,
    "timestamp": None
}
biometrics_lock = threading.Lock()

# Flask app (runs in a background thread)
app = Flask(__name__)


def _get_genai_client():
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("api_key")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY (or api_key) environment variable for Gemini.")
    return genai.Client(api_key=api_key)


def load_emotion_detector():
    """Load the DeepFace emotion detection model."""
    print("Loading emotion detection model... (this may take a moment)")
    
    try:
        from deepface import DeepFace
        
        # Warm up the model with a test image
        import numpy as np
        test_img = np.zeros((48, 48, 3), dtype=np.uint8)
        try:
            DeepFace.analyze(test_img, actions=['emotion'], enforce_detection=False)
        except:
            pass  # Warm-up may fail on blank image, that's okay
        
        print("[OK] Emotion detection model loaded successfully!")
        return DeepFace
    
    except ImportError as e:
        print("\n[ERROR] Required libraries not installed!")
        print("Please run: pip install -r requirements.txt")
        print(f"\nDetails: {e}")
        sys.exit(1)


def start_camera():
    """Initialize the webcam."""
    print(f"Starting camera (index {config.CAMERA_INDEX})...")
    
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    
    if not cap.isOpened():
        print("\n[ERROR] Could not open camera!")
        print("Make sure:")
        print("  1. Your webcam is connected")
        print("  2. No other app is using it")
        print("  3. Try changing CAMERA_INDEX in config.py (try 0, 1, or 2)")
        sys.exit(1)
    
    # Set camera resolution (lower = faster processing)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print("[OK] Camera started successfully!")
    return cap


def analyze_frame(DeepFace, frame):
    """Analyze a single frame for emotions."""
    try:
        # Resize for consistency
        frame_resized = cv2.resize(frame, (640, 480))

        # Improve contrast
        lab = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        frame_enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        results = DeepFace.analyze(
            frame_enhanced, 
            actions=['emotion'],
            detector_backend='ssd',  # More accurate face detection
            enforce_detection=False,  # Don't crash if no face found
            silent=True
        )
        
        if results and len(results) > 0:
            result = results[0]
            dominant_emotion = result['dominant_emotion']
            confidence = result['emotion'][dominant_emotion] / 100.0
            return dominant_emotion, confidence
        
        return None, 0.0
    
    except Exception as e:
        return None, 0.0


def _recent_emotions(window_seconds: float = 5.0):
    """Return recent (timestamp, emotion, confidence) samples within window."""
    cutoff = time.time() - window_seconds
    with analysis_lock:
        return [(ts, emo, conf) for (ts, emo, conf) in analysis_history if ts >= cutoff and emo]


def _build_gemini_prompt(samples: list[tuple[float, str, float]]):
    """Craft a concise prompt instructing Gemini to return one emotion word."""
    counts: Counter[str] = Counter()
    for _, emo, conf in samples:
        if emo:
            counts[emo] += 1
    top_emo, top_count = counts.most_common(1)[0]

    with biometrics_lock:
        pulse = latest_biometrics["pulse_average"]
        breath = latest_biometrics["breathing_average"]
        b_ts = latest_biometrics["timestamp"]
    biometrics_summary = (
        f"Biometrics (latest): pulse={pulse}, breathing={breath}, timestamp={b_ts}"
    )

    prompt = (
        "You are an emotion summarizer. "
        "Given recent emotion detections, return ONLY the single dominant emotion word "
        "from the list, no punctuation or extra words.\n\n"
        f"{biometrics_summary}\n\n"
        f"Samples in last {len(samples)} frames:\n"
    )
    for _, emo, conf in samples:
        prompt += f"- {emo} ({conf:.0%} confidence)\n"
    prompt += (
        f"\nDetected dominant emotion by count: {top_emo} ({top_count} samples). "
        "Respond with that dominant emotion unless evidence strongly contradicts it."
    )
    return prompt, top_emo


@app.route("/gemini", methods=["POST", "GET"])
def gemini_endpoint():
    """
    Returns a single emotion word based on the last few seconds of detections.
    Optional query param: window (seconds, default 5).
    """
    try:
        window = float(request.args.get("window", 5))
    except ValueError:
        window = 5.0

    samples = _recent_emotions(window)
    if not samples:
        return jsonify({
            "status": "error",
            "message": f"No emotion samples in the last {window} seconds"
        }), 404

    counts = Counter(emo for _, emo, _ in samples if emo)
    prompt, fallback_emotion = _build_gemini_prompt(samples)
    proportion = counts.get(fallback_emotion, 0) / float(len(samples) or 1)

    model_text = ""
    signal_payload = None
    source = "gemini"
    error_msg = None
    try:
        client = _get_genai_client()
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        model_text = (getattr(response, "text", "") or "").strip()
        # Keep only the first word to enforce a single emotion token
        one_word = model_text.split()[0] if model_text else fallback_emotion
    except Exception as e:
        # Fall back to the locally computed dominant emotion
        one_word = fallback_emotion
        source = "local_fallback"
        error_msg = str(e)

    if config.ENABLE_SIGNAL_ON_API:
        vibrations = config.EMOTION_TO_VIBRATION.get(one_word, 0)
        if vibrations > 0:
            # Use proportion of samples as a rough confidence signal
            signal_payload = hardware_bridge.send_vibration(
                vibrations, one_word, max(proportion, 0.01)
            )

    response_payload = {
        "status": "ok",
        "emotion": one_word,
        "gemini_raw": model_text,
        "samples_used": len(samples),
        "signal_triggered": bool(signal_payload),
        "source": source
    }
    if error_msg:
        response_payload["error"] = error_msg
    if signal_payload:
        response_payload["signal_payload"] = signal_payload

    return jsonify(response_payload), 200


@app.route("/biometrics", methods=["POST"])
def receive_biometrics():
    """
    POST endpoint to receive biometric data from a client.

    Expected JSON format:
    {
        "pulse_average": float,
        "breathing_average": float
    }
    """
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"status": "error", "message": "No JSON data received"}), 400

        if "pulse_average" not in data or "breathing_average" not in data:
            return jsonify({"status": "error", "message": "Missing pulse_average or breathing_average"}), 400

        pulse_avg = data.get("pulse_average")
        breathing_avg = data.get("breathing_average")

        if not isinstance(pulse_avg, (int, float)) or not isinstance(breathing_avg, (int, float)):
            return jsonify({"status": "error", "message": "pulse_average and breathing_average must be numeric"}), 400

        with biometrics_lock:
            latest_biometrics["pulse_average"] = float(pulse_avg)
            latest_biometrics["breathing_average"] = float(breathing_avg)
            latest_biometrics["timestamp"] = datetime.now().isoformat()

        print(f"[BIOMETRICS {latest_biometrics['timestamp']}] pulse={pulse_avg} breathing={breathing_avg}")

        return jsonify({
            "status": "success",
            "data": {
                "pulse_average": pulse_avg,
                "breathing_average": breathing_avg,
                "timestamp": latest_biometrics["timestamp"]
            }
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def draw_overlay(frame, signal_text: str | None):
    """Draw only the signal event on the video frame (no analysis details)."""
    if signal_text:
        cv2.rectangle(frame, (10, 10), (620, 90), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (620, 90), (255, 255, 255), 2)
        cv2.putText(frame, signal_text, (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
    # Always draw quit help
    h = frame.shape[0]
    cv2.putText(frame, "Press 'Q' to quit", (10, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    return frame


def run_detection_loop(DeepFace, cap, ui=None, stop_event=None):
    """Run the main emotion detection loop in a separate thread."""
    print("\n" + "-"*60)
    print("RUNNING - Point camera at a face to detect emotions")
    print("-"*60 + "\n")
    
    last_detection_time = 0
    last_video_update = 0
    show_cv_window = False  # Use UI instead of cv2.imshow

    # Cooldown control
    mute_until = 0.0

    # For brief on-screen signal message (not analysis)
    last_signal_text = None
    last_signal_shown_at = 0.0
    
    try:
        while not (stop_event and stop_event.is_set()):
            # Capture frame
            ret, frame = cap.read()
            if not ret:
                print("Warning: Could not read frame from camera")
                if ui:
                    ui.log("Warning: Could not read frame from camera")
                time.sleep(0.1)
                continue
            
            current_time = time.time()
            emotion = None
            confidence = 0.0
            
            # Update UI with video frame (limit to ~30fps for performance)
            if ui and (current_time - last_video_update >= 0.033):
                ui.update_video(frame)
                last_video_update = current_time
            
            # Only analyze at specified interval (to save CPU)
            if current_time - last_detection_time >= config.DETECTION_INTERVAL:
                last_detection_time = current_time

                # Analyze the frame for emotions
                emotion, confidence = analyze_frame(DeepFace, frame)

                # Update UI with current emotion
                if ui:
                    ui.update_emotion(emotion, confidence)

                # Record analysis result into sliding window
                with analysis_lock:
                    analysis_history.append((current_time, emotion, float(confidence or 0.0)))
                    # Purge old entries outside sustain window
                    window_start = current_time - config.SUSTAIN_WINDOW_SECONDS
                    while analysis_history and analysis_history[0][0] < window_start:
                        analysis_history.popleft()

                # Print all analysis to terminal
                ts = datetime.now().strftime("%H:%M:%S")
                if emotion:
                    print(f"[ANALYSIS {ts}] emotion={emotion:>8}  confidence={confidence:.0%}")
                    if ui:
                        ui.log(f"Detected: {emotion} ({confidence:.0%})")
                else:
                    print(f"[ANALYSIS {ts}] emotion=None     confidence=0%")

                # Check sustained emotion condition only if not muted and auto signaling enabled
                if config.ENABLE_AUTO_SIGNALING and current_time >= mute_until and analysis_history:
                    with analysis_lock:
                        snapshot = list(analysis_history)
                    total = len(snapshot)
                    # Count strong-confidence samples by emotion
                    counts: Counter[str] = Counter()
                    for _, e, conf in snapshot:
                        if e and conf >= config.STRONG_CONFIDENCE_THRESHOLD:
                            counts[e] += 1

                    if counts:
                        # Find dominant strong emotion
                        dominant_emotion, strong_count = counts.most_common(1)[0]
                        ratio = strong_count / float(total)
                        if ratio >= config.SUSTAIN_RATIO:
                            vibrations = config.EMOTION_TO_VIBRATION.get(dominant_emotion, 0)
                            # Only send if there is a non-zero mapping (neutral -> 0)
                            if vibrations > 0:
                                hardware_bridge.send_vibration(vibrations, dominant_emotion, 1.0)
                                mute_until = current_time + config.SIGNAL_COOLDOWN_SECONDS
                                last_signal_text = f"{dominant_emotion.upper()} -> {vibrations} vibration(s)"
                                last_signal_shown_at = current_time
                                
                                if ui:
                                    ui.update_signal(last_signal_text)
                                    ui.log(f"SIGNAL: {last_signal_text}")
            
            # Fallback: show OpenCV window if UI not available
            if not ui and show_cv_window:
                try:
                    signal_text = None
                    if last_signal_text and (current_time - last_signal_shown_at) <= 1.5:
                        signal_text = last_signal_text
                    display_frame = draw_overlay(frame.copy(), signal_text)
                    cv2.imshow('Emotion Detector', display_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == ord('Q'):
                        break
                except Exception:
                    show_cv_window = False
            
            # Small sleep to prevent tight loop
            time.sleep(0.01)
    
    except Exception as e:
        print(f"\n[ERROR] Detection loop error: {e}")
        if ui:
            ui.log(f"ERROR: {e}")
    
    finally:
        # Cleanup
        print("\nStopping detection loop...")
        cap.release()
        if not ui:
            cv2.destroyAllWindows()


def start_flask_server():
    """Start the Flask server in a background thread so detection keeps running."""
    def _run():
        # use_reloader=False to avoid double threads
        app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def main():
    """Main function to run the emotion detector."""
    
    print("\n" + "="*60)
    print("   EMOTION DETECTOR FOR BLIND ACCESSIBILITY")
    print("="*60 + "\n")
    
    # Load the emotion detection model
    DeepFace = load_emotion_detector()
    
    # Start Flask API in the background so /gemini can read analysis_history
    flask_thread = start_flask_server()
    print("[API] Flask server started on port 8080 (endpoints: POST/GET /gemini)")

    # Initialize hardware connection (if enabled)
    serial_connected = hardware_bridge.init_serial()
    
    # Start the camera
    cap = start_camera()
    
    # Initialize UI if available
    ui = None
    stop_event = None
    detection_thread = None
    
    if UI_AVAILABLE:
        try:
            print("[UI] Initializing UI...")
            from ui import EmotionDetectorUI
            ui = EmotionDetectorUI()
            print("[UI] UI window created! Check for 'VibeSense - Emotion Detector' window.")
            ui.set_serial_connected(serial_connected)
            ui.log("Application started")
            ui.log(f"Camera index: {config.CAMERA_INDEX}")
            if config.OUTPUT_TO_SERIAL:
                ui.log(f"Serial port: {config.SERIAL_PORT}")
            
            stop_event = threading.Event()
            
            # Start detection in separate thread
            def ui_quit_callback(action):
                if action == 'quit':
                    stop_event.set()
            
            ui.update_callback = ui_quit_callback
            
            detection_thread = threading.Thread(
                target=run_detection_loop,
                args=(DeepFace, cap, ui, stop_event),
                daemon=True
            )
            detection_thread.start()
            
            # Run UI in main thread (Tkinter requirement)
            ui.run()
            
        except Exception as e:
            print(f"Warning: Could not start UI: {e}")
            print("Falling back to terminal mode...")
            ui = None
    
    # Fallback: run detection in main thread if no UI
    if not ui:
        try:
            run_detection_loop(DeepFace, cap, ui=None, stop_event=None)
        except KeyboardInterrupt:
            print("\n\nStopped by user (Ctrl+C)")
    
    # Cleanup
    if stop_event:
        stop_event.set()
    
    if detection_thread:
        detection_thread.join(timeout=2.0)
    
    print("\nCleaning up...")
    hardware_bridge.cleanup()
    print("Done!")

if __name__ == "__main__":
    main()
