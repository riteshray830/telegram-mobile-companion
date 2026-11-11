import sys
import os
import json
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

    state_file = script_dir / ".last_forwarded_step"
    last_sent_step = -1
    if state_file.exists():
        try:
            last_sent_step = int(state_file.read_text(encoding="utf-8").strip())
        except Exception:
            last_sent_step = -1

    try:
        with open(transcript_path_str, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        target_step_idx = -1
        last_content = None

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
                        # Already sent or older step
                        break
            except Exception:
                continue

        if last_content and target_step_idx > last_sent_step:
            header = "🤖 *Antigravity:*\n\n"
            full_msg = header + last_content

            chunks = [full_msg[i:i+3800] for i in range(0, len(full_msg), 3800)]
            api_url = f"https://api.telegram.org/bot{token}/sendMessage"

            with httpx.Client(timeout=15.0) as client:
                for chunk in chunks:
                    resp = client.post(api_url, json={
                        "chat_id": chat_id,
                        "text": chunk,
                        "parse_mode": "Markdown"
                    })
                    res_data = resp.json()
                    if not res_data.get("ok"):
                        # Fallback without markdown
                        client.post(api_url, json={
                            "chat_id": chat_id,
                            "text": chunk
                        })

            # Update state
            state_file.write_text(str(target_step_idx), encoding="utf-8")
    except Exception as e:
        log_err(f"Error forwarding reply: {e}")

    print(json.dumps({}))

if __name__ == "__main__":
    main()
