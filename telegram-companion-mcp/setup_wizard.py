#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path
import httpx

# Ensure UTF-8 output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def print_banner():
    print("=" * 65)
    print(" 📱 Friday Mobile Companion & Remote Dev Assistant")
    print("    Interactive Multi-Platform Setup Wizard")
    print("=" * 65)
    print("This wizard will configure Friday on this laptop.\n")

def get_default_workspace():
    if sys.platform == "win32" and Path(r"D:\dev").exists():
        return r"D:\dev"
    home_dev = Path.home() / "dev"
    if home_dev.exists():
        return str(home_dev)
    return str(Path.cwd())

def prompt_input(prompt: str, default: str = "") -> str:
    if default:
        res = input(f"{prompt} [{default}]: ").strip()
        return res if res else default
    else:
        while True:
            res = input(f"{prompt}: ").strip()
            if res:
                return res
            print("  ⚠️  This field cannot be empty.")

def main():
    print_banner()

    script_dir = Path(__file__).resolve().parent
    env_file = script_dir / ".env"

    if env_file.exists():
        print(f"ℹ️ An existing configuration was found at:\n  {env_file}")
        overwrite = input("\nDo you want to reconfigure? (y/N): ").strip().lower()
        if overwrite not in ["y", "yes"]:
            print("Setup cancelled. Existing configuration retained.")
            return

    print("\n--- [Step 1/5] Workspace Directory ---")
    default_ws = get_default_workspace()
    ws_root = prompt_input("Enter the root dev folder to manage", default_ws)
    ws_path = Path(ws_root).resolve()
    if not ws_path.exists():
        create_ws = input(f"Directory `{ws_path}` does not exist. Create it? (Y/n): ").strip().lower()
        if create_ws not in ["n", "no"]:
            ws_path.mkdir(parents=True, exist_ok=True)
            print(f"  ✅ Created `{ws_path}`")

    print("\n--- [Step 2/5] AI Engine / Chatbot Selection ---")
    print("Choose the AI backend for your laptop:")
    print("  [1] Google Antigravity (Default — connects to active IDE pair programming)")
    print("  [2] Google Gemini (Gemini 2.5 Flash / Pro)")
    print("  [3] OpenAI (GPT-4o / GPT-4o-mini)")
    print("  [4] Anthropic Claude (Claude 3.5 Sonnet)")
    print("  [5] Ollama (Local offline models, e.g. Llama 3, Qwen, DeepSeek)")

    choice = prompt_input("Select an option (1-5)", "1")
    backend_map = {
        "1": "antigravity",
        "2": "gemini",
        "3": "openai",
        "4": "claude",
        "5": "ollama"
    }
    ai_backend = backend_map.get(choice, "antigravity")
    print(f"  👉 Selected AI Backend: {ai_backend}")

    api_key = ""
    extra_vars = {}

    if ai_backend == "gemini":
        print("\nGet a free API key from https://aistudio.google.com/")
        api_key = prompt_input("Enter your GEMINI_API_KEY")
        extra_vars["GEMINI_API_KEY"] = api_key
        extra_vars["GEMINI_MODEL"] = "gemini-2.5-flash"
    elif ai_backend == "openai":
        api_key = prompt_input("Enter your OPENAI_API_KEY")
        extra_vars["OPENAI_API_KEY"] = api_key
        extra_vars["OPENAI_MODEL"] = "gpt-4o-mini"
    elif ai_backend == "claude":
        api_key = prompt_input("Enter your ANTHROPIC_API_KEY")
        extra_vars["ANTHROPIC_API_KEY"] = api_key
        extra_vars["CLAUDE_MODEL"] = "claude-3-5-sonnet-20241022"
    elif ai_backend == "ollama":
        ollama_host = prompt_input("Enter Ollama host", "http://localhost:11434")
        ollama_model = prompt_input("Enter Ollama model name", "llama3.2")
        extra_vars["OLLAMA_HOST"] = ollama_host
        extra_vars["OLLAMA_MODEL"] = ollama_model

    print("\n--- [Step 3/5] Telegram Bot Token ---")
    print("1. Open Telegram on your phone and search for @BotFather.")
    print("2. Send `/newbot`, name your bot, and copy the Bot Token.")
    bot_token = prompt_input("Paste your Telegram Bot Token")

    # Validate bot token with getMe
    bot_name = ""
    bot_username = ""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
            data = resp.json()
            if not data.get("ok"):
                print(f"❌ Invalid Bot Token: {data.get('description')}")
                return
            bot_info = data.get("result", {})
            bot_name = bot_info.get("first_name", "Bot")
            bot_username = bot_info.get("username", "")
            print(f"  ✅ Validated Bot: {bot_name} (@{bot_username})")
    except Exception as e:
        print(f"⚠️ Could not reach Telegram API: {e}")

    print("\n--- [Step 4/5] Telegram User / Chat ID ---")
    print("To keep your laptop secure, the bot only responds to YOUR specific User ID.")
    print("  [1] Auto-Detect (Open your bot on phone & tap Start — wizard listens automatically)")
    print("  [2] Enter Numeric ID manually")

    id_mode = prompt_input("Choose ID detection method (1 or 2)", "1")
    chat_id = ""

    if id_mode == "1":
        print(f"\n👉 Open Telegram, open @{bot_username}, and tap START (or send 'hi')...")
        print("Listening for 60 seconds...")
        start_t = time.time()
        with httpx.Client(timeout=35.0) as client:
            while time.time() - start_t < 60:
                try:
                    r = client.get(f"https://api.telegram.org/bot{bot_token}/getUpdates", params={"timeout": 5})
                    d = r.json()
                    if d.get("ok") and d.get("result"):
                        for upd in d["result"]:
                            msg = upd.get("message") or upd.get("my_chat_member")
                            if msg:
                                chat = msg.get("chat", {})
                                c_id = chat.get("id")
                                if c_id:
                                    chat_id = str(c_id)
                                    u_name = chat.get("first_name", "User")
                                    print(f"  🎉 Detected User ID: {chat_id} ({u_name})!")
                                    break
                    if chat_id:
                        break
                except Exception:
                    time.sleep(1)
        if not chat_id:
            print("⏱ Auto-detect timed out. Please enter your ID manually.")
            chat_id = prompt_input("Enter your numeric Telegram User ID")
    else:
        chat_id = prompt_input("Enter your numeric Telegram User ID")

    print("\n--- [Step 5/5] Saving Configuration & Testing ---")
    env_lines = [
        f'TELEGRAM_BOT_TOKEN="{bot_token}"',
        f'TELEGRAM_CHAT_ID="{chat_id}"',
        f'PROJECTS_ROOT="{ws_path}"',
        f'AI_BACKEND="{ai_backend}"'
    ]
    for k, v in extra_vars.items():
        env_lines.append(f'{k}="{v}"')

    env_content = "\n".join(env_lines) + "\n"
    env_file.write_text(env_content, encoding="utf-8")
    print(f"✅ Configuration saved to: {env_file}")

    # Send welcome confirmation to Telegram
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": (
                        f"🎉 *Setup Complete on your Laptop!*\n\n"
                        f"• *AI Backend:* `{ai_backend}`\n"
                        f"• *Workspace:* `{ws_path}`\n"
                        f"• *Host:* `{sys.platform}`\n\n"
                        f"Type any message to start chatting!"
                    ),
                    "parse_mode": "Markdown"
                }
            )
            print("  📱 Test confirmation sent to your phone!")
    except Exception as e:
        print("  ⚠️ Could not send Telegram test message:", e)

    print("\n" + "=" * 65)
    print(" 🎉 Setup is complete!")
    print(" You can start Friday anytime with:")
    print("   python telegram-companion-mcp/friday_runner.py")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()

