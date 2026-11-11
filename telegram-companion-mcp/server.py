# /// script
# dependencies = [
#   "mcp<2",
#   "httpx",
#   "python-dotenv",
# ]
# ///

import os
import sys
import time
import json
import logging
from typing import List, Optional
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Setup logging to stderr (stdout is reserved for MCP JSON-RPC communication)
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram-companion")

# Load environment variables
script_dir = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(script_dir, ".env")
load_dotenv(env_file)
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

mcp = FastMCP(
    "Telegram Companion",
    dependencies=["httpx", "python-dotenv"]
)

def _reload_env_if_needed():
    global BOT_TOKEN, ALLOWED_CHAT_ID
    if not BOT_TOKEN or not ALLOWED_CHAT_ID:
        load_dotenv(env_file, override=True)
        load_dotenv(override=True)
        BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def _get_api_url(endpoint: str) -> str:
    _reload_env_if_needed()
    token = os.getenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN).strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured. Please set it in .env or environment.")
    return f"https://api.telegram.org/bot{token}/{endpoint}"

def _get_chat_id() -> str:
    _reload_env_if_needed()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", ALLOWED_CHAT_ID).strip()
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID is not configured. Please set it in .env or environment.")
    return chat_id

def _verify_sender(user_id: int) -> bool:
    """Ensure the update comes strictly from the authorized user."""
    expected_id = _get_chat_id()
    return str(user_id) == str(expected_id)

@mcp.tool()
def telegram_test_connection() -> str:
    """Tests the connection to Telegram using the configured BOT_TOKEN and verifies the bot identity."""
    try:
        url = _get_api_url("getMe")
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            data = resp.json()
            if not data.get("ok"):
                return f"Telegram API Error: {data.get('description', 'Unknown error')}"
            bot_info = data.get("result", {})
            return (
                f"Successfully connected to Telegram!\n"
                f"- Bot Name: {bot_info.get('first_name', 'Unknown')}\n"
                f"- Bot Username: @{bot_info.get('username', 'Unknown')}\n"
                f"- Target Chat ID: {_get_chat_id()}"
            )
    except Exception as e:
        return f"Connection failed: {str(e)}"

@mcp.tool()
def telegram_notify(message: str, parse_mode: Optional[str] = "Markdown") -> str:
    """
    Sends an informational notification or update to your mobile phone via Telegram.
    Use this for task completion notices, build results, or status updates.
    """
    try:
        chat_id = _get_chat_id()
        url = _get_api_url("sendMessage")
        payload = {
            "chat_id": chat_id,
            "text": message,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload)
            data = resp.json()
            if not data.get("ok"):
                # Fallback to plain text if markdown parsing failed
                if "can't parse entities" in data.get("description", "").lower():
                    payload.pop("parse_mode", None)
                    resp = client.post(url, json=payload)
                    data = resp.json()
                if not data.get("ok"):
                    return f"Failed to send notification: {data.get('description')}"

            msg_id = data.get("result", {}).get("message_id")
            return f"Notification delivered successfully (Message ID: {msg_id})."
    except Exception as e:
        return f"Error sending notification: {str(e)}"

@mcp.tool()
def telegram_ask_permission(
    prompt: str,
    options: List[str] = ["Approve", "Reject"],
    timeout_seconds: int = 120
) -> str:
    """
    Sends an interactive approval prompt to your mobile phone with action buttons.
    Blocks and waits until you tap a button on your phone or until timeout_seconds elapses.
    Default-to-deny: If timeout occurs or unauthorized tap happens, it defaults to 'Reject (Timeout)'.
    """
    try:
        chat_id = _get_chat_id()
        session_id = f"act_{int(time.time() * 1000) % 1000000}"
        
        # Build inline keyboard buttons
        keyboard = []
        row = []
        for opt in options:
            cb_data = f"{session_id}:{opt}"
            # Telegram callback_data limit is 64 bytes
            if len(cb_data.encode("utf-8")) > 64:
                cb_data = cb_data[:64]
            row.append({"text": opt, "callback_data": cb_data})
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        formatted_text = f"🚨 *Permission Request*\n\n{prompt}\n\n⏱ _Waiting for approval (timeout: {timeout_seconds}s)..._"
        
        # Send message with inline buttons
        send_url = _get_api_url("sendMessage")
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                send_url,
                json={
                    "chat_id": chat_id,
                    "text": formatted_text,
                    "parse_mode": "Markdown",
                    "reply_markup": {"inline_keyboard": keyboard}
                }
            )
            msg_data = resp.json()
            if not msg_data.get("ok"):
                # Retry without markdown
                resp = client.post(
                    send_url,
                    json={
                        "chat_id": chat_id,
                        "text": f"Permission Request:\n\n{prompt}\n\n(Waiting for approval, timeout: {timeout_seconds}s)",
                        "reply_markup": {"inline_keyboard": keyboard}
                    }
                )
                msg_data = resp.json()
                if not msg_data.get("ok"):
                    return f"Failed to send permission prompt: {msg_data.get('description')}"

            sent_msg_id = msg_data.get("result", {}).get("message_id")

            # Flush current updates offset to ignore older clicks
            updates_url = _get_api_url("getUpdates")
            up_resp = client.get(updates_url, params={"limit": 1, "offset": -1})
            up_data = up_resp.json()
            offset = None
            if up_data.get("ok") and up_data.get("result"):
                offset = up_data["result"][-1]["update_id"] + 1

            start_time = time.time()
            selected_option = None

            # Long-poll loop
            while time.time() - start_time < timeout_seconds:
                poll_params = {"timeout": 5, "allowed_updates": ["callback_query"]}
                if offset:
                    poll_params["offset"] = offset

                try:
                    p_resp = client.get(updates_url, params=poll_params, timeout=10.0)
                    p_data = p_resp.json()
                    if p_data.get("ok") and p_data.get("result"):
                        for upd in p_data["result"]:
                            offset = upd["update_id"] + 1
                            cb = upd.get("callback_query")
                            if not cb:
                                continue

                            sender = cb.get("from", {}).get("id")
                            cb_id = cb.get("id")
                            data = cb.get("data", "")

                            # Enforce user whitelist
                            if not _verify_sender(sender):
                                # Reject unauthorized click
                                client.post(_get_api_url("answerCallbackQuery"), json={
                                    "callback_query_id": cb_id,
                                    "text": "Unauthorized user.",
                                    "show_alert": True
                                })
                                continue

                            # Check if matches this session
                            if data.startswith(f"{session_id}:"):
                                selected_option = data.split(":", 1)[1]
                                # Acknowledge the callback query
                                client.post(_get_api_url("answerCallbackQuery"), json={
                                    "callback_query_id": cb_id,
                                    "text": f"Selected: {selected_option}"
                                })
                                break
                    if selected_option:
                        break
                except httpx.RequestError:
                    time.sleep(1)

            # Update the original message to remove buttons and show the outcome
            if selected_option:
                status_emoji = "✅" if selected_option.lower() in ["approve", "yes", "proceed", "ok"] else "❌"
                edit_text = f"🚨 *Permission Request*\n\n{prompt}\n\n*Result:* {status_emoji} `{selected_option}`"
            else:
                selected_option = "Reject (Timeout)"
                edit_text = f"🚨 *Permission Request*\n\n{prompt}\n\n*Result:* ⏱ Expired / Denied automatically."

            try:
                client.post(_get_api_url("editMessageText"), json={
                    "chat_id": chat_id,
                    "message_id": sent_msg_id,
                    "text": edit_text,
                    "parse_mode": "Markdown"
                })
            except Exception:
                pass

            return selected_option

    except Exception as e:
        return f"Error handling permission request: {str(e)}"

