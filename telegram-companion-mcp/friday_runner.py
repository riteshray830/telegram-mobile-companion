import os
import sys
import glob
import json
import time
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from dotenv import load_dotenv

# Import multi-backend engine, system controls, and human mediator
from ai_backends import get_backend_instance, find_active_conversation_id
import system_controls
from mediator import mediator

# Ensure stdout uses UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

script_dir = Path(__file__).resolve().parent
env_file = script_dir / ".env"

# Auto-check if setup is needed
if not env_file.exists():
    print("=" * 65)
    print(" ⚠️  No configuration found! Launching setup wizard...")
    print("=" * 65)
    import setup_wizard
    setup_wizard.main()

load_dotenv(env_file)
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
DEV_ROOT = Path(os.getenv("PROJECTS_ROOT", Path.home() / "dev")).resolve()
AI_BACKEND = os.getenv("AI_BACKEND", "antigravity").strip().lower()

if not TOKEN or not ALLOWED_CHAT_ID:
    print(f"Error: Incomplete credentials in {env_file}. Please run setup_wizard.py.")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{TOKEN}"
backend = get_backend_instance(AI_BACKEND)

# State: start at DEV_ROOT or projects/exploring if exists
if (DEV_ROOT / "projects" / "exploring").exists():
    current_dir = DEV_ROOT / "projects" / "exploring"
else:
    current_dir = DEV_ROOT

def is_authorized(user_id: int) -> bool:
    return str(user_id) == str(ALLOWED_CHAT_ID)

