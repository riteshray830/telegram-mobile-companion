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

# Import multi-backend engine
from ai_backends import get_backend_instance, find_active_conversation_id

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

async def send_typing(client: httpx.AsyncClient):
    try:
        await client.post(f"{API_URL}/sendChatAction", json={"chat_id": ALLOWED_CHAT_ID, "action": "typing"})
    except Exception:
        pass

async def handle_user_message(client: httpx.AsyncClient, text: str):
    await send_typing(client)
    context = {
        "dev_root": str(DEV_ROOT),
        "current_dir": str(current_dir),
        "platform": sys.platform
    }
    reply = await backend.generate_reply(text, context)
    if reply:
        await send_msg(client, reply)

async def main():
    print(f"🚀 Friday Remote Assistant is running!")
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
                        f"⚡ *Friday Assistant Online!*\n\n"
                        f"• *Backend:* `{AI_BACKEND}`\n"
                        f"• *Workspace:* `{DEV_ROOT}`\n"
                        f"• *Platform:* `{sys.platform}`\n\n"
                        f"Ready for your messages!"
                    )
                    first_run = False

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

                                if text in ["/start", "/help"]:
                                    await send_msg(
                                        client,
                                        f"🤖 *Friday Mobile Assistant*\n\n"
                                        f"• Backend: `{AI_BACKEND}`\n"
                                        f"• Workspace: `{DEV_ROOT}`\n\n"
                                        f"Simply type any question or task in human language, and I will process it directly!"
                                    )
                                else:
                                    await handle_user_message(client, text)

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
