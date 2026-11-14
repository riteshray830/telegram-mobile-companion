import os
import sys
from pathlib import Path
from typing import Optional, Tuple, List

SEARCH_ROOTS = [
    Path(r"D:\dev\projects\Antigravity remove chat tool"),
    Path(r"D:\dev\projects\exploring"),
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Documents",
    Path(r"D:\dev"),
]

IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "build", "dist", ".gradle", ".idea", "vendor", "cache"}

UPLOAD_DIR = Path.home() / "Downloads" / "TelegramUploads"

def get_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR

def resolve_file_to_send(user_query: str) -> Tuple[Optional[Path], str]:
    """
    Locates the requested file on the laptop quickly with depth limits and directory pruning.
    Returns: (file_path, status_message)
    """
    clean = user_query.strip().strip('"').strip("'")
    
    # 1. Direct path check
    direct = Path(clean)
    if direct.exists() and direct.is_file():
        return check_file_size(direct)

    # 2. Check if path exists directly inside SEARCH_ROOTS
    for root in SEARCH_ROOTS:
        candidate = root / clean
        if candidate.exists() and candidate.is_file():
            return check_file_size(candidate)

    # 3. Fast pruned search in search roots (max depth 3, skipping node_modules/.git)
    filename = Path(clean).name.lower()
    matches: List[Path] = []
    
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        root_depth = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(str(root)):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d.lower() not in IGNORE_DIRS]
            curr_depth = len(Path(dirpath).parts)
            if curr_depth - root_depth > 3:
                dirnames.clear()
                continue

            for f in filenames:
                f_lower = f.lower()
                if filename == f_lower or (len(filename) >= 3 and filename in f_lower):
                    p = Path(dirpath) / f
                    if p not in matches:
                        matches.append(p)
                    if len(matches) >= 8:
                        break
            if len(matches) >= 8:
                break
        if len(matches) >= 8:
            break

    if not matches:
        return None, f"❌ File `{clean}` was not found in `D:\\dev`, Desktop, or Downloads."

    # Prioritize exact filename match over partial substring matches
    exact_matches = [p for p in matches if p.name.lower() == filename]
    if len(exact_matches) == 1:
        return check_file_size(exact_matches[0])

    if len(matches) == 1:
        return check_file_size(matches[0])

    # Multiple matches
    lines = [f"• `{p}`" for p in matches[:5]]
    return None, f"🔍 Found multiple matching files. Please specify the exact path:\n\n" + "\n".join(lines)

def check_file_size(path: Path) -> Tuple[Optional[Path], str]:
    """Validates that file is within Telegram's 50MB bot upload limit."""
    try:
        size_bytes = path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > 50:
            return None, f"⚠️ File `{path.name}` is `{size_mb:.1f} MB`, which exceeds Telegram's 50MB bot upload limit."
        return path, f"Found `{path.name}` ({size_mb:.2f} MB)"
    except Exception as e:
        return None, f"❌ Cannot read file: {e}"

def save_uploaded_file(filename: str, content: bytes) -> Tuple[bool, Path, str]:
    """Saves a file uploaded from Telegram onto the laptop."""
    try:
        out_dir = get_upload_dir()
        safe_name = Path(filename).name
        target_path = out_dir / safe_name
        
        # Deduplicate filename if exists
        counter = 1
        base_stem = target_path.stem
        base_suffix = target_path.suffix
        while target_path.exists():
            target_path = out_dir / f"{base_stem}_{counter}{base_suffix}"
            counter += 1

        with open(target_path, "wb") as f:
            f.write(content)

        size_kb = len(content) / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{(size_kb/1024):.2f} MB"

        return True, target_path, f"📥 *File Saved to Laptop!*\n\n• **Filename:** `{target_path.name}`\n• **Size:** `{size_str}`\n• **Location:** `{target_path}`"
    except Exception as e:
        return False, Path("."), f"❌ Failed to save file to laptop: {e}"