async def send_msg(client: httpx.AsyncClient, text: str, parse_mode: Optional[str] = "Markdown"):
    if len(text) > 4000:
        chunks = [text[i:i+3800] for i in range(0, len(text), 3800)]
        for chunk in chunks:
            payload = {"chat_id": ALLOWED_CHAT_ID, "text": chunk}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            try:
                r = await client.post(f"{API_URL}/sendMessage", json=payload)
                if not r.json().get("ok") and parse_mode:
                    payload.pop("parse_mode")
                    await client.post(f"{API_URL}/sendMessage", json=payload)
            except Exception as e:
                print("Error sending msg chunk:", e)
        return

    payload = {"chat_id": ALLOWED_CHAT_ID, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = await client.post(f"{API_URL}/sendMessage", json=payload)
        res = r.json()
        if not res.get("ok") and parse_mode:
            payload.pop("parse_mode")
            await client.post(f"{API_URL}/sendMessage", json=payload)
    except Exception as e:
        print("Error sending msg:", e)

async def send_photo_file(client: httpx.AsyncClient, photo_path: Path, caption: str = ""):
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": (photo_path.name, f, "image/png")}
            data = {"chat_id": ALLOWED_CHAT_ID, "caption": caption}
            await client.post(f"{API_URL}/sendPhoto", data=data, files=files, timeout=40.0)
    except Exception as e:
        await send_msg(client, f"❌ Failed to send photo: {e}")

async def send_typing(client: httpx.AsyncClient):
    try:
        await client.post(f"{API_URL}/sendChatAction", json={"chat_id": ALLOWED_CHAT_ID, "action": "typing"})
    except Exception:
        pass

async def handle_user_message(client: httpx.AsyncClient, text: str):
    # 1. Let the Human Mediator worker interpret the message first (<1ms execution on laptop)
    handled, reply, photo_path = mediator.process_request(text)
    if handled:
        if photo_path:
            await send_photo_file(client, photo_path, caption=reply or "🖥️ Current Laptop Screen")
            try:
                photo_path.unlink(missing_ok=True)
            except Exception:
                pass
        elif reply:
            await send_msg(client, reply)
        return

    # 2. General AI / Antigravity Execution (for coding, files, projects, or complex tasks)
    await send_typing(client)
    context = {
        "dev_root": str(DEV_ROOT),
        "current_dir": str(current_dir),
        "platform": sys.platform
    }
    reply = await backend.generate_reply(text, context)
    if reply:
        await send_msg(client, reply)

async def battery_watchdog(client: httpx.AsyncClient):
    """Proactive battery monitor: warns if battery drops below 15% and discharging."""
    import psutil
    last_alert_time = 0
    while True:
        try:
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged and battery.percent <= 15:
                now = time.time()
                # Cooldown of 15 minutes between alerts
                if now - last_alert_time > 900:
                    await send_msg(
                        client,
                        f"🚨 *CRITICAL BATTERY ALERT*\n\n"
                        f"Your laptop is at `{battery.percent}%` and currently *discharging*!\n"
                        f"Please plug in your charger to avoid an unexpected shutdown."
                    )
                    last_alert_time = now
        except Exception as e:
            print("Watchdog error:", e)
        await asyncio.sleep(60)

async def main():
    print(f"🚀 Friday Remote Assistant & System Controller is running!")
    print(f"Host: {sys.platform}")
    print(f"Authorized Chat ID: {ALLOWED_CHAT_ID}")
    print(f"AI Backend: {AI_BACKEND}")
    print(f"Workspace Root: {DEV_ROOT}")

    offset = None
    first_run = True

    while True:
        try:
            async with httpx.AsyncClient(timeout=35.0, limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=10.0)) as client:
                if first_run:
                    await send_msg(
                        client,
                        f"⚡ *Friday Remote Assistant & Controller Online!*\n\n"
                        f"• *Backend:* `{AI_BACKEND}`\n"
                        f"• *Workspace:* `{DEV_ROOT}`\n"
                        f"• *Host:* `{sys.platform}`\n\n"
                        f"🕹️ *New System Controls Available:*\n"
                        f"• `/battery` - Battery health & charging status\n"
                        f"• `/stats` - CPU, RAM & Disk health\n"
                        f"• `/wifi` - Wi-Fi signal & connection\n"
                        f"• `/ps` - Top running processes\n"
                        f"• `/kill <PID>` - Terminate runaway process\n"
                        f"• `/screenshot` - Capture current display\n"
                        f"• `/lock` - Lock laptop workstation remotely\n\n"
                        f"Or just chat in natural language!"
                    )
                    first_run = False
                    # Start battery watchdog
                    asyncio.create_task(battery_watchdog(client))

                while True:
                    try:
                        params = {"timeout": 20}
                        if offset:
                            params["offset"] = offset

                        resp = await client.get(f"{API_URL}/getUpdates", params=params)
                        data = resp.json()

                        if not data.get("ok"):
                            await asyncio.sleep(2)
                            continue

                        for update in data.get("result", []):
                            offset = update["update_id"] + 1

                            if "message" in update:
                                msg = update["message"]
                                sender_id = msg.get("from", {}).get("id")
                                if not is_authorized(sender_id):
                                    continue

                                text = msg.get("text", "").strip()
                                if not text:
                                    continue

                                print(f"📩 [{sender_id}] Received: '{text}'")

                                if text in ["/start", "/help"]:
                                    asyncio.create_task(send_msg(
                                        client,
                                        f"🤖 *Friday Remote Assistant & Controller*\n\n"
                                        f"• Backend: `{AI_BACKEND}`\n"
                                        f"• Workspace: `{DEV_ROOT}`\n\n"
                                        f"🕹️ *Laptop Controls:*\n"
                                        f"• `/battery` - Battery health, charge & cycles\n"
                                        f"• `/stats` - CPU, RAM & Storage usage\n"
                                        f"• `/wifi` - Wi-Fi connection & signal\n"
                                        f"• `/ps` - Top running processes\n"
                                        f"• `/kill <PID>` - Terminate process\n"
                                        f"• `/screenshot` - Snap laptop screen\n"
                                        f"• `/lock` - Lock Windows PC\n\n"
                                        f"💬 *Chat with Antigravity:*\n"
                                        f"Type any question or instruction in human language!"
                                    ))
                                else:
                                    asyncio.create_task(handle_user_message(client, text))

                    except httpx.RequestError as e:
                        print("Connection recycled:", e)
                        break
                    except Exception as e:
                        print("Inner loop error:", e)
                        await asyncio.sleep(2)

        except Exception as e:
            print("Outer loop error:", e)
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
