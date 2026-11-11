import os
import sys
import glob
import json
import time
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

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
DEV_ROOT = Path(os.getenv("PROJECTS_ROOT", r"d:\dev")).resolve()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not TOKEN or not ALLOWED_CHAT_ID:
    print(f"Error: Missing credentials in {env_file}")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{TOKEN}"

# State: start at D:\dev or D:\dev\projects\exploring
if (DEV_ROOT / "projects" / "exploring").exists():
    current_dir = DEV_ROOT / "projects" / "exploring"
else:
    current_dir = DEV_ROOT

def is_authorized(user_id: int) -> bool:
    return str(user_id) == str(ALLOWED_CHAT_ID)

def resolve_safe(path_str: str) -> Optional[Path]:
    """Resolves a path safely ensuring it remains within DEV_ROOT."""
    p_str = path_str.strip().strip('"').strip("'")
    if not p_str or p_str in ["~", "/"]:
        return DEV_ROOT
    if p_str == "..":
        parent = current_dir.parent
        return parent if parent >= DEV_ROOT else DEV_ROOT

    # Check if absolute path or relative
    target = Path(p_str)
    if not target.is_absolute():
        target = (current_dir / target).resolve()
    else:
        target = target.resolve()

    try:
        if target == DEV_ROOT or target.is_relative_to(DEV_ROOT):
            return target
    except AttributeError:
        # Fallback for Python < 3.9 (though we are on 3.13)
        if str(target).lower().startswith(str(DEV_ROOT).lower()):
            return target
    return None

async def send_msg(client: httpx.AsyncClient, text: str, parse_mode: Optional[str] = "Markdown", reply_markup: Optional[dict] = None):
    # Telegram message limit is 4096 chars
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
            payload.pop("parse_mode")
            await client.post(f"{API_URL}/sendMessage", json=payload)
    except Exception as e:
        print("Error sending msg:", e)

async def send_file_doc(client: httpx.AsyncClient, file_path: Path, caption: str = ""):
    if not file_path.exists():
        await send_msg(client, f"File not found: `{file_path}`")
        return
    try:
        with open(file_path, "rb") as f:
            files = {"document": (file_path.name, f)}
            data = {"chat_id": ALLOWED_CHAT_ID, "caption": caption}
            await client.post(f"{API_URL}/sendDocument", data=data, files=files, timeout=40.0)
    except Exception as e:
        await send_msg(client, f"Failed to send file: {e}")

# ==========================================
# Workspace & Project Management Handlers
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
    if (p / "AndroidManifest.xml").exists() or (p / "build.gradle").exists():
        return "Android / Gradle"
    if (p / ".git").exists():
        return "Git Repo"
    return "Folder"

async def handle_pwd(client: httpx.AsyncClient):
    rel = current_dir.relative_to(DEV_ROOT) if current_dir != DEV_ROOT else "."
    ptype = get_project_type(current_dir)
    await send_msg(client, f"📍 *Current Location:*\n`{current_dir}`\nRelative: `D:\\dev\\{rel}`\nType: _{ptype}_")

async def handle_cd(client: httpx.AsyncClient, target_str: str):
    global current_dir
    target = resolve_safe(target_str)
    if not target or not target.exists() or not target.is_dir():
        await send_msg(client, f"❌ Directory not found or outside `D:\\dev`: `{target_str}`")
        return

    current_dir = target
    rel = current_dir.relative_to(DEV_ROOT) if current_dir != DEV_ROOT else "."
    ptype = get_project_type(current_dir)
    await send_msg(client, f"📂 Switched to: *{current_dir.name}*\n`D:\\dev\\{rel}` ({ptype})")

