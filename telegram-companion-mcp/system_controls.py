import os
import sys
import time
import ctypes
import tempfile
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

import psutil

# Ensure stdout uses UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def get_battery_report() -> str:
    """Detailed battery health, charge, and power status."""
    battery = psutil.sensors_battery()
    if not battery:
        return "ℹ️ No battery detected (Desktop PC or AC only)."

    percent = battery.percent
    plugged = battery.power_plugged
    status_emoji = "⚡ Charging" if plugged else ("🔋 On Battery" if percent > 20 else "🪫 Low Battery!")
    
    # Estimate time left
    time_left = ""
    if battery.secsleft != psutil.POWER_TIME_UNLIMITED and battery.secsleft != psutil.POWER_TIME_UNKNOWN and not plugged:
        hrs = battery.secsleft // 3600
        mins = (battery.secsleft % 3600) // 60
        time_left = f"• *Estimated Time Remaining:* `{hrs}h {mins}m`\n"

    # Deep battery health metrics on Windows
    health_extra = ""
    if sys.platform == "win32":
        try:
            cmd = (
                "powercfg /batteryreport /xml /output \"$env:TEMP\\b_rep.xml\" 2>$null; "
                "[xml]$r = Get-Content \"$env:TEMP\\b_rep.xml\" -ErrorAction SilentlyContinue; "
                "$b = $r.BatteryReport.Batteries.Battery; "
                "\"$($b.DesignCapacity)|$($b.FullChargeCapacity)|$($b.CycleCount)|$($b.Manufacturer)\""
            )
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=6)
            out = res.stdout.strip()
            if "|" in out:
                parts = out.split("|")
                if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                    des = int(parts[0])
                    full = int(parts[1])
                    cycle = parts[2] if parts[2] else "N/A"
                    mfg = parts[3] if len(parts) > 3 and parts[3] else "Unknown"
                    if des > 0:
                        h_pct = round((full / des) * 100, 2)
                        health_extra = (
                            f"• *Battery Health:* `{h_pct}%`\n"
                            f"• *Cycle Count:* `{cycle}` cycles\n"
                            f"• *Current Max Capacity:* `{full} mWh` (Design: `{des} mWh`)\n"
                            f"• *Manufacturer:* `{mfg}`\n"
                        )
        except Exception:
            pass

    return (
        f"🔋 *Battery Telemetry & Health*\n\n"
        f"• *Current Level:* `{percent}%`\n"
        f"• *Power Status:* `{status_emoji}`\n"
        f"{time_left}"
        f"{health_extra}"
    )

def get_system_health() -> str:
    """CPU, RAM, Disks, Uptime, and Host metrics."""
    cpu_pct = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count(logical=True)
    
    # RAM
    ram = psutil.virtual_memory()
    ram_used = round(ram.used / (1024**3), 2)
    ram_total = round(ram.total / (1024**3), 2)
    ram_pct = ram.percent

    # Disks
    disk_lines = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            free_gb = round(usage.free / (1024**3), 1)
            total_gb = round(usage.total / (1024**3), 1)
            disk_lines.append(f"  - `{part.mountpoint}`: `{free_gb} GB free` / `{total_gb} GB` ({usage.percent}% used)")
        except Exception:
            pass
    disks_str = "\n".join(disk_lines) if disk_lines else "  - No drives found"

    # Uptime
    boot_time = psutil.boot_time()
    uptime_secs = int(time.time() - boot_time)
    hrs = uptime_secs // 3600
    mins = (uptime_secs % 3600) // 60
    
    # Host / OS
    os_name = f"{platform.system()} {platform.release()}"

    return (
        f"💻 *Laptop System Health*\n\n"
        f"• *OS:* `{os_name}`\n"
        f"• *Uptime:* `{hrs}h {mins}m`\n"
        f"• *CPU Usage:* `{cpu_pct}%` ({cpu_count} cores)\n"
        f"• *RAM:* `{ram_used} GB` / `{ram_total} GB` (`{ram_pct}%`)\n"
        f"• *Storage:*\n{disks_str}\n"
    )

