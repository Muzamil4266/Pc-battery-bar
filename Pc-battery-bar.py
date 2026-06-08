import tkinter as tk
from tkinter import colorchooser
import psutil
import sys
import os
import winreg

# --- Auto-Startup via Registry (reliable, no CMD flash) ---
APP_NAME = "BatteryBar"

def register_startup():
    """Adds this EXE to HKCU Run registry key so it launches on boot with no CMD window."""
    try:
        # Get the path of the running EXE (works after PyInstaller build)
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            # During development just use the script path
            exe_path = os.path.abspath(__file__)

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
    except Exception:
        pass  # Silently fail — never crash the app over this

def unregister_startup():
    """Removes the registry entry (called on Exit)."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except Exception:
        pass

def exit_app():
    """Clean exit — removes registry key then destroys window."""
    unregister_startup()
    root.destroy()

# --- Global States & Variables ---
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

    # Graphics
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
    # Exit now calls exit_app() which cleans up registry
    menu.add_command(label="Exit Battery Bar", command=exit_app)
    menu.tk_popup(event.x_root, event.y_root)


def keep_on_top():
    root.attributes("-topmost", True)
    root.after(2500, keep_on_top)


# --- GUI Setup ---
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

# --- Register on every launch (keeps path fresh if EXE moves) ---
register_startup()

# --- Launch Everything ---
check_hardware()
render_loop()
keep_on_top()
root.mainloop()
