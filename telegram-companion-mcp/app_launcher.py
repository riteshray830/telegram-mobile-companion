import os
import sys
import json
import urllib.parse
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
]

# In-memory caches for sub-millisecond execution
_CACHED_CHROME_EXE: Optional[Path] = None
_CACHED_PROFILES: Optional[Dict[str, Dict[str, str]]] = None

def get_chrome_exe() -> Optional[Path]:
    global _CACHED_CHROME_EXE
    if _CACHED_CHROME_EXE and _CACHED_CHROME_EXE.exists():
        return _CACHED_CHROME_EXE
    for p in CHROME_PATHS:
        if p.exists():
            _CACHED_CHROME_EXE = p
            return p
    return None

def get_chrome_profiles() -> Dict[str, Dict[str, str]]:
    """
    Parses Chrome's Local State to discover all profile directory names,
    display names, and user email addresses with in-memory caching.
    """
    global _CACHED_PROFILES
    if _CACHED_PROFILES:
        return _CACHED_PROFILES

    state_path = Path.home() / r"AppData\Local\Google\Chrome\User Data\Local State"
    profiles = {}
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            cache = d.get("profile", {}).get("info_cache", {})
            for dir_name, info in cache.items():
                profiles[dir_name] = {
                    "name": info.get("name", "Unknown"),
                    "email": info.get("user_name", "")
                }
        except Exception:
            pass
    if not profiles:
        # Fallback default
        profiles["Default"] = {"name": "Default", "email": "riteshray830@gmail.com"}

    _CACHED_PROFILES = profiles
    return profiles

# Pre-warm caches immediately on module load
try:
    get_chrome_exe()
    get_chrome_profiles()
except Exception:
    pass

def is_workstation_locked() -> bool:
    """Checks if the Windows desktop is currently locked."""
    if sys.platform != "win32":
        return False
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            pname = (p.info['name'] or '').lower()
            if pname in ['lockapp.exe', 'logonui.exe']:
                return True
    except Exception:
        pass
    return False

