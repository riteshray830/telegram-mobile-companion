#!/usr/bin/env python3
import os
import sys
import json
import shutil
from pathlib import Path

# Ensure UTF-8 output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def register_antigravity():
    print("=" * 65)
    print(" 🛠️  Configuring Telegram Companion for Antigravity on this Machine")
    print("=" * 65)

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    server_script = script_dir / "server.py"
    hook_script = script_dir / "forward_reply_hook.py"
    py_exe = sys.executable

    gemini_config_dir = Path.home() / ".gemini" / "config"
    gemini_config_dir.mkdir(parents=True, exist_ok=True)

    # 1. Register MCP Server in ~/.gemini/config/mcp_config.json
    mcp_config_file = gemini_config_dir / "mcp_config.json"
    mcp_data = {"mcpServers": {}}
    if mcp_config_file.exists():
        try:
            mcp_data = json.loads(mcp_config_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Read .env for credentials
    env_file = script_dir / ".env"
    bot_token = ""
    chat_id = ""
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                bot_token = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("TELEGRAM_CHAT_ID="):
                chat_id = line.split("=", 1)[1].strip().strip('"').strip("'")

    mcp_data["mcpServers"]["telegram-companion"] = {
        "command": py_exe,
        "args": [str(server_script)],
        "env": {
            "TELEGRAM_BOT_TOKEN": bot_token,
            "TELEGRAM_CHAT_ID": chat_id
        }
    }
    mcp_config_file.write_text(json.dumps(mcp_data, indent=2), encoding="utf-8")
    print(f"✅ Registered MCP Server in: {mcp_config_file}")

    # 2. Register Hook in ~/.gemini/config/hooks.json
    hooks_file = gemini_config_dir / "hooks.json"
    hooks_data = {}
    if hooks_file.exists():
        try:
            hooks_data = json.loads(hooks_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    cmd_hook = f'python "{hook_script.as_posix()}"'
    hooks_data["telegram-forwarder"] = {
        "Stop": [
            {
                "type": "command",
                "command": cmd_hook,
                "timeout": 15
            }
        ]
    }
    hooks_file.write_text(json.dumps(hooks_data, indent=2), encoding="utf-8")
    print(f"✅ Registered Lifecycle Hook in: {hooks_file}")

    # 3. Register Global Plugin & Skill in ~/.gemini/config/plugins/telegram-companion
    plugin_dest = gemini_config_dir / "plugins" / "telegram-companion"
    plugin_dest.mkdir(parents=True, exist_ok=True)
    skills_dest = plugin_dest / "skills" / "telegram-companion"
    skills_dest.mkdir(parents=True, exist_ok=True)

    plugin_json_src = repo_root / "plugin.json"
    skill_md_src = repo_root / "SKILL.md"

    plugin_meta = {
        "name": "telegram-companion",
        "displayName": "Telegram Mobile Companion",
        "version": "1.0.0",
        "description": "Two-way Telegram mobile companion and remote dev controller.",
        "author": {"name": "Ritesh Ray"}
    }
    (plugin_dest / "plugin.json").write_text(json.dumps(plugin_meta, indent=2), encoding="utf-8")

    if skill_md_src.exists():
        shutil.copy(skill_md_src, skills_dest / "SKILL.md")
    print(f"✅ Installed Global Antigravity Plugin & Skill at: {plugin_dest}")

    print("\n" + "=" * 65)
    print(" 🎉 Antigravity on this laptop is now fully configured!")
    print("    Every project opened in Antigravity will now automatically have")
    print("    Telegram Companion tools and remote controls available.")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    register_antigravity()
