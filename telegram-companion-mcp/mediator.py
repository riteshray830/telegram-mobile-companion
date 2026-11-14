import re
import sys
import os
import time
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List

import system_controls
import app_launcher

def format_natural_battery() -> str:
    """Translates battery data into friendly, natural conversation."""
    import psutil
    battery = psutil.sensors_battery()
    if not battery:
        return "Your laptop doesn't seem to have a battery detected (it might be a desktop or running on pure AC power)."

    pct = battery.percent
    plugged = battery.power_plugged

    if plugged:
        status_text = "plugged in and charging" if pct < 100 else "plugged in and fully charged"
    else:
        status_text = "running on battery (unplugged)"

    # Get health details
    rep = system_controls.get_battery_report()
    health_match = re.search(r"Battery Health:\* `([\d\.]+)%`", rep)
    cycles_match = re.search(r"Cycle Count:\* `(\d+)`", rep)

    health_info = ""
    if health_match and cycles_match:
        health_pct = health_match.group(1)
        cycles = cycles_match.group(1)
        health_info = f" Overall battery health is in good shape at {health_pct}% across {cycles} cycles."

    urgency = ""
    if not plugged and pct <= 15:
        urgency = " ⚠️ It's getting pretty low, so you might want to plug in the charger soon!"

    return f"Your laptop is currently at **{pct}%** and it is **{status_text}**.{health_info}{urgency}"

def format_natural_health() -> str:
    """Translates CPU, RAM, and Disk into everyday human speech."""
    import psutil
    cpu = psutil.cpu_percent(interval=0.4)
    ram = psutil.virtual_memory()
    used_ram = round(ram.used / (1024**3), 1)
    total_ram = round(ram.total / (1024**3), 1)
    free_ram = round(ram.available / (1024**3), 1)

    # Disks
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
            free_gb = round(u.free / (1024**3), 1)
            disks.append(f"{free_gb} GB free on your {part.mountpoint.replace(':', '')} drive")
        except Exception:
            pass
    disk_str = ", and ".join(disks) if disks else "plenty of disk space"

    load_desc = "running very cool and relaxed" if cpu < 30 else ("working fairly hard" if cpu < 70 else "under heavy load right now")

    return (
        f"Here's how your laptop is doing right now:\n\n"
        f"• **Performance:** Your CPU is {load_desc} ({cpu}% usage).\n"
        f"• **Memory (RAM):** You have {free_ram} GB free out of {total_ram} GB (using {used_ram} GB).\n"
        f"• **Storage:** You have {disk_str}."
    )

def format_natural_storage() -> str:
    """Translates disk space into clear English."""
    import psutil
    parts_info = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
            free_gb = round(u.free / (1024**3), 1)
            total_gb = round(u.total / (1024**3), 1)
            pct = u.percent
            parts_info.append(f"• **Drive {part.mountpoint}:** {free_gb} GB free out of {total_gb} GB ({pct}% used)")
        except Exception:
            pass
    return "Here is your current storage breakdown:\n\n" + "\n".join(parts_info)

def format_natural_wifi() -> str:
    """Translates Wi-Fi network info into natural conversation."""
    raw = system_controls.get_wifi_status()
    ssid_match = re.search(r"SSID:\* `([^`]+)`", raw)
    signal_match = re.search(r"Signal Strength:\* `([^`]+)`", raw)

    if ssid_match and ssid_match.group(1) != "Disconnected":
        ssid = ssid_match.group(1)
        signal = signal_match.group(1) if signal_match else "good"
        return f"You're currently connected to Wi-Fi network **'{ssid}'** with a **{signal}** signal strength."
    return "Your laptop doesn't seem to be connected to Wi-Fi right now."

def format_natural_processes() -> str:
    """Summarizes top memory consumers in plain words."""
    import psutil
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            mem = round(p.info['memory_info'].rss / (1024 * 1024), 0)
            procs.append((p.info['name'], int(mem), p.info['pid']))
        except Exception:
            pass
    procs.sort(key=lambda x: x[1], reverse=True)
    top_3 = procs[:4]
    lines = [f"• **{name}** (taking about {mem} MB, PID: {pid})" for name, mem, pid in top_3]
    return (
        "Here are the biggest apps currently running on your laptop:\n\n"
        + "\n".join(lines)
        + "\n\nIf you'd like me to close any of them, just tell me: *'close cmd'* or *'kill [PID]'*."
    )

