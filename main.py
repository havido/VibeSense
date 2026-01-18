"""
Emotion Detector for Blind Accessibility
=========================================
This script uses your webcam to detect facial emotions of people in front of you
and converts them to vibration patterns for haptic feedback.

Run with: python main.py

Press 'Q' to quit (if display window is open)
Press Ctrl+C in terminal to stop
"""

import cv2
import time
import sys
import threading
from collections import deque, Counter
from datetime import datetime

# Import our modules
import config
import hardware_bridge

# Try to import UI (requires Pillow for PIL)
try:
    from PIL import Image, ImageTk
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    print("Note: UI not available. Install Pillow: pip install Pillow")


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
        results = DeepFace.analyze(
            frame, 
            actions=['emotion'],
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

    # Sliding window of recent analyses: (timestamp, emotion, confidence)
    analysis_history: deque[tuple[float, str | None, float]] = deque()

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

                # Check sustained emotion condition only if not muted
                if current_time >= mute_until and analysis_history:
                    total = len(analysis_history)
                    # Count strong-confidence samples by emotion
                    counts: Counter[str] = Counter()
                    for _, e, conf in analysis_history:
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


def main():
    """Main function to run the emotion detector."""
    
    print("\n" + "="*60)
    print("   EMOTION DETECTOR FOR BLIND ACCESSIBILITY")
    print("="*60 + "\n")
    
    # Load the emotion detection model
    DeepFace = load_emotion_detector()
    
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
