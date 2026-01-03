import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pyautogui
import json
import threading
import queue
from pynput import keyboard
from pynput.keyboard import Key, Listener
import pystray
from PIL import Image, ImageDraw
import sys
import os

# Windows API for click-through functionality
try:
    import ctypes
    from ctypes import wintypes
    WINDOWS = True
    WS_EX_TRANSPARENT = 0x00000020
    GWL_EXSTYLE = -20
    
    # Try to use SetWindowLongPtrW (64-bit) or SetWindowLongW (32-bit)
    if hasattr(ctypes.windll.user32, 'SetWindowLongPtrW'):
        SetWindowLong = ctypes.windll.user32.SetWindowLongPtrW
        GetWindowLong = ctypes.windll.user32.GetWindowLongPtrW
    else:
        SetWindowLong = ctypes.windll.user32.SetWindowLongW
        GetWindowLong = ctypes.windll.user32.GetWindowLongW
except:
    WINDOWS = False


class TargetOverlay:
    def __init__(self, parent, target_number, x=100, y=100, delay_ms=500):
        self.parent = parent
        self.target_number = target_number
        self.x = x
        self.y = y
        self.delay_ms = delay_ms
        self.visible = True
        self.move_mode = True
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Create overlay window
        self.window = tk.Toplevel()
        self.window.overrideredirect(True)  # Remove window decorations
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.8)
        
        # Make window small with crosshair
        self.window.geometry(f"60x60+{x}+{y}")
        self.window.configure(bg='black')
        
        # Create canvas for crosshair
        self.canvas = tk.Canvas(self.window, width=60, height=60, bg='black', highlightthickness=0)
        self.canvas.pack()
        
        # Draw crosshair
        self.draw_crosshair()
        
        # Add number label
        self.number_label = tk.Label(
            self.window,
            text=str(target_number),
            bg='red',
            fg='white',
            font=('Arial', 12, 'bold'),
            width=2,
            height=1
        )
        self.number_label.place(x=2, y=2)
        
        # Bind events for dragging
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.number_label.bind('<Button-1>', self.on_click)
        self.number_label.bind('<B1-Motion>', self.on_drag)
        self.number_label.bind('<ButtonRelease-1>', self.on_release)
        
        # Update position tracking
        self.update_position()
    
    def draw_crosshair(self):
        """Draw crosshair in the center of the canvas"""
        self.canvas.delete("all")
        center_x, center_y = 30, 30
        # Horizontal line
        self.canvas.create_line(10, center_y, 50, center_y, fill='red', width=2)
        # Vertical line
        self.canvas.create_line(center_x, 10, center_x, 50, fill='red', width=2)
        # Circle in center
        self.canvas.create_oval(center_x-5, center_y-5, center_x+5, center_y+5, outline='red', width=2)
    
    def on_click(self, event):
        """Handle mouse click on overlay"""
        if self.move_mode and self.visible:
            self.dragging = True
            self.drag_start_x = event.x_root
            self.drag_start_y = event.y_root
    
    def on_drag(self, event):
        """Handle mouse drag"""
        if self.dragging and self.move_mode and self.visible:
            dx = event.x_root - self.drag_start_x
            dy = event.y_root - self.drag_start_y
            new_x = self.window.winfo_x() + dx
            new_y = self.window.winfo_y() + dy
            self.window.geometry(f"60x60+{new_x}+{new_y}")
            self.drag_start_x = event.x_root
            self.drag_start_y = event.y_root
            self.update_position()
    
    def on_release(self, event):
        """Handle mouse release"""
        self.dragging = False
        self.update_position()
    
    def update_position(self):
        """Update stored position from window geometry"""
        self.x = self.window.winfo_x() + 30  # Center of crosshair
        self.y = self.window.winfo_y() + 30
    
    def set_visible(self, visible):
        """Show or hide the overlay"""
        self.visible = visible
        if visible:
            self.window.deiconify()
        else:
            self.window.withdraw()
    
    def set_move_mode(self, move_mode):
        """Set move mode (True) or click-through mode (False)"""
        self.move_mode = move_mode
        if move_mode:
            self.window.attributes('-alpha', 0.8)
            self.window.attributes('-topmost', True)
            # Re-enable event handling for dragging
            self.canvas.bind('<Button-1>', self.on_click)
            self.canvas.bind('<B1-Motion>', self.on_drag)
            self.canvas.bind('<ButtonRelease-1>', self.on_release)
            self.number_label.bind('<Button-1>', self.on_click)
            self.number_label.bind('<B1-Motion>', self.on_drag)
            self.number_label.bind('<ButtonRelease-1>', self.on_release)
            # Remove click-through style on Windows
            if WINDOWS:
                try:
                    # Get window handle - tkinter's winfo_id() returns the window handle
                    hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())
                    if hwnd == 0:
                        hwnd = self.window.winfo_id()
                    ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)
                    ex_style &= ~WS_EX_TRANSPARENT
                    SetWindowLong(hwnd, GWL_EXSTYLE, ex_style)
                except:
                    pass
        else:
            # Click-through mode: make window more transparent
            self.window.attributes('-alpha', 0.3)
            self.window.attributes('-topmost', True)
            # Disable event handling - clicks pass through
            self.canvas.unbind('<Button-1>')
            self.canvas.unbind('<B1-Motion>')
            self.canvas.unbind('<ButtonRelease-1>')
            self.number_label.unbind('<Button-1>')
            self.number_label.unbind('<B1-Motion>')
            self.number_label.unbind('<ButtonRelease-1>')
            self.dragging = False
            # Enable click-through style on Windows
            if WINDOWS:
                try:
                    # Get window handle - tkinter's winfo_id() returns the window handle
                    hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())
                    if hwnd == 0:
                        hwnd = self.window.winfo_id()
                    ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)
                    ex_style |= WS_EX_TRANSPARENT
                    SetWindowLong(hwnd, GWL_EXSTYLE, ex_style)
                except:
                    pass
    
    def update_number(self, new_number):
        """Update the target number"""
        self.target_number = new_number
        self.number_label.config(text=str(new_number))
    
    def destroy(self):
        """Destroy the overlay window"""
        self.window.destroy()


