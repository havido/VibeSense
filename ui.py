"""
UI Module for Emotion Detector
==============================
Tkinter-based interface for configuration and live monitoring.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import cv2
from PIL import Image, ImageTk
import threading
import time
from collections import deque
from datetime import datetime


class EmotionDetectorUI:
    """Main UI window for emotion detector."""
    
    def __init__(self, update_callback=None):
        self.root = tk.Tk()
        self.root.title("VibeSense - Emotion Detector")
        self.root.geometry("1200x800")
        self.root.configure(bg='#2b2b2b')
        
        # Bring window to front on macOS
        try:
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after_idle(lambda: self.root.attributes('-topmost', False))
        except:
            pass
        
        # State variables
        self.current_emotion = None
        self.current_confidence = 0.0
        self.last_signal_text = None
        self.camera_frame = None
        self.video_label = None
        self.running = True
        self.update_callback = update_callback
        
        # Connection status
        self.camera_connected = False
        self.serial_connected = False
        
        # History for statistics
        self.emotion_history = deque(maxlen=100)
        
        # Create UI components
        self._create_widgets()
        
        # Start update loop
        self._update_loop()
        
        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Main container
        main_frame = tk.Frame(self.root, bg='#2b2b2b')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - Video feed and status
        left_panel = tk.Frame(main_frame, bg='#2b2b2b')
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Video display frame
        video_frame = tk.LabelFrame(left_panel, text="Live Camera Feed", 
                                   bg='#2b2b2b', fg='white', font=('Arial', 12, 'bold'))
        video_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.video_label = tk.Label(video_frame, bg='black', text="Initializing camera...")
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status bar
        status_frame = tk.Frame(left_panel, bg='#2b2b2b')
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Current emotion display
        emotion_frame = tk.LabelFrame(status_frame, text="Current Emotion", 
                                     bg='#2b2b2b', fg='white', font=('Arial', 11, 'bold'))
        emotion_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.emotion_label = tk.Label(emotion_frame, text="No face detected", 
                                      font=('Arial', 16, 'bold'), bg='#2b2b2b', fg='#888888')
        self.emotion_label.pack(pady=10)
        
        self.confidence_label = tk.Label(emotion_frame, text="Confidence: 0%", 
                                         font=('Arial', 12), bg='#2b2b2b', fg='#aaaaaa')
        self.confidence_label.pack(pady=(0, 10))
        
        # Confidence bar
        self.confidence_bar = tk.Canvas(emotion_frame, height=20, bg='#2b2b2b', highlightthickness=0)
        self.confidence_bar.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Connection status
        conn_frame = tk.LabelFrame(status_frame, text="Connection Status", 
                                  bg='#2b2b2b', fg='white', font=('Arial', 11, 'bold'))
        conn_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        self.camera_status = tk.Label(conn_frame, text="📷 Camera: Disconnected", 
                                      font=('Arial', 11), bg='#2b2b2b', fg='#ff6666')
        self.camera_status.pack(pady=5)
        
        self.serial_status = tk.Label(conn_frame, text="🔌 Hardware: Not connected", 
                                      font=('Arial', 11), bg='#2b2b2b', fg='#ff6666')
        self.serial_status.pack(pady=5)
        
        # Right panel - Settings and log
        right_panel = tk.Frame(main_frame, bg='#2b2b2b', width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        # Settings panel
        settings_frame = tk.LabelFrame(right_panel, text="Settings", 
                                      bg='#2b2b2b', fg='white', font=('Arial', 12, 'bold'))
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        self._create_settings_widgets(settings_frame)
        
        # Log/Activity panel
        log_frame = tk.LabelFrame(right_panel, text="Activity Log", 
                                 bg='#2b2b2b', fg='white', font=('Arial', 12, 'bold'))
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, 
                                                   bg='#1e1e1e', fg='#00ff00',
                                                   font=('Courier', 9), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.config(state=tk.DISABLED)
        
        # Statistics panel
        stats_frame = tk.LabelFrame(right_panel, text="Statistics (Last 100)", 
                                   bg='#2b2b2b', fg='white', font=('Arial', 11, 'bold'))
        stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.stats_label = tk.Label(stats_frame, text="No data yet", 
                                    font=('Arial', 9), bg='#2b2b2b', fg='#aaaaaa', justify=tk.LEFT)
        self.stats_label.pack(padx=10, pady=10, anchor=tk.W)
    
    def _create_settings_widgets(self, parent):
        """Create settings control widgets."""
        import config
        
        # Detection interval
        tk.Label(parent, text="Detection Interval (s):", bg='#2b2b2b', fg='white', 
                font=('Arial', 9)).pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.interval_var = tk.DoubleVar(value=config.DETECTION_INTERVAL)
        interval_scale = tk.Scale(parent, from_=0.1, to=2.0, resolution=0.1, 
                                  variable=self.interval_var, orient=tk.HORIZONTAL,
                                  bg='#2b2b2b', fg='white', highlightthickness=0,
                                  command=self._on_interval_change)
        interval_scale.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Strong confidence threshold
        tk.Label(parent, text="Strong Confidence Threshold:", bg='#2b2b2b', fg='white', 
                font=('Arial', 9)).pack(anchor=tk.W, padx=10, pady=(0, 0))
        self.conf_thresh_var = tk.DoubleVar(value=config.STRONG_CONFIDENCE_THRESHOLD)
        conf_scale = tk.Scale(parent, from_=0.1, to=1.0, resolution=0.05, 
                              variable=self.conf_thresh_var, orient=tk.HORIZONTAL,
                              bg='#2b2b2b', fg='white', highlightthickness=0,
                              command=self._on_threshold_change)
        conf_scale.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Cooldown period
        tk.Label(parent, text="Signal Cooldown (s):", bg='#2b2b2b', fg='white', 
                font=('Arial', 9)).pack(anchor=tk.W, padx=10, pady=(0, 0))
        self.cooldown_var = tk.DoubleVar(value=config.SIGNAL_COOLDOWN_SECONDS)
        cooldown_scale = tk.Scale(parent, from_=1.0, to=30.0, resolution=1.0, 
                                  variable=self.cooldown_var, orient=tk.HORIZONTAL,
                                  bg='#2b2b2b', fg='white', highlightthickness=0,
                                  command=self._on_cooldown_change)
        cooldown_scale.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Test buttons
        test_frame = tk.Frame(parent, bg='#2b2b2b')
        test_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(test_frame, text="Test Vibration 1", command=lambda: self._test_vibration(1),
                 bg='#444444', fg='white', relief=tk.RAISED, padx=10, pady=5).pack(side=tk.LEFT, padx=2)
        tk.Button(test_frame, text="Test Vibration 3", command=lambda: self._test_vibration(3),
                 bg='#444444', fg='white', relief=tk.RAISED, padx=10, pady=5).pack(side=tk.LEFT, padx=2)
    
    def _on_interval_change(self, value):
        """Update detection interval."""
        import config
        config.DETECTION_INTERVAL = float(value)
        self.log(f"Detection interval set to {value}s")
    
    def _on_threshold_change(self, value):
        """Update confidence threshold."""
        import config
        config.STRONG_CONFIDENCE_THRESHOLD = float(value)
        self.log(f"Confidence threshold set to {float(value):.0%}")
    
    def _on_cooldown_change(self, value):
        """Update cooldown period."""
        import config
        config.SIGNAL_COOLDOWN_SECONDS = float(value)
        self.log(f"Cooldown set to {value}s")
    
    def _test_vibration(self, count):
        """Test vibration manually."""
        import hardware_bridge
        hardware_bridge.send_vibration(count, "test", 1.0)
        self.log(f"Test: Sent {count} vibration(s)")
    
    def update_video(self, frame):
        """Update the video display with a new frame."""
        if not self.running:
            return
        
        try:
            # Resize frame for display
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_rgb)
            frame_pil = frame_pil.resize((640, 480), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(image=frame_pil)
            
            # Update label
            self.video_label.configure(image=photo, text="")
            self.video_label.image = photo  # Keep a reference
            self.camera_connected = True
            self._update_connection_status()
        except Exception as e:
            self.log(f"Error updating video: {e}")
    
    def update_emotion(self, emotion, confidence):
        """Update the current emotion display."""
        self.current_emotion = emotion
        self.current_confidence = confidence
        
        # Update labels
        if emotion:
            self.emotion_label.config(text=emotion.upper(), fg='#00ff88')
            self.confidence_label.config(text=f"Confidence: {confidence:.0%}", fg='#aaaaaa')
        else:
            self.emotion_label.config(text="No face detected", fg='#888888')
            self.confidence_label.config(text="Confidence: 0%", fg='#aaaaaa')
        
        # Update confidence bar
        self.confidence_bar.delete("all")
        bar_width = self.confidence_bar.winfo_width() - 20
        if bar_width > 0:
            fill_width = int(bar_width * confidence)
            self.confidence_bar.create_rectangle(10, 5, 10 + fill_width, 15, 
                                                fill='#00ff88', outline='')
        
        # Add to history
        if emotion:
            self.emotion_history.append(emotion)
            self._update_statistics()
    
    def update_signal(self, signal_text):
        """Update the last signal text."""
        self.last_signal_text = signal_text
    
    def set_serial_connected(self, connected):
        """Update serial connection status."""
        self.serial_connected = connected
        self._update_connection_status()
    
    def _update_connection_status(self):
        """Update connection status labels."""
        if self.camera_connected:
            self.camera_status.config(text="📷 Camera: Connected", fg='#66ff66')
        else:
            self.camera_status.config(text="📷 Camera: Disconnected", fg='#ff6666')
        
        if self.serial_connected:
            self.serial_status.config(text="🔌 Hardware: Connected", fg='#66ff66')
        else:
            self.serial_status.config(text="🔌 Hardware: Not connected", fg='#ff6666')
    
    def _update_statistics(self):
        """Update statistics display."""
        if not self.emotion_history:
            self.stats_label.config(text="No data yet")
            return
        
        from collections import Counter
        counts = Counter(self.emotion_history)
        total = len(self.emotion_history)
        
        stats_lines = [f"Total detections: {total}"]
        for emotion, count in counts.most_common():
            percentage = (count / total) * 100
            stats_lines.append(f"{emotion:>10}: {count:>3} ({percentage:>5.1f}%)")
        
        self.stats_label.config(text="\n".join(stats_lines))
    
    def log(self, message):
        """Add a message to the activity log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        
        # Limit log size
        lines = self.log_text.get("1.0", tk.END).split('\n')
        if len(lines) > 200:
            self.log_text.delete("1.0", f"{len(lines)-200}.0")
        
        self.log_text.config(state=tk.DISABLED)
    
    def _update_loop(self):
        """Non-blocking update loop for UI."""
        if self.running:
            self.root.update()
            self.root.after(10, self._update_loop)  # Update every 10ms
    
    def on_closing(self):
        """Handle window closing."""
        self.running = False
        if self.update_callback:
            self.update_callback('quit')
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Start the UI main loop (blocking)."""
        self.root.mainloop()
