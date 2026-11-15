import sys
import os
import json
import time
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Ensure stdout uses UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def log_err(msg):
    sys.stderr.write(f"[forward_reply_hook] {msg}\n")
    sys.stderr.flush()

def main():
    try:
        raw_input = sys.stdin.read().strip()
        if raw_input.startswith("\ufeff"):
            raw_input = raw_input[1:]
        payload = json.loads(raw_input) if raw_input else {}
    except Exception as e:
        log_err(f"Failed to parse stdin JSON: {e}")
        print(json.dumps({}))
        return

    transcript_path_str = payload.get("transcriptPath", "")

    # Load credentials
    script_dir = Path(__file__).resolve().parent
    env_file = script_dir / ".env"
    load_dotenv(env_file)
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        log_err("Missing bot token or chat ID.")
        print(json.dumps({}))
        return

    if not transcript_path_str or not os.path.exists(transcript_path_str):
        log_err(f"Transcript path not found: {transcript_path_str}")
        print(json.dumps({}))
        return

    t_path = Path(transcript_path_str)
    # Extract conversation ID from path: brain/<conv_id>/.system_generated/logs/transcript.jsonl
    try:
        conv_id = t_path.parent.parent.parent.name
    except Exception:
        conv_id = "default"

    # Automatically bind this conversation as the active Telegram session
    project_label = "Project"
    try:
        import session_manager
        meta = session_manager.bind_session(conv_id)
        ws = meta.get("workspace", "")
        if ws and ws != "Unknown":
            project_label = Path(ws).name
        else:
            project_label = meta.get("title", "Project")
    except Exception as e:
        log_err(f"Error updating active session: {e}")

    # Automatically log conversation turns to CHAT.md
    try:
        import chat_logger
        chat_logger.sync_from_transcript(transcript_path_str)
    except Exception as e:
        log_err(f"Error updating CHAT.md: {e}")

    # Conversation-scoped step tracking
    steps_file = script_dir / ".last_forwarded_steps.json"
    steps_map = {}
    if steps_file.exists():
        try:
            steps_map = json.loads(steps_file.read_text(encoding="utf-8"))
        except Exception:
            steps_map = {}

    last_sent_step = steps_map.get(conv_id, -1)

    # Prefer transcript_full.jsonl to ensure content is NEVER truncated
    full_transcript_path = t_path.parent / "transcript_full.jsonl"
    source_file = full_transcript_path if full_transcript_path.exists() else t_path

    try:
        with open(source_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        target_step_idx = -1
        last_content = None

        # Look for the last model response (prefer PLANNER_RESPONSE)
        for line in reversed(lines):
            try:
                data = json.loads(line)
                is_model = (data.get("source") == "MODEL")
                msg_type = data.get("type")
                content = data.get("content", "").strip()

                if is_model and msg_type == "PLANNER_RESPONSE" and content:
                    step_idx = data.get("step_index", -1)
                    if step_idx > last_sent_step:
                        target_step_idx = step_idx
                        last_content = content
                        break
                    else:
                        break
            except Exception:
                continue

        # Fallback if no PLANNER_RESPONSE with content found
        if not last_content:
            for line in reversed(lines):
                try:
                    data = json.loads(line)
                    if data.get("source") == "MODEL" and data.get("content"):
                        step_idx = data.get("step_index", -1)
                        if step_idx > last_sent_step:
                            target_step_idx = step_idx
                            last_content = data["content"].strip()
                            break
                        else:
                            break
                except Exception:
                    continue

        if last_content and target_step_idx > last_sent_step:
            header = f"🤖 *Antigravity [{project_label}]:*\n\n"
            full_msg = header + last_content

            # Chunk into safe 3800-character segments
            chunks = [full_msg[i:i+3800] for i in range(0, len(full_msg), 3800)]
            api_url = f"https://api.telegram.org/bot{token}/sendMessage"

            with httpx.Client(timeout=20.0) as client:
                for idx, chunk in enumerate(chunks):
                    payload = {
                        "chat_id": chat_id,
                        "text": chunk,
                        "parse_mode": "Markdown"
                    }
                    try:
                        resp = client.post(api_url, json=payload)
                        res_data = resp.json()
                        # If Telegram rejects markdown formatting across chunks, fallback to raw clean text
                        if not res_data.get("ok"):
                            payload.pop("parse_mode", None)
                            client.post(api_url, json=payload)
                    except Exception as net_err:
                        log_err(f"Network error delivering chunk {idx}: {net_err}")

                    # Slight pause between chunks to respect Telegram rate limits and preserve sequence
                    if idx < len(chunks) - 1:
                        time.sleep(0.35)

            # Update conversation-scoped step map
            steps_map[conv_id] = target_step_idx
            steps_file.write_text(json.dumps(steps_map, indent=2), encoding="utf-8")

    except Exception as e:
        log_err(f"Error forwarding reply: {e}")

    print(json.dumps({}))

if __name__ == "__main__":
    main()
