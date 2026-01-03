import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import pyautogui
import json
import threading
import time
import keyboard
from typing import List, Dict, Optional, Tuple
import sys
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

class TargetWindow:
    def __init__(self, target_id: int, x: int = None, y: int = None):
        self.target_id = target_id
        self.window = tk.Toplevel()
        self.window.overrideredirect(True)  # Remove window decorations
        self.window.attributes('-topmost', True)  # Always on top
        self.window.attributes('-alpha', 0.7)  # Semi-transparent
        self.window.configure(bg='red')
        
        # Set size
        self.window.geometry('30x30')
        
        # Set position
        if x is None or y is None:
            # Center on screen
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            x = screen_width // 2 + (target_id - 1) * 50
            y = screen_height // 2
        self.window.geometry(f'30x30+{x}+{y}')
        
        # Create label with cross and number
        self.label = tk.Label(
            self.window,
            text=f'✕\n{target_id}',
            bg='red',
            fg='white',
            font=('Arial', 8, 'bold'),
            justify=tk.CENTER
        )
        self.label.pack(fill=tk.BOTH, expand=True)
        
        # Make window click-through when not editing
        self.set_click_through(True)
        
        # Drag functionality
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        
        self.label.bind('<Button-1>', self.start_drag)
        self.label.bind('<B1-Motion>', self.on_drag)
        self.label.bind('<ButtonRelease-1>', self.stop_drag)
        
    def set_click_through(self, value: bool):
        """Set window click-through attribute"""
        try:
            if value:
                # Make more transparent and keep on top
                self.window.attributes('-alpha', 0.01)
            else:
                # Make visible and draggable
                self.window.attributes('-alpha', 0.7)
                self.window.attributes('-topmost', True)
        except:
            pass
    
    def start_drag(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_dragging = True
    
    def on_drag(self, event):
        if self.is_dragging:
            x = self.window.winfo_x() + event.x - self.drag_start_x
            y = self.window.winfo_y() + event.y - self.drag_start_y
            self.window.geometry(f'30x30+{x}+{y}')
    
    def stop_drag(self, event):
        self.is_dragging = False
    
    def get_position(self) -> Tuple[int, int]:
        """Get current position of the target"""
        return (self.window.winfo_x(), self.window.winfo_y())
    
    def destroy(self):
        try:
            self.window.destroy()
        except:
            pass
    
    def show(self):
        try:
            self.window.deiconify()
            self.window.lift()
        except:
            pass
    
    def hide(self):
        try:
            self.window.withdraw()
        except:
            pass

class Script:
    def __init__(self, name: str):
        self.name = name
        self.targets: List[Dict] = []  # List of {x, y, delay, id}
        self.keybind: Optional[str] = None
        self.keybind_hotkey: Optional[str] = None  # Format for keyboard library
        self.target_windows: List[TargetWindow] = []
        self.is_editing = False
    
    def add_target(self, x: int = None, y: int = None, delay: int = 0):
        """Add a new target to the script"""
        target_id = len(self.targets) + 1
        if x is None or y is None:
            screen_width = tk.Tk().winfo_screenwidth()
            screen_height = tk.Tk().winfo_screenheight()
            x = screen_width // 2 + (target_id - 1) * 50
            y = screen_height // 2
        
        target = {
            'id': target_id,
            'x': x,
            'y': y,
            'delay': delay
        }
        self.targets.append(target)
        return target_id
    
    def to_dict(self) -> Dict:
        """Convert script to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'targets': self.targets,
            'keybind': self.keybind
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Script':
        """Create script from dictionary"""
        script = cls(data['name'])
        script.targets = data.get('targets', [])
        script.keybind = data.get('keybind')
        return script

class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoClicker")
        self.root.geometry("900x700")
        
        self.scripts: List[Script] = []
        self.currently_editing: Optional[Script] = None
        self.is_running = False
        self.keyboard_hooks = {}  # Store keyboard hook IDs
        self.selected_script_index = None
        self.tray_icon = None
        self.tray_thread = None
        
        # Create UI
        self.create_ui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind('<Unmap>', self.on_minimize)
        
        # Bind selection change
        self.scripts_listbox.bind('<<ListboxSelect>>', self.on_script_select)
        
        # Create system tray icon
        if HAS_PYSTRAY:
            self.create_tray_icon()
        
    def create_ui(self):
        # Main container
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - Scripts list
        left_panel = tk.Frame(main_frame, width=200)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        tk.Label(left_panel, text="Scripts", font=('Arial', 14, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        # Scripts listbox with scrollbar
        list_frame = tk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.scripts_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.scripts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.scripts_listbox.yview)
        
        # Buttons frame
        buttons_frame = tk.Frame(left_panel)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        self.add_script_btn = tk.Button(buttons_frame, text="Add Script", command=self.add_script)
        self.add_script_btn.pack(fill=tk.X, pady=2)
        
        self.save_scripts_btn = tk.Button(buttons_frame, text="Save Scripts", command=self.save_scripts)
        self.save_scripts_btn.pack(fill=tk.X, pady=2)
        
        self.load_scripts_btn = tk.Button(buttons_frame, text="Load Scripts", command=self.load_scripts)
        self.load_scripts_btn.pack(fill=tk.X, pady=2)
        
        self.run_btn = tk.Button(buttons_frame, text="Run", command=self.toggle_run, bg='green', fg='white', font=('Arial', 10, 'bold'))
        self.run_btn.pack(fill=tk.X, pady=5)
        
        # Right panel - Script details
        right_panel = tk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.details_frame = tk.Frame(right_panel)
        self.details_frame.pack(fill=tk.BOTH, expand=True)
        
        self.current_script_frame = None
        self.update_details_view()
    
    def on_script_select(self, event):
        """Handle script selection"""
        selection = self.scripts_listbox.curselection()
        if selection:
            self.selected_script_index = selection[0]
            self.update_details_view()
    
    def update_details_view(self):
        """Update the details view based on selected script"""
        # Clear current details
        if self.current_script_frame:
            self.current_script_frame.destroy()
        
        self.current_script_frame = tk.Frame(self.details_frame)
        self.current_script_frame.pack(fill=tk.BOTH, expand=True)
        
        if self.selected_script_index is None or self.selected_script_index >= len(self.scripts):
            tk.Label(self.current_script_frame, text="Select a script to view details", font=('Arial', 12)).pack(pady=50)
            return
        
        script = self.scripts[self.selected_script_index]
        
        # Script name with highlight if editing
        name_frame = tk.Frame(self.current_script_frame)
        name_frame.pack(fill=tk.X, pady=5)
        
        name_bg = 'yellow' if script.is_editing else 'SystemButtonFace'
        name_label_frame = tk.Frame(name_frame, bg=name_bg, relief=tk.RIDGE, borderwidth=2)
        name_label_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Label(name_label_frame, text=f"Script: {script.name}", font=('Arial', 12, 'bold'), bg=name_bg).pack(padx=5, pady=2)
        
        # Edit/Finish button
        edit_text = "Finish Editing" if script.is_editing else "Edit Script"
        edit_color = 'orange' if script.is_editing else 'blue'
        edit_btn = tk.Button(name_frame, text=edit_text, command=lambda: self.toggle_edit_script(self.selected_script_index), bg=edit_color, fg='white')
        edit_btn.pack(side=tk.RIGHT)
        
        # Keybind
        keybind_frame = tk.Frame(self.current_script_frame)
        keybind_frame.pack(fill=tk.X, pady=5)
        tk.Label(keybind_frame, text="Keybind:", font=('Arial', 10)).pack(side=tk.LEFT)
        keybind_label = tk.Label(keybind_frame, text=script.keybind if script.keybind else "Not set", fg='gray', font=('Arial', 10))
        keybind_label.pack(side=tk.LEFT, padx=5)
        set_keybind_btn = tk.Button(keybind_frame, text="Set Keybind", command=lambda: self.set_keybind(self.selected_script_index))
        set_keybind_btn.pack(side=tk.RIGHT)
        
        # Targets section
        targets_label_frame = tk.Frame(self.current_script_frame)
        targets_label_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(targets_label_frame, text="Targets:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        add_target_btn = tk.Button(targets_label_frame, text="Add Target", command=lambda: self.add_target(self.selected_script_index))
        add_target_btn.pack(side=tk.RIGHT)
        
        # Targets list with scrollbar
        targets_list_frame = tk.Frame(self.current_script_frame)
        targets_list_frame.pack(fill=tk.BOTH, expand=True)
        
        targets_scrollbar = tk.Scrollbar(targets_list_frame)
        targets_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        targets_canvas = tk.Canvas(targets_list_frame, yscrollcommand=targets_scrollbar.set)
        targets_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        targets_scrollbar.config(command=targets_canvas.yview)
        
        targets_inner_frame = tk.Frame(targets_canvas)
        targets_canvas_window = targets_canvas.create_window((0, 0), window=targets_inner_frame, anchor=tk.NW)
        
        # Update scroll region
        def update_scroll_region(event):
            targets_canvas.configure(scrollregion=targets_canvas.bbox("all"))
            targets_canvas.configure(width=targets_inner_frame.winfo_reqwidth())
        
        targets_inner_frame.bind('<Configure>', update_scroll_region)
        targets_canvas.bind('<Configure>', lambda e: targets_canvas.configure(width=e.width))
        
        # Create target entries
        for i, target in enumerate(script.targets):
            target_frame = tk.Frame(targets_inner_frame, relief=tk.RIDGE, borderwidth=1)
            target_frame.pack(fill=tk.X, pady=2, padx=5)
            
            tk.Label(target_frame, text=f"Target {target['id']}:", width=10, anchor=tk.W).pack(side=tk.LEFT, padx=5)
            tk.Label(target_frame, text="Delay (ms):").pack(side=tk.LEFT, padx=5)
            
            delay_var = tk.StringVar(value=str(target['delay']))
            delay_entry = tk.Entry(target_frame, textvariable=delay_var, width=10)
            delay_entry.pack(side=tk.LEFT, padx=5)
            delay_entry.bind('<KeyRelease>', lambda e, idx=i: self.update_target_delay(self.selected_script_index, idx))
            delay_entry.bind('<FocusOut>', lambda e, idx=i: self.update_target_delay(self.selected_script_index, idx))
            
            # Store reference to update
            target['delay_var'] = delay_var
        
        targets_inner_frame.update_idletasks()
        targets_canvas.configure(scrollregion=targets_canvas.bbox("all"))
    
    def add_script(self):
        """Add a new script"""
        name = simpledialog.askstring("Add Script", "Enter script name:")
        if name:
            script = Script(name)
            self.scripts.append(script)
            self.scripts_listbox.insert(tk.END, name)
            self.scripts_listbox.selection_clear(0, tk.END)
            self.scripts_listbox.selection_set(tk.END)
            self.scripts_listbox.see(tk.END)
            self.selected_script_index = len(self.scripts) - 1
            self.update_details_view()
            self.update_scripts_listbox()
    
    def toggle_edit_script(self, script_index: int):
        """Toggle edit mode for a script"""
        if script_index >= len(self.scripts):
            return
        
        script = self.scripts[script_index]
        
        if script.is_editing:
            # Finish editing - save positions and hide windows
            script.is_editing = False
            self.save_target_positions(script)
            self.hide_target_windows(script)
            if self.currently_editing == script:
                self.currently_editing = None
        else:
            # Start editing - hide previous script's targets
            if self.currently_editing:
                self.currently_editing.is_editing = False
                self.save_target_positions(self.currently_editing)
                self.hide_target_windows(self.currently_editing)
            
            script.is_editing = True
            self.currently_editing = script
            self.show_target_windows(script)
        
        self.update_details_view()
        self.update_scripts_listbox()
    
    def save_target_positions(self, script: Script):
        """Save current positions of target windows to script targets"""
        for window, target in zip(script.target_windows, script.targets):
            if window.target_id == target['id']:
                pos = window.get_position()
                target['x'] = pos[0]
                target['y'] = pos[1]
    
    def show_target_windows(self, script: Script):
        """Show and make target windows visible and draggable"""
        # Destroy old windows
        for window in script.target_windows:
            window.destroy()
        script.target_windows = []
        
        # Create new windows for all targets
        for target in script.targets:
            window = TargetWindow(target['id'], target['x'], target['y'])
            window.set_click_through(False)  # Make draggable
            script.target_windows.append(window)
    
    def hide_target_windows(self, script: Script):
        """Hide target windows and make them click-through"""
        for window in script.target_windows:
            window.set_click_through(True)
        # Positions are saved before hiding
    
    def add_target(self, script_index: int):
        """Add a target to a script"""
        if script_index >= len(self.scripts):
            return
        
        script = self.scripts[script_index]
        target_id = script.add_target(delay=0)
        
        if script.is_editing:
            # Create window immediately
            target = script.targets[-1]
            window = TargetWindow(target_id, target['x'], target['y'])
            window.set_click_through(False)
            script.target_windows.append(window)
        
        self.update_details_view()
    
    def update_target_delay(self, script_index: int, target_index: int):
        """Update delay for a target"""
        if script_index >= len(self.scripts):
            return
        
        script = self.scripts[script_index]
        if target_index < len(script.targets):
            target = script.targets[target_index]
            try:
                delay = int(target['delay_var'].get())
                target['delay'] = delay
            except ValueError:
                pass
    
    def set_keybind(self, script_index: int):
        """Set keybind for a script"""
        if script_index >= len(self.scripts):
            return
        
        script = self.scripts[script_index]
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Keybind")
        dialog.geometry("500x250")
        dialog.attributes('-topmost', True)
        dialog.transient(self.root)
        
        tk.Label(dialog, text="Press the key combination you want to use", font=('Arial', 11)).pack(pady=20)
        tk.Label(dialog, text="(e.g., alt+p, ctrl+e+r)", font=('Arial', 9), fg='gray').pack()
        
        keybind_var = tk.StringVar(value="Waiting for keys...")
        keybind_label = tk.Label(dialog, textvariable=keybind_var, font=('Arial', 14, 'bold'), fg='blue')
        keybind_label.pack(pady=15)
        
        captured_hotkey = [None]
        capture_active = [True]
        
        def capture_hotkey_thread():
            """Capture hotkey in background thread"""
            try:
                # Use keyboard library to read hotkey
                hotkey = keyboard.read_hotkey()
                if capture_active[0] and hotkey:
                    captured_hotkey[0] = hotkey
                    # Format for display
                    parts = hotkey.split('+')
                    display_parts = []
                    for part in parts:
                        if len(part) > 1:
                            display_parts.append(part.capitalize())
                        else:
                            display_parts.append(part.upper())
                    display_str = '+'.join(display_parts)
                    dialog.after(0, lambda: keybind_var.set(display_str))
            except Exception as e:
                print(f"Error capturing hotkey: {e}")
        
        def start_capture():
            """Start capturing hotkey"""
            keybind_var.set("Press your key combination now...")
            threading.Thread(target=capture_hotkey_thread, daemon=True).start()
        
        def save_keybind():
            if captured_hotkey[0]:
                hotkey = captured_hotkey[0]
                # Format for display
                parts = hotkey.split('+')
                display_parts = []
                for part in parts:
                    if len(part) > 1:
                        display_parts.append(part.capitalize())
                    else:
                        display_parts.append(part.upper())
                display_str = '+'.join(display_parts)
                
                script.keybind = display_str
                script.keybind_hotkey = hotkey
                capture_active[0] = False
                dialog.destroy()
                self.update_details_view()
                # Restart keyboard hooks if running
                if self.is_running:
                    self.stop_running()
                    self.start_running()
            else:
                messagebox.showwarning("Warning", "Please capture a keybind first!")
        
        def cancel():
            capture_active[0] = False
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        capture_btn = tk.Button(btn_frame, text="Start Capture", command=start_capture, width=12)
        capture_btn.pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Save", command=save_keybind, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        # Instructions
        tk.Label(dialog, text="Click 'Start Capture', then press your key combination", font=('Arial', 8), fg='gray').pack(pady=5)
        
        # Auto-start capture
        dialog.after(100, start_capture)
    
    def save_scripts(self):
        """Save scripts to JSON file"""
        # Save target positions before saving
        for script in self.scripts:
            if script.is_editing:
                self.save_target_positions(script)
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            data = [script.to_dict() for script in self.scripts]
            try:
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                messagebox.showinfo("Success", "Scripts saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save scripts: {str(e)}")
    
    def load_scripts(self):
        """Load scripts from JSON file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                # Stop running before loading
                was_running = self.is_running
                if self.is_running:
                    self.stop_running()
                
                self.scripts = [Script.from_dict(item) for item in data]
                
                # Update listbox
                self.scripts_listbox.delete(0, tk.END)
                for script in self.scripts:
                    self.scripts_listbox.insert(tk.END, script.name)
                
                # Restore keybind hotkeys
                for script in self.scripts:
                    if script.keybind:
                        # Parse keybind back to hotkey format
                        parts = script.keybind.lower().split('+')
                        script.keybind_hotkey = '+'.join(parts)
                
                if was_running:
                    self.start_running()
                
                messagebox.showinfo("Success", "Scripts loaded successfully!")
                self.update_details_view()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load scripts: {str(e)}")
    
    def toggle_run(self):
        """Toggle run mode (start/stop listening for keybinds)"""
        if self.is_running:
            self.stop_running()
        else:
            self.start_running()
    
    def start_running(self):
        """Start listening for keybinds"""
        self.is_running = True
        self.run_btn.config(text="Stop", bg='red')
        
        # Register hotkeys for all scripts with keybinds
        self.keyboard_hooks.clear()
        for script in self.scripts:
            if script.keybind_hotkey:
                try:
                    # Register hotkey
                    keyboard.add_hotkey(script.keybind_hotkey, lambda s=script: self.execute_script(s))
                    self.keyboard_hooks[script] = script.keybind_hotkey
                except Exception as e:
                    print(f"Error registering hotkey for {script.name}: {e}")
    
    def stop_running(self):
        """Stop listening for keybinds"""
        self.is_running = False
        self.run_btn.config(text="Run", bg='green')
        
        # Unregister all hotkeys
        try:
            keyboard.unhook_all_hotkeys()
        except:
            pass
        self.keyboard_hooks.clear()
    
    def execute_script(self, script: Script):
        """Execute a script (click targets in order)"""
        if not script.targets:
            return
        
        # Execute in separate thread to avoid blocking
        threading.Thread(target=self._execute_script_thread, args=(script,), daemon=True).start()
    
    def _execute_script_thread(self, script: Script):
        """Execute script in thread"""
        try:
            for target in script.targets:
                if target['delay'] > 0:
                    time.sleep(target['delay'] / 1000.0)
                # Click at target position (center of 30x30 window)
                pyautogui.click(target['x'] + 15, target['y'] + 15)
                time.sleep(0.05)  # Small delay between clicks
        except Exception as e:
            print(f"Error executing script {script.name}: {e}")
    
    def update_scripts_listbox(self):
        """Update the scripts listbox display with highlights"""
        # Note: tkinter listbox doesn't easily support per-item colors
        # We'll highlight in the details view instead
        pass
    
    def create_tray_icon(self):
        """Create system tray icon"""
        if not HAS_PYSTRAY:
            return
        
        try:
            # Create icon image
            image = Image.new('RGB', (64, 64), color='white')
            draw = ImageDraw.Draw(image)
            draw.ellipse([16, 16, 48, 48], fill='blue', outline='black', width=2)
            # Draw "AC" text centered
            try:
                from PIL import ImageFont
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = None
            draw.text((32, 32), "AC", fill='white', anchor='mm', font=font)
            
            # Create menu
            menu = pystray.Menu(
                pystray.MenuItem("Show Window", self.show_window),
                pystray.MenuItem("Exit", self.quit_app)
            )
            
            # Create icon
            self.tray_icon = pystray.Icon("AutoClicker", image, "AutoClicker", menu)
            
            # Run tray in separate thread
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self.tray_thread.start()
        except Exception as e:
            print(f"Error creating tray icon: {e}")
    
    def show_window(self, icon=None, item=None):
        """Show the main window"""
        self.root.after(0, self._show_window)
    
    def _show_window(self):
        """Show window from main thread"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def quit_app(self, icon=None, item=None):
        """Quit application"""
        if self.is_running:
            self.stop_running()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.quit)
    
    def on_minimize(self, event):
        """Handle window minimization"""
        if event.widget != self.root:
            return
        # Check if window is being minimized
        if self.root.state() == 'iconic':
            # Hide to system tray
            self.root.withdraw()
    
    def on_closing(self):
        """Handle window closing"""
        # Hide window instead of destroying (for system tray functionality)
        self.root.withdraw()
        
        # Note: Target windows will remain visible if a script is being edited
        # This is intentional per requirements

def main():
    # Set PyAutoGUI failsafe (move mouse to corner to stop)
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.01
    
    root = tk.Tk()
    app = AutoClickerApp(root)
    
    # Run main loop
    # System tray icon is created in __init__ if pystray is available
    # User can minimize/close window, and target windows will persist
    
    root.mainloop()
    
    # Cleanup
    if app.is_running:
        app.stop_running()
    if app.tray_icon:
        app.tray_icon.stop()

if __name__ == "__main__":
    main()
