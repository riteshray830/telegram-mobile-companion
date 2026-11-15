import os
import sys
import json
import time
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

CONFIG_DIR = Path.home() / ".gemini" / "config"
BRAIN_DIR = Path.home() / ".gemini" / "antigravity" / "brain"
TITLES_DIR = Path.home() / ".gemini" / "antigravity" / "chapter_titles"
ACTIVE_SESSION_FILE = CONFIG_DIR / "telegram_active_session.json"

def format_relative_time(epoch_time: float) -> str:
    diff = int(time.time() - epoch_time)
    if diff < 60:
        return f"{diff}s ago"
    elif diff < 3600:
        return f"{diff // 60}m ago"
    elif diff < 86400:
        return f"{diff // 3600}h ago"
    else:
        return f"{diff // 86400}d ago"

def get_conversation_metadata(conv_id: str) -> Dict[str, Any]:
    """Extracts human-readable title and workspace directory for a conversation."""
    meta = {
        "conv_id": conv_id,
        "title": "Antigravity Chat",
        "workspace": "Unknown",
        "last_active": 0.0,
        "last_active_str": "unknown"
    }

    conv_brain = BRAIN_DIR / conv_id
    log_file = conv_brain / ".system_generated" / "logs" / "transcript.jsonl"
    if log_file.exists():
        try:
            mtime = log_file.stat().st_mtime
            meta["last_active"] = mtime
            meta["last_active_str"] = format_relative_time(mtime)
        except Exception:
            pass

    # Extract title from chapter_titles pb file
    pb_file = TITLES_DIR / f"{conv_id}.pb"
    if pb_file.exists():
        try:
            raw = pb_file.read_bytes().decode("latin1", errors="ignore")
            # Extract plain text chapter phrases
            matches = re.findall(r"[A-Za-z0-9_\-\.\:\s\(\)\/]{5,60}", raw)
            clean_matches = [m.strip() for m in matches if len(m.strip()) >= 5 and not m.startswith("Exa") and not m.startswith("http")]
            if clean_matches:
                meta["title"] = clean_matches[-1]
        except Exception:
            pass

    # Extract workspace path from transcript
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                for _ in range(60):
                    line = f.readline()
                    if not line:
                        break
                    match = re.search(r"([A-Za-z]:\\[^\"\'\n\r<>]+)", line)
                    if match:
                        p_str = match.group(1).replace("\\\\", "\\")
                        cand = Path(p_str)
                        if cand.exists():
                            ws = cand if cand.is_dir() else cand.parent
                            meta["workspace"] = str(ws)
                            break
        except Exception:
            pass

    return meta

def list_recent_sessions(limit: int = 5) -> List[Dict[str, Any]]:
    """Lists recent Antigravity conversations sorted by activity timestamp."""
    if not BRAIN_DIR.exists():
        return []

    sessions = []
    for p in BRAIN_DIR.glob("*"):
        if not p.is_dir():
            continue
        log_file = p / ".system_generated" / "logs" / "transcript.jsonl"
        if log_file.exists():
            sessions.append((p.name, log_file.stat().st_mtime))

    sessions.sort(key=lambda x: x[1], reverse=True)
    top_sessions = sessions[:limit]

    results = []
    for cid, _ in top_sessions:
        results.append(get_conversation_metadata(cid))

    return results

def get_active_session() -> Dict[str, Any]:
    """Gets the currently bound session or defaults to the most recently active one."""
    # 1. Check explicit session file
    if ACTIVE_SESSION_FILE.exists():
        try:
            data = json.loads(ACTIVE_SESSION_FILE.read_text(encoding="utf-8"))
            cid = data.get("conv_id")
            if cid and (BRAIN_DIR / cid).exists():
                meta = get_conversation_metadata(cid)
                if data.get("workspace") and meta["workspace"] == "Unknown":
                    meta["workspace"] = data["workspace"]
                if data.get("title") and meta["title"] == "Antigravity Chat":
                    meta["title"] = data["title"]
                return meta
        except Exception:
            pass

    # 2. Default to most recently active conversation
    recents = list_recent_sessions(limit=1)
    if recents:
        return recents[0]

    return {
        "conv_id": "",
        "title": "No Active Session",
        "workspace": "None",
        "last_active": 0.0,
        "last_active_str": "never"
    }

def bind_session(conv_id: str, title: str = "", workspace: str = "") -> Dict[str, Any]:
    """Explicitly binds Friday to an Antigravity conversation."""
    meta = get_conversation_metadata(conv_id)
    if title:
        meta["title"] = title
    if workspace:
        meta["workspace"] = workspace

    data = {
        "conv_id": conv_id,
        "title": meta["title"],
        "workspace": meta["workspace"],
        "updated_at": time.time()
    }
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_SESSION_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return meta

def switch_session_by_hint(hint: str) -> Tuple[bool, str]:
    """Switches active session by index ('1', '2') or partial match on ID or project name."""
    recents = list_recent_sessions(limit=8)
    if not recents:
        return False, "❌ No active Antigravity conversations found on this laptop."

    clean = hint.strip().lower()

    # Match by numeric index (1-based)
    if clean.isdigit():
        idx = int(clean) - 1
        if 0 <= idx < len(recents):
            chosen = recents[idx]
            bind_session(chosen["conv_id"], chosen["title"], chosen["workspace"])
            ws_name = Path(chosen["workspace"]).name if chosen["workspace"] != "Unknown" else chosen["workspace"]
            return True, f"✅ *Switched to Chat #{idx+1}:*\n• **Project:** `{ws_name}`\n• **Topic:** _{chosen['title']}_\n• **Session:** `{chosen['conv_id'][:8]}...`"
        else:
            return False, f"❌ Invalid index `{hint}`. Choose a number between 1 and {len(recents)}."

    # Match by ID or workspace substring
    for idx, s in enumerate(recents):
        if clean in s["conv_id"].lower() or clean in s["workspace"].lower() or clean in s["title"].lower():
            bind_session(s["conv_id"], s["title"], s["workspace"])
            ws_name = Path(s["workspace"]).name if s["workspace"] != "Unknown" else s["workspace"]
            return True, f"✅ *Switched to Chat #{idx+1}:*\n• **Project:** `{ws_name}`\n• **Topic:** _{s['title']}_\n• **Session:** `{s['conv_id'][:8]}...`"

    return False, f"❌ No project matching `{hint}`. Send `/chats` to see available projects."

def format_sessions_list() -> str:
    """Formats the list of active Antigravity conversations for Telegram display."""
    recents = list_recent_sessions(limit=6)
    if not recents:
        return "ℹ️ No Antigravity conversations are currently open on this laptop."

    active = get_active_session()
    active_cid = active.get("conv_id")

    lines = ["📂 *Active Antigravity Chats & Projects:*\n"]
    for i, s in enumerate(recents, start=1):
        is_active = (s["conv_id"] == active_cid)
        badge = "🟢 **[CURRENT]** " if is_active else ""
        ws_name = Path(s["workspace"]).name if s["workspace"] != "Unknown" else s["workspace"]
        lines.append(f"{i}. {badge}**{ws_name}** ({s['last_active_str']})")
        lines.append(f"   • Topic: _{s['title']}_")
        lines.append(f"   • Session: `{s['conv_id'][:12]}...`\n")

    lines.append("💡 _To switch to another project, reply with:_ `/switch <number>`")
    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "switch" and len(sys.argv) > 2:
        ok, msg = switch_session_by_hint(sys.argv[2])
        print(msg)
    else:
        print(format_sessions_list())

