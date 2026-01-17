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
from collections import deque, Counter
from datetime import datetime

# Import our modules
import config
import hardware_bridge


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


def main():
    """Main function to run the emotion detector."""
    
    print("\n" + "="*60)
    print("   EMOTION DETECTOR FOR BLIND ACCESSIBILITY")
    print("="*60 + "\n")
    
    # Load the emotion detection model
    DeepFace = load_emotion_detector()
    
    # Initialize hardware connection (if enabled)
    hardware_bridge.init_serial()
    
    # Start the camera
    cap = start_camera()
    
    print("\n" + "-"*60)
    print("RUNNING - Point camera at a face to detect emotions")
    print("-"*60 + "\n")
    
    last_detection_time = 0
    show_window = True

    # Sliding window of recent analyses: (timestamp, emotion, confidence)
    analysis_history: deque[tuple[float, str | None, float]] = deque()

    # Cooldown control
    mute_until = 0.0

    # For brief on-screen signal message (not analysis)
    last_signal_text = None
    last_signal_shown_at = 0.0
    
    try:
        while True:
            # Capture frame
            ret, frame = cap.read()
            if not ret:
                print("Warning: Could not read frame from camera")
                continue
            
            current_time = time.time()
            emotion = None
            confidence = 0.0
            
            # Only analyze at specified interval (to save CPU)
            if current_time - last_detection_time >= config.DETECTION_INTERVAL:
                last_detection_time = current_time

                # Analyze the frame for emotions
                emotion, confidence = analyze_frame(DeepFace, frame)

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
                                last_signal_text = f"SIGNAL: {dominant_emotion.upper()} -> {vibrations} vibration(s)"
                                last_signal_shown_at = current_time
            
            # Try to show video window (optional - for debugging)
            if show_window:
                try:
                    # Only show signal banner for ~1.5s after it fires
                    signal_text = None
                    if last_signal_text and (current_time - last_signal_shown_at) <= 1.5:
                        signal_text = last_signal_text
                    else:
                        last_signal_text = None
                    display_frame = draw_overlay(frame.copy(), signal_text)
                    cv2.imshow('Emotion Detector', display_frame)
                    
                    # Check for quit key
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == ord('Q'):
                        print("\nQuitting...")
                        break
                except Exception as e:
                    # If display fails (headless system), continue without it
                    show_window = False
                    print("Note: Running in headless mode (no display window)")
    
    except KeyboardInterrupt:
        print("\n\nStopped by user (Ctrl+C)")
    
    finally:
        # Cleanup
        print("\nCleaning up...")
        cap.release()
        cv2.destroyAllWindows()
        hardware_bridge.cleanup()
        print("Done!")


if __name__ == "__main__":
    main()
