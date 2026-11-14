import os
import sys
import subprocess
from pathlib import Path
from typing import Tuple, List

# Ensure paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
STARTUP_DIR = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
SHORTCUT_PATH = STARTUP_DIR / "FridayRemoteCompanion.lnk"
VBS_PATH = PROJECT_ROOT / "friday_silent_runner.vbs"

def get_pythonw_path() -> Path:
    """Finds pythonw.exe (windowless Python) next to python.exe."""
    py_exe = Path(sys.executable)
    pyw_candidate = py_exe.parent / "pythonw.exe"
    if pyw_candidate.exists():
        return pyw_candidate
    return py_exe

def create_silent_vbs() -> Path:
    """Creates or updates the silent VBScript launcher."""
    pyw_exe = get_pythonw_path()
    runner_script = SCRIPT_DIR / "friday_runner.py"

    vbs_content = (
        "' Friday Silent Background Launcher (Zero Console Window)\n"
        "Set WshShell = CreateObject(\"WScript.Shell\")\n"
        f"WshShell.CurrentDirectory = \"{SCRIPT_DIR}\"\n"
        f"WshShell.Run \"\"\"{pyw_exe}\"\" \"\"{runner_script}\"\"\", 0, False\n"
    )

    with open(VBS_PATH, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    return VBS_PATH

def is_autostart_enabled() -> bool:
    """Checks if the startup shortcut exists in Windows Startup."""
    return SHORTCUT_PATH.exists()

def enable_autostart() -> Tuple[bool, str]:
    """
    Installs Friday into Windows Startup (shell:startup) to launch silently on boot.
    Returns (success, message).
    """
    if sys.platform != "win32":
        return False, "❌ Windows Auto-Start is only supported on Windows OS."

    try:
        # 1. Create the silent VBS launcher
        vbs_file = create_silent_vbs()

        # 2. Create the shortcut in shell:startup using a temp helper VBScript
        temp_vbs = Path(os.environ.get("TEMP", ".")) / "_make_startup_lnk.vbs"
        script_code = (
            "Set ws = CreateObject(\"WScript.Shell\")\n"
            f"Set sc = ws.CreateShortcut(\"{SHORTCUT_PATH}\")\n"
            f"sc.TargetPath = \"{vbs_file}\"\n"
            f"sc.WorkingDirectory = \"{PROJECT_ROOT}\"\n"
            "sc.Description = \"Friday Remote Companion Silent Auto-Start\"\n"
            "sc.WindowStyle = 7\n"  # Minimized / silent
            "sc.Save()\n"
        )

        with open(temp_vbs, "w", encoding="utf-8") as f:
            f.write(script_code)

        subprocess.run(["cscript", "//nologo", str(temp_vbs)], capture_output=True, timeout=5)
        try:
            temp_vbs.unlink(missing_ok=True)
        except Exception:
            pass

        if SHORTCUT_PATH.exists():
            return True, (
                "🚀 *Auto-Start on Boot ENABLED!*\n\n"
                "• **Status:** Active in Windows Startup (`shell:startup`)\n"
                "• **Mode:** Completely silent background daemon (no console window)\n"
                "• **Startup Shortcut:** `FridayRemoteCompanion.lnk`\n\n"
                "Friday will now start silently whenever your laptop boots or you log in.\n"
                "You can turn it off anytime by sending `/autostart off` or double-clicking `disable_autostart.bat`."
            )
        else:
            return False, "❌ Failed to create shortcut in Windows Startup folder."

    except Exception as e:
        return False, f"❌ Error configuring Windows Auto-Start: {e}"

def disable_autostart() -> Tuple[bool, str]:
    """
    Removes Friday from Windows Startup so it will NOT start on boot.
    Returns (success, message).
    """
    try:
        if SHORTCUT_PATH.exists():
            SHORTCUT_PATH.unlink()

        # Check if successfully removed
        if not SHORTCUT_PATH.exists():
            return True, (
                "🛑 *Auto-Start on Boot DISABLED!*\n\n"
                "• **Status:** Removed from Windows Startup (`shell:startup`)\n"
                "• Friday will no longer start automatically when your laptop boots.\n\n"
                "You can start it manually anytime using `start_friday.bat`, or re-enable boot startup by sending `/autostart on`."
            )
        return False, "❌ Failed to remove shortcut from Startup folder."

    except Exception as e:
        return False, f"❌ Error disabling Auto-Start: {e}"

def get_autostart_status() -> str:
    """Returns the current status of Windows Auto-Start."""
    enabled = is_autostart_enabled()
    running, pids = is_friday_running()

    running_desc = f"🟢 Running (PID: `{', '.join(map(str, pids))}`)" if running else "🔴 Stopped"
    autostart_desc = "🟢 **Enabled** (Starts silently on laptop boot)" if enabled else "⚪ **Disabled** (Manual start only)"

    return (
        f"⚙️ *Friday Auto-Start & Service Status*\n\n"
        f"• **Current Process:** {running_desc}\n"
        f"• **Boot Auto-Start:** {autostart_desc}\n"
        f"• **Startup Path:** `{SHORTCUT_PATH}`\n\n"
        f"💡 *Commands:*\n"
        f"• `/autostart on` — Enable start on boot\n"
        f"• `/autostart off` — Disable start on boot\n"
        f"• `/stop` — Stop current running instance"
    )

def is_friday_running() -> Tuple[bool, List[int]]:
    """Checks if Friday runner is currently running."""
    import psutil
    pids = []
    my_pid = os.getpid()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            pname = (p.info['name'] or '').lower()
            if not pname.startswith("python"):
                continue
            cmd = " ".join(p.info['cmdline'] or []).lower()
            if "friday_runner.py" in cmd and p.info['pid'] != my_pid:
                pids.append(p.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return len(pids) > 0, pids

def stop_all_friday_processes() -> Tuple[int, str]:
    """Terminates any running instances of friday_runner.py."""
    import psutil
    running, pids = is_friday_running()
    stopped = 0
    for pid in pids:
        try:
            psutil.Process(pid).terminate()
            stopped += 1
        except Exception:
            pass
    return stopped, f"Stopped {stopped} Friday instance(s)."

if __name__ == "__main__":
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").lower().strip()
    if arg in ["enable", "on", "install"]:
        ok, msg = enable_autostart()
        print(msg)
    elif arg in ["disable", "off", "uninstall", "remove"]:
        ok, msg = disable_autostart()
        print(msg)
    elif arg in ["stop", "kill"]:
        count, msg = stop_all_friday_processes()
        print(msg)
    else:
        print(get_autostart_status())
