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
    # Read hook input from stdin
    try:
        raw_input = sys.stdin.read().strip()
        if raw_input.startswith("\ufeff"):
            raw_input = raw_input[1:]
        payload = json.loads(raw_input) if raw_input else {}
    except Exception as e:
        log_err(f"Failed to parse stdin JSON: {e}")
        # Always output valid JSON on exit
        print(json.dumps({}))
        return

    # Check termination reason: only forward when model finished responding (normal completion)
    term_reason = payload.get("terminationReason", "")
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

    try:
        # Read the last response from transcript
        with open(transcript_path_str, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        last_content = None
        for line in reversed(lines):
            try:
                data = json.loads(line)
                if data.get("source") == "MODEL" and data.get("content"):
                    last_content = data["content"].strip()
                    break
            except Exception:
                continue

        if last_content:
            # Format and send to Telegram
            header = "🤖 *Antigravity:*\n\n"
            full_msg = header + last_content

            # Chunk into safe sizes (under 4096 limit)
            chunks = [full_msg[i:i+3800] for i in range(0, len(full_msg), 3800)]
            api_url = f"https://api.telegram.org/bot{token}/sendMessage"

            with httpx.Client(timeout=15.0) as client:
                for chunk in chunks:
                    resp = client.post(api_url, json={
                        "chat_id": chat_id,
                        "text": chunk,
                        "parse_mode": "Markdown"
                    })
                    # If markdown parsing fails due to unmatched asterisks/entities, retry as plain text
                    res_data = resp.json()
                    if not res_data.get("ok"):
                        client.post(api_url, json={
                            "chat_id": chat_id,
                            "text": chunk
                        })
    except Exception as e:
        log_err(f"Error forwarding reply: {e}")

    # Hook response contract
    print(json.dumps({}))

if __name__ == "__main__":
    main()
