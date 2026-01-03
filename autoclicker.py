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
        # Show the window and make it fully visible
        self.window.deiconify()
        self.window.wm_attributes('-alpha', 1.0)  # Fully opaque
        self._draw_target()
    
    def make_readonly(self):
        """Make target read-only and completely invisible (click-through)."""
        self.is_editing = False
        # Make completely invisible (0 opacity) and click-through
        self.window.wm_attributes('-alpha', 0.0)  # Completely transparent
        # Hide the window to make it truly click-through
        self.window.withdraw()
    
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
        self.return_mouse = False
        self.return_delay_ms = 500
    
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
        new_script.return_mouse = self.return_mouse
        new_script.return_delay_ms = self.return_delay_ms
        for target in self.targets:
            x, y = target.get_position()
            new_script.add_target(x, y, target.delay_ms)
        return new_script
    
    def execute(self):
        """Execute the script by clicking all targets in order."""
        if not self.targets:
            return
        
        # Save starting mouse position if return is enabled
        start_x, start_y = None, None
        if self.return_mouse:
            start_x, start_y = pyautogui.position()
        
        # Click all targets
        for target in self.targets:
            x, y = target.get_position()
            time.sleep(target.delay_ms / 1000.0)  # Convert ms to seconds
            pyautogui.click(x, y)
        
        # Return mouse to starting position if enabled
        if self.return_mouse and start_x is not None and start_y is not None:
            time.sleep(self.return_delay_ms / 1000.0)  # Wait before returning
            pyautogui.moveTo(start_x, start_y)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert script to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'keybind': self.keybind,
            'targets': [target.to_dict() for target in self.targets],
            'return_mouse': self.return_mouse,
            'return_delay_ms': self.return_delay_ms
        }
    
    @classmethod
    def from_dict(cls, parent, data: Dict[str, Any]) -> 'Script':
        """Create script from dictionary."""
        script = cls(parent, data.get('name', 'Script'))
        script.keybind = data.get('keybind', [])
        script.return_mouse = data.get('return_mouse', False)
        script.return_delay_ms = data.get('return_delay_ms', 500)
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
        self.root.geometry("800x700")
        
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
        
        def update_scrollregion(event=None):
            """Update the scroll region when content changes."""
            self.canvas.update_idletasks()
            bbox = self.canvas.bbox("all")
            if bbox:
                self.canvas.configure(scrollregion=bbox)
        
        self.scrollable_frame.bind("<Configure>", update_scrollregion)
        
        # Bind mouse wheel to canvas
        def on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        self.canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Update canvas window width when canvas resizes
        def configure_canvas_window(event):
            canvas_width = event.width
            self.canvas.itemconfig(self.canvas_window_id, width=canvas_width)
        
        self.canvas.bind('<Configure>', configure_canvas_window)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Store canvas window ID for later updates
        self.canvas_window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
    
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
        
        # Update scroll region after UI is updated
        self.root.after_idle(self._update_scroll_region)
    
    def _update_scroll_region(self):
        """Update the scroll region of the canvas."""
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)
    
    def _create_script_ui(self, script: Script):
        """Create UI for a single script."""
        # Main script frame
        script.frame = tk.Frame(self.scrollable_frame, relief='raised', borderwidth=2, padx=10, pady=10)
        script.frame.pack(fill='x', pady=5, padx=5)
        
        # Script header
        header_frame = tk.Frame(script.frame)
        header_frame.pack(fill='x', pady=5)
        
        tk.Label(header_frame, text="Name:", font=('Arial', 10)).pack(side='left', padx=(0, 5))
        
        # Editable name entry
        script.name_var = tk.StringVar(value=script.name)
        name_entry = tk.Entry(header_frame, textvariable=script.name_var, font=('Arial', 12, 'bold'), width=20)
        name_entry.pack(side='left', padx=5)
        name_entry.bind('<FocusOut>', lambda e, s=script: self._update_script_name(s))
        name_entry.bind('<Return>', lambda e, s=script: self._update_script_name(s))
        
        # Save button for script name
        save_name_btn = tk.Button(header_frame, text="Save Name", command=lambda s=script: self._update_script_name(s), 
                                 width=12, font=('Arial', 9))
        save_name_btn.pack(side='left', padx=5)
        
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
        
        # Delete script button
        tk.Button(buttons_frame, text="Delete Script", 
                 command=lambda s=script: self._delete_script(s),
                 bg='lightcoral', fg='white').pack(side='left', padx=5)
        
        # Return checkbox
        return_check_frame = tk.Frame(script.frame)
        return_check_frame.pack(fill='x', pady=5)
        
        script.return_var = tk.BooleanVar(value=script.return_mouse)
        return_checkbox = tk.Checkbutton(return_check_frame, text="Return", 
                                        variable=script.return_var,
                                        command=lambda s=script: self._toggle_return(s))
        return_checkbox.pack(side='left', padx=5)
        
        # Targets list
        targets_label = tk.Label(script.frame, text="Targets:", font=('Arial', 10))
        targets_label.pack(anchor='w', pady=(10, 5))
        
        script.target_frame = tk.Frame(script.frame)
        script.target_frame.pack(fill='x', padx=20)
        
        self._update_script_ui(script)
    
    def _save_delay_values(self, script: Script):
        """Save delay values from Entry fields before UI update."""
        if not script.target_frame:
            return
        
        # Find all Entry widgets and save their values
        for widget in script.target_frame.winfo_children():
            if isinstance(widget, tk.Frame):
                # Look for Entry widgets in this row
                for child in widget.winfo_children():
                    if isinstance(child, tk.Entry):
                        try:
                            # Get the value from the Entry
                            entry_value = child.get()
                            # Get target reference stored in Entry widget
                            if hasattr(child, '_target_ref'):
                                target = child._target_ref
                                try:
                                    delay = int(entry_value)
                                    target.delay_ms = delay
                                except ValueError:
                                    pass
                            # Check if this is the return delay entry
                            elif hasattr(child, '_return_delay_ref'):
                                try:
                                    delay = int(entry_value)
                                    script.return_delay_ms = delay
                                except ValueError:
                                    pass
                        except:
                            pass
    
    def _update_script_ui(self, script: Script):
        """Update the targets list for a script."""
        if not script.target_frame:
            return
        
        # Save delay values from existing Entry fields before destroying them
        self._save_delay_values(script)
        
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
            # Store target reference in Entry widget for easy access
            delay_entry._target_ref = target
            delay_entry.pack(side='left', padx=5)
            delay_entry.bind('<FocusOut>', lambda e, t=target, v=delay_var: self._update_target_delay(t, v))
            delay_entry.bind('<Return>', lambda e, t=target, v=delay_var: self._update_target_delay(t, v))
            
            tk.Label(target_row, text="ms").pack(side='left')
            
            # Delete button
            tk.Button(target_row, text="Delete", 
                     command=lambda t=target: self._delete_target(script, t)).pack(side='left', padx=5)
        
        # Return delay field (only visible when return is enabled)
        if script.return_var.get():
            return_delay_frame = tk.Frame(script.target_frame)
            return_delay_frame.pack(fill='x', pady=5)
            
            tk.Label(return_delay_frame, text="Return delay:", font=('Arial', 10)).pack(side='left', padx=5)
            
            return_delay_var = tk.StringVar(value=str(script.return_delay_ms))
            return_delay_entry = tk.Entry(return_delay_frame, textvariable=return_delay_var, width=10)
            # Mark this as return delay entry for saving
            return_delay_entry._return_delay_ref = True
            return_delay_entry.pack(side='left', padx=5)
            return_delay_entry.bind('<FocusOut>', lambda e, s=script, v=return_delay_var: self._update_return_delay(s, v))
            return_delay_entry.bind('<Return>', lambda e, s=script, v=return_delay_var: self._update_return_delay(s, v))
            
            tk.Label(return_delay_frame, text="ms", font=('Arial', 10)).pack(side='left', padx=5)
        
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
    
    def _update_script_name(self, script: Script):
        """Update script name from input."""
        new_name = script.name_var.get().strip()
        if new_name:
            script.name = new_name
        else:
            # If empty, restore old name
            script.name_var.set(script.name)
    
    def _toggle_return(self, script: Script):
        """Toggle return mouse checkbox."""
        script.return_mouse = script.return_var.get()
        # Update UI to show/hide return delay field
        self._update_script_ui(script)
    
    def _update_return_delay(self, script: Script, var: tk.StringVar):
        """Update return delay from input."""
        try:
            delay = int(var.get())
            script.return_delay_ms = delay
        except ValueError:
            var.set(str(script.return_delay_ms))
    
    def _delete_target(self, script: Script, target: Target):
        """Delete a target from a script."""
        script.remove_target(target)
        self.root.after_idle(self._update_scroll_region)
    
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
        self.root.after_idle(self._update_scroll_region)
    
    def _set_keybind(self, script: Script):
        """Set keybind for a script."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Keybind")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Use a label with wraplength to ensure text fits
        instruction_label = tk.Label(dialog, 
                                    text="Press your key combination now", 
                                    font=('Arial', 10), 
                                    wraplength=450,
                                    justify='center')
        instruction_label.pack(pady=20)
        
        captured_keys_list = []
        hook_ref = [None]
        
        # Display current keybind if exists
        current_keybind_label = tk.Label(dialog, text="", font=('Arial', 9), fg='gray')
        current_keybind_label.pack(pady=5)
        if script.keybind:
            current_keybind_label.config(text=f"Current: {self._format_keybind(script.keybind)}")
        
        # Display captured keys
        status_label = tk.Label(dialog, text="Waiting for keypress...", font=('Arial', 12, 'bold'), fg='blue')
        status_label.pack(pady=15)
        
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
                
                # Skip if already captured
                if mapped_key not in captured_keys_list:
                    captured_keys_list.append(mapped_key)
                    # Schedule UI update in main thread
                    def update_ui():
                        try:
                            if status_label.winfo_exists():
                                status_label.config(text=" + ".join([k.capitalize() for k in captured_keys_list]), fg='green')
                        except:
                            pass
                    try:
                        dialog.after(0, update_ui)
                    except:
                        pass
        
        def cleanup():
            """Clean up keyboard hook."""
            try:
                if hook_ref[0] is not None:
                    keyboard.unhook(hook_ref[0])
                    hook_ref[0] = None
            except:
                pass
        
        def on_ok():
            """Handle OK button click."""
            cleanup()
            if captured_keys_list:
                script.keybind = captured_keys_list.copy()
                self._update_scripts_ui()
                dialog.destroy()
            else:
                status_label.config(text="No keys captured. Please press keys.", fg='orange')
        
        def on_cancel():
            """Handle Cancel button click."""
            cleanup()
            dialog.destroy()
        
        # Start capturing immediately
        hook_ref[0] = keyboard.on_press(on_press)
        
        # Clean up on window close
        def on_closing():
            cleanup()
            dialog.destroy()
        
        dialog.protocol("WM_DELETE_WINDOW", on_closing)
        
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)
        
        tk.Button(button_frame, text="OK", command=on_ok, width=15).pack(side='left', padx=5)
        tk.Button(button_frame, text="Cancel", command=on_cancel, width=15).pack(side='left', padx=5)
    
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
    
    def _delete_script(self, script: Script):
        """Delete a script."""
        # Ask for confirmation
        result = messagebox.askyesno("Delete Script", 
                                    f"Are you sure you want to delete '{script.name}'?\n\nThis will remove all targets and cannot be undone.",
                                    icon='warning')
        if result:
            # Destroy all target windows
            for target in script.targets:
                target.destroy()
            
            # Remove from scripts list
            if script in self.scripts:
                self.scripts.remove(script)
            
            # Clear editing reference if this was the editing script
            if self.current_editing_script == script:
                self.current_editing_script = None
            
            # Update UI
            self._update_scripts_ui()
            self.root.after_idle(self._update_scroll_region)
    
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

