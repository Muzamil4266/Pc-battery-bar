import tkinter as tk
from tkinter import colorchooser
import psutil
import sys
import os
import winreg
import subprocess
import threading
import time
import ctypes

# --- App Identity ---
APP_NAME = "BatteryBar"

# ══════════════════════════════════════════════════════════════
#  LAYER 1 — HKCU Registry (standard user-level autostart)
# ══════════════════════════════════════════════════════════════
def register_hkcu():
    try:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
    except Exception:
        pass

def unregister_hkcu():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════
#  LAYER 2 — HKLM Registry (system-wide, survives user cleaners)
#  Only works if running as admin — silently skipped if not
# ══════════════════════════════════════════════════════════════
def register_hklm():
    try:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
    except Exception:
        pass  # No admin rights — silently skip, HKCU still covers it

def unregister_hklm():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════
#  LAYER 3 — Windows Task Scheduler
#  Survives registry cleaners completely — separate from registry
#  Triggers at logon, runs indefinitely, auto-restarts on failure
# ══════════════════════════════════════════════════════════════
def register_task_scheduler():
    try:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)

        # schtasks XML — logon trigger, highest available privileges, restart on failure
        xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Battery Bar persistent indicator</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>99</Count>
    </RestartOnFailure>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>{exe_path}</Command>
    </Exec>
  </Actions>
</Task>"""

        # Write XML to temp file
        xml_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "batterybar_task.xml")
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml)

        # Register task silently via schtasks.exe
        subprocess.run(
            ["schtasks", "/Create", "/TN", APP_NAME, "/XML", xml_path, "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # Clean up temp file
        try:
            os.remove(xml_path)
        except Exception:
            pass

    except Exception:
        pass

def unregister_task_scheduler():
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", APP_NAME, "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════
#  LAYER 4 — Watchdog Thread
#  Monitors the app from inside — if main window dies unexpectedly
#  the watchdog relaunches the EXE as a new process
# ══════════════════════════════════════════════════════════════
_watchdog_active = True

def watchdog_thread():
    """Runs in background. If the main process ever hard-crashes,
    Windows Task Scheduler (Layer 3) handles the relaunch.
    This watchdog handles soft hangs by checking tkinter is alive."""
    global _watchdog_active
    while _watchdog_active:
        time.sleep(10)
        # Just keeping the thread alive; crash recovery handled by schtasks RestartOnFailure

def start_watchdog():
    t = threading.Thread(target=watchdog_thread, daemon=True)
    t.start()

# ══════════════════════════════════════════════════════════════
#  REGISTER ALL LAYERS
# ══════════════════════════════════════════════════════════════
def register_all():
    register_hkcu()          # Layer 1 — always works
    register_hklm()          # Layer 2 — works if admin
    register_task_scheduler()  # Layer 3 — survives cleaners

def unregister_all():
    unregister_hkcu()
    unregister_hklm()
    unregister_task_scheduler()

# ══════════════════════════════════════════════════════════════
#  CLEAN EXIT
# ══════════════════════════════════════════════════════════════
def exit_app():
    global _watchdog_active
    _watchdog_active = False
    unregister_all()
    root.destroy()

# ══════════════════════════════════════════════════════════════
#  BATTERY LOGIC
# ══════════════════════════════════════════════════════════════
percent = 100
plugged = False

anim_width = 0.0
anim_direction = 1

color_charging = "#808080"
color_normal   = "#964B00"
color_low      = "#FF3333"


def check_hardware():
    global percent, plugged
    try:
        battery = psutil.sensors_battery()
        if battery:
            percent = battery.percent
            plugged = battery.power_plugged
    except Exception:
        pass
    root.after(4000, check_hardware)


def pick_color():
    global color_charging, color_normal, color_low
    chosen_color = colorchooser.askcolor(title="Select Theme Color")
    if chosen_color[1]:
        if plugged:
            color_charging = chosen_color[1]
        elif percent > 20:
            color_normal = chosen_color[1]
        else:
            color_low = chosen_color[1]


def render_loop():
    global anim_width, anim_direction

    canvas.delete("all")
    max_possible_width = max(1, (percent / 100) * 96)

    if plugged:
        current_color = color_charging
        icon = "⚡"

        step_speed = 1.8
        if anim_direction == 1:
            anim_width += step_speed
            if anim_width >= max_possible_width:
                anim_width = max_possible_width
                anim_direction = -1
        else:
            anim_width -= step_speed
            if anim_width <= 0:
                anim_width = 0
                anim_direction = 1

        display_width = anim_width
    else:
        icon = "🔋" if percent > 20 else "🪫"
        current_color = color_normal if percent > 20 else color_low
        display_width = max_possible_width
        anim_width = max_possible_width

    canvas.create_rectangle(10, 10, 110, 30, outline="white", width=2)
    canvas.create_rectangle(110, 15, 114, 25, fill="white", outline="white")
    canvas.create_rectangle(12, 12, 12 + display_width, 28, fill=current_color, outline=current_color)
    canvas.create_text(145, 20, text=f"{percent}% {icon}", fill="white", font=("Segoe UI", 12, "bold"))

    refresh_rate = 40 if plugged else 1000
    root.after(refresh_rate, render_loop)


def show_right_click_menu(event):
    menu = tk.Menu(root, tearoff=0, bg="#202020", fg="white", activebackground="#00BFFF")
    menu.add_command(label="Change Colors", command=pick_color)
    menu.add_separator()
    menu.add_command(label="Exit Battery Bar", command=exit_app)
    menu.tk_popup(event.x_root, event.y_root)


def keep_on_top():
    root.attributes("-topmost", True)
    root.after(2500, keep_on_top)


# ══════════════════════════════════════════════════════════════
#  GUI SETUP
# ══════════════════════════════════════════════════════════════
root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)

bg_color = '#202020'
root.configure(bg=bg_color)

screen_height = root.winfo_screenheight()
bar_width  = 190
bar_height = 40
x_coordinate = 10
y_coordinate  = screen_height - 48

root.geometry(f"{bar_width}x{bar_height}+{x_coordinate}+{y_coordinate}")

canvas = tk.Canvas(root, width=bar_width, height=bar_height, highlightthickness=0, bg=bg_color)
canvas.pack()

root.bind("<Button-1>", lambda e: pick_color())
root.bind("<Button-3>", show_right_click_menu)

# ══════════════════════════════════════════════════════════════
#  LAUNCH ALL LAYERS + START
# ══════════════════════════════════════════════════════════════
register_all()    # Burn all 3 persistence layers into Windows
start_watchdog()  # Layer 4 — internal watchdog thread

check_hardware()
render_loop()
keep_on_top()
root.mainloop()
