import re
import sys
import os
import time
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

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

class MediatorWorker:
    """
    Intelligent Conversational Mediator & Translator:
    Understands human speech, executes laptop commands automatically,
    and returns warm, conversational responses without technical jargon.
    """

    def process_request(self, user_text: str) -> Tuple[bool, Optional[str], Optional[Path]]:
        """
        Analyzes the user's plain English message.
        Returns: (handled_by_mediator, text_response, optional_photo_path)
        """
        text = user_text.lower().strip()

        # 1. Battery / Power / Charging
        battery_keywords = [
            "battery", "charging", "charger", "plugged in", "juice", 
            "power", "how much battery", "is my laptop charging", "will it die"
        ]
        if any(k in text for k in battery_keywords) and not any(neg in text for neg in ["not", "dont", "code"]):
            return True, format_natural_battery(), None

        # 2. Lock Laptop
        lock_keywords = ["lock my laptop", "lock laptop", "lock the laptop", "lock my pc", "lock pc", "lock the screen", "lock screen", "/lock"]
        if any(k in text for k in lock_keywords):
            res = system_controls.lock_workstation()
            if "Successfully" in res:
                return True, "🔒 Done! I've locked your laptop screen for you. Your laptop is now secured.", None
            return True, res, None

        # 3. Screenshot / Display
        screenshot_keywords = [
            "screenshot", "screen capture", "show me my screen", "what is on my screen", 
            "what's on my screen", "take a picture of my screen", "see my screen", "snap screen"
        ]
        if any(k in text for k in screenshot_keywords):
            path, msg = system_controls.take_screenshot()
            if path:
                return True, "Here's what is currently on your laptop screen! 📸", path
            return True, f"I couldn't grab the screen right now because the display is locked or turned off.", None

        # 4. Storage / Hard Drive / Space
        storage_keywords = [
            "storage", "disk space", "hard drive", "space left", "how much space", 
            "disk full", "free space", "c drive", "d drive"
        ]
        if any(k in text for k in storage_keywords):
            return True, format_natural_storage(), None

        # 5. Performance / Slowness / RAM / CPU / Health
        health_keywords = [
            "how is my laptop", "laptop health", "system health", "is it slow", 
            "why is it slow", "is my laptop lagging", "ram", "memory", "cpu usage", "performance"
        ]
        if any(k in text for k in health_keywords):
            return True, format_natural_health(), None

        # 6. Wi-Fi / Internet / Signal
        wifi_keywords = [
            "wifi", "wi-fi", "internet", "am i connected", "network", 
            "wifi signal", "wifi status", "which wifi"
        ]
        if any(k in text for k in wifi_keywords):
            return True, format_natural_wifi(), None

        # 7. Heavy apps / Processes / Closing apps
        kill_match = re.search(r"(?:close|kill|terminate|stop)\s+([a-zA-Z0-9_\-\.]+)", text)
        if kill_match and not any(w in text for w in ["session", "agent", "bot", "chat"]):
            target = kill_match.group(1).strip()
            # If target is "app" or "process", user might be asking to list them
            if target not in ["app", "apps", "process", "processes", "the"]:
                res = system_controls.kill_process(target)
                return True, res, None

        proc_keywords = ["what apps are running", "heavy apps", "biggest apps", "processes", "what is running", "running apps"]
        if any(k in text for k in proc_keywords):
            return True, format_natural_processes(), None

        # 8. Instant App & Browser Launchers (Ultra-fast, <1ms execution)

        # 8a. Chrome / Browser direct intent (catches "chrome", "open chrome", "can u open chrome", "chrome please", etc.)
        chrome_triggers = ["chrome", "google chrome", "browser", "chromium"]
        if any(b in text for b in chrome_triggers):
            if not any(neg in text for neg in ["close", "kill", "terminate", "stop", "dont", "don't"]):
                url = app_launcher.parse_url_or_search(text)
                prof_dir, prof_label = app_launcher.resolve_chrome_profile(text)
                ok, res_msg = app_launcher.launch_chrome(url=url, profile_dir=prof_dir)
                return True, res_msg, None

        # 8b. Popular websites / YouTube (catches "youtube", "open youtube", "github", "google", etc.)
        website_triggers = ["youtube", "google", "github", "reddit", "netflix", "twitter", "x.com", "linkedin", "chatgpt", "claude"]
        if any(w in text for w in website_triggers):
            if not any(neg in text for neg in ["close", "kill", "terminate", "stop", "code review", "ticket", "commit", "push"]):
                url = app_launcher.parse_url_or_search(text)
                if url:
                    prof_dir, prof_label = app_launcher.resolve_chrome_profile(text)
                    ok, res_msg = app_launcher.launch_chrome(url=url, profile_dir=prof_dir)
                    return True, res_msg, None

        # 8c. Popular Desktop Apps (catches "vs code", "vscode", "notepad", "calculator", "spotify", "terminal", etc.)
        app_triggers = ["vs code", "vscode", "notepad", "calculator", "calc", "spotify", "powershell", "terminal", "explorer", "dev folder", "downloads folder"]
        if any(a in text for a in app_triggers):
            if not any(neg in text for neg in ["close", "kill", "terminate", "stop"]):
                ok, res_msg = app_launcher.launch_app(text)
                return True, res_msg, None

        # 8d. Generic Open pattern ("open ...", "launch ...", "start ...", "play ...")
        open_pattern = r"(?:open|launch|start|play|goto|go to|kholo)\s+(.+)"
        open_match = re.search(open_pattern, text)
        if open_match and not any(neg in text for neg in ["source", "file", "pr", "issue", "branch", "ticket"]):
            target = open_match.group(1).strip()
            # If user asks to open/play a website
            url = app_launcher.parse_url_or_search(target)
            if url:
                prof_dir, prof_label = app_launcher.resolve_chrome_profile(text)
                ok, res_msg = app_launcher.launch_chrome(url=url, profile_dir=prof_dir)
                return True, res_msg, None

            # If user explicitly asked for Chrome / Browser
            if any(b in target for b in ["chrome", "browser", "internet"]):
                prof_dir, prof_label = app_launcher.resolve_chrome_profile(text)
                ok, res_msg = app_launcher.launch_chrome(profile_dir=prof_dir)
                return True, res_msg, None

            # General desktop apps and folders
            ok, res_msg = app_launcher.launch_app(target)
            return True, res_msg, None

        # If not a system control task, return False so it routes to Antigravity
        return False, None, None

mediator = MediatorWorker()
