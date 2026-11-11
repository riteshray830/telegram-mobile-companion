import os
import sys
import glob
import json
import time
import shutil
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
PROJECTS_ROOT = Path(os.getenv("PROJECTS_ROOT", r"d:\dev\projects")).resolve()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not TOKEN or not ALLOWED_CHAT_ID:
    print(f"Error: Missing credentials in {env_file}")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{TOKEN}"

# State
current_project = PROJECTS_ROOT / "exploring"
if not current_project.exists():
    current_project = PROJECTS_ROOT

def is_authorized(user_id: int) -> bool:
    return str(user_id) == str(ALLOWED_CHAT_ID)

async def send_msg(client: httpx.AsyncClient, text: str, parse_mode: Optional[str] = "Markdown", reply_markup: Optional[dict] = None):
    # Telegram message text limit is 4096 characters
    if len(text) > 4000:
        chunks = [text[i:i+3800] for i in range(0, len(text), 3800)]
        for idx, chunk in enumerate(chunks):
            payload = {"chat_id": ALLOWED_CHAT_ID, "text": chunk}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if idx == len(chunks) - 1 and reply_markup:
                payload["reply_markup"] = reply_markup
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
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        r = await client.post(f"{API_URL}/sendMessage", json=payload)
        res = r.json()
        if not res.get("ok") and parse_mode:
            # Fallback to plain text if markdown entity parse failed
            payload.pop("parse_mode")
            await client.post(f"{API_URL}/sendMessage", json=payload)
    except Exception as e:
        print("Error sending msg:", e)

async def send_file_doc(client: httpx.AsyncClient, file_path: Path, caption: str = ""):
    if not file_path.exists():
        await send_msg(client, f"File not found: {file_path}")
        return
    try:
        with open(file_path, "rb") as f:
            files = {"document": (file_path.name, f)}
            data = {"chat_id": ALLOWED_CHAT_ID, "caption": caption}
            await client.post(f"{API_URL}/sendDocument", data=data, files=files, timeout=40.0)
    except Exception as e:
        await send_msg(client, f"Failed to send file: {e}")

# ==========================================
# Project Management Handlers
# ==========================================

def get_project_type(p: Path) -> str:
    if (p / "pubspec.yaml").exists():
        return "Flutter / Dart"
    if (p / "package.json").exists():
        return "Node.js / Web"
    if (p / "pyproject.toml").exists() or (p / "requirements.txt").exists():
        return "Python"
    if (p / "index.html").exists():
        return "HTML / Frontend"
    if (p / ".git").exists():
        return "Git Repo"
    return "Directory"