class KeybindCapture:
    def __init__(self, callback):
        self.callback = callback
        self.pressed_keys = set()
        self.listener = None
        self.capturing = False
        self.first_release = True
    
    def start_capture(self):
        """Start capturing keybind"""
        self.pressed_keys = set()
        self.capturing = True
        self.first_release = True
        self.listener = Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
    
    def stop_capture(self):
        """Stop capturing keybind"""
        self.capturing = False
        if self.listener:
            self.listener.stop()
            self.listener = None
    
    def on_press(self, key):
        """Handle key press"""
        if not self.capturing:
            return
        
        try:
            # Handle special keys
            if key == Key.ctrl_l or key == Key.ctrl_r:
                self.pressed_keys.add('Ctrl')
            elif key == Key.alt_l or key == Key.alt_r:
                self.pressed_keys.add('Alt')
            elif key == Key.shift_l or key == Key.shift_r:
                self.pressed_keys.add('Shift')
            else:
                # Regular key
                try:
                    if hasattr(key, 'char') and key.char:
                        self.pressed_keys.add(key.char.upper())
                    else:
                        key_name = str(key).replace("'", "")
                        if key_name.startswith('Key.'):
                            key_name = key_name.replace('Key.', '')
                            if key_name not in ['ctrl_l', 'ctrl_r', 'alt_l', 'alt_r', 'shift_l', 'shift_r']:
                                self.pressed_keys.add(key_name)
                        else:
                            self.pressed_keys.add(key_name.upper())
                except:
                    key_name = str(key).replace("'", "")
                    if key_name.startswith('Key.'):
                        key_name = key_name.replace('Key.', '')
                        if key_name not in ['ctrl_l', 'ctrl_r', 'alt_l', 'alt_r', 'shift_l', 'shift_r']:
                            self.pressed_keys.add(key_name)
        except:
            pass
    
    def on_release(self, key):
        """Handle key release - finish capture"""
        if not self.capturing:
            return False
        
        # On first release of a non-modifier, finish capture
        if self.first_release:
            # Check if released key is a modifier
            is_modifier = (key == Key.ctrl_l or key == Key.ctrl_r or 
                          key == Key.alt_l or key == Key.alt_r or
                          key == Key.shift_l or key == Key.shift_r)
            
            if not is_modifier or len(self.pressed_keys) > 3:  # If we have modifiers + regular key
                import time
                time.sleep(0.05)  # Small delay to capture all keys
                
                if self.pressed_keys:
                    # Sort: modifiers first, then regular keys
                    modifiers = [k for k in self.pressed_keys if k in ['Ctrl', 'Alt', 'Shift']]
                    regular = [k for k in self.pressed_keys if k not in ['Ctrl', 'Alt', 'Shift']]
                    keybind_str = '+'.join(sorted(modifiers) + sorted(regular))
                    self.callback(keybind_str)
                
                self.stop_capture()
                return False  # Stop listener
        
        return True


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Autoclicker")
        self.root.geometry("600x700")
        
        self.targets = []
        self.keybinds = {
            "activate": None,
            "toggle_visibility": None,
            "toggle_mode": None
        }
        self.keybind_listeners = {}
        self.script_running = False
        self.targets_visible = True
        self.targets_move_mode = True
        
        # Queue for thread communication
        self.event_queue = queue.Queue()
        
        # Keybind capture
        self.current_capture = None
        self.capture_callback = None
        
        # System tray
        self.tray_icon = None
        self.tray_thread = None
        
        self.setup_ui()
        self.setup_system_tray()
        self.check_queue()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons frame
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        # Add Target button
        ttk.Button(control_frame, text="Add Target", command=self.add_target).pack(side=tk.LEFT, padx=5)
        
        # Keybind buttons frame
        keybind_frame = ttk.LabelFrame(main_frame, text="Keybinds", padding="10")
        keybind_frame.pack(fill=tk.X, pady=5)
        
        # Script activation keybind
        activate_frame = ttk.Frame(keybind_frame)
        activate_frame.pack(fill=tk.X, pady=2)
        ttk.Button(activate_frame, text="Set Keybind (Activate)", command=lambda: self.set_keybind("activate")).pack(side=tk.LEFT, padx=5)
        self.activate_keybind_label = ttk.Label(activate_frame, text="Not set")
        self.activate_keybind_label.pack(side=tk.LEFT, padx=5)
        
        # Visibility toggle keybind
        visibility_frame = ttk.Frame(keybind_frame)
        visibility_frame.pack(fill=tk.X, pady=2)
        ttk.Button(visibility_frame, text="Set Visibility Toggle", command=lambda: self.set_keybind("toggle_visibility")).pack(side=tk.LEFT, padx=5)
        self.visibility_keybind_label = ttk.Label(visibility_frame, text="Not set")
        self.visibility_keybind_label.pack(side=tk.LEFT, padx=5)
        
        # Move/Click-through toggle keybind
        mode_frame = ttk.Frame(keybind_frame)
        mode_frame.pack(fill=tk.X, pady=2)
        ttk.Button(mode_frame, text="Set Mode Toggle", command=lambda: self.set_keybind("toggle_mode")).pack(side=tk.LEFT, padx=5)
        self.mode_keybind_label = ttk.Label(mode_frame, text="Not set")
        self.mode_keybind_label.pack(side=tk.LEFT, padx=5)
        
        # Save/Load buttons
        file_frame = ttk.LabelFrame(main_frame, text="File Operations", padding="10")
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(file_frame, text="Save Script", command=self.save_script).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Load Script", command=self.load_script).pack(side=tk.LEFT, padx=5)
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack()
        
        # Targets list frame
        targets_frame = ttk.LabelFrame(main_frame, text="Targets", padding="10")
        targets_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollable frame for targets
        canvas = tk.Canvas(targets_frame)
        scrollbar = ttk.Scrollbar(targets_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.targets_container = self.scrollable_frame
    
    def add_target(self):
        """Add a new target overlay"""
        # Get current mouse position
        x, y = pyautogui.position()
        target_number = len(self.targets) + 1
        delay_ms = 500
        
        target = TargetOverlay(self.root, target_number, x-30, y-30, delay_ms)
        self.targets.append(target)
        
        self.update_targets_list()
        self.update_target_visibility()
        self.update_target_move_mode()
    
    def update_targets_list(self):
        """Update the targets list in the UI"""
        # Clear existing widgets
        for widget in self.targets_container.winfo_children():
            widget.destroy()
        
        # Create widgets for each target
        for i, target in enumerate(self.targets):
            target_frame = ttk.Frame(self.targets_container)
            target_frame.pack(fill=tk.X, pady=2)
            
            # Target number and position
            info_label = ttk.Label(target_frame, text=f"Target {target.target_number}: ({target.x}, {target.y})")
            info_label.pack(side=tk.LEFT, padx=5)
            
            # Delay input
            delay_label = ttk.Label(target_frame, text="Delay (ms):")
            delay_label.pack(side=tk.LEFT, padx=5)
            
            delay_var = tk.StringVar(value=str(target.delay_ms))
            delay_entry = ttk.Entry(target_frame, textvariable=delay_var, width=10)
            delay_entry.pack(side=tk.LEFT, padx=5)
            
            def update_delay(t=target, v=delay_var):
                try:
                    t.delay_ms = int(v.get())
                except ValueError:
                    pass
            
            delay_var.trace('w', lambda *args, t=target, v=delay_var: update_delay(t, v))
            
            # Delete button
            ttk.Button(target_frame, text="Delete", command=lambda idx=i: self.delete_target(idx)).pack(side=tk.LEFT, padx=5)
    
    def delete_target(self, index):
        """Delete a target"""
        if 0 <= index < len(self.targets):
            self.targets[index].destroy()
            self.targets.pop(index)
            self.renumber_targets()
            self.update_targets_list()
    
    def renumber_targets(self):
        """Renumber all targets starting from 1"""
        for i, target in enumerate(self.targets):
            target.update_number(i + 1)
    
    def set_keybind(self, keybind_type):
        """Set a keybind for the specified action"""
        self.status_label.config(text=f"Press keys for {keybind_type}...")
        self.root.update()
        
        # Stop any existing capture
        if self.current_capture:
            self.current_capture.stop_capture()
        
        # Stop existing listener for this keybind type
        if keybind_type in self.keybind_listeners:
            self.keybind_listeners[keybind_type].stop()
            del self.keybind_listeners[keybind_type]
        
        def on_capture(keybind_str):
            self.keybinds[keybind_type] = keybind_str
            self.update_keybind_labels()
            self.status_label.config(text="Keybind set!")
            self.setup_keybind_listener(keybind_type, keybind_str)
        
        self.capture_callback = on_capture
        self.current_capture = KeybindCapture(on_capture)
        self.current_capture.start_capture()
    
    def update_keybind_labels(self):
        """Update keybind display labels"""
        self.activate_keybind_label.config(text=self.keybinds["activate"] or "Not set")
        self.visibility_keybind_label.config(text=self.keybinds["toggle_visibility"] or "Not set")
        self.mode_keybind_label.config(text=self.keybinds["toggle_mode"] or "Not set")
    
    def setup_keybind_listener(self, keybind_type, keybind_str):
        """Setup global keybind listener"""
        if not keybind_str:
            return
        
        # Parse keybind string
        keys = [k.strip() for k in keybind_str.split('+')]
        required_modifiers = set()
        required_keys = []
        
        for key in keys:
            if key in ['Ctrl', 'Alt', 'Shift']:
                required_modifiers.add(key)
            else:
                required_keys.append(key)
        
        # Create listener in separate thread
        def listen_thread():
            try:
                pressed_modifiers = set()
                pressed_keys = set()
                last_trigger_time = 0
                
                def on_press(key):
                    nonlocal last_trigger_time
                    try:
                        # Track modifiers
                        if key == Key.ctrl_l or key == Key.ctrl_r:
                            pressed_modifiers.add('Ctrl')
                        elif key == Key.alt_l or key == Key.alt_r:
                            pressed_modifiers.add('Alt')
                        elif key == Key.shift_l or key == Key.shift_r:
                            pressed_modifiers.add('Shift')
                        else:
                            # Track regular keys
                            if hasattr(key, 'char') and key.char:
                                pressed_keys.add(key.char.upper())
                            else:
                                key_name = str(key).replace("'", "")
                                if key_name.startswith('Key.'):
                                    key_name = key_name.replace('Key.', '')
                                    if key_name not in ['ctrl_l', 'ctrl_r', 'alt_l', 'alt_r', 'shift_l', 'shift_r']:
                                        pressed_keys.add(key_name)
                                else:
                                    pressed_keys.add(key_name.upper())
                        
                        # Check if all required keys are pressed
                        if (required_modifiers.issubset(pressed_modifiers) and 
                            all(k in pressed_keys for k in required_keys)):
                            import time
                            current_time = time.time()
                            # Prevent rapid repeated triggers
                            if current_time - last_trigger_time > 0.3:
                                last_trigger_time = current_time
                                self.event_queue.put(('keybind', keybind_type))
                    except Exception as e:
                        pass
                
                def on_release(key):
                    try:
                        # Remove from pressed sets
                        if key == Key.ctrl_l or key == Key.ctrl_r:
                            pressed_modifiers.discard('Ctrl')
                        elif key == Key.alt_l or key == Key.alt_r:
                            pressed_modifiers.discard('Alt')
                        elif key == Key.shift_l or key == Key.shift_r:
                            pressed_modifiers.discard('Shift')
                        else:
                            if hasattr(key, 'char') and key.char:
                                pressed_keys.discard(key.char.upper())
                            else:
                                key_name = str(key).replace("'", "")
                                if key_name.startswith('Key.'):
                                    key_name = key_name.replace('Key.', '')
                                    if key_name not in ['ctrl_l', 'ctrl_r', 'alt_l', 'alt_r', 'shift_l', 'shift_r']:
                                        pressed_keys.discard(key_name)
                                else:
                                    pressed_keys.discard(key_name.upper())
                    except:
                        pass
                
                listener = keyboard.Listener(on_press=on_press, on_release=on_release)
                listener.start()
                self.keybind_listeners[keybind_type] = listener
            except Exception as e:
                print(f"Error setting up keybind listener: {e}")
        
        thread = threading.Thread(target=listen_thread, daemon=True)
        thread.start()
    
    def check_queue(self):
        """Check for events from threads"""
        try:
            while True:
                event_type, data = self.event_queue.get_nowait()
                if event_type == 'keybind':
                    self.handle_keybind(data)
                elif event_type == 'script_done':
                    self.script_running = False
                    self.status_label.config(text="Script completed!")
                elif event_type == 'script_error':
                    self.script_running = False
                    self.status_label.config(text=f"Script error: {data}")
        except queue.Empty:
            pass
        
        self.root.after(100, self.check_queue)
    
    def handle_keybind(self, keybind_type):
        """Handle keybind activation"""
        if keybind_type == "activate":
            if self.script_running:
                self.stop_script()
            else:
                self.start_script()
        elif keybind_type == "toggle_visibility":
            self.toggle_targets_visibility()
        elif keybind_type == "toggle_mode":
            if self.targets_visible:
                self.toggle_targets_move_mode()
    
    def start_script(self):
        """Start the clicking script"""
        if not self.targets:
            self.status_label.config(text="No targets to click!")
            return
        
        if self.script_running:
            return
        
        self.script_running = True
        self.status_label.config(text="Script running...")
        
        def run_script():
            try:
                for target in self.targets:
                    if not self.script_running:
                        break
                    
                    # Wait for delay
                    import time
                    time.sleep(target.delay_ms / 1000.0)
                    
                    if not self.script_running:
                        break
                    
                    # Click at target position
                    pyautogui.click(target.x, target.y)
                
                self.event_queue.put(('script_done', None))
            except Exception as e:
                self.event_queue.put(('script_error', str(e)))
        
        thread = threading.Thread(target=run_script, daemon=True)
        thread.start()
    
    def stop_script(self):
        """Stop the clicking script"""
        self.script_running = False
        self.status_label.config(text="Script stopped")
    
    def toggle_targets_visibility(self):
        """Toggle targets visibility"""
        self.targets_visible = not self.targets_visible
        self.update_target_visibility()
        status = "visible" if self.targets_visible else "hidden"
        self.status_label.config(text=f"Targets {status}")
    
    def update_target_visibility(self):
        """Update visibility of all targets"""
        for target in self.targets:
            target.set_visible(self.targets_visible)
    
    def toggle_targets_move_mode(self):
        """Toggle between move mode and click-through mode"""
        self.targets_move_mode = not self.targets_move_mode
        self.update_target_move_mode()
        mode = "move mode" if self.targets_move_mode else "click-through mode"
        self.status_label.config(text=f"Targets: {mode}")
    
    def update_target_move_mode(self):
        """Update move mode of all targets"""
        for target in self.targets:
            target.set_move_mode(self.targets_move_mode)
    
    def save_script(self):
        """Save script to JSON file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            data = {
                "targets": [
                    {
                        "number": target.target_number,
                        "x": target.x,
                        "y": target.y,
                        "delay_ms": target.delay_ms
                    }
                    for target in self.targets
                ],
                "keybinds": self.keybinds
            }
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.status_label.config(text="Script saved!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save script: {e}")
    
    def load_script(self):
        """Load script from JSON file"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # Clear existing targets
            for target in self.targets:
                target.destroy()
            self.targets = []
            
            # Load targets
            for target_data in data.get("targets", []):
                target = TargetOverlay(
                    self.root,
                    target_data["number"],
                    target_data["x"] - 30,
                    target_data["y"] - 30,
                    target_data.get("delay_ms", 500)
                )
                self.targets.append(target)
            
            # Load keybinds
            self.keybinds = data.get("keybinds", {
                "activate": None,
                "toggle_visibility": None,
                "toggle_mode": None
            })
            
            # Stop existing listeners
            for listener in self.keybind_listeners.values():
                listener.stop()
            self.keybind_listeners = {}
            
            # Setup new listeners
            for keybind_type, keybind_str in self.keybinds.items():
                if keybind_str:
                    self.setup_keybind_listener(keybind_type, keybind_str)
            
            self.update_targets_list()
            self.update_keybind_labels()
            self.update_target_visibility()
            self.update_target_move_mode()
            
            self.status_label.config(text="Script loaded!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load script: {e}")
    
    def setup_system_tray(self):
        """Setup system tray icon"""
        # Create a simple icon
        image = Image.new('RGB', (64, 64), color='red')
        draw = ImageDraw.Draw(image)
        draw.ellipse([16, 16, 48, 48], fill='white')
        
        menu = pystray.Menu(
            pystray.MenuItem("Show Window", self.show_window),
            pystray.MenuItem("Exit", self.quit_app)
        )
        
        self.tray_icon = pystray.Icon("Autoclicker", image, "Autoclicker", menu)
        
        def run_tray():
            self.tray_icon.run()
        
        self.tray_thread = threading.Thread(target=run_tray, daemon=True)
        self.tray_thread.start()
    
    def show_window(self, icon=None, item=None):
        """Show the main window"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def quit_app(self, icon=None, item=None):
        """Quit the application"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
        sys.exit()
    
    def on_closing(self):
        """Handle window closing - minimize to tray"""
        self.root.withdraw()
    
    def run(self):
        """Start the application"""
        self.root.mainloop()


if __name__ == "__main__":
    app = MainWindow()
    app.run()

