import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyautogui
import keyboard
import json
import threading
import time
from typing import List, Optional, Dict, Any
import pystray
from PIL import Image, ImageDraw
import sys


class Target:
    """Represents a click target with position, delay, and visual indicator."""
    
    def __init__(self, parent, script, number: int, x: int = 100, y: int = 100, delay_ms: int = 500):
        self.parent = parent
        self.script = script
        self.number = number
        self.x = x
        self.y = y
        self.delay_ms = delay_ms
        self.window = None
        self.canvas = None
        self.is_editing = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        self._create_window()
    
    def _create_window(self):
        """Create the target window with circular icon and number."""
        # Create window - use root if available, otherwise create standalone
        if hasattr(self.parent, 'root') and self.parent.root:
            self.window = tk.Toplevel(self.parent.root)
        else:
            # Fallback: create with a hidden root if parent root doesn't exist
            if not hasattr(Target, '_hidden_root'):
                Target._hidden_root = tk.Tk()
                Target._hidden_root.withdraw()
            self.window = tk.Toplevel(Target._hidden_root)
        
        self.window.overrideredirect(True)  # Remove window decorations
        self.window.wm_attributes('-topmost', True)
        
        # Set window size
        size = 50
        self.window.geometry(f'{size}x{size}+{self.x-size//2}+{self.y-size//2}')
        
        # Create canvas for drawing
        self.canvas = tk.Canvas(self.window, width=size, height=size, bg='white', highlightthickness=0)
        self.canvas.pack()
        
        # Draw circle and number
        self._draw_target()
        
        # Bind mouse events for dragging
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        
        # Prevent window from being destroyed when parent closes
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Set initial state
        self.make_readonly()
    
    def _draw_target(self):
        """Draw the circular target with number."""
        self.canvas.delete('all')
        size = 50
        center = size // 2
        
        # Draw circle
        if self.is_editing:
            self.canvas.create_oval(5, 5, size-5, size-5, fill='red', outline='darkred', width=2)
        else:
            self.canvas.create_oval(5, 5, size-5, size-5, fill='gray', outline='darkgray', width=2)
        
        # Draw number
        self.canvas.create_text(center, center, text=str(self.number), 
                               font=('Arial', 16, 'bold'), fill='white')
    
    def _on_click(self, event):
        """Handle mouse click for dragging."""
        if self.is_editing:
            self.drag_start_x = event.x
            self.drag_start_y = event.y
    
    def _on_drag(self, event):
        """Handle mouse drag to move target."""
        if self.is_editing:
            # Calculate new position
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            
            # Get current window position
            x = self.window.winfo_x() + dx
            y = self.window.winfo_y() + dy
            
            # Update position
            self.x = x + 25  # Center of window
            self.y = y + 25
            
            # Move window
            self.window.geometry(f'50x50+{x}+{y}')
    
    def _on_release(self, event):
        """Handle mouse release."""
        pass
    
    def make_editable(self):
        """Make target editable and visible."""
        self.is_editing = True
        self.window.wm_attributes('-alpha', 1.0)  # Fully opaque
        self._draw_target()
    
    def make_readonly(self):
        """Make target read-only and semi-transparent."""
        self.is_editing = False
        self.window.wm_attributes('-alpha', 0.5)  # Semi-transparent
        # Note: Click-through requires platform-specific code, keeping visible but semi-transparent
        self._draw_target()
    
    def update_number(self, number: int):
        """Update the target number."""
        self.number = number
        self._draw_target()
    
    def get_position(self):
        """Get the click position (center of target)."""
        return self.x, self.y
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert target to dictionary for JSON serialization."""
        return {
            'x': self.x,
            'y': self.y,
            'delay_ms': self.delay_ms
        }
    
    def destroy(self):
        """Destroy the target window."""
        if self.window:
            self.window.destroy()
            self.window = None


class Script:
    """Represents a script with targets and keybind."""
    
    def __init__(self, parent, name: str = None):
        self.parent = parent
        self.name = name or f"Script {len(parent.scripts) + 1}"
        self.targets: List[Target] = []
        self.keybind: List[str] = []
        self.is_editing = False
        self.frame = None
        self.target_frame = None
    
    def add_target(self, x: int = None, y: int = None, delay_ms: int = 500) -> Target:
        """Add a new target to the script."""
        if x is None or y is None:
            # Default position in center of screen
            x, y = pyautogui.size()
            x //= 2
            y //= 2
        
        number = len(self.targets) + 1
        target = Target(self.parent, self, number, x, y, delay_ms)
        self.targets.append(target)
        
        # Make editable if script is in edit mode
        if self.is_editing:
            target.make_editable()
        else:
            target.make_readonly()
        
        self.parent._update_script_ui(self)
        return target
    
    def remove_target(self, target: Target):
        """Remove a target from the script."""
        if target in self.targets:
            self.targets.remove(target)
            target.destroy()
            self._renumber_targets()
            self.parent._update_script_ui(self)
    
    def _renumber_targets(self):
        """Renumber targets sequentially."""
        for i, target in enumerate(self.targets, 1):
            target.update_number(i)
    
    def set_editing(self, editing: bool):
        """Set edit mode for the script."""
        self.is_editing = editing
        for target in self.targets:
            if editing:
                target.make_editable()
            else:
                target.make_readonly()
    
    def duplicate(self) -> 'Script':
        """Create a duplicate of this script."""
        new_script = Script(self.parent, f"{self.name} (Copy)")
        for target in self.targets:
            x, y = target.get_position()
            new_script.add_target(x, y, target.delay_ms)
        return new_script
    
    def execute(self):
        """Execute the script by clicking all targets in order."""
        if not self.targets:
            return
        
        for target in self.targets:
            x, y = target.get_position()
            time.sleep(target.delay_ms / 1000.0)  # Convert ms to seconds
            pyautogui.click(x, y)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert script to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'keybind': self.keybind,
            'targets': [target.to_dict() for target in self.targets]
        }
    
    @classmethod
    def from_dict(cls, parent, data: Dict[str, Any]) -> 'Script':
        """Create script from dictionary."""
        script = cls(parent, data.get('name', 'Script'))
        script.keybind = data.get('keybind', [])
        for target_data in data.get('targets', []):
            script.add_target(
                target_data.get('x', 100),
                target_data.get('y', 100),
                target_data.get('delay_ms', 500)
            )
        return script


class AutoclickerApp:
    """Main application class."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Autoclicker")
        self.root.geometry("600x700")
        
        self.scripts: List[Script] = []
        self.current_editing_script: Optional[Script] = None
        self.is_running = False
        self.keybind_hooks = []
        
        # System tray
        self.tray_icon = None
        self.tray_thread = None
        
        self._create_ui()
        self._setup_system_tray()
        self._setup_window_close()
    
    def _create_ui(self):
        """Create the main UI."""
        # Top buttons
        top_frame = tk.Frame(self.root)
        top_frame.pack(pady=10, padx=10, fill='x')
        
        tk.Button(top_frame, text="Save Scripts", command=self._save_scripts).pack(side='left', padx=5)
        tk.Button(top_frame, text="Load Scripts", command=self._load_scripts).pack(side='left', padx=5)
        self.run_button = tk.Button(top_frame, text="Run", command=self._toggle_run, 
                                   bg='lightgreen', font=('Arial', 10, 'bold'))
        self.run_button.pack(side='left', padx=5)
        
        # Scripts container
        self.scripts_frame = tk.Frame(self.root)
        self.scripts_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Add script button
        add_script_frame = tk.Frame(self.root)
        add_script_frame.pack(pady=10)
        tk.Button(add_script_frame, text="+ Add Script", command=self._add_script,
                 font=('Arial', 10, 'bold')).pack()
        
        # Scrollable canvas for scripts
        self.canvas = tk.Canvas(self.scripts_frame, bg='white')
        scrollbar = ttk.Scrollbar(self.scripts_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _add_script(self):
        """Add a new script."""
        script = Script(self, None)
        self.scripts.append(script)
        self._update_scripts_ui()
    
    def _update_scripts_ui(self):
        """Update the entire scripts UI."""
        # Clear existing script frames
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Create UI for each script
        for script in self.scripts:
            self._create_script_ui(script)
    
    def _create_script_ui(self, script: Script):
        """Create UI for a single script."""
        # Main script frame
        script.frame = tk.Frame(self.scrollable_frame, relief='raised', borderwidth=2, padx=10, pady=10)
        script.frame.pack(fill='x', pady=5, padx=5)
        
        # Script header
        header_frame = tk.Frame(script.frame)
        header_frame.pack(fill='x', pady=5)
        
        tk.Label(header_frame, text=script.name, font=('Arial', 12, 'bold')).pack(side='left')
        
        # Buttons frame
        buttons_frame = tk.Frame(script.frame)
        buttons_frame.pack(fill='x', pady=5)
        
        # Edit/Finish button
        edit_text = "Finish editing" if script.is_editing else "Edit script"
        edit_btn = tk.Button(buttons_frame, text=edit_text, 
                           command=lambda s=script: self._toggle_edit_script(s))
        edit_btn.pack(side='left', padx=5)
        
        # Add target button
        tk.Button(buttons_frame, text="Add target", 
                 command=lambda s=script: self._add_target(s)).pack(side='left', padx=5)
        
        # Set keybind button
        keybind_text = f"Keybind: {self._format_keybind(script.keybind)}" if script.keybind else "Set keybind"
        keybind_btn = tk.Button(buttons_frame, text=keybind_text,
                               command=lambda s=script: self._set_keybind(s))
        keybind_btn.pack(side='left', padx=5)
        
        # Duplicate button
        tk.Button(buttons_frame, text="Duplicate", 
                 command=lambda s=script: self._duplicate_script(s)).pack(side='left', padx=5)
        
        # Targets list
        targets_label = tk.Label(script.frame, text="Targets:", font=('Arial', 10))
        targets_label.pack(anchor='w', pady=(10, 5))
        
        script.target_frame = tk.Frame(script.frame)
        script.target_frame.pack(fill='x', padx=20)
        
        self._update_script_ui(script)
    
    def _update_script_ui(self, script: Script):
        """Update the targets list for a script."""
        if not script.target_frame:
            return
        
        # Clear existing target entries
        for widget in script.target_frame.winfo_children():
            widget.destroy()
        
        # Create entry for each target
        for i, target in enumerate(script.targets):
            target_row = tk.Frame(script.target_frame)
            target_row.pack(fill='x', pady=2)
            
            tk.Label(target_row, text=f"{target.number}:", width=5).pack(side='left')
            
            # Delay input
            delay_var = tk.StringVar(value=str(target.delay_ms))
            delay_entry = tk.Entry(target_row, textvariable=delay_var, width=10)
            delay_entry.pack(side='left', padx=5)
            delay_entry.bind('<FocusOut>', lambda e, t=target, v=delay_var: self._update_target_delay(t, v))
            delay_entry.bind('<Return>', lambda e, t=target, v=delay_var: self._update_target_delay(t, v))
            
            tk.Label(target_row, text="ms").pack(side='left')
            
            # Delete button
            tk.Button(target_row, text="Delete", 
                     command=lambda t=target: self._delete_target(script, t)).pack(side='left', padx=5)
        
        # Update keybind button text
        if script.frame:
            for widget in script.frame.winfo_children():
                if isinstance(widget, tk.Frame):
                    for btn in widget.winfo_children():
                        if isinstance(btn, tk.Button) and "keybind" in btn.cget('text').lower():
                            keybind_text = f"Keybind: {self._format_keybind(script.keybind)}" if script.keybind else "Set keybind"
                            btn.config(text=keybind_text)
    
    def _update_target_delay(self, target: Target, var: tk.StringVar):
        """Update target delay from input."""
        try:
            delay = int(var.get())
            target.delay_ms = delay
        except ValueError:
            var.set(str(target.delay_ms))
    
    def _delete_target(self, script: Script, target: Target):
        """Delete a target from a script."""
        script.remove_target(target)
    
    def _toggle_edit_script(self, script: Script):
        """Toggle edit mode for a script."""
        if script.is_editing:
            # Finish editing
            script.set_editing(False)
            self.current_editing_script = None
        else:
            # Start editing - first stop editing any other script
            if self.current_editing_script:
                self.current_editing_script.set_editing(False)
            
            script.set_editing(True)
            self.current_editing_script = script
        
        self._update_scripts_ui()
        self._highlight_editing_script()
    
    def _highlight_editing_script(self):
        """Highlight the script that is being edited."""
        for script in self.scripts:
            if script.frame:
                if script.is_editing:
                    script.frame.config(bg='lightyellow', relief='solid', borderwidth=3)
                else:
                    script.frame.config(bg='SystemButtonFace', relief='raised', borderwidth=2)
    
    def _add_target(self, script: Script):
        """Add a target to a script."""
        script.add_target()
        self._update_script_ui(script)
    
    def _set_keybind(self, script: Script):
        """Set keybind for a script."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Keybind")
        dialog.geometry("450x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Enter key combination (e.g., 'ctrl+alt+p' or 'alt+p'):", 
                font=('Arial', 10)).pack(pady=15)
        
        entry_frame = tk.Frame(dialog)
        entry_frame.pack(pady=10)
        
        manual_entry = tk.Entry(entry_frame, width=35, font=('Arial', 11))
        manual_entry.pack(side='left', padx=5)
        if script.keybind:
            manual_entry.insert(0, '+'.join(script.keybind))
        
        captured_keys_list = []
        hook_ref = [None]
        
        def capture_keys():
            """Capture keys using keyboard library."""
            manual_entry.config(state='disabled')
            status_label.config(text="Press your key combination now... (Press ESC to finish)", fg='blue')
            dialog.update()
            captured_keys_list.clear()
            
            def on_press(event):
                if event.event_type == 'down':
                    key_name = event.name.lower()
                    # Map common key names
                    key_map = {
                        'left ctrl': 'ctrl', 'right ctrl': 'ctrl',
                        'left alt': 'alt', 'right alt': 'alt',
                        'left shift': 'shift', 'right shift': 'shift',
                        'left windows': 'windows', 'right windows': 'windows',
                        'left win': 'windows', 'right win': 'windows'
                    }
                    mapped_key = key_map.get(key_name, key_name)
                    
                    # Skip if already captured or if it's esc
                    if mapped_key == 'esc':
                        stop_capture()
                        return
                    
                    if mapped_key not in captured_keys_list:
                        captured_keys_list.append(mapped_key)
                        status_label.config(text=" + ".join([k.capitalize() for k in captured_keys_list]), fg='green')
            
            def stop_capture():
                if hook_ref[0] is not None:
                    keyboard.unhook(hook_ref[0])
                    hook_ref[0] = None
                manual_entry.config(state='normal')
                if captured_keys_list:
                    manual_entry.delete(0, tk.END)
                    manual_entry.insert(0, '+'.join(captured_keys_list))
                    status_label.config(text="Keys captured! Click OK to save.", fg='green')
                else:
                    status_label.config(text="No keys captured. Try again or enter manually.", fg='orange')
            
            # Hook keyboard events
            hook_ref[0] = keyboard.on_press(on_press)
            
            # Stop button
            def stop_capture_btn():
                stop_capture()
            
            stop_btn = tk.Button(entry_frame, text="Stop", command=stop_capture_btn)
            stop_btn.pack(side='left', padx=5)
            
            # Auto-stop after 15 seconds
            dialog.after(15000, stop_capture)
        
        status_label = tk.Label(dialog, text="", font=('Arial', 10))
        status_label.pack(pady=10)
        
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=15)
        
        tk.Button(button_frame, text="Capture Keys", command=capture_keys, width=15).pack(side='left', padx=5)
        
        def use_manual():
            text = manual_entry.get().strip().lower()
            if text:
                keys = [k.strip() for k in text.split('+')]
                script.keybind = keys
                self._update_scripts_ui()
                dialog.destroy()
            else:
                status_label.config(text="Please enter a key combination", fg='red')
        
        tk.Button(button_frame, text="OK", command=use_manual, width=15).pack(side='left', padx=5)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy, width=15).pack(side='left', padx=5)
        
        manual_entry.focus_set()
        manual_entry.bind('<Return>', lambda e: use_manual())
    
    def _format_keybind(self, keybind: List[str]) -> str:
        """Format keybind for display."""
        if not keybind:
            return "None"
        return " + ".join([k.capitalize() for k in keybind])
    
    def _duplicate_script(self, script: Script):
        """Duplicate a script."""
        new_script = script.duplicate()
        self.scripts.append(new_script)
        self._update_scripts_ui()
    
    def _toggle_run(self):
        """Toggle run mode."""
        self.is_running = not self.is_running
        
        if self.is_running:
            self.run_button.config(text="Stop", bg='lightcoral')
            self._register_keybinds()
        else:
            self.run_button.config(text="Run", bg='lightgreen')
            self._unregister_keybinds()
    
    def _register_keybinds(self):
        """Register all keybinds for active scripts."""
        self._unregister_keybinds()  # Clear existing
        
        for script in self.scripts:
            if script.keybind and len(script.keybind) > 0:
                # Create hotkey string - keyboard library uses + for combination
                # Normalize key names
                normalized = []
                for key in script.keybind:
                    key_lower = key.lower()
                    # Map common variations
                    if key_lower in ['ctrl', 'control']:
                        normalized.append('ctrl')
                    elif key_lower == 'alt':
                        normalized.append('alt')
                    elif key_lower == 'shift':
                        normalized.append('shift')
                    elif key_lower in ['windows', 'win', 'cmd']:
                        normalized.append('windows')
                    else:
                        # Keep the key as-is (e.g., 'p', 'f1', etc.)
                        normalized.append(key_lower)
                
                hotkey = '+'.join(normalized)
                try:
                    def make_handler(s):
                        return lambda: self._execute_script(s)
                    hook = keyboard.add_hotkey(hotkey, make_handler(script))
                    self.keybind_hooks.append((hotkey, hook))
                except Exception as e:
                    print(f"Error registering keybind for {script.name}: {e}")
                    # Try alternative format
                    try:
                        hotkey_alt = ' + '.join(normalized)  # Space-separated
                        hook = keyboard.add_hotkey(hotkey_alt, make_handler(script))
                        self.keybind_hooks.append((hotkey_alt, hook))
                    except:
                        pass
    
    def _unregister_keybinds(self):
        """Unregister all keybinds."""
        for hotkey, hook in self.keybind_hooks:
            try:
                keyboard.remove_hotkey(hook)
            except:
                pass
        self.keybind_hooks.clear()
    
    def _execute_script(self, script: Script):
        """Execute a script in a separate thread."""
        thread = threading.Thread(target=script.execute, daemon=True)
        thread.start()
    
    def _save_scripts(self):
        """Save scripts to JSON file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                data = {
                    'scripts': [script.to_dict() for script in self.scripts]
                }
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
                messagebox.showinfo("Success", "Scripts saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save scripts: {e}")
    
    def _load_scripts(self):
        """Load scripts from JSON file."""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                # Clear existing scripts and targets
                for script in self.scripts:
                    for target in script.targets:
                        target.destroy()
                
                self.scripts.clear()
                self.current_editing_script = None
                
                # Load new scripts
                for script_data in data.get('scripts', []):
                    script = Script.from_dict(self, script_data)
                    self.scripts.append(script)
                
                self._update_scripts_ui()
                messagebox.showinfo("Success", "Scripts loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load scripts: {e}")
    
    def _create_tray_icon(self):
        """Create system tray icon."""
        # Create a simple icon
        image = Image.new('RGB', (64, 64), color='gray')
        draw = ImageDraw.Draw(image)
        draw.ellipse([16, 16, 48, 48], fill='red')
        draw.text((28, 28), "AC", fill='white')
        
        menu = pystray.Menu(
            pystray.MenuItem("Show", self._show_window),
            pystray.MenuItem("Exit", self._exit_app)
        )
        
        self.tray_icon = pystray.Icon("Autoclicker", image, "Autoclicker", menu)
        self.tray_icon.run()
    
    def _setup_system_tray(self):
        """Setup system tray in a separate thread."""
        self.tray_thread = threading.Thread(target=self._create_tray_icon, daemon=True)
        self.tray_thread.start()
    
    def _show_window(self, icon=None, item=None):
        """Show the main window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def _hide_window(self):
        """Hide the main window to system tray."""
        self.root.withdraw()
    
    def _exit_app(self, icon=None, item=None):
        """Exit the application."""
        self._unregister_keybinds()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
        self.root.destroy()
        sys.exit()
    
    def _setup_window_close(self):
        """Setup window close event to minimize to tray."""
        def on_closing():
            self._hide_window()
        
        self.root.protocol("WM_DELETE_WINDOW", on_closing)
    
    def run(self):
        """Start the application."""
        self.root.mainloop()


if __name__ == "__main__":
    app = AutoclickerApp()
    app.run()

