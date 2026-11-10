"""
PC Battery Bar (fixed version)

What changed compared to the old version:
  * Waits for the Windows taskbar to exist before showing the bar, and keeps
    re-raising / re-positioning it (survives slow logins, explorer.exe restarts,
    Windows updates, resolution / dock changes).
  * "Exit" no longer deletes the autostart entries.
  * Only one copy can run (named mutex), so Run key + Task Scheduler don't stack bars.
  * Task Scheduler entry is per-user, non-elevated, delayed 15 s (the old elevated /
    all-users version needs admin rights and failed silently).
  * Every error is written to %LOCALAPPDATA%\\BatteryBar\\battery_bar.log
    instead of being swallowed.
"""
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
import faulthandler
import logging
from ctypes import wintypes
from logging.handlers import RotatingFileHandler
from xml.sax.saxutils import escape

# --- App Identity ---
APP_NAME = "BatteryBar"
TASK_VERSION = "v2"          # bump to force the scheduled task to be rewritten

# ══════════════════════════════════════════════════════════════
#  LOGGING  (log + hard-crash dump in %LOCALAPPDATA%\BatteryBar)
# ══════════════════════════════════════════════════════════════
LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME)
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    LOG_DIR = os.environ.get("TEMP", ".")

log = logging.getLogger(APP_NAME)
log.setLevel(logging.INFO)
try:
    _fh = RotatingFileHandler(
        os.path.join(LOG_DIR, "battery_bar.log"),
        maxBytes=200_000, backupCount=2, encoding="utf-8",
    )
    _fh.setFormatter(logging.Formatter("%(asctime)s [pid %(process)d] %(levelname)s %(message)s"))
    log.addHandler(_fh)
except Exception:
    log.addHandler(logging.NullHandler())

try:
    _crash_file = open(os.path.join(LOG_DIR, "crash.log"), "a")
    faulthandler.enable(file=_crash_file)   # records hard crashes (e.g. Tk access violations)
except Exception:
    pass


def _log_uncaught(exc_type, exc, tb):
    log.error("Uncaught exception", exc_info=(exc_type, exc, tb))


sys.excepthook = _log_uncaught
if hasattr(threading, "excepthook"):
    threading.excepthook = lambda a: log.error(
        "Uncaught thread exception", exc_info=(a.exc_type, a.exc_value, a.exc_traceback)
    )

_last_logged = {}


def log_throttled(tag, msg):
    """Log the current exception at most once a minute per tag (avoids log spam)."""
    now = time.time()
    if now - _last_logged.get(tag, 0) > 60:
        _last_logged[tag] = now
        log.exception(msg)


# ══════════════════════════════════════════════════════════════
#  SINGLE INSTANCE  (so Run key + Task Scheduler never stack two bars)
# ══════════════════════════════════════════════════════════════
ERROR_ACCESS_DENIED = 5
ERROR_ALREADY_EXISTS = 183
_mutex_handle = None


def ensure_single_instance():
    """Return True if we are the only instance, False if another one is running."""
    global _mutex_handle
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        _mutex_handle = kernel32.CreateMutexW(None, False, "Local\\BatteryBar_SingleInstance")
        err = ctypes.get_last_error()
        if not _mutex_handle or err in (ERROR_ALREADY_EXISTS, ERROR_ACCESS_DENIED):
            return False
    except Exception:
        log.exception("Single-instance check failed (continuing anyway)")
    return True


# ══════════════════════════════════════════════════════════════
#  AUTOSTART
#  Layer 1: HKCU Run key   (backup, starts immediately at logon)
#  Layer 2: Task Scheduler (per-user, 15 s after logon, non-elevated)
# ══════════════════════════════════════════════════════════════
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"


def launch_command():
    """Return (program, arguments) that starts this app."""
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    script = os.path.abspath(__file__)
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return (pythonw if os.path.exists(pythonw) else sys.executable), f'"{script}"'


def run_key_value():
    prog, args = launch_command()
    return f'"{prog}" {args}'.strip()      # quoted: paths with spaces are safe


