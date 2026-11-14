import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

DEFAULT_DEV_ROOT = Path(r"D:\dev")

def find_git_repo(hint: Optional[str] = None) -> Optional[Path]:
    """Finds target git repository in D:\\dev."""
    if hint:
        h = hint.strip().lower()
        if (DEFAULT_DEV_ROOT / h).is_dir() and (DEFAULT_DEV_ROOT / h / ".git").exists():
            return DEFAULT_DEV_ROOT / h
        # Search D:\dev subdirectories
        for p in DEFAULT_DEV_ROOT.glob("*"):
            if p.is_dir() and h in p.name.lower() and (p / ".git").exists():
                return p
        for p in (DEFAULT_DEV_ROOT / "projects").glob("*"):
            if p.is_dir() and h in p.name.lower() and (p / ".git").exists():
                return p

    # Default to current project or exploring
    curr = Path(r"D:\dev\projects\Antigravity remove chat tool")
    if (curr / ".git").exists():
        return curr
    if (DEFAULT_DEV_ROOT / "projects" / "exploring" / ".git").exists():
        return DEFAULT_DEV_ROOT / "projects" / "exploring"
    return None

def get_git_status_report(repo_hint: Optional[str] = None) -> Tuple[str, List[List[Dict[str, str]]]]:
    """
    Returns (markdown_text, inline_keyboard_buttons).
    """
    repo = find_git_repo(repo_hint)
    if not repo:
        return f"❌ No git repository found matching `{repo_hint or 'default'}` in `D:\\dev`.", []

    try:
        # Branch
        branch_res = subprocess.run(["git", "branch", "--show-current"], cwd=str(repo), capture_output=True, text=True, timeout=4)
        branch = branch_res.stdout.strip() or "HEAD"

        # Status
        status_res = subprocess.run(["git", "status", "-s"], cwd=str(repo), capture_output=True, text=True, timeout=4)
        status_lines = [l.strip() for l in status_res.stdout.splitlines() if l.strip()]

        # Last commit
        log_res = subprocess.run(["git", "log", "-1", "--oneline"], cwd=str(repo), capture_output=True, text=True, timeout=4)
        last_commit = log_res.stdout.strip() or "No commits yet"

        is_clean = len(status_lines) == 0
        state_icon = "🟢 Clean" if is_clean else f"🟡 {len(status_lines)} Modified File(s)"

        changes_preview = ""
        if status_lines:
            preview_items = [f"• `{l}`" for l in status_lines[:8]]
            more = f"\n_...and {len(status_lines)-8} more_" if len(status_lines) > 8 else ""
            changes_preview = "\n**Uncommitted Changes:**\n" + "\n".join(preview_items) + more + "\n"

        msg = (
            f"🌿 *Git Command Center*\n\n"
            f"• **Repository:** `{repo.name}`\n"
            f"• **Branch:** `{branch}`\n"
            f"• **Working Tree:** {state_icon}\n"
            f"• **Latest Commit:** `{last_commit}`\n"
            f"{changes_preview}"
        )

        # Inline buttons
        buttons = []
        if not is_clean:
            buttons.append([
                {"text": "✅ Commit & Push", "callback_data": f"git:commit:{repo.name}"},
                {"text": "📦 Stash", "callback_data": f"git:stash:{repo.name}"}
            ])
            buttons.append([
                {"text": "🔍 View Diff", "callback_data": f"git:diff:{repo.name}"},
                {"text": "📥 Pull Latest", "callback_data": f"git:pull:{repo.name}"}
            ])
        else:
            buttons.append([
                {"text": "📥 Pull Latest", "callback_data": f"git:pull:{repo.name}"},
                {"text": "🚀 Push to Remote", "callback_data": f"git:push:{repo.name}"}
            ])

        return msg, buttons

    except Exception as e:
        return f"❌ Git execution error: {e}", []

def execute_git_action(action: str, repo_name: str) -> str:
    """Executes button callback action."""
    repo = find_git_repo(repo_name)
    if not repo:
        return f"❌ Repository `{repo_name}` not found."

    try:
        if action == "pull":
            res = subprocess.run(["git", "pull"], cwd=str(repo), capture_output=True, text=True, timeout=20)
            return f"📥 *Git Pull Result (`{repo.name}`):*\n\n```\n{res.stdout.strip() or res.stderr.strip()}\n```"

        elif action == "push":
            res = subprocess.run(["git", "push"], cwd=str(repo), capture_output=True, text=True, timeout=20)
            return f"🚀 *Git Push Result (`{repo.name}`):*\n\n```\n{res.stdout.strip() or res.stderr.strip()}\n```"

        elif action == "stash":
            res = subprocess.run(["git", "stash"], cwd=str(repo), capture_output=True, text=True, timeout=10)
            return f"📦 *Git Stash Result (`{repo.name}`):*\n\n```\n{res.stdout.strip()}\n```"

        elif action == "diff":
            res = subprocess.run(["git", "diff", "--stat"], cwd=str(repo), capture_output=True, text=True, timeout=10)
            diff_text = res.stdout.strip() or "No diff to display."
            return f"🔍 *Git Diff Summary (`{repo.name}`):*\n\n```\n{diff_text[:1800]}\n```"

        elif action == "commit":
            # Add all and commit
            subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, text=True, timeout=10)
            c_res = subprocess.run(["git", "commit", "-m", "Remote update via Friday Mobile Companion"], cwd=str(repo), capture_output=True, text=True, timeout=10)
            p_res = subprocess.run(["git", "push"], cwd=str(repo), capture_output=True, text=True, timeout=20)
            return f"✅ *Committed & Pushed (`{repo.name}`):*\n\n```\n{c_res.stdout.strip()}\n{p_res.stdout.strip()}\n```"

        return f"Unknown action: {action}"
    except Exception as e:
        return f"❌ Error executing git action `{action}`: {e}"
