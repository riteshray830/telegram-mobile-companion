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

# Ensure stdout uses UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load environment
script_dir = Path(__file__).resolve().parent
env_file = script_dir / ".env"
load_dotenv(env_file)
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
DEV_ROOT = Path(os.getenv("PROJECTS_ROOT", r"d:\dev")).resolve()
AGY_EXE = Path.home() / ".gemini" / "bin" / "agy.exe"

if not TOKEN or not ALLOWED_CHAT_ID:
    print(f"Error: Missing credentials in {env_file}")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{TOKEN}"

def is_authorized(user_id: int) -> bool:
    return str(user_id) == str(ALLOWED_CHAT_ID)

def find_active_conversation_id() -> Optional[str]:
    """Finds the most recently active Antigravity conversation ID."""
    conv_dir = Path.home() / ".gemini" / "antigravity" / "conversations"
    if not conv_dir.exists():
        return None
    dbs = sorted([f for f in conv_dir.glob("*.db")], key=lambda f: f.stat().st_mtime, reverse=True)
    return dbs[0].stem if dbs else None

async def send_msg(client: httpx.AsyncClient, text: str, parse_mode: Optional[str] = "Markdown"):
    if len(text) > 4000:
        chunks = [text[i:i+3800] for i in range(0, len(full_msg), 3800)]
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

async def forward_to_antigravity(client: httpx.AsyncClient, user_message: str):
    """Forwards natural human language directly into the active Antigravity conversation."""
    conv_id = find_active_conversation_id()
    if not conv_id:
        await send_msg(client, "❌ Could not find an active Antigravity conversation session.")
        return

    if not AGY_EXE.exists():
        await send_msg(client, f"❌ agy.exe not found at `{AGY_EXE}`.")
        return

    await send_typing(client)
    await send_msg(client, "⚡ *Delivered to Antigravity.* Working on it...")

    # Execute agy agentapi send-message
    try:
        # Format message so agent knows it came live from user's phone
        content = f"[User via Mobile Telegram]: {user_message}"
        proc = await asyncio.create_subprocess_exec(
            str(AGY_EXE),
            "agentapi",
            "send-message",
            conv_id,
            content,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")
            print("Failed to dispatch message to agy:", err_msg)
            await send_msg(client, f"⚠️ Error dispatching to agent: `{err_msg[:200]}`")
        else:
            print(f"Dispatched message to conversation {conv_id}: {user_message[:50]}...")
    except Exception as e:
        print("Exception forwarding to agentapi:", e)
        await send_msg(client, f"❌ Error sending to agent: {e}")

async def main():
    print(f"🚀 Friday 2-Way Chat Bridge is running!")
    print(f"Authorized Chat ID: {ALLOWED_CHAT_ID}")
    print(f"agy.exe path: {AGY_EXE}")
    print(f"Dev Root: {DEV_ROOT}")

    conv_id = find_active_conversation_id()
    print(f"Active Conversation ID: {conv_id}")

    offset = None
    first_run = True

    while True:
        try:
            async with httpx.AsyncClient(timeout=35.0, limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=10.0)) as client:
                if first_run:
                    await send_msg(
                        client,
                        f"💬 *Friday 2-Way Antigravity Chat is Live!*\n\n"
                        f"Whatever you type here is delivered directly to Antigravity as a human command, and its full response will appear right here.\n\n"
                        f"Try typing anything: e.g. _\"What projects are in my dev folder?\"_ or _\"Can you check git status in exploring?\"_"
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
                                        "💬 *Antigravity Direct Chat*\n\n"
                                        "Simply send any message in plain English! I will forward it straight to your active Antigravity session on your PC, and return the agent's exact response here."
                                    )
                                else:
                                    # Forward message directly to Antigravity!
                                    await forward_to_antigravity(client, text)

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
