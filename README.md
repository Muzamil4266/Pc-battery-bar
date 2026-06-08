## Charging State

![Charging](Charging.png)

## Rest State

![Rest](Rest.png)



🔋 PC BATTERY BAR

A lightweight, always-on-top Windows battery indicator that displays your laptop's battery percentage and charging status in real-time. The app sits unobtrusively in the corner of your screen with a sleek dark theme, animated charging indicator, and customizable colors.

✨ FEATURES

✨ Real-Time Battery Monitoring — Displays current battery percentage with live updates every 4 seconds

⚡ Charging Animation — Smooth pulse animation when your laptop is plugged in

🪫 Low Battery Warning — Color changes to red when battery drops below 20%

🎨 Custom Color Themes — Click to change colors for different battery states

🔌 Always On Top — Never hidden behind other windows

🚀 Auto-Startup — Automatically launches on every system reboot

🖱️ Right-Click Menu — Easy access to color picker and exit options

💻 Lightweight — Minimal CPU and memory footprint

🔇 Silent Operation — No notifications, no popups, just the indicator

⚙️ HOW IT WORKS

Core Functionality

PC Battery Bar continuously monitors your system's battery status using the psutil library, which interfaces directly with Windows' power management system. Here's how each component works:

Battery Detection (check_hardware())

The application queries your laptop's battery information every 4 seconds:

battery = psutil.sensors_battery()

This retrieves two critical pieces of data:

· Battery Percentage (battery.percent) — Current charge level from 0-100%
· Charging Status (battery.power_plugged) — Boolean indicating if AC adapter is connected

The 4-second update interval balances real-time accuracy with minimal resource consumption. If Windows temporarily locks the sensor (common in some enterprise setups), the app gracefully catches the exception and continues without crashing.

Visual Rendering (render_loop())

The display updates at different refresh rates depending on state:

· While Charging: 40ms refresh (25 FPS) to show smooth animation
· While Unplugged: 1000ms refresh (1 FPS) for battery preservation

The visual components include:

· Battery Housing — White outlined rectangle (100 pixels wide × 20 pixels tall)
· Battery Nozzle — Small white connector on the right side
· Charge Bar — Colored fill inside the housing, width proportional to battery percentage
· Percentage Text — Current charge level + icon (🔋 normal, ⚡ charging, 🪫 low battery)

Color Coding System

The app uses three distinct color states:

