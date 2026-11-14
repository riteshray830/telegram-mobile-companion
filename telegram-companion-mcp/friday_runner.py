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

def ensure_single_instance():
    """Ensures only one Friday runner process runs at any time, terminating stale duplicates."""
    import psutil
    current_pid = os.getpid()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            pname = (p.info['name'] or '').lower()
            if not pname.startswith("python"):
                continue
            cmd = " ".join(p.info['cmdline'] or []).lower()
            if "friday_runner.py" in cmd and p.info['pid'] != current_pid:
                print(f"⚠️ Existing Friday process detected (PID: {p.info['pid']}). Reclaiming session...")
                p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

ensure_single_instance()

# State: start at DEV_ROOT or projects/exploring if exists
if (DEV_ROOT / "projects" / "exploring").exists():
    current_dir = DEV_ROOT / "projects" / "exploring"
else:
    current_dir = DEV_ROOT

def is_authorized(user_id: int) -> bool:
    return str(user_id) == str(ALLOWED_CHAT_ID)

async def send_msg(
    client: httpx.AsyncClient,
    text: str,
    parse_mode: Optional[str] = "Markdown",
    reply_markup: Optional[Dict[str, Any]] = None
):
    """Sends a Telegram message, splitting long content into chunks if needed."""
    if len(text) > 4000:
        chunks = [text[i:i+3800] for i in range(0, len(text), 3800)]
        for idx, chunk in enumerate(chunks):
            payload: Dict[str, Any] = {"chat_id": ALLOWED_CHAT_ID, "text": chunk}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_markup and idx == len(chunks) - 1:
                payload["reply_markup"] = reply_markup
            try:
                r = await client.post(f"{API_URL}/sendMessage", json=payload)
                if not r.json().get("ok") and parse_mode:
                    payload.pop("parse_mode")
                    await client.post(f"{API_URL}/sendMessage", json=payload)
            except Exception as e:
                print("Error sending msg chunk:", e)
        return

    payload: Dict[str, Any] = {"chat_id": ALLOWED_CHAT_ID, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = await client.post(f"{API_URL}/sendMessage", json=payload)
        res = r.json()
        if not res.get("ok") and parse_mode:
            payload.pop("parse_mode")
            await client.post(f"{API_URL}/sendMessage", json=payload)
    except Exception as e:
        print("Error sending msg:", e)

async def send_photo_file(client: httpx.AsyncClient, photo_path: Path, caption: str = ""):
    """Sends a photo file (e.g. screenshot or webcam capture) to Telegram."""
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": (photo_path.name, f, "image/png")}
            data = {"chat_id": ALLOWED_CHAT_ID, "caption": caption}
            await client.post(f"{API_URL}/sendPhoto", data=data, files=files, timeout=40.0)
    except Exception as e:
        await send_msg(client, f"❌ Failed to send photo: {e}")

async def send_document_file(client: httpx.AsyncClient, doc_path: Path, caption: str = ""):
    """Sends any document or code file from laptop to phone via Telegram."""
    try:
        with open(doc_path, "rb") as f:
            files = {"document": (doc_path.name, f, "application/octet-stream")}
            data = {"chat_id": ALLOWED_CHAT_ID, "caption": caption}
            await client.post(f"{API_URL}/sendDocument", data=data, files=files, timeout=60.0)
    except Exception as e:
        await send_msg(client, f"❌ Failed to send file: {e}")

async def send_typing(client: httpx.AsyncClient):
    try:
        await client.post(f"{API_URL}/sendChatAction", json={"chat_id": ALLOWED_CHAT_ID, "action": "typing"})
    except Exception:
        pass

# Stop Triggers for remote shutdown
STOP_TRIGGERS = {
    "/stop", "/exit", "/shutdown", "/quit", "/killbot",
    "stop friday", "close friday", "exit friday", "shutdown friday", "turn off friday",
    "stop tool", "close tool", "exit tool", "shutdown tool", "stop bot", "close bot",
    "friday band karo", "bot band karo", "tool band karo", "band karo friday"
}

def is_stop_trigger(text: str) -> bool:
    t = text.lower().strip()
    if t in STOP_TRIGGERS:
        return True
    return any(t.startswith(prefix) for prefix in ["/stop", "/exit", "/shutdown"])

async def shutdown_friday(client: httpx.AsyncClient):
    """Gracefully notifies user and shuts down Friday."""
    print("🛑 Received shutdown command. Stopping Friday Remote Companion...")
    farewell = (
        "🛑 *Friday Remote Companion is shutting down.* 👋\n\n"
        "• Background monitoring: **Stopped**\n"
        "• Telegram connection: **Disconnected**\n\n"
        "To start Friday again, double-click `start_friday.bat` on your laptop!"
    )
    try:
        await send_msg(client, farewell)
        await asyncio.sleep(0.8)
    except Exception as e:
        print("Error sending farewell:", e)
    finally:
        print("Friday has shut down.")
        os._exit(0)

async def handle_user_message(client: httpx.AsyncClient, text: str):
    """Processes incoming text command through mediator or general AI."""
    # Check stop trigger first
    if is_stop_trigger(text):
        await shutdown_friday(client)
        return

    # 1. Let the Human Mediator worker interpret the message first (<1ms execution on laptop)
    res = mediator.process_request(text)
    if res.handled:
        if res.reply == "__FRIDAY_SHUTDOWN__":
            await shutdown_friday(client)
            return

        # If sending a document (Remote File Transfer from laptop to phone)
        if res.doc_path:
            await send_msg(client, res.reply or f"📁 Sending `{res.doc_path.name}`...")
            await send_document_file(client, res.doc_path, caption=res.doc_path.name)
            try:
                import chat_logger
                chat_logger.append_turn_to_chat(user_msg=text, assistant_msg=f"[Sent document {res.doc_path.name}]", source="Telegram")
            except Exception:
                pass
            return

        # If sending a photo (Screenshot or Webcam snap)
        if res.photo_path:
            await send_photo_file(client, res.photo_path, caption=res.reply or "📸 Photo")
            try:
                import chat_logger
                chat_logger.append_turn_to_chat(user_msg=text, assistant_msg=res.reply or "📸 Photo", source="Telegram")
            except Exception:
                pass
            try:
                res.photo_path.unlink(missing_ok=True)
            except Exception:
                pass
            return

        # If returning interactive buttons (Git Command Center)
        if res.buttons:
            reply_markup = {"inline_keyboard": res.buttons}
            await send_msg(client, res.reply or "🌿 Git Command Center:", reply_markup=reply_markup)
            try:
                import chat_logger
                chat_logger.append_turn_to_chat(user_msg=text, assistant_msg=res.reply or "🌿 Git Command Center", source="Telegram")
            except Exception:
                pass
            return

        # Plain text reply
        if res.reply:
            await send_msg(client, res.reply)
            try:
                import chat_logger
                chat_logger.append_turn_to_chat(user_msg=text, assistant_msg=res.reply, source="Telegram")
            except Exception:
                pass
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
        try:
            import chat_logger
            chat_logger.append_turn_to_chat(user_msg=text, assistant_msg=reply, source="Telegram")
        except Exception:
            pass

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
            print("Battery Watchdog error:", e)
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
                    banner = (
                        f"⚡ *Friday Remote Assistant & Controller Online!*\n\n"
                        f"• *Backend:* `{AI_BACKEND}`\n"
                        f"• *Workspace:* `{DEV_ROOT}`\n"
                        f"• *Host:* `{sys.platform}`\n\n"
                        f"✨ *All 7 Upgraded Capabilities Active:*\n"
                        f"• 🎙️ *Voice Notes:* Speak voice messages to execute laptop tasks\n"
                        f"• 📷 `/webcam` - Instant desk / room security camera snap\n"
                        f"• 📋 `/clip` or `copy: <text>` - Shared mobile-laptop clipboard\n"
                        f"• 📁 `download <file>` - Download files to phone; or send files to save on laptop\n"
                        f"• 🔔 `/watch <port>` - Proactive dev server crash watchdog\n"
                        f"• 🌿 `/git` - Git command center with one-tap action buttons\n"
                        f"• 🪟 *Tray Widget:* Double click `start_tray.bat` for desktop tray control\n\n"
                        f"Send `/help` anytime to view all controls!"
                    )
                    await send_msg(client, banner)
                    first_run = False
                    
                    # Start battery watchdog
                    asyncio.create_task(battery_watchdog(client))

                    # Start dev server watchdog
                    import dev_watchdog
                    async def send_watchdog_alert(alert_text: str):
                        await send_msg(client, alert_text)
                    asyncio.create_task(dev_watchdog.run_watchdog_loop(send_watchdog_alert))

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

                            # 1. Handle Inline Keyboard Callback Queries (Git Command Center buttons)
                            if "callback_query" in update:
                                cb = update["callback_query"]
                                cb_id = cb.get("id")
                                cb_sender = cb.get("from", {}).get("id")
                                if not is_authorized(cb_sender):
                                    continue

                                cb_data = cb.get("data", "")
                                # Acknowledge callback query immediately so Telegram stops spinner
                                try:
                                    await client.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb_id})
                                except Exception:
                                    pass

                                if cb_data.startswith("git:"):
                                    parts = cb_data.split(":")
                                    if len(parts) >= 3:
                                        action = parts[1]
                                        repo_name = parts[2]
                                        await send_typing(client)
                                        import git_center
                                        git_res = git_center.execute_git_action(action, repo_name)
                                        await send_msg(client, git_res)
                                        try:
                                            import chat_logger
                                            chat_logger.append_turn_to_chat(
                                                user_msg=f"[Git Action: {action} on {repo_name}]",
                                                assistant_msg=git_res,
                                                source="Telegram"
                                            )
                                        except Exception:
                                            pass
                                continue

                            # 2. Handle Messages
                            if "message" in update:
                                msg = update["message"]
                                sender_id = msg.get("from", {}).get("id")
                                if not is_authorized(sender_id):
                                    continue

                                # 2a. Voice Note / Audio Message
                                voice_obj = msg.get("voice") or msg.get("audio")
                                if voice_obj:
                                    file_id = voice_obj.get("file_id")
                                    mime_type = voice_obj.get("mime_type", "audio/ogg")
                                    await send_typing(client)
                                    gf_resp = await client.get(f"{API_URL}/getFile", params={"file_id": file_id})
                                    gf_data = gf_resp.json()
                                    if gf_data.get("ok"):
                                        file_path = gf_data["result"]["file_path"]
                                        dl_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
                                        dl_resp = await client.get(dl_url, timeout=30.0)
                                        if dl_resp.status_code == 200:
                                            import voice_handler
                                            transcript, err = await voice_handler.transcribe_telegram_voice(dl_resp.content, mime_type)
                                            if transcript:
                                                await send_msg(client, f"🎙️ *Voice Note:* \"_{transcript}_\"")
                                                # Execute transcribed command
                                                asyncio.create_task(handle_user_message(client, transcript))
                                                continue
                                            else:
                                                await send_msg(client, err or "❌ Could not transcribe voice note.")
                                                continue

                                # 2b. File Upload Document (Phone to Laptop)
                                doc_obj = msg.get("document")
                                if doc_obj:
                                    file_id = doc_obj.get("file_id")
                                    file_name = doc_obj.get("file_name", f"upload_{int(time.time())}")
                                    await send_typing(client)
                                    gf_resp = await client.get(f"{API_URL}/getFile", params={"file_id": file_id})
                                    gf_data = gf_resp.json()
                                    if gf_data.get("ok"):
                                        file_path = gf_data["result"]["file_path"]
                                        dl_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
                                        dl_resp = await client.get(dl_url, timeout=60.0)
                                        if dl_resp.status_code == 200:
                                            import file_transfer
                                            ok, saved_path, res_msg = file_transfer.save_uploaded_file(file_name, dl_resp.content)
                                            await send_msg(client, res_msg)
                                            try:
                                                import chat_logger
                                                chat_logger.append_turn_to_chat(
                                                    user_msg=f"[Uploaded file: {file_name}]",
                                                    assistant_msg=res_msg,
                                                    source="Telegram"
                                                )
                                            except Exception:
                                                pass
                                            continue

                                # 2c. Text Message
                                text = msg.get("text", "").strip()
                                if not text:
                                    continue

                                print(f"📩 [{sender_id}] Received: '{text}'")

                                if text in ["/start", "/help"]:
                                    help_msg = (
                                        f"🤖 *Friday Remote Assistant & Controller*\n\n"
                                        f"• **Backend:** `{AI_BACKEND}`\n"
                                        f"• **Workspace:** `{DEV_ROOT}`\n\n"
                                        f"🕹️ *Laptop System Controls:*\n"
                                        f"• `/battery` - Battery health, charge & cycles\n"
                                        f"• `/stats` - CPU, RAM & Storage usage\n"
                                        f"• `/wifi` - Wi-Fi connection & signal\n"
                                        f"• `/ps` - Top running processes\n"
                                        f"• `/kill <PID>` - Terminate runaway process\n"
                                        f"• `/screenshot` - Snap current laptop screen\n"
                                        f"• `/lock` - Lock Windows PC\n"
                                        f"• `/autostart` - Check / toggle auto-start on boot\n"
                                        f"• `/stop` - Remotely shut down Friday\n\n"
                                        f"✨ *Roadmap Capabilities:*\n"
                                        f"• 🎙️ *Voice Notes:* Speak voice notes to run tasks\n"
                                        f"• 📷 `/webcam` - Desk / room security camera snap\n"
                                        f"• 📋 `/clip` or `copy: <text>` - Shared mobile-laptop clipboard\n"
                                        f"• 📁 `download <file>` - Transfer files from laptop to phone\n"
                                        f"• 📥 *File Upload:* Send any document here to save to laptop\n"
                                        f"• 🔔 `/watch <port>` - Dev server crash monitor\n"
                                        f"• 🌿 `/git` - Git command center with one-tap buttons\n"
                                        f"• 🪟 *System Tray:* Minimalist desktop tray widget\n\n"
                                        f"💬 *Chat with Antigravity:*\n"
                                        f"Type or speak any instruction in natural language!"
                                    )
                                    asyncio.create_task(send_msg(client, help_msg))
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