def get_wifi_status() -> str:
    """Wi-Fi SSID, connection state, and signal strength."""
    if sys.platform != "win32":
        return "Wi-Fi query only supported on Windows."
    try:
        res = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=5)
        out = res.stdout
        ssid = "Disconnected"
        signal = "N/A"
        state = "Disconnected"
        for line in out.splitlines():
            line_str = line.strip()
            if line_str.startswith("SSID") and not line_str.startswith("BSSID"):
                parts = line_str.split(":", 1)
                if len(parts) > 1:
                    ssid = parts[1].strip()
            elif line_str.startswith("State"):
                parts = line_str.split(":", 1)
                if len(parts) > 1:
                    state = parts[1].strip()
            elif line_str.startswith("Signal"):
                parts = line_str.split(":", 1)
                if len(parts) > 1:
                    signal = parts[1].strip()

        return (
            f"📶 *Wi-Fi Status*\n\n"
            f"• *State:* `{state}`\n"
            f"• *SSID:* `{ssid}`\n"
            f"• *Signal Strength:* `{signal}`\n"
        )
    except Exception as e:
        return f"❌ Failed to query Wi-Fi: {e}"

def get_top_processes(limit: int = 8) -> str:
    """Top running processes by Memory."""
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
        try:
            mem_mb = round(p.info['memory_info'].rss / (1024 * 1024), 1)
            procs.append({
                "pid": p.info['pid'],
                "name": p.info['name'],
                "mem_mb": mem_mb
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    procs.sort(key=lambda x: x["mem_mb"], reverse=True)
    lines = [f"📊 *Top {min(limit, len(procs))} Running Processes (by RAM)*:\n"]
    for pr in procs[:limit]:
        lines.append(f"• `{pr['pid']}` — *{pr['name']}*: `{pr['mem_mb']} MB`")
    lines.append("\n_To terminate a runaway process, send:_ `/kill <PID>`")
    return "\n".join(lines)

def lock_workstation() -> str:
    """Instantly locks the Windows workstation."""
    if sys.platform != "win32":
        return "❌ Remote lock is only supported on Windows."
    try:
        user32 = ctypes.windll.User32
        success = user32.LockWorkStation()
        if success:
            return "🔒 *Laptop Locked Successfully!* The screen is now secured."
        else:
            return "❌ LockWorkStation API returned failure."
    except Exception as e:
        return f"❌ Error locking workstation: {e}"

def kill_process(target: str) -> str:
    """Kills a process by PID or Name safely."""
    target_clean = target.strip()
    if not target_clean:
        return "Usage: `/kill <PID or ProcessName>`\nExample: `/kill 1234` or `/kill notepad.exe`"

    # Critical protection list
    protected = ["explorer.exe", "svchost.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "smss.exe"]
    if target_clean.lower() in protected:
        return f"🛡️ *Action Blocked:* `{target_clean}` is a critical Windows system process and cannot be terminated."

    killed = []
    if target_clean.isdigit():
        pid = int(target_clean)
        try:
            p = psutil.Process(pid)
            p_name = p.name()
            if p_name.lower() in protected:
                return f"🛡️ *Action Blocked:* PID {pid} is `{p_name}` and cannot be killed."
            p.terminate()
            return f"🛑 Successfully terminated *{p_name}* (PID: `{pid}`)."
        except psutil.NoSuchProcess:
            return f"❌ Process with PID `{pid}` not found."
        except psutil.AccessDenied:
            return f"⚠️ Access denied when attempting to kill PID `{pid}`."
    else:
        # Match by name
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if p.info['name'].lower() == target_clean.lower():
                    p.terminate()
                    killed.append(p.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if killed:
            return f"🛑 Terminated {len(killed)} process(es) matching *{target_clean}* (PIDs: `{killed}`)."
        return f"❌ No running processes found matching `{target_clean}`."

def take_screenshot() -> Tuple[Optional[Path], str]:
    """Captures laptop screen. Returns (path, status_message)."""
    if sys.platform != "win32":
        return None, "Screenshot is currently optimized for Windows."

    # Using PowerShell .NET System.Drawing for high compatibility
    out_file = Path(tempfile.gettempdir()) / f"screen_{int(time.time())}.png"
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        "$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
        f"$bmp.Save('{out_file}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "$g.Dispose(); $bmp.Dispose();"
    )
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=8)
        if out_file.exists() and out_file.stat().st_size > 1000:
            return out_file, "Screenshot captured successfully."
        else:
            err = proc.stderr.strip()
            if "The handle is invalid" in err or "handle" in err.lower():
                return None, "⚠️ Screen is currently locked, turned off, or display handle is inactive."
            return None, f"Could not capture screen: {err[:150]}"
    except Exception as e:
        return None, f"Screenshot error: {e}"
