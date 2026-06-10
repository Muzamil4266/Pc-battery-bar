## Charging State

![Charging](Charging.png)

## Rest State

![Rest](Rest.png)

🔋 BatteryBar - Persistent Battery Status Indicator

A lightweight, always-on-top battery status bar for Windows that never disappears - featuring multi-layer autostart persistence and self-healing capabilities.


---

✨ Features

🎨 Real-time battery display - Percentage and animated charging indicator

⚡ Smart color coding - Different colors for charging, normal, and low battery

🔄 Auto-startup persistence - 4 independent layers ensure it always launches

🛡️ Self-healing - Automatically restarts if crashed or terminated

🎯 Always on top - Never gets lost behind other windows

🎛️ Customizable colors - Right-click or left-click to change theme colors

🚀 Zero distractions - Undecorated window that sits unobtrusively in corner



---

📋 Requirements

Windows 10/11 (64-bit recommended)

Python 3.7+ (if running from source)

Administrator privileges (optional - for enhanced persistence)


📦 Dependencies

pip install psutil tkinter  
  
  
  
  
Note: tkinter comes bundled with most Python installations on Windows  
  
---  
  
🚀 Installation  
  
🔧 From Source  
  
1. Clone or download the script  
2. Install dependencies:  
   ```bash  
   pip install psutil

3. Run the script:

python batterybar.py



📦 As Compiled EXE (Recommended)

Using PyInstaller:

pip install pyinstaller  
pyinstaller --onefile --noconsole --name BatteryBar batterybar.py

The EXE will be in the dist folder.


---

🎮 Usage

Basic Controls

Action Result
Left-click anywhere on bar Change current context color (charging/normal/low)
Right-click anywhere on bar Open context menu
Exit from menu Cleanly removes all autostart entries

🎨 Color Contexts

· ⚡ When charging - Changes the charging color
· 🔋 Battery > 20% - Changes normal battery color
· 🪫 Battery ≤ 20% - Changes low battery warning color


---

🔒 Persistence Layers (The "Never Dies" Feature)

Code 2 implements 4 independent persistence mechanisms:

🥇 Layer 1 - HKCU Registry

· Always active, works without admin rights
· Standard Windows user-level autostart

🥈 Layer 2 - HKLM Registry

· System-wide persistence (requires admin on install)
· Survives user-level cleanup tools

🥉 Layer 3 - Task Scheduler

· Most robust layer - completely separate from registry
· Auto-restarts on failure (up to 99 times)
· Survives registry cleaners, CCleaner, etc.

🛡️ Layer 4 - Internal Watchdog

· Background thread monitoring app health
· Handles soft hangs and unresponsive states

💡 Note: Even if registry entries are deleted, the Task Scheduler layer ensures the app restarts at next login.


---

🛠️ Configuration

📍 Window Position

Edit these lines in the script:

x_coordinate = 10        # Distance from left edge (pixels)  
y_coordinate = screen_height - 48   # Distance from bottom edge

🎨 Default Colors

color_charging = "#808080"   # Gray when charging  
color_normal   = "#964B00"   # Brown when discharging >20%  
color_low      = "#FF3333"   # Red when battery ≤20%

⏱️ Update Intervals

root.after(4000, check_hardware)  # Check battery every 4 seconds  
refresh_rate = 40 if plugged else 1000  # Animation: 40ms, Static: 1s


---

🗑️ Uninstallation

The app cleans up after itself automatically when you click Exit from the context menu.

Manual Cleanup (if needed):

Remove Registry Entries:

reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v BatteryBar /f  
reg delete HKLM\Software\Microsoft\Windows\CurrentVersion\Run /v BatteryBar /f

Remove Task Scheduler Entry:

schtasks /delete /tn BatteryBar /f

Delete the EXE/script file from its location.


---

🐛 Troubleshooting

❌ App Doesn't Start Automatically

1. Check Task Scheduler:

schtasks /query /tn BatteryBar


2. Verify registry entries exist


3. Run once manually - this re-registers all layers



🔄 Multiple Instances Running

The Task Scheduler and registry might both launch the app. Solution:

· Edit register_task_scheduler() to add instance checking, OR
· Keep only HKCU + Task Scheduler (remove HKLM layer)

🚫 Permission Errors

· Normal operation doesn't require admin rights
· Enhanced persistence (HKLM + Task Scheduler) needs admin on first run
· The app handles permission errors silently - basic functionality always works

📊 Battery Not Showing

· Check if psutil can access battery:

import psutil  
print(psutil.sensors_battery())

· Verify Windows battery drivers are installed
· Restart Windows - sometimes battery sensors need reset


---

🔧 Advanced Customization

Change Window Size

bar_width = 190   # Total width in pixels  
bar_height = 40   # Total height in pixels

Modify Animation Speed

step_speed = 1.8   # Lower = slower pulse animation when charging

Disable Task Scheduler Layer

Comment out this line in register_all():

# register_task_scheduler()  # Disable Task Scheduler persistence


---

📝 Technical Details

How It Works

1. Battery Monitoring - Uses psutil.sensors_battery() for real-time data


2. Canvas Drawing - Tkinter creates custom-drawn battery icon


3. Persistence - winreg + subprocess for Task Scheduler integration


4. Always On Top - attributes("-topmost", True) keeps window visible



Resource Usage

· CPU: ~0-1% (minimal, updates only when needed)
· RAM: ~15-25 MB
· Disk: ~8 KB (script) or ~8 MB (compiled EXE)

Security Considerations

· ✅ No network access
· ✅ No data collection
· ✅ Registry modifications only for autostart
· ✅ Task Scheduler uses standard Windows APIs
· ✅ Source code is open and auditable


---

🤝 Contributing

Feel free to:

· 🐛 Report bugs
· 💡 Suggest features
· 🔧 Submit pull requests
· 📖 Improve documentation


---

📄 License

MIT License - Free for personal and commercial use.


---

🙏 Acknowledgments

· psutil library for cross-platform system monitoring
· tkinter for lightweight GUI capabilities
· Windows Task Scheduler API documentation


---

📞 Support

For issues:

1. Check the Troubleshooting section above


2. Verify all dependencies are installed


3. Test running as administrator (if persistence fails)


4. Open an issue on the project repository




---

Made with ⚡ for Windows users who never want to be surprised by a dead battery again

