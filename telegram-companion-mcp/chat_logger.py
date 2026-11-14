import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CHAT_MD_PATH = PROJECT_ROOT / "CHAT.md"
DOT_CHAT_MD_PATH = PROJECT_ROOT / ".chat.md"
LAST_STEP_FILE = SCRIPT_DIR / ".last_logged_step"

def clean_text(text: str) -> str:
    """Strips metadata tags from user requests."""
    t = re.sub(r'<USER_REQUEST>\s*', '', text)
    t = re.sub(r'\s*</USER_REQUEST>', '', t)
    t = re.sub(r'<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>', '', t, flags=re.DOTALL)
    t = re.sub(r'<SYSTEM_MESSAGE>.*?</SYSTEM_MESSAGE>', '', t, flags=re.DOTALL)
    return t.strip()

def format_timestamp(iso_str: Optional[str]) -> str:
    if not iso_str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # Local time formatting
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str[:19].replace("T", " ")

def init_chat_file():
    """Initializes CHAT.md with clean header if not exists."""
    if not CHAT_MD_PATH.exists() or CHAT_MD_PATH.stat().st_size == 0:
        header = (
            "# 💬 Project Conversation & Activity Log (`CHAT.md`)\n\n"
            "> **Project:** Telegram Mobile Companion (`Friday`)\n"
            "> **Repository:** [https://github.com/riteshray830/telegram-mobile-companion](https://github.com/riteshray830/telegram-mobile-companion)\n"
            f"> **Tracking Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "---\n\n"
        )
        CHAT_MD_PATH.write_text(header, encoding="utf-8")
        try:
            DOT_CHAT_MD_PATH.write_text(header, encoding="utf-8")
        except Exception:
            pass

def append_turn_to_chat(user_msg: str, assistant_msg: str, timestamp_str: Optional[str] = None, source: str = "Chat"):
    """Appends a single Q&A turn to CHAT.md and .chat.md."""
    init_chat_file()
    time_display = format_timestamp(timestamp_str)

    src_badge = f"`[{source}]`" if source != "Chat" else ""

    entry = (
        f"### 🕒 {time_display} {src_badge}\n\n"
        f"#### 👤 **User:**\n"
        f"{user_msg.strip()}\n\n"
        f"#### 🤖 **Friday / Assistant:**\n"
        f"{assistant_msg.strip()}\n\n"
        f"---\n\n"
    )

    with open(CHAT_MD_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

    try:
        with open(DOT_CHAT_MD_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

def sync_from_transcript(transcript_path: str):
    """
    Parses transcript.jsonl, identifies new user/assistant turns since last logged step,
    and appends them to CHAT.md.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return

    last_step = -1
    if LAST_STEP_FILE.exists():
        try:
            last_step = int(LAST_STEP_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            last_step = -1

    init_chat_file()

    turns = []
    current_user = None
    current_user_time = None
    max_step_found = last_step

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    src = d.get("source")
                    t = d.get("type")
                    step_idx = d.get("step_index", -1)
                    created = d.get("created_at")
                    content = d.get("content", "")

                    if step_idx <= last_step and last_step != -1:
                        continue

                    if step_idx > max_step_found:
                        max_step_found = step_idx

                    if src == "USER_EXPLICIT" and t == "USER_INPUT" and content:
                        clean_u = clean_text(content)
                        if clean_u:
                            current_user = clean_u
                            current_user_time = created

                    elif src == "MODEL" and t == "PLANNER_RESPONSE" and content:
                        if current_user:
                            turns.append({
                                "user": current_user,
                                "assistant": content.strip(),
                                "time": current_user_time or created
                            })
                            current_user = None
                except Exception:
                    continue

        for turn in turns:
            append_turn_to_chat(
                user_msg=turn["user"],
                assistant_msg=turn["assistant"],
                timestamp_str=turn["time"],
                source="Antigravity"
            )

        if max_step_found > last_step:
            LAST_STEP_FILE.write_text(str(max_step_found), encoding="utf-8")

    except Exception as e:
        sys.stderr.write(f"[chat_logger] Error syncing transcript: {e}\n")

def rebuild_full_chat_history(transcript_path: str):
    """Rebuilds the entire CHAT.md file from scratch using the full transcript."""
    if not transcript_path or not os.path.exists(transcript_path):
        return

    # Reset
    header = (
        "# 💬 Project Conversation & Activity Log (`CHAT.md`)\n\n"
        "> **Project:** Telegram Mobile Companion (`Friday`)\n"
        "> **Repository:** [https://github.com/riteshray830/telegram-mobile-companion](https://github.com/riteshray830/telegram-mobile-companion)\n"
        f"> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "> **Notice:** This file automatically records all conversation turns and commands across both Antigravity and Telegram.\n\n"
        "---\n\n"
    )
    CHAT_MD_PATH.write_text(header, encoding="utf-8")
    try:
        DOT_CHAT_MD_PATH.write_text(header, encoding="utf-8")
    except Exception:
        pass

    if LAST_STEP_FILE.exists():
        LAST_STEP_FILE.unlink()

    sync_from_transcript(transcript_path)

if __name__ == "__main__":
    t_path = sys.argv[1] if len(sys.argv) > 1 else ""
    if t_path:
        rebuild_full_chat_history(t_path)
        print(f"Rebuilt CHAT.md from: {t_path}")
    else:
        print("Usage: python chat_logger.py <transcript_path>")