class MediatorResult:
    """Encapsulates the response from the human mediator worker."""
    def __init__(
        self,
        handled: bool = False,
        reply: Optional[str] = None,
        photo_path: Optional[Path] = None,
        doc_path: Optional[Path] = None,
        buttons: Optional[List[List[Dict[str, str]]]] = None
    ):
        self.handled = handled
        self.reply = reply
        self.photo_path = photo_path
        self.doc_path = doc_path
        self.buttons = buttons

    def __bool__(self):
        return self.handled

    def __iter__(self):
        return iter((self.handled, self.reply, self.photo_path, self.doc_path, self.buttons))

    def __repr__(self):
        return f"<MediatorResult handled={self.handled} reply={bool(self.reply)} photo={bool(self.photo_path)} doc={bool(self.doc_path)} buttons={bool(self.buttons)}>"

class MediatorWorker:
    """
    Intelligent Conversational Mediator & Translator:
    Understands human speech, executes laptop commands automatically,
    and returns warm, conversational responses without technical jargon.
    """

    def process_request(self, user_text: str) -> MediatorResult:
        """
        Analyzes the user's plain English message.
        Returns: MediatorResult(handled, reply, photo_path, doc_path, buttons)
        """
        raw_text = user_text.strip()
        text = raw_text.lower()

        # Tokenize words for precise matching
        words = set(re.findall(r'[a-z0-9_\-\./]+', text))

        # ------------------------------------------------------------------
        # 0. Remote Stop / Shutdown Trigger
        # ------------------------------------------------------------------
        if text.startswith(("/stop", "/exit", "/shutdown", "/killbot")) or any(
            p in text for p in [
                "stop friday", "close friday", "exit friday", "shutdown friday", "turn off friday",
                "stop tool", "close tool", "stop bot", "close bot", "friday band karo", "bot band karo"
            ]
        ) or (
            any(w in words for w in ["stop", "close", "shutdown", "exit", "band"]) and any(w in words for w in ["friday", "bot", "tool", "companion"])
        ):
            return MediatorResult(True, "__FRIDAY_SHUTDOWN__")

        # ------------------------------------------------------------------
        # 0b. Windows Auto-Start on Boot Intent
        # ------------------------------------------------------------------
        if "autostart" in text or "auto start" in text or "auto-start" in text or text.startswith("/autostart"):
            import autostart_manager
            if any(k in text for k in ["on", "enable", "activate", "chalu", "install"]):
                ok, msg = autostart_manager.enable_autostart()
                return MediatorResult(True, msg)
            elif any(k in text for k in ["off", "disable", "deactivate", "band", "remove", "uninstall"]):
                ok, msg = autostart_manager.disable_autostart()
                return MediatorResult(True, msg)
            else:
                return MediatorResult(True, autostart_manager.get_autostart_status())

        # ------------------------------------------------------------------
        # 1. Volume & Audio Control Intent
        # ------------------------------------------------------------------
        if any(w in words for w in ["mute", "unmute", "/mute", "silence"]) or "awaz band" in text or "sound off" in text:
            return MediatorResult(True, system_controls.control_volume("mute"))

        if any(p in text for p in ["volume up", "vol up", "/volup", "sound up", "awaz badhao", "louder", "sound badhao", "increase volume"]):
            return MediatorResult(True, system_controls.control_volume("up"))

        if any(p in text for p in ["volume down", "vol down", "/voldown", "sound down", "awaz kam karo", "quieter", "lower volume", "decrease volume"]):
            return MediatorResult(True, system_controls.control_volume("down"))

        # ------------------------------------------------------------------
        # 2. Media Playback Control Intent
        # ------------------------------------------------------------------
        if any(p in text for p in ["next song", "next track", "skip song", "skip track", "agla song", "/next"]):
            return MediatorResult(True, system_controls.control_media("next"))

        if any(p in text for p in ["prev song", "previous song", "prev track", "previous track", "pichla song", "/prev"]):
            return MediatorResult(True, system_controls.control_media("prev"))

        if any(p in text for p in ["stop music", "stop song", "stop playback"]):
            return MediatorResult(True, system_controls.control_media("stop"))

        # Play/Pause toggle (only if not searching a song e.g. "play bohemian rhapsody on youtube")
        if text in ["play", "pause", "/play", "/pause", "play/pause", "resume", "pause music", "resume music", "play music", "gana roko", "gana chalao"] or (
            any(w in words for w in ["pause", "resume"]) and not any(k in text for k in ["youtube", "video", "download", "search"])
        ):
            return MediatorResult(True, system_controls.control_media("play_pause"))

        # ------------------------------------------------------------------
        # 3. Screen Brightness Control Intent
        # ------------------------------------------------------------------
        if "brightness" in text or "chamak" in text or "/brightness" in text:
            num_match = re.search(r'\b(\d{1,3})\b', text)
            if num_match and 0 <= int(num_match.group(1)) <= 100:
                lvl = int(num_match.group(1))
                return MediatorResult(True, system_controls.set_brightness(lvl))
            elif any(k in text for k in ["up", "increase", "more", "badhao"]):
                return MediatorResult(True, system_controls.set_brightness(100))
            elif any(k in text for k in ["down", "decrease", "less", "lower", "kam"]):
                return MediatorResult(True, system_controls.set_brightness(50))
            else:
                return MediatorResult(True, system_controls.get_brightness())

        # ------------------------------------------------------------------
        # 4. Lock Screen Intent
        # ------------------------------------------------------------------
        if ("lock" in words or "/lock" in words or "lock karo" in text or "screen lock" in text) and not any(neg in text for neg in ["unlock", "clock", "block", "dont", "don't"]):
            res = system_controls.lock_workstation()
            if "Successfully" in res:
                return MediatorResult(True, "🔒 Done! I've locked your laptop screen for you. Your laptop is now secured.")
            return MediatorResult(True, res)

        # ------------------------------------------------------------------
        # 5. Screenshot Intent
        # ------------------------------------------------------------------
        if any(st in words for st in ["screenshot", "ss", "/screenshot", "/ss"]) or any(st in text for st in ["screen capture", "snap screen", "show me my screen", "what is on my screen", "what's on my screen", "see my screen", "screen dikhao", "photo of screen", "take a screenshot"]):
            path, msg = system_controls.take_screenshot()
            if path:
                return MediatorResult(True, "Here's what is currently on your laptop screen! 📸", photo_path=path)
            return MediatorResult(True, "I couldn't grab the screen right now because the display is locked or turned off.")

        # ------------------------------------------------------------------
        # 5b. Desk / Room Security Webcam Snap Intent
        # ------------------------------------------------------------------
        if any(wt in words for wt in ["webcam", "/webcam", "/camera", "/cam"]) or any(
            p in text for p in [
                "desk photo", "desk snap", "room photo", "room snap", "take webcam photo",
                "take camera photo", "take photo", "take a photo", "take a picture",
                "take picture", "security snap", "front camera", "webcam photo", "webcam snap"
            ]
        ):
            import webcam_snap
            ok, cam_path, cam_msg = webcam_snap.take_webcam_photo()
            if ok and cam_path:
                return MediatorResult(True, "📷 Here's a live photo from your laptop webcam!", photo_path=cam_path)
            return MediatorResult(True, cam_msg)

        # ------------------------------------------------------------------
        # 5c. Shared Clipboard Bridge Intent (Sync Phone <-> Laptop)
        # ------------------------------------------------------------------
        clip_copy_match = re.search(r'^(?:copy|clip|/copy|set\s+clipboard|copy\s+to\s+laptop)\s*[:\s]\s*(.+)', text, re.DOTALL)
        if clip_copy_match:
            import clipboard_bridge
            raw_copy_match = re.search(r'^(?:copy|clip|/copy|set\s+clipboard|copy\s+to\s+laptop)\s*[:\s]\s*(.+)', raw_text, re.DOTALL | re.IGNORECASE)
            text_to_copy = raw_copy_match.group(1).strip() if raw_copy_match else clip_copy_match.group(1).strip()
            ok, res_msg = clipboard_bridge.set_clipboard_content(text_to_copy)
            return MediatorResult(True, res_msg)

        if text in ["/clip", "/clipboard", "clip", "clipboard"] or text.startswith(("/clip", "/clipboard")) or any(ct in words for ct in ["clipboard", "/clip", "/clipboard", "clip"]) or any(
            p in text for p in [
                "get clipboard", "read clipboard", "show clipboard", "what is on my clipboard",
                "what's on my clipboard", "laptop clipboard", "clipboard content", "clipboard status"
            ]
        ):
            import clipboard_bridge
            ok, res_msg = clipboard_bridge.get_clipboard_content()
            return MediatorResult(True, res_msg)

        # ------------------------------------------------------------------
        # 5d. Remote File Transfer Intent (Send File from Laptop to Phone)
        # ------------------------------------------------------------------
        file_match = re.search(r'^(?:/file|/download|send\s+file|send\s+me|download|get\s+file|fetch\s+file|fetch)\s+(.+)', text)
        if file_match and not any(neg in text for neg in ["youtube", "video", "song", "app", "chrome", "vscode", "netflix", "spotify"]):
            import file_transfer
            raw_file_match = re.search(r'^(?:/file|/download|send\s+file|send\s+me|download|get\s+file|fetch\s+file|fetch)\s+(.+)', raw_text, re.IGNORECASE)
            target_query = raw_file_match.group(1).strip() if raw_file_match else file_match.group(1).strip()
            file_path, status_msg = file_transfer.resolve_file_to_send(target_query)
            if file_path:
                return MediatorResult(True, f"📁 Found `{file_path.name}`. Sending to your phone...", doc_path=file_path)
            return MediatorResult(True, status_msg)

        # ------------------------------------------------------------------
        # 5e. Dev Server Crash Watchdog Intent
        # ------------------------------------------------------------------
        unwatch_match = re.search(r'^(?:/unwatch|unwatch|stop\s+watching|stop\s+watch)\s+(.+)', text)
        if unwatch_match:
            import dev_watchdog
            target = unwatch_match.group(1).strip()
            ok, res_msg = dev_watchdog.remove_watch_target(target)
            return MediatorResult(True, res_msg)

        if any(wt in words for wt in ["/watchers", "/watchdog", "watchers"]) or any(
            p in text for p in [
                "watch status", "dev servers", "server status", "watch list", "watched servers",
                "are servers up", "is server up", "check servers"
            ]
        ) or text in ["/watch", "watch"]:
            import dev_watchdog
            return MediatorResult(True, dev_watchdog.get_watch_status())

        watch_match = re.search(r'^(?:/watch|watch|monitor)\s+([a-zA-Z0-9_\-\.:/]+)', text)
        if watch_match:
            import dev_watchdog
            target = watch_match.group(1).strip()
            ok, res_msg = dev_watchdog.add_watch_target(target)
            return MediatorResult(True, res_msg)

        # ------------------------------------------------------------------
        # 5f. Remote Git Command Center Intent
        # ------------------------------------------------------------------
        git_match = re.search(r'^(?:/git|git\s+status|git\s+diff|git\s+check|repo\s+status|git\s+center|git)(?:\s+(.+))?$', text)
        if git_match and (text.startswith(("/git", "git ", "git")) or "repo status" in text):
            hint = git_match.group(1).strip() if git_match.group(1) else None
            import git_center
            report_msg, buttons = git_center.get_git_status_report(hint)
            return MediatorResult(True, report_msg, buttons=buttons)

        # ------------------------------------------------------------------
        # 6. Battery / Power / Charging Intent
        # ------------------------------------------------------------------
        battery_triggers = ["battery", "charging", "charger", "plugged in", "juice", "power", "/battery"]
        if (any(b in text for b in battery_triggers) or "battery kitni" in text or "kitni battery" in text) and not any(neg in text for neg in ["not", "dont", "code"]):
            return MediatorResult(True, format_natural_battery())

        # ------------------------------------------------------------------
        # 7. Storage / Disk Space Intent
        # ------------------------------------------------------------------
        storage_triggers = ["storage", "disk", "disks", "drives", "hard drive", "hard disk", "free space", "space left", "c drive", "d drive", "/storage", "/disk"]
        if (any(st in words for st in ["storage", "disk", "disks", "drives", "/storage", "/disk"]) or any(st in text for st in ["disk space", "hard drive", "free space", "space left", "kitna space"])) and not any(neg in text for neg in ["not", "code"]):
            return MediatorResult(True, format_natural_storage())

        # ------------------------------------------------------------------
        # 8. Performance / RAM / CPU / System Health Intent
        # ------------------------------------------------------------------
        health_triggers = ["stats", "health", "cpu", "ram", "memory", "/stats", "/health"]
        if any(ht in words for ht in health_triggers) or any(ht in text for ht in ["system health", "laptop health", "performance", "cpu usage", "how is my laptop", "is it slow", "why is it slow", "is my laptop lagging", "hanging", "overheating"]):
            return MediatorResult(True, format_natural_health())

        # ------------------------------------------------------------------
        # 9. Wi-Fi / Internet / Network Signal Intent
        # ------------------------------------------------------------------
        wifi_triggers = ["wifi", "wi-fi", "internet", "network", "/wifi", "/net"]
        if (any(wt in words for wt in wifi_triggers) or any(wt in text for wt in ["wifi status", "wifi signal", "am i connected", "am i online", "net chal raha"])) and not any(neg in text for neg in ["code"]):
            return MediatorResult(True, format_natural_wifi())

        # ------------------------------------------------------------------
        # 10. Process Management (Kill / Close / Terminate)
        # ------------------------------------------------------------------
        kill_pattern = r"(?:close|kill|terminate|stop|exit|quit|band\s*karo)\s+(?:the\s+|app\s+|process\s+)?([a-zA-Z0-9_\-\.]+)"
        kill_match = re.search(kill_pattern, text)
        if not kill_match:
            rev_match = re.search(r"([a-zA-Z0-9_\-\.]+)\s+(?:band\s*karo|close\s*karo|kill\s*karo|ko\s*band\s*karo)", text)
            if rev_match:
                kill_match = rev_match

        if kill_match and not any(w in text for w in ["session", "agent", "bot", "chat", "music", "playback"]):
            target = kill_match.group(1).strip()
            if target not in ["app", "apps", "process", "processes", "the", "window"]:
                res = system_controls.kill_process(target)
                return MediatorResult(True, res)

        proc_triggers = ["processes", "running apps", "open apps", "task manager", "heavy apps", "biggest apps", "what is running", "what apps are open", "/ps", "/tasks"]
        if any(pt in text for pt in proc_triggers) or any(pt in words for pt in ["processes", "/ps"]):
            return MediatorResult(True, format_natural_processes())

        # ------------------------------------------------------------------
        # 11. Chrome & Browser Intent (with Automatic Profile Bypass)
        # ------------------------------------------------------------------
        chrome_triggers = ["chrome", "google chrome", "browser", "chromium"]
        if any(b in text for b in chrome_triggers):
            if not any(neg in text for neg in ["close", "kill", "terminate", "stop", "dont", "don't"]):
                url = app_launcher.parse_url_or_search(text)
                prof_dir, prof_label = app_launcher.resolve_chrome_profile(text)
                ok, res_msg = app_launcher.launch_chrome(url=url, profile_dir=prof_dir)
                return MediatorResult(True, res_msg)

        # ------------------------------------------------------------------
        # 12. Popular Websites & YouTube Search Intent
        # ------------------------------------------------------------------
        website_triggers = ["youtube", "google", "github", "reddit", "netflix", "twitter", "x.com", "linkedin", "chatgpt", "claude", "ai studio"]
        if any(w in text for w in website_triggers) or re.search(r'\b[a-zA-Z0-9\-]+\.(?:com|org|io|dev|net|ai|co)\b', text):
            if not any(neg in text for neg in ["close", "kill", "terminate", "stop", "code review", "ticket", "commit", "push", "pr", "branch"]):
                url = app_launcher.parse_url_or_search(text)
                if url:
                    prof_dir, prof_label = app_launcher.resolve_chrome_profile(text)
                    ok, res_msg = app_launcher.launch_chrome(url=url, profile_dir=prof_dir)
                    return MediatorResult(True, res_msg)

        # ------------------------------------------------------------------
        # 13. Desktop Apps & System Folders Intent
        # ------------------------------------------------------------------
        app_triggers = [
            "vs code", "vscode", "notepad", "calculator", "calc", "spotify",
            "powershell", "terminal", "cmd", "explorer", "dev folder", "downloads folder",
            "desktop folder", "task manager", "paint", "camera", "settings", "control panel"
        ]
        if any(a in text for a in app_triggers):
            if not any(neg in text for neg in ["close", "kill", "terminate", "stop"]):
                ok, res_msg = app_launcher.launch_app(text)
                return MediatorResult(True, res_msg)

        # ------------------------------------------------------------------
        # 14. Generic Open / Launch / Play Intent ("open ...", "launch ...", "kholo ...", "chalao ...")
        # ------------------------------------------------------------------
        open_pattern = r"(?:open|launch|start|play|goto|go to|kholo|chalao)\s+(.+)"
        open_match = re.search(open_pattern, text)
        if open_match and not any(neg in text for neg in ["source", "file", "pr", "issue", "branch", "ticket"]):
            target = open_match.group(1).strip()
            # If user asks to open/play a website
            url = app_launcher.parse_url_or_search(target)
            if url:
                prof_dir, prof_label = app_launcher.resolve_chrome_profile(text)
                ok, res_msg = app_launcher.launch_chrome(url=url, profile_dir=prof_dir)
                return MediatorResult(True, res_msg)

            # If user explicitly asked for Chrome / Browser
            if any(b in target for b in ["chrome", "browser", "internet"]):
                prof_dir, prof_label = app_launcher.resolve_chrome_profile(text)
                ok, res_msg = app_launcher.launch_chrome(profile_dir=prof_dir)
                return MediatorResult(True, res_msg)

            # General desktop apps and folders
            ok, res_msg = app_launcher.launch_app(target)
            return MediatorResult(True, res_msg)

        # If not a system control task, return False so it routes to Antigravity
        return MediatorResult(False)

mediator = MediatorWorker()