@mcp.tool()
def telegram_ask_text(prompt: str, timeout_seconds: int = 180) -> str:
    """
    Sends a prompt asking for text input from your mobile phone.
    Waits until you send a text reply on Telegram or until timeout_seconds expires.
    """
    try:
        chat_id = _get_chat_id()
        send_url = _get_api_url("sendMessage")
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(send_url, json={
                "chat_id": chat_id,
                "text": f"💬 *Input Needed*\n\n{prompt}\n\n_Reply to this message with your text..._",
                "parse_mode": "Markdown"
            })
            msg_data = resp.json()
            if not msg_data.get("ok"):
                return f"Failed to send input prompt: {msg_data.get('description')}"

            # Flush offset to recent
            updates_url = _get_api_url("getUpdates")
            up_resp = client.get(updates_url, params={"limit": 1, "offset": -1})
            up_data = up_resp.json()
            offset = None
            if up_data.get("ok") and up_data.get("result"):
                offset = up_data["result"][-1]["update_id"] + 1

            start_time = time.time()
            user_reply = None

            while time.time() - start_time < timeout_seconds:
                poll_params = {"timeout": 5, "allowed_updates": ["message"]}
                if offset:
                    poll_params["offset"] = offset

                try:
                    p_resp = client.get(updates_url, params=poll_params, timeout=10.0)
                    p_data = p_resp.json()
                    if p_data.get("ok") and p_data.get("result"):
                        for upd in p_data["result"]:
                            offset = upd["update_id"] + 1
                            msg = upd.get("message")
                            if not msg:
                                continue

                            sender = msg.get("from", {}).get("id")
                            if not _verify_sender(sender):
                                continue

                            text = msg.get("text")
                            if text:
                                user_reply = text
                                break
                    if user_reply is not None:
                        break
                except httpx.RequestError:
                    time.sleep(1)

            if user_reply is not None:
                return user_reply
            return "Timeout (No response received)"

    except Exception as e:
        return f"Error waiting for input: {str(e)}"

@mcp.tool()
def telegram_send_photo(photo_path: str, caption: str = "") -> str:
    """
    Sends an image or screenshot file to your mobile phone.
    """
    if not os.path.exists(photo_path):
        return f"File not found: {photo_path}"

    try:
        chat_id = _get_chat_id()
        url = _get_api_url("sendPhoto")
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": chat_id, "caption": caption}
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, data=data, files=files)
                res = resp.json()
                if not res.get("ok"):
                    return f"Failed to send photo: {res.get('description')}"
                return "Photo sent successfully."
    except Exception as e:
        return f"Error sending photo: {str(e)}"

@mcp.tool()
def telegram_send_file(file_path: str, caption: str = "") -> str:
    """
    Sends any document, log file, diff, or artifact to your mobile phone.
    """
    if not os.path.exists(file_path):
        return f"File not found: {file_path}"

    try:
        chat_id = _get_chat_id()
        url = _get_api_url("sendDocument")
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": chat_id, "caption": caption}
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(url, data=data, files=files)
                res = resp.json()
                if not res.get("ok"):
                    return f"Failed to send document: {res.get('description')}"
                return "Document sent successfully."
    except Exception as e:
        return f"Error sending document: {str(e)}"

@mcp.tool()
def telegram_update_progress(message_id: int, text: str) -> str:
    """
    Updates the text of an existing message in-place on Telegram.
    Ideal for real-time progress bars or dynamic status updates without spamming notifications.
    """
    try:
        chat_id = _get_chat_id()
        url = _get_api_url("editMessageText")
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown"
            })
            res = resp.json()
            if not res.get("ok"):
                return f"Failed to update progress: {res.get('description')}"
            return "Progress updated successfully."
    except Exception as e:
        return f"Error updating progress: {str(e)}"

if __name__ == "__main__":
    mcp.run()
