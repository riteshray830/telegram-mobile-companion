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

def get_chrome_exe() -> Optional[Path]:
    for p in CHROME_PATHS:
        if p.exists():
            return p
    return None

def get_chrome_profiles() -> Dict[str, Dict[str, str]]:
    """
    Parses Chrome's Local State to discover all profile directory names,
    display names, and user email addresses.
    """
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
    return profiles

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
        search_terms = re_strip(lower, ["youtube", "search for", "search", "and play", "play", "open", "on"])
        if search_terms:
            encoded = urllib.parse.quote_plus(search_terms)
            return f"https://www.youtube.com/results?search_query={encoded}"
        return "https://www.youtube.com"

    # Google search
    if lower.startswith("google ") or lower.startswith("search ") or "search for " in lower:
        search_terms = re_strip(lower, ["google", "search for", "search", "open"])
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
        "x": "https://x.com",
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
    Launches Google Chrome directly into the specified profile, completely
    bypassing the 'Who is using Chrome?' profile picker screen.
    """
    chrome_exe = get_chrome_exe()
    if not chrome_exe:
        # Fallback to default browser if chrome not found
        if url:
            os.startfile(url)
            return True, f"🚀 Opened {url} in your default browser!"
        return False, "❌ Google Chrome executable was not found on this laptop."

    args = [str(chrome_exe), f"--profile-directory={profile_dir}"]
    if url:
        args.append(url)

    try:
        subprocess.Popen(args, shell=False)
        target_desc = f"to `{url}`" if url else ""
        return True, f"🚀 Opened Chrome directly into **{profile_dir}** {target_desc} (Profile picker bypassed!)"
    except Exception as e:
        return False, f"❌ Failed to launch Chrome: {e}"

def launch_app(app_target: str) -> Tuple[bool, str]:
    """Launches desktop apps, folders, or system utilities on the laptop."""
    lower = app_target.lower().strip()

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
        subprocess.Popen(["notepad.exe"])
        return True, "📝 Opened Notepad on your laptop."

    if any(k in lower for k in ["calc", "calculator"]):
        subprocess.Popen(["calc.exe"])
        return True, "🔢 Opened Calculator on your laptop."

    if any(k in lower for k in ["vs code", "vscode", "code"]):
        # Check if workspace path was given
        target_dir = r"D:\dev" if "dev" in lower else None
        cmd = ["code"]
        if target_dir:
            cmd.append(target_dir)
        try:
            subprocess.Popen(cmd, shell=True)
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
        subprocess.Popen(["powershell.exe"])
        return True, "⚡ Opened PowerShell terminal on your laptop."

    if "explorer" in lower or "files" in lower:
        subprocess.Popen(["explorer.exe"])
        return True, "📁 Opened File Explorer on your laptop."

    # Generic startfile attempt
    try:
        os.startfile(app_target)
        return True, f"🚀 Launched `{app_target}` on your laptop!"
    except Exception as e:
        return False, f"❌ Could not find or launch `{app_target}`: {e}"
