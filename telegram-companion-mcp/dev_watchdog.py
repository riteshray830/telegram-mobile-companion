import asyncio
import time
import httpx
from typing import Dict, Any, Optional, Tuple, List, Callable

# Target storage: {url: {"status": "UP"|"DOWN", "consecutive_fails": 0, "last_check": timestamp, "last_err": ""}}
WATCH_TARGETS: Dict[str, Dict[str, Any]] = {}

def normalize_target(target: str) -> str:
    t = target.strip()
    if t.isdigit():
        return f"http://localhost:{t}"
    if not t.startswith("http://") and not t.startswith("https://"):
        return f"http://{t}"
    return t

def add_watch_target(target: str) -> Tuple[bool, str]:
    url = normalize_target(target)
    if url in WATCH_TARGETS:
        return True, f"ℹ️ Already watching `{url}`."
    
    WATCH_TARGETS[url] = {
        "status": "UNKNOWN",
        "consecutive_fails": 0,
        "last_check": time.time(),
        "last_err": ""
    }
    return True, f"👁️ *Now Watching:* `{url}`\n\nI will ping it every 15 seconds and notify your phone immediately if it crashes or goes down!"

def remove_watch_target(target: str) -> Tuple[bool, str]:
    url = normalize_target(target)
    if url in WATCH_TARGETS:
        del WATCH_TARGETS[url]
        return True, f"🛑 Stopped watching `{url}`."
    
    # Try by port
    for k in list(WATCH_TARGETS.keys()):
        if target.strip() in k:
            del WATCH_TARGETS[k]
            return True, f"🛑 Stopped watching `{k}`."

    return False, f"❌ Target `{target}` is not currently being watched."

def get_watch_status() -> str:
    if not WATCH_TARGETS:
        return (
            "🔔 *Dev Server Watchdog*\n\n"
            "No dev servers are currently being watched.\n\n"
            "To watch a server, tell me:\n"
            "• *'watch localhost:3000'*\n"
            "• *'watch 8080'*\n"
            "• *'/watch 3000'*"
        )

    lines = ["🔔 *Active Dev Server Watchdogs:*\n"]
    for url, info in WATCH_TARGETS.items():
        st = info["status"]
        st_icon = "🟢 UP" if st == "UP" else ("🔴 DOWN" if st == "DOWN" else "🟡 CHECKING")
        err_info = f" ({info['last_err']})" if st == "DOWN" and info['last_err'] else ""
        lines.append(f"• `{url}` — **{st_icon}**{err_info}")

    lines.append("\n_To stop watching, send:_ `/unwatch <port or url>`")
    return "\n".join(lines)

async def run_watchdog_loop(alert_callback: Callable[[str], Any]):
    """Background loop that checks endpoints every 15 seconds."""
    while True:
        try:
            if WATCH_TARGETS:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    for url, info in list(WATCH_TARGETS.items()):
                        try:
                            resp = await client.get(url)
                            info["last_check"] = time.time()
                            if resp.status_code < 500:
                                if info["status"] == "DOWN":
                                    # Recovery alert!
                                    info["status"] = "UP"
                                    info["consecutive_fails"] = 0
                                    await alert_callback(f"✅ *DEV SERVER RECOVERED!*\n\n`{url}` is back online! (HTTP `{resp.status_code}`)")
                                else:
                                    info["status"] = "UP"
                                    info["consecutive_fails"] = 0
                            else:
                                raise Exception(f"HTTP {resp.status_code} Internal Server Error")
                        except Exception as e:
                            err_msg = str(e)
                            if "ConnectError" in err_msg or "refused" in err_msg.lower():
                                err_msg = "Connection Refused (Server stopped)"
                            info["consecutive_fails"] += 1
                            info["last_err"] = err_msg
                            
                            # Alert after 2 consecutive failures
                            if info["consecutive_fails"] == 2 and info["status"] != "DOWN":
                                info["status"] = "DOWN"
                                await alert_callback(
                                    f"🚨 *CRITICAL DEV SERVER CRASH!*\n\n"
                                    f"• **Endpoint:** `{url}`\n"
                                    f"• **Issue:** `{err_msg}`\n\n"
                                    f"Please check your laptop build/server process!"
                                )
        except Exception as loop_err:
            pass

        await asyncio.sleep(15)