async def handle_list_projects(client: httpx.AsyncClient):
    global current_project
    if not PROJECTS_ROOT.exists():
        await send_msg(client, f"Projects directory does not exist: `{PROJECTS_ROOT}`")
        return

    items = [p for p in PROJECTS_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if not items:
        await send_msg(client, f"No projects found in `{PROJECTS_ROOT}`.\n\nUse `/create <type> <name>` to start one!")
        return

    lines = [f"📂 *Projects in* `{PROJECTS_ROOT}`:\n"]
    buttons = []
    for p in items:
        ptype = get_project_type(p)
        active_mark = " 👉 *(active)*" if p == current_project else ""
        lines.append(f"• *{p.name}* — _{ptype}_{active_mark}")
        buttons.append([{"text": f"Select: {p.name}", "callback_data": f"select:{p.name}"}])

    lines.append(f"\n_Active Project:_ `{current_project.name}`")
    keyboard = {"inline_keyboard": buttons}
    await send_msg(client, "\n".join(lines), reply_markup=keyboard)

async def handle_select_project(client: httpx.AsyncClient, name: str):
    global current_project
    target = PROJECTS_ROOT / name.strip()
    if not target.exists() or not target.is_dir():
        await send_msg(client, f"❌ Project not found: `{name}`")
        return

    current_project = target
    ptype = get_project_type(target)
    await send_msg(client, f"✅ Active project switched to: *{target.name}* (`{ptype}`)\nPath: `{target}`")

async def handle_create_project(client: httpx.AsyncClient, args_str: str):
    global current_project
    parts = args_str.strip().split(maxsplit=1)
    if len(parts) == 1:
        ptype = "python"
        pname = parts[0]
    elif len(parts) == 2:
        ptype = parts[0].lower()
        pname = parts[1]
    else:
        await send_msg(client, "Usage: `/create <type> <name>`\nTypes: `python`, `node`, `web`, `empty`\nExample: `/create python my-bot`")
        return

    target = PROJECTS_ROOT / pname
    if target.exists():
        await send_msg(client, f"❌ Project `{pname}` already exists in `{PROJECTS_ROOT}`!")
        return

    try:
        target.mkdir(parents=True, exist_ok=True)
        # Template scaffolding
        if ptype in ["python", "py"]:
            (target / "main.py").write_text("#!/usr/bin/env python3\n\ndef main():\n    print('Hello from " + pname + "!')\n\nif __name__ == '__main__':\n    main()\n", encoding="utf-8")
            (target / "README.md").write_text(f"# {pname}\n\nPython project created via Telegram.\n", encoding="utf-8")
            (target / ".gitignore").write_text("__pycache__/\n*.pyc\n.venv/\n.env\n", encoding="utf-8")
        elif ptype in ["node", "js", "ts"]:
            pkg = {
                "name": pname,
                "version": "1.0.0",
                "description": "Created via Telegram",
                "main": "index.js",
                "scripts": {"start": "node index.js"},
                "license": "MIT"
            }
            (target / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
            (target / "index.js").write_text("console.log('Hello from " + pname + "!');\n", encoding="utf-8")
            (target / "README.md").write_text(f"# {pname}\n\nNode.js project created via Telegram.\n", encoding="utf-8")
            (target / ".gitignore").write_text("node_modules/\n.env\n", encoding="utf-8")
        elif ptype in ["web", "html"]:
            (target / "index.html").write_text(f"<!DOCTYPE html>\n<html>\n<head><title>{pname}</title></head>\n<body>\n  <h1>Welcome to {pname}</h1>\n</body>\n</html>\n", encoding="utf-8")
            (target / "style.css").write_text("body { font-family: sans-serif; margin: 2rem; }\n", encoding="utf-8")
            (target / "README.md").write_text(f"# {pname}\n\nWeb project created via Telegram.\n", encoding="utf-8")
        else:
            (target / "README.md").write_text(f"# {pname}\n\nProject created via Telegram.\n", encoding="utf-8")

        # Initialize Git repo
        try:
            subprocess.run(["git", "init"], cwd=target, capture_output=True, timeout=5)
        except Exception:
            pass

        current_project = target
        await send_msg(client, f"🎉 *Project Created Successfully!*\n\n• Name: *{pname}*\n• Type: `{ptype}`\n• Path: `{target}`\n\nSet as active project.")
    except Exception as e:
        await send_msg(client, f"❌ Failed to create project: {e}")

async def handle_list_files(client: httpx.AsyncClient, subpath: str = ""):
    target_dir = current_project / subpath.strip() if subpath else current_project
    if not target_dir.exists() or not target_dir.is_dir():
        await send_msg(client, f"Directory not found: `{target_dir}`")
        return

    items = list(target_dir.iterdir())
    if not items:
        await send_msg(client, f"📁 `{target_dir.name}` is empty.")
        return

    dirs = sorted([f"📁 {p.name}/" for p in items if p.is_dir() and not p.name.startswith(".")])
    files = sorted([f"📄 {p.name} ({p.stat().st_size} B)" for p in items if p.is_file() and not p.name.startswith(".")])
    
    listing = "\n".join(dirs + files)
    rel_path = target_dir.relative_to(PROJECTS_ROOT)
    await send_msg(client, f"📂 *Listing:* `{rel_path}`\n\n```text\n{listing}\n```")

async def handle_find_files(client: httpx.AsyncClient, query: str):
    if not query.strip():
        await send_msg(client, "Usage: `/find <filename or pattern>`\nExample: `/find *.py` or `/find server`")
        return

    q = query.strip()
    pattern = f"*{q}*" if not any(c in q for c in "*?[]") else q
    matches = list(current_project.rglob(pattern))
    
    # Filter out venv, git, node_modules
    clean_matches = [
        m for m in matches 
        if not any(part.startswith(".") or part in ["node_modules", ".venv", "__pycache__"] for part in m.parts)
    ][:20]

    if not clean_matches:
        await send_msg(client, f"🔍 No files found matching `{q}` in *{current_project.name}*.")
        return

    lines = [f"🔍 *Found {len(clean_matches)} matches in* `{current_project.name}`:\n"]
    for m in clean_matches:
        rel = m.relative_to(current_project)
        icon = "📁" if m.is_dir() else "📄"
        lines.append(f"{icon} `{rel}`")

    await send_msg(client, "\n".join(lines))

async def handle_read_file(client: httpx.AsyncClient, file_str: str):
    if not file_str.strip():
        await send_msg(client, "Usage: `/read <relative_file_path>`\nExample: `/read main.py`")
        return

    target = (current_project / file_str.strip()).resolve()
    if not target.exists() or not target.is_file():
        await send_msg(client, f"❌ File not found: `{file_str}`")
        return

    # Check size
    size = target.stat().st_size
    if size > 30000:
        # Too big for text message, send as document
        await send_msg(client, f"📄 File is large ({size} bytes). Sending as document...")
        await send_file_doc(client, target, caption=f"{target.name}")
        return

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        ext = target.suffix.lstrip(".") or "text"
        await send_msg(client, f"📄 *{target.name}* (`{file_str}`):\n\n```{ext}\n{content}\n```")
    except Exception as e:
        await send_msg(client, f"❌ Failed to read file: {e}")

async def handle_write_file(client: httpx.AsyncClient, text_payload: str):
    lines = text_payload.strip().split("\n", 1)
    if len(lines) < 2:
        await send_msg(client, "Usage:\n`/write <filename>`\n`<file contents>`")
        return

    first_line = lines[0].replace("/write", "").strip()
    content = lines[1]
    target = (current_project / first_line).resolve()

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        await send_msg(client, f"✅ Successfully written to `{target.relative_to(PROJECTS_ROOT)}` ({len(content)} chars).")
    except Exception as e:
        await send_msg(client, f"❌ Failed to write file: {e}")

async def handle_run_command(client: httpx.AsyncClient, cmd_str: str):
    cmd = cmd_str.strip()
    if not cmd:
        await send_msg(client, "Usage: `/run <command>`\nExample: `/run git status` or `/run python main.py`")
        return

    await send_msg(client, f"⚙️ Running in `{current_project.name}`:\n`{cmd}`...")
    
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(current_project),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=45.0)
            out_str = stdout.decode("utf-8", errors="replace").strip()
            err_str = stderr.decode("utf-8", errors="replace").strip()
            code = proc.returncode

            result_parts = []
            if out_str:
                result_parts.append(f"```text\n{out_str}\n```")
            if err_str:
                result_parts.append(f"⚠️ *Stderr:*\n```text\n{err_str}\n```")
            if not result_parts:
                result_parts.append("_Command finished with no output._")

            status_icon = "✅" if code == 0 else f"❌ (Exit {code})"
            header = f"{status_icon} *Result for:* `{cmd}`\n\n"
            await send_msg(client, header + "\n".join(result_parts))
        except asyncio.TimeoutError:
            proc.kill()
            await send_msg(client, f"⏱ Command timed out after 45s: `{cmd}`")
    except Exception as e:
        await send_msg(client, f"❌ Execution error: {e}")

async def handle_git(client: httpx.AsyncClient, git_args: str):
    sub = git_args.strip() or "status -s"
    await handle_run_command(client, f"git {sub}")

async def handle_ai_chat(client: httpx.AsyncClient, user_text: str):
    """Fallback natural-language chat assistant."""
    # Check if user query matches common natural requests
    lower = user_text.lower()
    if any(k in lower for k in ["list project", "my project", "show project", "what project"]):
        await handle_list_projects(client)
        return
    if lower.startswith("create project "):
        await handle_create_project(client, user_text[15:])
        return
    if lower.startswith("run "):
        await handle_run_command(client, user_text[4:])
        return
    if lower in ["git status", "git diff", "git log"]:
        await handle_git(client, lower[4:])
        return
    if any(k in lower for k in ["files", "list files", "ls"]):
        await handle_list_files(client)
        return

    # If GEMINI_API_KEY is available, invoke Gemini AI chat
    if GEMINI_API_KEY:
        try:
            prompt = (
                f"You are Friday, an AI developer assistant connected to the user's PC via Telegram.\n"
                f"Active project: {current_project.name} at {current_project}\n"
                f"Projects root: {PROJECTS_ROOT}\n"
                f"User asked: {user_text}\n"
                f"Give a concise, helpful response formatted in Telegram markdown."
            )
            g_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            async with httpx.AsyncClient(timeout=30.0) as g_client:
                res = await g_client.post(g_url, json={
                    "contents": [{"parts": [{"text": prompt}]}]
                })
                g_data = res.json()
                reply = g_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if reply:
                    await send_msg(client, reply)
                    return
        except Exception as e:
            print("Gemini API error:", e)

    # Default friendly command guidance
    help_text = (
        f"🤖 *Friday Mobile Assistant*\n\n"
        f"Active Project: `{current_project.name}`\n\n"
        f"Available Commands:\n"
        f"• `/projects` - List all projects\n"
        f"• `/create <type> <name>` - Create a new project (`python`, `node`, `web`)\n"
        f"• `/cd <name>` - Switch active project\n"
        f"• `/ls [dir]` - List files in current project\n"
        f"• `/find <pattern>` - Search files\n"
        f"• `/read <file>` - View file content or code\n"
        f"• `/write <file>` - Write/edit a file\n"
        f"• `/run <command>` - Execute shell command on PC\n"
        f"• `/git [status/diff/commit]` - Git controls\n"
        f"• `/help` - Show this menu\n"
    )
    await send_msg(client, help_text)

# ==========================================
# Main Telegram Polling Loop
# ==========================================

async def main():
    print(f"🚀 Friday Mobile Assistant is running!")
    print(f"Authorized Chat ID: {ALLOWED_CHAT_ID}")
    print(f"Projects Root: {PROJECTS_ROOT}")
    print(f"Active Project: {current_project}")

    offset = None
    async with httpx.AsyncClient(timeout=35.0) as client:
        # Send a startup ping
        await send_msg(
            client,
            f"⚡ *Friday Mobile Assistant Online!*\n\n"
            f"• *PC:* Connected\n"
            f"• *Active Project:* `{current_project.name}`\n"
            f"• *Root:* `{PROJECTS_ROOT}`\n\n"
            f"Type `/projects` or `/help` to get started."
        )

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

                    # Handle Callback Queries (Buttons)
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        sender_id = cb.get("from", {}).get("id")
                        if not is_authorized(sender_id):
                            continue

                        cb_data = cb.get("data", "")
                        cb_id = cb.get("id")
                        await client.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb_id})

                        if cb_data.startswith("select:"):
                            proj_name = cb_data.split(":", 1)[1]
                            await handle_select_project(client, proj_name)
                        continue

                    # Handle Messages
                    if "message" in update:
                        msg = update["message"]
                        sender_id = msg.get("from", {}).get("id")
                        if not is_authorized(sender_id):
                            continue

                        text = msg.get("text", "").strip()
                        if not text:
                            continue

                        # Routing commands
                        if text == "/start" or text == "/help":
                            await handle_ai_chat(client, "help")
                        elif text in ["/projects", "/list"]:
                            await handle_list_projects(client)
                        elif text.startswith("/create"):
                            await handle_create_project(client, text[7:])
                        elif text.startswith("/cd ") or text.startswith("/open "):
                            await handle_select_project(client, text.split(maxsplit=1)[1])
                        elif text == "/ls" or text.startswith("/ls "):
                            sub = text[3:].strip()
                            await handle_list_files(client, sub)
                        elif text.startswith("/find "):
                            await handle_find_files(client, text[6:])
                        elif text.startswith("/read ") or text.startswith("/cat "):
                            await handle_read_file(client, text.split(maxsplit=1)[1])
                        elif text.startswith("/write "):
                            await handle_write_file(client, text)
                        elif text.startswith("/run "):
                            await handle_run_command(client, text[5:])
                        elif text.startswith("/git"):
                            await handle_git(client, text[4:])
                        else:
                            # Natural language chat
                            await handle_ai_chat(client, text)

            except httpx.RequestError as e:
                print("Polling connection error:", e)
                await asyncio.sleep(3)
            except Exception as e:
                print("Unexpected loop error:", e)
                await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())