async def handle_list_projects(client: httpx.AsyncClient):
    r"""Discovers projects across D:\dev and D:\dev\projects."""
    if not DEV_ROOT.exists():
        await send_msg(client, f"Dev directory not found: `{DEV_ROOT}`")
        return

    # Check top-level items in D:\dev
    top_items = [p for p in DEV_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")]
    
    # Also include items in D:\dev\projects if it exists
    proj_items = []
    projects_dir = DEV_ROOT / "projects"
    if projects_dir.exists() and projects_dir.is_dir():
        proj_items = [p for p in projects_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

    all_targets = sorted(list(set(top_items + proj_items)), key=lambda x: str(x))
    
    lines = [f"📂 *Workspaces in* `{DEV_ROOT}`:\n"]
    buttons = []
    
    for p in all_targets:
        ptype = get_project_type(p)
        rel_str = str(p.relative_to(DEV_ROOT))
        active_mark = " 👉 *(active)*" if p == current_dir else ""
        lines.append(f"• *{rel_str}* — _{ptype}_{active_mark}")
        # Add tap buttons (limit button payload length)
        btn_data = f"cd:{rel_str}"
        if len(btn_data.encode("utf-8")) <= 64:
            buttons.append([{"text": f"📂 {p.name}", "callback_data": btn_data}])

    lines.append(f"\n_Current Folder:_ `{current_dir.relative_to(DEV_ROOT) if current_dir != DEV_ROOT else '.'}`")
    lines.append(f"\n_Tip: Use `/cd <folder>` or `/cd ..` to navigate freely._")
    
    # Show at most 10 buttons to prevent clutter
    keyboard = {"inline_keyboard": buttons[:10]} if buttons else None
    await send_msg(client, "\n".join(lines), reply_markup=keyboard)

async def handle_list_files(client: httpx.AsyncClient, subpath: str = ""):
    target_dir = resolve_safe(subpath) if subpath else current_dir
    if not target_dir or not target_dir.exists() or not target_dir.is_dir():
        await send_msg(client, f"Directory not found: `{subpath}`")
        return

    items = list(target_dir.iterdir())
    if not items:
        await send_msg(client, f"📁 `{target_dir.name}` is empty.")
        return

    dirs = sorted([p for p in items if p.is_dir() and not p.name.startswith(".")])
    files = sorted([p for p in items if p.is_file() and not p.name.startswith(".")])

    dir_lines = [f"📁 {p.name}/" for p in dirs]
    file_lines = [f"📄 {p.name} ({p.stat().st_size} B)" for p in files]
    
    listing = "\n".join(dir_lines + file_lines)
    rel_path = target_dir.relative_to(DEV_ROOT) if target_dir != DEV_ROOT else "."

    # Create quick navigation buttons for subdirectories
    buttons = []
    if target_dir != DEV_ROOT:
        buttons.append([{"text": "⬆️ Parent (..)", "callback_data": "cd:.."}])
    
    for d in dirs[:8]:
        rel_d = str(d.relative_to(DEV_ROOT))
        cb = f"cd:{rel_d}"
        if len(cb.encode("utf-8")) <= 64:
            buttons.append([{"text": f"📁 {d.name}/", "callback_data": cb}])

    keyboard = {"inline_keyboard": buttons} if buttons else None
    await send_msg(client, f"📂 *Listing:* `D:\\dev\\{rel_path}`\n\n```text\n{listing}\n```", reply_markup=keyboard)

async def handle_find_files(client: httpx.AsyncClient, query: str):
    if not query.strip():
        await send_msg(client, "Usage: `/find <pattern>`\nExample: `/find *.py` or `/find server`")
        return

    q = query.strip()
    pattern = f"*{q}*" if not any(c in q for c in "*?[]") else q
    matches = list(current_dir.rglob(pattern))
    
    clean_matches = [
        m for m in matches 
        if not any(part.startswith(".") or part in ["node_modules", ".venv", "__pycache__", "build", ".dart_tool"] for part in m.parts)
    ][:25]

    if not clean_matches:
        await send_msg(client, f"🔍 No files matching `{q}` in *{current_dir.name}*.")
        return

    lines = [f"🔍 *Found {len(clean_matches)} matches in* `{current_dir.name}`:\n"]
    for m in clean_matches:
        rel = m.relative_to(current_dir)
        icon = "📁" if m.is_dir() else "📄"
        lines.append(f"{icon} `{rel}`")

    await send_msg(client, "\n".join(lines))

async def handle_read_file(client: httpx.AsyncClient, file_str: str):
    if not file_str.strip():
        await send_msg(client, "Usage: `/read <file_path>`\nExample: `/read main.py` or `/read src/index.js`")
        return

    target = resolve_safe(file_str)
    if not target or not target.exists() or not target.is_file():
        await send_msg(client, f"❌ File not found: `{file_str}`")
        return

    size = target.stat().st_size
    if size > 30000:
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
    target = resolve_safe(first_line)
    if not target:
        await send_msg(client, "❌ Invalid path outside `D:\\dev`.")
        return

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = target.relative_to(DEV_ROOT)
        await send_msg(client, f"✅ Written to `{rel}` ({len(content)} characters).")
    except Exception as e:
        await send_msg(client, f"❌ Failed to write file: {e}")

async def handle_create_project(client: httpx.AsyncClient, args_str: str):
    global current_dir
    parts = args_str.strip().split(maxsplit=1)
    if len(parts) == 1:
        ptype = "python"
        pname = parts[0]
    elif len(parts) == 2:
        ptype = parts[0].lower()
        pname = parts[1]
    else:
        await send_msg(client, "Usage: `/create <type> <name>`\nTypes: `python`, `node`, `web`, `empty`\nExample: `/create python test-app`")
        return

    target = current_dir / pname
    if target.exists():
        await send_msg(client, f"❌ `{pname}` already exists in `{current_dir}`!")
        return

    try:
        target.mkdir(parents=True, exist_ok=True)
        if ptype in ["python", "py"]:
            (target / "main.py").write_text("#!/usr/bin/env python3\n\ndef main():\n    print('Hello from " + pname + "!')\n\nif __name__ == '__main__':\n    main()\n", encoding="utf-8")
            (target / "README.md").write_text(f"# {pname}\n\nPython project created via Telegram.\n", encoding="utf-8")
            (target / ".gitignore").write_text("__pycache__/\n*.pyc\n.venv/\n.env\n", encoding="utf-8")
        elif ptype in ["node", "js", "ts"]:
            pkg = {
                "name": pname,
                "version": "1.0.0",
                "main": "index.js",
                "scripts": {"start": "node index.js"}
            }
            (target / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
            (target / "index.js").write_text("console.log('Hello from " + pname + "!');\n", encoding="utf-8")
            (target / "README.md").write_text(f"# {pname}\n\nNode.js project created via Telegram.\n", encoding="utf-8")
        elif ptype in ["web", "html"]:
            (target / "index.html").write_text(f"<!DOCTYPE html>\n<html>\n<head><title>{pname}</title></head>\n<body>\n  <h1>Welcome to {pname}</h1>\n</body>\n</html>\n", encoding="utf-8")
            (target / "style.css").write_text("body { font-family: sans-serif; margin: 2rem; }\n", encoding="utf-8")
            (target / "README.md").write_text(f"# {pname}\n\nWeb project created via Telegram.\n", encoding="utf-8")
        else:
            (target / "README.md").write_text(f"# {pname}\n\nCreated via Telegram.\n", encoding="utf-8")

        try:
            subprocess.run(["git", "init"], cwd=target, capture_output=True, timeout=5)
        except Exception:
            pass

        current_dir = target
        await send_msg(client, f"🎉 *Created Successfully!*\n• Name: *{pname}*\n• Type: `{ptype}`\n• Path: `{target}`\n\nActive directory updated.")
    except Exception as e:
        await send_msg(client, f"❌ Failed to create: {e}")

async def handle_run_command(client: httpx.AsyncClient, cmd_str: str):
    cmd = cmd_str.strip()
    if not cmd:
        await send_msg(client, "Usage: `/run <command>`\nExample: `/run git status` or `/run python main.py`")
        return

    await send_msg(client, f"⚙️ Running in `{current_dir.name}`:\n`{cmd}`...")
    
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(current_dir),
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
                result_parts.append("_Finished with no output._")

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
    lower = user_text.lower().strip()
    if any(k in lower for k in ["list project", "my project", "show project", "projects"]):
        await handle_list_projects(client)
        return
    if lower == "pwd" or lower == "where am i":
        await handle_pwd(client)
        return
    if lower.startswith("cd "):
        await handle_cd(client, user_text[3:].strip())
        return
    if lower.startswith("create project ") or lower.startswith("create "):
        arg = user_text[15:] if lower.startswith("create project ") else user_text[7:]
        await handle_create_project(client, arg)
        return
    if lower.startswith("run "):
        await handle_run_command(client, user_text[4:])
        return
    if lower in ["git status", "git diff", "git log"]:
        await handle_git(client, lower[4:])
        return
    if lower in ["ls", "dir", "list files", "files"]:
        await handle_list_files(client)
        return

    # If GEMINI_API_KEY is configured
    if GEMINI_API_KEY:
        try:
            prompt = (
                f"You are Friday, an AI developer assistant connected to the user's PC via Telegram.\n"
                f"Dev Root: {DEV_ROOT}\n"
                f"Current directory: {current_dir}\n"
                f"User asked: {user_text}\n"
                f"Give a concise, helpful response formatted for Telegram markdown."
            )
            g_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            async with httpx.AsyncClient(timeout=30.0) as g_client:
                res = await g_client.post(g_url, json={"contents": [{"parts": [{"text": prompt}]}]})
                g_data = res.json()
                reply = g_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if reply:
                    await send_msg(client, reply)
                    return
        except Exception as e:
            print("Gemini API error:", e)

    help_text = (
        f"🤖 *Friday Remote Dev Assistant*\n\n"
        f"📍 Location: `{current_dir.relative_to(DEV_ROOT) if current_dir != DEV_ROOT else '.'}` (`{current_dir}`)\n\n"
        f"Navigation & Exploration:\n"
        f"• `/pwd` - Show current path\n"
        f"• `/cd <dir>` - Go into folder (or `/cd ..` / `/cd ~`)\n"
        f"• `/ls [dir]` - List files & folders with tap buttons\n"
        f"• `/projects` - List all projects across D:\\dev\n\n"
        f"Project & File Management:\n"
        f"• `/create <type> <name>` - Create project (`python`, `node`, `web`)\n"
        f"• `/find <pattern>` - Search files\n"
        f"• `/read <file>` - Inspect code or file content\n"
        f"• `/write <file>` - Write/edit a file\n\n"
        f"Execution:\n"
        f"• `/run <command>` - Run shell commands on PC\n"
        f"• `/git [status/diff/commit]` - Git commands\n"
    )
    await send_msg(client, help_text)

# ==========================================
# Main Loop
# ==========================================

async def main():
    print(f"🚀 Friday Remote Assistant is running across {DEV_ROOT}!")
    print(f"Authorized Chat ID: {ALLOWED_CHAT_ID}")
    print(f"Current Directory: {current_dir}")

    offset = None
    async with httpx.AsyncClient(timeout=35.0) as client:
        await send_msg(
            client,
            f"⚡ *Friday Assistant Updated!*\n\n"
            f"• *Scope:* Entire `D:\\dev` folder unlocked\n"
            f"• *Current Path:* `{current_dir}`\n\n"
            f"Use `/cd`, `/ls`, `/pwd`, or `/projects` to navigate anywhere in `D:\\dev`."
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

                    if "callback_query" in update:
                        cb = update["callback_query"]
                        sender_id = cb.get("from", {}).get("id")
                        if not is_authorized(sender_id):
                            continue

                        cb_data = cb.get("data", "")
                        cb_id = cb.get("id")
                        await client.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb_id})

                        if cb_data.startswith("cd:"):
                            target = cb_data.split(":", 1)[1]
                            await handle_cd(client, target)
                        continue

                    if "message" in update:
                        msg = update["message"]
                        sender_id = msg.get("from", {}).get("id")
                        if not is_authorized(sender_id):
                            continue

                        text = msg.get("text", "").strip()
                        if not text:
                            continue

                        if text in ["/start", "/help"]:
                            await handle_ai_chat(client, "help")
                        elif text == "/pwd":
                            await handle_pwd(client)
                        elif text == "/cd" or text.startswith("/cd "):
                            target = text[3:].strip() or "~"
                            await handle_cd(client, target)
                        elif text in ["/projects", "/list"]:
                            await handle_list_projects(client)
                        elif text.startswith("/create"):
                            await handle_create_project(client, text[7:])
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
                            await handle_ai_chat(client, text)

            except httpx.RequestError as e:
                print("Polling connection error:", e)
                await asyncio.sleep(3)
            except Exception as e:
                print("Unexpected loop error:", e)
                await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
