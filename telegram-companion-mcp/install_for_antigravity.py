#!/usr/bin/env python3
import os
import sys
import json
import shutil
import asyncio
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

    # 1. Register MCP Server in ~/.gemini/config/mcp_config.json with unbuffered python
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
        "args": ["-u", str(server_script)],
        "env": {
            "TELEGRAM_BOT_TOKEN": bot_token,
            "TELEGRAM_CHAT_ID": chat_id,
            "PYTHONUNBUFFERED": "1"
        }
    }
    mcp_config_file.write_text(json.dumps(mcp_data, indent=2), encoding="utf-8")
    print(f"✅ Registered MCP Server (unbuffered) in: {mcp_config_file}")

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

    # 3. Export all MCP tool schemas directly to ~/.gemini/antigravity/mcp/telegram-companion
    try:
        sys.path.insert(0, str(script_dir))
        from server import mcp
        mcp_dest = Path.home() / ".gemini" / "antigravity" / "mcp" / "telegram-companion"
        mcp_dest.mkdir(parents=True, exist_ok=True)

        async def dump_schemas():
            tools = await mcp.list_tools()
            for t in tools:
                t_data = {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema or {"type": "object", "properties": {}}
                }
                (mcp_dest / f"{t.name}.json").write_text(json.dumps(t_data, indent=2), encoding="utf-8")
            print(f"✅ Exported {len(tools)} tool schemas to: {mcp_dest}")

        asyncio.run(dump_schemas())
    except Exception as e:
        print(f"⚠️ Could not auto-dump MCP schemas: {e}")

    # 4. Register Global Plugin & Skill in ~/.gemini/config/plugins/telegram-companion
    plugin_dest = gemini_config_dir / "plugins" / "telegram-companion"
    plugin_dest.mkdir(parents=True, exist_ok=True)
    skills_dest = plugin_dest / "skills" / "telegram-companion"
    skills_dest.mkdir(parents=True, exist_ok=True)

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

    # 5. Bind current active session
    try:
        import session_manager
        active = session_manager.get_active_session()
        cid = active.get("conv_id")
        if cid:
            session_manager.bind_session(cid, active.get("title", ""), active.get("workspace", ""))
            print(f"✅ Bound active session: {cid} ({active.get('workspace')})")
    except Exception as e:
        pass

    print("\n" + "=" * 65)
    print(" 🎉 Antigravity on this laptop is now 100% configured!")
    print("    Every project opened in Antigravity will now automatically have")
    print("    Telegram Companion tools, full replies, and remote controls available.")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    register_antigravity()
