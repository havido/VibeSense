"""
UI Module for Emotion Detector
==============================
Tkinter-based interface for configuration and live monitoring.
Includes keyboard navigation with audio descriptions for accessibility.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import cv2
from PIL import Image, ImageTk
import threading
import time
from collections import deque
from datetime import datetime
import subprocess
import platform


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
        
        # Keyboard navigation state
        self.focused_control_index = 0
        self.focusable_controls = []  # List of (widget, name, type) tuples
        self.audio_enabled = True  # Enable audio descriptions
        
        # Create UI components
        self._create_widgets()
        
        # Setup keyboard navigation
        self._setup_keyboard_navigation()
        
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
        """Create settings control widgets with keyboard navigation."""
        import config
        
        # Detection interval
        tk.Label(parent, text="Detection Interval (s):", bg='#2b2b2b', fg='white', 
                font=('Arial', 12)).pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.interval_var = tk.DoubleVar(value=config.DETECTION_INTERVAL)
        self.interval_scale = tk.Scale(parent, from_=0.1, to=2.0, resolution=0.1, 
                                  variable=self.interval_var, orient=tk.HORIZONTAL,
                                  bg='#2b2b2b', fg='white', highlightthickness=2,
                                  highlightbackground='#555555',
                                  command=self._on_interval_change)
        self.interval_scale.pack(fill=tk.X, padx=10, pady=(0, 10))
        # Make Up/Down navigate instead of adjusting slider value
        # Add to focusable controls: (widget, name, type, get_value_func)
        self.focusable_controls.append((self.interval_scale, "Detection Interval", "slider", 
                                       lambda: f"{self.interval_var.get():.1f} seconds"))
        
        # Strong confidence threshold
        tk.Label(parent, text="Strong Confidence Threshold:", bg='#2b2b2b', fg='white', 
                font=('Arial', 12)).pack(anchor=tk.W, padx=10, pady=(0, 0))
        self.conf_thresh_var = tk.DoubleVar(value=config.STRONG_CONFIDENCE_THRESHOLD)
        self.conf_scale = tk.Scale(parent, from_=0.1, to=1.0, resolution=0.05, 
                              variable=self.conf_thresh_var, orient=tk.HORIZONTAL,
                              bg='#2b2b2b', fg='white', highlightthickness=2,
                              highlightbackground='#555555',
                              command=self._on_threshold_change)
        self.conf_scale.pack(fill=tk.X, padx=10, pady=(0, 10))
        # Make Up/Down navigate instead of adjusting slider value
        self.focusable_controls.append((self.conf_scale, "Confidence Threshold", "slider",
                                       lambda: f"{self.conf_thresh_var.get():.0%}"))
        
        # Cooldown period (COMMENTED OUT - uncomment if needed)
        # tk.Label(parent, text="Signal Cooldown (s):", bg='#2b2b2b', fg='white', 
        #         font=('Arial', 9)).pack(anchor=tk.W, padx=10, pady=(0, 0))
        # self.cooldown_var = tk.DoubleVar(value=config.SIGNAL_COOLDOWN_SECONDS)
        # self.cooldown_scale = tk.Scale(parent, from_=1.0, to=30.0, resolution=1.0, 
        #                           variable=self.cooldown_var, orient=tk.HORIZONTAL,
        #                           bg='#2b2b2b', fg='white', highlightthickness=2,
        #                           highlightbackground='#555555',
        #                           command=self._on_cooldown_change)
        # self.cooldown_scale.pack(fill=tk.X, padx=10, pady=(0, 10))
        # # Make Up/Down navigate instead of adjusting slider value
        # self.focusable_controls.append((self.cooldown_scale, "Signal Cooldown", "slider",
        #                                lambda: f"{self.cooldown_var.get():.0f} seconds"))
    
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
    
    # Cooldown change handler (COMMENTED OUT - uncomment if Signal Cooldown slider is enabled)
    # def _on_cooldown_change(self, value):
    #     """Update cooldown period."""
    #     import config
    #     config.SIGNAL_COOLDOWN_SECONDS = float(value)
    #     self.log(f"Cooldown set to {value}s")
    
    
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
    
    def _setup_keyboard_navigation(self):
        """Setup keyboard navigation with arrow keys."""
        # Arrow keys for navigation - bind to root and all widget classes
        self.root.bind('<Up>', lambda e: self._navigate_focus(-1) or 'break')
        self.root.bind('<Down>', lambda e: self._navigate_focus(1) or 'break')
        # Bind to Scale class (sliders) - this will override individual binds
        self.root.bind_class('Scale', '<Up>', lambda e: self._navigate_focus(-1) or 'break')
        self.root.bind_class('Scale', '<Down>', lambda e: self._navigate_focus(1) or 'break')
        # Bind to Button class
        self.root.bind_class('Button', '<Up>', lambda e: self._navigate_focus(-1) or 'break')
        self.root.bind_class('Button', '<Down>', lambda e: self._navigate_focus(1) or 'break')
        
        # Left/Right for adjusting sliders - only when slider is focused
        self.root.bind('<Left>', lambda e: self._handle_left_right(-1))
        self.root.bind('<Right>', lambda e: self._handle_left_right(1))
        self.root.bind_class('Scale', '<Left>', lambda e: self._handle_left_right(-1))
        self.root.bind_class('Scale', '<Right>', lambda e: self._handle_left_right(1))
        
        # Space/Enter for activating buttons
        self.root.bind('<space>', lambda e: self._activate_focused())
        self.root.bind('<Return>', lambda e: self._activate_focused())
        
        # Tab as alternative navigation
        self.root.bind('<Tab>', lambda e: self._navigate_focus(1))
        self.root.bind('<Shift-Tab>', lambda e: self._navigate_focus(-1))
        
        # Set initial focus
        if self.focusable_controls:
            self._update_focus_display()
    
    def _navigate_focus(self, direction):
        """Navigate focus between controls."""
        if not self.focusable_controls:
            return "break"
        
        # Remove focus from current control
        self._clear_focus_display()
        
        # Move to next/previous control
        self.focused_control_index = (self.focused_control_index + direction) % len(self.focusable_controls)
        
        # Update focus display and announce
        self._update_focus_display()
        
        # Prevent default behavior
        return "break"
    
    def _clear_focus_display(self):
        """Clear visual focus from current control."""
        if 0 <= self.focused_control_index < len(self.focusable_controls):
            widget, _, _, _ = self.focusable_controls[self.focused_control_index]
            if isinstance(widget, tk.Scale):
                widget.config(highlightbackground='#555555', highlightthickness=2)
            elif isinstance(widget, tk.Button):
                widget.config(highlightbackground='#555555', highlightthickness=2)
    
    def _update_focus_display(self):
        """Update visual focus and announce current control."""
        if not self.focusable_controls or self.focused_control_index < 0:
            return
        
        widget, name, control_type, get_value = self.focusable_controls[self.focused_control_index]
        
        # Highlight focused control
        if isinstance(widget, tk.Scale):
            widget.config(highlightbackground='green', highlightthickness=3)  # Green highlight
            widget.focus_set()
        elif isinstance(widget, tk.Button):
            widget.config(highlightbackground='green', highlightthickness=3)
            widget.focus_set()
        
        # Announce via audio
        if control_type == "slider":
            value_text = get_value() if get_value else ""
            announcement = f"{name} slider, value: {value_text}. Use left and right arrows to adjust."
        else:  # button
            announcement = f"{name} button. Press Space or Enter to activate."
        
        self._announce(announcement)
    
    def _handle_left_right(self, direction):
        """Handle left/right arrow keys - adjust slider only if slider is focused."""
        if not self.focusable_controls or self.focused_control_index < 0:
            return "break"
        
        widget, name, control_type, get_value = self.focusable_controls[self.focused_control_index]
        
        # Only adjust if a slider is focused
        if control_type == "slider" and isinstance(widget, tk.Scale):
            self._adjust_slider_value(widget, name, get_value, direction)
        
        # Prevent default slider behavior
        return "break"
    
    def _adjust_slider_value(self, widget, name, get_value, direction):
        """Adjust slider value."""
        current = widget.get()
        resolution = widget['resolution']
        new_value = current + (direction * resolution)
        
        # Clamp to min/max
        min_val = widget['from']
        max_val = widget['to']
        new_value = max(min_val, min(max_val, new_value))
        
        widget.set(new_value)
        # Trigger the callback manually (they expect string from command callback)
        if widget == self.interval_scale:
            self._on_interval_change(str(new_value))
        elif widget == self.conf_scale:
            self._on_threshold_change(str(new_value))
        # elif widget == self.cooldown_scale:
        #     self._on_cooldown_change(str(new_value))
        
        # Announce new value (throttled)
        value_text = get_value() if get_value else f"{new_value:.2f}"
        # Don't announce every tiny change - only log it
        self.log(f"{name} adjusted to {value_text}")
    
    def _activate_focused(self):
        """Activate the focused control (button press)."""
        if not self.focusable_controls or self.focused_control_index < 0:
            return
        
        widget, name, control_type, _ = self.focusable_controls[self.focused_control_index]
        
        if control_type == "button" and isinstance(widget, tk.Button):
            widget.invoke()  # Simulate button click
            self._announce(f"{name} activated")
    
    def _announce(self, message):
        """Announce message via text-to-speech (non-blocking)."""
        self.log(f"[Navigation] {message}")
        
        if self.audio_enabled:
            try:
                # Use threading to prevent blocking
                def speak():
                    try:
                        if platform.system() == 'Darwin':  # macOS
                            subprocess.Popen(['say', message], 
                                           stdout=subprocess.DEVNULL, 
                                           stderr=subprocess.DEVNULL,
                                           start_new_session=True)
                        elif platform.system() == 'Linux':
                            subprocess.Popen(['espeak', message], 
                                           stdout=subprocess.DEVNULL, 
                                           stderr=subprocess.DEVNULL,
                                           start_new_session=True)
                    except:
                        pass
                
                threading.Thread(target=speak, daemon=True).start()
            except:
                pass
    
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