def activate_display_and_foreground(window_class_substr: str = "Chrome_WidgetWin"):
    """Wakes the display and brings target windows to the active foreground."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 1. Wake screen if dimmed or idling
        kernel32.SetThreadExecutionState(0x80000002 | 0x00000001)
        user32.SendMessageW(0xFFFF, 0x0112, 0xF170, -1)
        user32.mouse_event(0x0001, 1, 1, 0, 0)
        user32.mouse_event(0x0001, -1, -1, 0, 0)

        # 2. Bring window to front
        def enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls, 256)
                if window_class_substr.lower() in cls.value.lower():
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass

def resolve_chrome_profile(user_text: str) -> Tuple[str, str]:
    """
    Resolves requested profile from user text.
    Returns: (directory_name, friendly_label)
    Defaults to 'Default' (riteshray830@gmail.com) if no specific profile is mentioned.
    """
    text = user_text.lower()
    profiles = get_chrome_profiles()

    # Specific profile matching
    if "snigdha" in text:
        for k, v in profiles.items():
            if "snigdha" in v["name"].lower() or "snigdha" in v["email"].lower():
                return k, f"{v['name']} ({v['email']})"
        return "Profile 8", "Snigdha"

    if "318" in text:
        for k, v in profiles.items():
            if "318" in v["email"]:
                return k, f"{v['name']} ({v['email']})"
        return "Profile 10", "riteshray318"

    if "566" in text:
        for k, v in profiles.items():
            if "566" in v["email"]:
                return k, f"{v['name']} ({v['email']})"
        return "Profile 5", "riteshray566"

    if "roy" in text or "roy830" in text:
        for k, v in profiles.items():
            if "roy" in v["email"]:
                return k, f"{v['name']} ({v['email']})"
        return "Profile 3", "riteshroy830"

    # Default profile (Primary: riteshray830@gmail.com)
    def_info = profiles.get("Default", {"name": "Primary", "email": "riteshray830@gmail.com"})
    return "Default", f"{def_info['name']} ({def_info['email']})"

def parse_url_or_search(query: str) -> Optional[str]:
    """Smartly normalizes search queries or website names to full URLs."""
    q = query.strip()
    if not q:
        return None

    # Already a full URL
    if q.startswith("http://") or q.startswith("https://"):
        return q

    lower = q.lower()
    
    # YouTube search
    if "youtube" in lower:
        # Check if searching for something
        search_terms = re_strip(lower, [
            "youtube", "search for", "search", "and play", "play", "open", "on",
            "in chrome", "on chrome", "using chrome", "in browser", "with chrome"
        ])
        if search_terms:
            encoded = urllib.parse.quote_plus(search_terms)
            return f"https://www.youtube.com/results?search_query={encoded}"
        return "https://www.youtube.com"

    # Google search
    if lower.startswith("google ") or lower.startswith("search ") or "search for " in lower:
        search_terms = re_strip(lower, [
            "google", "search for", "search", "open",
            "in chrome", "on chrome", "using chrome", "in browser", "with chrome"
        ])
        if search_terms:
            encoded = urllib.parse.quote_plus(search_terms)
            return f"https://www.google.com/search?q={encoded}"
        return "https://www.google.com"

    # Common domains
    domain_map = {
        "github": "https://github.com",
        "reddit": "https://reddit.com",
        "chatgpt": "https://chatgpt.com",
        "netflix": "https://netflix.com",
        "twitter": "https://x.com",
        "x.com": "https://x.com",
        "linkedin": "https://linkedin.com",
        "gmail": "https://mail.google.com",
        "drive": "https://drive.google.com",
        "claude": "https://claude.ai",
        "ai studio": "https://aistudio.google.com"
    }
    for k, v in domain_map.items():
        if k in lower:
            return v

    # Dot com / org check
    if "." in q and not " " in q:
        return f"https://{q}"

    return None

def re_strip(text: str, remove_words: list) -> str:
    cleaned = text
    for w in sorted(remove_words, key=len, reverse=True):
        cleaned = cleaned.replace(w, " ")
    return " ".join(cleaned.split()).strip()

def launch_chrome(url: Optional[str] = None, profile_dir: str = "Default") -> Tuple[bool, str]:
    """
    Launches Google Chrome instantly directly into the specified profile,
    completely bypassing the 'Who is using Chrome?' profile picker screen.
    Optimized for <10ms execution and window foregrounding.
    """
    chrome_exe = get_chrome_exe()
    if not chrome_exe:
        # Fallback to default browser if chrome not found
        if url:
            os.startfile(url)
            return True, f"🚀 Opened {url} in your default browser!"
        return False, "❌ Google Chrome executable was not found on this laptop."

    # Performance flags: bypass default check, bypass first run, bypass profile picker
    args = [
        str(chrome_exe),
        f"--profile-directory={profile_dir}",
        "--no-default-browser-check",
        "--no-first-run"
    ]
    # Pass target URL or newtab so Chrome immediately activates a window
    target_url = url or "chrome://newtab"
    args.append(target_url)

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        subprocess.Popen(args, creationflags=creation_flags, close_fds=True, shell=False)
        
        # Bring to front & wake display
        activate_display_and_foreground("Chrome_WidgetWin")

        locked = is_workstation_locked()
        target_desc = f"to `{url}`" if url else ""
        
        if locked:
            return True, (
                f"⚡ **Chrome Launched Instantly!**\n\n"
                f"• Profile: **{profile_dir}** {target_desc}\n"
                f"• Profile picker: **Bypassed**\n\n"
                f"💡 *Note:* Your laptop screen is currently **locked**. Chrome is running in the background and will be right on your screen as soon as you unlock your laptop!"
            )
        else:
            return True, f"⚡ **Opened Chrome Instantly!** Switched directly to **{profile_dir}** {target_desc}."
    except Exception as e:
        return False, f"❌ Failed to launch Chrome: {e}"

def launch_app(app_target: str) -> Tuple[bool, str]:
    """Launches desktop apps, folders, or system utilities on the laptop."""
    lower = app_target.lower().strip()
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    # 1. Folders
    if any(k in lower for k in ["dev folder", "dev directory", "d:\\dev", "dev"]):
        dev_path = r"D:\dev"
        if os.path.exists(dev_path):
            os.startfile(dev_path)
            return True, "📂 Opened your `D:\\dev` folder in File Explorer on your laptop!"

    if "downloads" in lower:
        d_path = str(Path.home() / "Downloads")
        os.startfile(d_path)
        return True, "📂 Opened your `Downloads` folder on your laptop!"

    if "desktop" in lower:
        d_path = str(Path.home() / "Desktop")
        os.startfile(d_path)
        return True, "📂 Opened your `Desktop` folder on your laptop!"

    # 2. Known desktop apps
    if "notepad" in lower:
        subprocess.Popen(["notepad.exe"], creationflags=creation_flags, close_fds=True)
        return True, "📝 Opened Notepad on your laptop."

    if any(k in lower for k in ["calc", "calculator"]):
        subprocess.Popen(["calc.exe"], creationflags=creation_flags, close_fds=True)
        return True, "🔢 Opened Calculator on your laptop."

    if any(k in lower for k in ["vs code", "vscode", "code"]):
        target_dir = r"D:\dev" if "dev" in lower else None
        cmd = ["code"]
        if target_dir:
            cmd.append(target_dir)
        try:
            subprocess.Popen(cmd, shell=True, creationflags=creation_flags, close_fds=True)
            return True, f"💻 Opened VS Code on your laptop!"
        except Exception:
            return False, "Could not launch VS Code (verify `code` is on PATH)."

    if "spotify" in lower:
        try:
            os.startfile("spotify:")
            return True, "🎵 Opened Spotify on your laptop!"
        except Exception as e:
            return False, f"Could not launch Spotify: {e}"

    if "terminal" in lower or "powershell" in lower:
        subprocess.Popen(["powershell.exe"], creationflags=creation_flags, close_fds=True)
        return True, "⚡ Opened PowerShell terminal on your laptop."

    if "cmd" in lower or "command prompt" in lower:
        subprocess.Popen(["cmd.exe"], creationflags=creation_flags, close_fds=True)
        return True, "⚡ Opened Command Prompt on your laptop."

    if "task manager" in lower or "taskmgr" in lower:
        subprocess.Popen(["taskmgr.exe"], creationflags=creation_flags, close_fds=True)
        return True, "📊 Opened Windows Task Manager on your laptop."

    if "paint" in lower:
        subprocess.Popen(["mspaint.exe"], creationflags=creation_flags, close_fds=True)
        return True, "🎨 Opened MS Paint on your laptop."

    if "settings" in lower:
        os.startfile("ms-settings:")
        return True, "⚙️ Opened Windows Settings on your laptop."

    if "camera" in lower:
        os.startfile("microsoft.windows.camera:")
        return True, "📷 Opened Windows Camera on your laptop."

    if "control panel" in lower:
        subprocess.Popen(["control.exe"], creationflags=creation_flags, close_fds=True)
        return True, "🎛️ Opened Control Panel on your laptop."

    if "explorer" in lower or "files" in lower:
        subprocess.Popen(["explorer.exe"], creationflags=creation_flags, close_fds=True)
        return True, "📁 Opened File Explorer on your laptop."

    # Generic startfile attempt
    try:
        os.startfile(app_target)
        return True, f"🚀 Launched `{app_target}` on your laptop!"
    except Exception as e:
        return False, f"❌ Could not find or launch `{app_target}`: {e}"
