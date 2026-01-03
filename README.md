# AutoClicker

An advanced autoclicker application built with Python, Tkinter, and PyAutoGUI. This application allows you to create multiple scripts with customizable click targets, keybind activation, and system tray integration.

## Features

- **Multiple Scripts**: Create and manage multiple autoclicker scripts
- **Customizable Targets**: Add multiple click targets per script with individual delays
- **Visual Target Editing**: Drag and drop targets on screen when editing scripts
- **Keybind Activation**: Set custom keyboard shortcuts (e.g., Alt+P, Ctrl+E+R) to activate scripts
- **Save/Load Scripts**: Save your scripts to JSON files and load them later
- **System Tray Integration**: Minimize to system tray, targets remain visible
- **Persistent Targets**: Target windows stay on top even when main window is closed

## Installation

1. Install Python 3.7 or higher

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Workflow

1. **Add a Script**: Click "Add Script" button and enter a name for your script

2. **Edit Script**: Select a script from the list and click "Edit Script" to enter edit mode
   - Script name will be highlighted in yellow when editing
   - Targets become visible and draggable

3. **Add Targets**: Click "Add Target" to add click targets
   - Targets appear as numbered red circles with an X
   - Each target is numbered sequentially (1, 2, 3...)
   - Drag targets to position them on screen

4. **Set Delays**: Enter delay time in milliseconds for each target
   - Delay is the time to wait before clicking that target
   - Use the input field next to each target

5. **Set Keybind**: Click "Set Keybind" to assign a keyboard shortcut
   - Click "Start Capture" in the dialog
   - Press your desired key combination (e.g., Alt+P, Ctrl+E+R)
   - Click "Save" to confirm

6. **Finish Editing**: Click "Finish Editing" to exit edit mode
   - Targets become invisible and click-through
   - Only one script can be edited at a time

7. **Run**: Click "Run" button to start listening for keybinds
   - Button turns red and says "Stop"
   - Press your keybinds to activate scripts
   - Click "Stop" to disable keybind listening

8. **Save/Load**: Use "Save Scripts" and "Load Scripts" buttons to persist your configurations

### System Tray

- When you close or minimize the window, it hides to the system tray
- Click the system tray icon to show the window again
- Target windows remain visible even when main window is hidden
- Right-click system tray icon for options (Show Window, Exit)

## JSON File Format

Scripts are saved in JSON format with the following structure:

```json
[
  {
    "name": "Script Name",
    "keybind": "Alt+P",
    "targets": [
      {
        "id": 1,
        "x": 100,
        "y": 200,
        "delay": 500
      },
      {
        "id": 2,
        "x": 300,
        "y": 400,
        "delay": 1000
      }
    ]
  }
]
```

## Requirements

- Python 3.7+
- pyautogui
- keyboard
- pystray (for system tray)
- Pillow (for system tray icon)

## Notes

- **Administrator Rights**: The `keyboard` library may require administrator/root privileges on some systems for global hotkey detection
- **Fail-Safe**: PyAutoGUI has a failsafe - move your mouse to the top-left corner to stop any running script
- **Target Windows**: Target windows are separate from the main window and stay on top of other applications
- **Editing Mode**: Only one script can be edited at a time. Editing another script will hide the previous script's targets

## Troubleshooting

- **Keybinds not working**: Make sure you've clicked "Run" and that you're using the correct key combination
- **System tray not appearing**: Make sure pystray and Pillow are installed correctly
- **Targets not visible**: Make sure you've clicked "Edit Script" for the script you want to edit
- **Permissions error**: On Windows/Linux, you may need to run with administrator/root privileges for keyboard hooks

## License

This project is provided as-is for educational and personal use.