def _run(cmd):
    # stdin=DEVNULL matters: in a windowed (--noconsole) exe there is no stdin
    # handle and subprocess can fail with "WinError 6: The handle is invalid".
    return subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        errors="ignore",
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def register_hkcu():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, run_key_value())
        log.info("HKCU Run entry set: %s", run_key_value())
    except Exception:
        log.exception("HKCU Run registration failed")


def check_startup_approved():
    """Windows lets you disable a Run entry (Settings > Apps > Startup). Just report it."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as key:
            data, _ = winreg.QueryValueEx(key, APP_NAME)
            if data and (data[0] & 1):
                log.warning("Windows shows the startup entry as DISABLED "
                            "(Settings > Apps > Startup) - turn it back on.")
    except FileNotFoundError:
        pass
    except Exception:
        log.exception("StartupApproved check failed")


def build_task_xml(prog, args, workdir, user, marker):
    user_xml = f"<UserId>{escape(user)}</UserId>" if user else ""
    args_xml = f"<Arguments>{escape(args)}</Arguments>" if args else ""
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{escape(marker)}</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      {user_xml}
      <Delay>PT15S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      {user_xml}
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>99</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(prog)}</Command>
      {args_xml}
      <WorkingDirectory>{escape(workdir)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""


def task_matches(marker):
    """True if the scheduled task already exists with our current definition."""
    try:
        r = _run(["schtasks", "/Query", "/TN", APP_NAME, "/XML"])
        return r.returncode == 0 and escape(marker) in r.stdout
    except Exception:
        return False


def register_task_scheduler():
    try:
        prog, args = launch_command()
        workdir = os.path.dirname(prog)
        domain = os.environ.get("USERDOMAIN", "")
        name = os.environ.get("USERNAME", "")
        user = f"{domain}\\{name}" if domain and name else name
        marker = f"{APP_NAME} {TASK_VERSION} | {prog} {args}".strip()

        if task_matches(marker):
            log.info("Scheduled task already up to date")
            return

        xml_path = os.path.join(os.environ.get("TEMP", LOG_DIR), "batterybar_task.xml")
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(build_task_xml(prog, args, workdir, user, marker))
        try:
            r = _run(["schtasks", "/Create", "/TN", APP_NAME, "/XML", xml_path, "/F"])
        finally:
            try:
                os.remove(xml_path)
            except Exception:
                pass

        if r.returncode == 0:
            log.info("Scheduled task created/updated")
        else:
            log.error("schtasks /Create failed (code %s): %s %s",
                      r.returncode, r.stdout.strip(), r.stderr.strip())
    except Exception:
        log.exception("Task Scheduler registration failed")


def register_all():
    try:
        check_startup_approved()
        register_hkcu()
        register_task_scheduler()
    except Exception:
        log.exception("register_all failed")


def unregister_all():
    """Only used by 'Remove from startup & exit'."""
    for hive, label in ((winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")):
        try:
            with winreg.OpenKey(hive, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, APP_NAME)
            log.info("%s Run entry removed", label)
        except FileNotFoundError:
            pass
        except Exception:
            log.warning("Could not remove %s Run entry (may need admin)", label)
    try:
        _run(["schtasks", "/Delete", "/TN", APP_NAME, "/F"])
        log.info("Scheduled task removed")
    except Exception:
        log.exception("Could not remove scheduled task")


# ══════════════════════════════════════════════════════════════
#  WINDOW PLACEMENT  (taskbar-aware, keeps the bar on top)
# ══════════════════════════════════════════════════════════════
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL

HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0010, 0x0040

TASKBAR_WAIT_SECONDS = 120   # how long to wait for the taskbar at login before showing anyway
MAINTAIN_MS = 1500           # how often we re-raise / re-position the bar


def find_taskbar():
    return user32.FindWindowW("Shell_TrayWnd", None)


def target_position():
    """Left edge of the taskbar, vertically centred in it (falls back to old formula)."""
    try:
        hwnd = find_taskbar()
        if hwnd:
            r = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                w, h = r.right - r.left, r.bottom - r.top
                if w > h >= bar_height and r.top > 0:
                    return r.left + 10, r.top + (h - bar_height) // 2
    except Exception:
        log_throttled("pos", "taskbar position lookup failed")
    return 10, root.winfo_screenheight() - 48


def raise_topmost():
    """Real SetWindowPos call. Tk's attributes('-topmost', True) does nothing if the
    flag is already set, so it cannot lift the bar back above a re-created taskbar."""
    child = root.winfo_id()
    hwnd = user32.GetParent(child) or child
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)


_last_pos = None


def maintain():
    """Runs forever: re-place the bar if the taskbar moved/was re-created, keep on top."""
    global _last_pos
    try:
        pos = target_position()
        if pos != _last_pos:
            root.geometry(f"{bar_width}x{bar_height}+{pos[0]}+{pos[1]}")
            _last_pos = pos
        raise_topmost()
    except Exception:
        log_throttled("maintain", "maintain loop failed")
    finally:
        root.after(MAINTAIN_MS, maintain)


def show_when_taskbar_ready(waited=0):
    if find_taskbar() or waited >= TASKBAR_WAIT_SECONDS:
        uptime = int(time.time() - psutil.boot_time())
        log.info("Showing bar (waited %ss for taskbar, taskbar found=%s, uptime=%ss)",
                 waited, bool(find_taskbar()), uptime)
        root.deiconify()
        root.update_idletasks()
        maintain()
    else:
        root.after(1000, lambda: show_when_taskbar_ready(waited + 1))


# ══════════════════════════════════════════════════════════════
#  EXIT
# ══════════════════════════════════════════════════════════════
def exit_app():
    """Close the bar for this session. Autostart stays, so it is back next login."""
    log.info("Exit chosen from menu (autostart kept)")
    root.destroy()


def remove_startup_and_exit():
    log.info("'Remove from startup & exit' chosen")
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
        log_throttled("battery", "battery read failed")
    finally:
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
    refresh_rate = 1000
    try:
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
    except Exception:
        log_throttled("render", "render failed")
    finally:
        # always schedule the next frame, even after an error
        root.after(refresh_rate, render_loop)


def show_right_click_menu(event):
    menu = tk.Menu(root, tearoff=0, bg="#202020", fg="white", activebackground="#00BFFF")
    menu.add_command(label="Change Colors", command=pick_color)
    menu.add_separator()
    menu.add_command(label="Exit Battery Bar", command=exit_app)
    menu.add_command(label="Remove from startup & exit", command=remove_startup_and_exit)
    menu.tk_popup(event.x_root, event.y_root)


# ══════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════
if not ensure_single_instance():
    log.info("Another instance is already running - this one exits quietly")
    sys.exit(0)

log.info("Starting. exe=%s frozen=%s uptime=%ss",
         sys.executable, getattr(sys, "frozen", False), int(time.time() - psutil.boot_time()))
try:
    if psutil.sensors_battery() is None:
        log.warning("psutil reports no battery on this machine")
except Exception:
    log.exception("Initial battery probe failed")

root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)
root.withdraw()                      # stay hidden until the taskbar exists
root.report_callback_exception = lambda exc, val, tb: log.error(
    "Tk callback error", exc_info=(exc, val, tb))

bg_color = '#202020'
root.configure(bg=bg_color)

bar_width  = 190
bar_height = 40
_x, _y = target_position()
root.geometry(f"{bar_width}x{bar_height}+{_x}+{_y}")

canvas = tk.Canvas(root, width=bar_width, height=bar_height, highlightthickness=0, bg=bg_color)
canvas.pack()

root.bind("<Button-1>", lambda e: pick_color())
root.bind("<Button-3>", show_right_click_menu)

# Autostart registration runs in the background so it never delays the bar
threading.Thread(target=register_all, daemon=True).start()

check_hardware()
render_loop()
show_when_taskbar_ready()
root.mainloop()
log.info("Main loop ended")