· Charging: Bright Green (#00FF00) — AC adapter connected
· Normal: Sky Blue (#00BFFF) — Battery > 20%, unplugged
· Low Battery: Bright Red (#FF3333) — Battery ≤ 20%, unplugged

Each color is independently customizable through left-click color picker.

Charging Animation

When plugged in, the charge bar doesn't just fill statically. Instead, it animates smoothly:

if anim_direction == 1:
anim_width += 1.8  # Expand
if anim_width >= max_possible_width:
anim_direction = -1  # Reverse direction
else:
anim_width -= 1.8  # Contract
if anim_width <= 0:
anim_direction = 1  # Reverse direction again

This creates a breathing/pulsing effect that visually communicates active charging without being distracting.

Window Management

The app runs as a borderless, always-on-top window positioned in the bottom-left corner:

root.overrideredirect(True)  # Removes window decorations (title bar, borders)
root.attributes("-topmost", True)  # Always on top of other windows

A background task reinforces the topmost status every 2.5 seconds (keep_on_top()) to prevent other applications from stealing focus.

The window size is fixed at 190×40 pixels and positioned at:

· X: 10 pixels from left edge
· Y: Screen height - 48 pixels (bottom corner with small margin)

This ensures it doesn't obscure taskbars or critical screen real estate.

🔧 WHY IT PERSISTS AFTER REBOOT (THE STARTUP REGISTRY MAGIC)

This is the most important technical feature of PC Battery Bar. Unlike startup folder shortcuts that can be deleted, disabled, or fail silently, the app uses Windows Registry autostart, which is the native, reliable method Windows itself uses.

The Registry Approach

When you run the EXE for the first time, this code executes:

def register_startup():
exe_path = sys.executable  # Path to the running EXE
key = winreg.OpenKey(
winreg.HKEY_CURRENT_USER,
r"Software\Microsoft\Windows\CurrentVersion\Run",
0,
winreg.KEY_SET_VALUE
)
winreg.SetValueEx(key, "BatteryBar", 0, winreg.REG_SZ, exe_path)
winreg.CloseKey(key)

This writes a registry entry at:
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run

With the value:
BatteryBar = C:\Path\To\BatteryBar.exe

Why Registry > Startup Folder

· Reliability: Registry is Windows native and guaranteed vs. Startup Folder which can be disabled by antivirus/group policy
· Persistence: Registry survives Windows updates vs. Startup Folder sometimes cleared by cleanup tools
· Execution Method: Registry uses direct Windows hook vs. Startup Folder where shell executes shortcut (slower, less reliable)
· User Awareness: Registry is hidden and clean vs. Startup Folder visible as file in folder
· Recovery: Registry auto-updates on each launch vs. Startup Folder one-time setup that breaks if file moves

Auto-Path Update

The registration runs on every launch, not just the first time:

register_startup()  # Runs before mainloop()

This means:

· If you move the EXE to a different folder, registry updates automatically on next run
· If the path changes, Windows always launches the correct version
· No manual re-registration needed

Safe Cleanup

When you exit through the right-click menu:

def exit_app():
unregister_startup()  # Removes registry entry
root.destroy()

The registry entry is cleanly removed, so if you uninstall, no orphaned entries remain.

📥 INSTALLATION & SETUP

Requirements

· Windows 10 or later
· Python 3.7+ (if running from source)
· psutil library

Building the EXE

The critical step is using the --noconsole flag with PyInstaller. This tells Windows to build a GUI application with no console window:

pip install psutil pyinstaller
pyinstaller --onefile --noconsole --name BatteryBar Pc-battery-bar.py

The --noconsole flag is essential because:

· Without it, a CMD window flashes briefly on startup
· Windows GUI detection fails without this flag
· The application won't register as a proper background service

First Launch

Simply run BatteryBar.exe once. The application:

· Registers itself in Windows Registry
· Displays on screen immediately
· Continues to display on every reboot thereafter

No shortcuts, no manual registry editing, no configuration files needed.

🖱️ USER INTERACTIONS

Left Click
Opens the color picker for the currently relevant color state (charging, normal, or low battery). Perfect for theme customization.

Right Click
Displays a context menu with two options:

· Change Colors — Same as left-click color picker
· Exit Battery Bar — Cleanly closes the app and removes registry entry

No Taskbar Icon
The app intentionally has no taskbar presence. It's designed to be invisible until you need it, keeping your taskbar clean.

💻 TECHNICAL STACK

· Language: Python 3
· GUI Framework: Tkinter (built-in to Python, no dependencies)
· Hardware Monitoring: psutil (cross-platform battery API)
· System Integration: winreg (Windows registry access)
· Packaging: PyInstaller (converts Python to standalone EXE)

📊 PERFORMANCE

· CPU Usage: < 1% when idle
· Memory Usage: ~30-40 MB (Python runtime included in EXE)
· Disk Space: ~50 MB (standalone executable)
· Battery Impact: Negligible (1000ms refresh rate when unplugged)

🗑️ UNINSTALLING

1. Right-click the battery bar indicator
2. Select "Exit Battery Bar"
3. Delete the EXE file
4. Done — no registry cleanup needed (the exit option handles it automatically)

🎨 CUSTOMIZATION

All colors are hardcoded variables at the top of the source file:

color_charging = "#00FF00"  # Bright green
color_normal = "#00BFFF"    # Sky blue
color_low = "#FF3333"       # Bright red

Modify these hex values before building the EXE to create your own color scheme, then rebuild with PyInstaller.

📄 LICENSE

MIT License — Use, modify, and distribute freely.

🤝 CONTRIBUTING
Found a bug or have a feature request? Open an issue on GitHub!

Made with ⚡ for Windows laptop users who care about battery awareness.
Found a bug or have a feature request? Open an issue on GitHub!

Made with ⚡ for Windows laptop users who care about battery awareness.
