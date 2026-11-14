import os
import sys
import subprocess
import threading
from pathlib import Path
from PIL import Image, ImageDraw

import pystray
from pystray import MenuItem as item

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

def create_tray_icon_image():
    """Generates a sleek 64x64 glowing Friday 'F' icon."""
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Circle base
    d.ellipse((3, 3, 61, 61), fill=(18, 24, 38), outline=(0, 210, 255), width=3)
    # 'F' letter
    d.rectangle((20, 16, 44, 22), fill=(0, 210, 255))
    d.rectangle((20, 16, 26, 48), fill=(0, 210, 255))
    d.rectangle((20, 30, 40, 36), fill=(0, 210, 255))
    return img

def open_chat_log(icon, item):
    chat_file = PROJECT_ROOT / "CHAT.md"
    if chat_file.exists():
        os.startfile(chat_file)

def open_dev_folder(icon, item):
    dev_path = r"D:\dev"
    if os.path.exists(dev_path):
        os.startfile(dev_path)

def toggle_autostart(icon, item):
    try:
        import autostart_manager
        if autostart_manager.is_autostart_enabled():
            autostart_manager.disable_autostart()
        else:
            autostart_manager.enable_autostart()
    except Exception:
        pass

def is_autostart_checked(item):
    try:
        import autostart_manager
        return autostart_manager.is_autostart_enabled()
    except Exception:
        return False

def restart_friday(icon, item):
    try:
        import autostart_manager
        autostart_manager.stop_all_friday_processes()
        runner = SCRIPT_DIR / "friday_runner.py"
        subprocess.Popen([sys.executable, str(runner)], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    except Exception:
        pass

def stop_friday_action(icon, item):
    try:
        import autostart_manager
        autostart_manager.stop_all_friday_processes()
    except Exception:
        pass

def exit_tray(icon, item):
    icon.stop()

def run_tray():
    icon_img = create_tray_icon_image()
    
    menu = pystray.Menu(
        item("🟢 Friday Remote Companion", None, enabled=False),
        item("💬 View Chat Log (CHAT.md)", open_chat_log),
        item("📂 Open Dev Root (D:\\dev)", open_dev_folder),
        pystray.Menu.SEPARATOR,
        item("🚀 Run on Windows Boot", toggle_autostart, checked=is_autostart_checked),
        item("🔄 Restart Friday Daemon", restart_friday),
        item("🛑 Stop Friday Daemon", stop_friday_action),
        pystray.Menu.SEPARATOR,
        item("❌ Exit Tray Icon", exit_tray)
    )

    icon = pystray.Icon("FridayCompanion", icon_img, "Friday Remote Companion", menu)
    icon.run()

if __name__ == "__main__":
    run_tray()
