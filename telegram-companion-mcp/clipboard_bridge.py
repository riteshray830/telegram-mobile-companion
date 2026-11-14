import sys
from typing import Tuple

def set_clipboard_content(text: str) -> Tuple[bool, str]:
    """Sets the laptop's clipboard to the given text."""
    if not text:
        return False, "❌ Cannot copy empty text."
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        preview = text[:150] + ("..." if len(text) > 150 else "")
        return True, f"📋 *Copied to your laptop clipboard!*\n\n```\n{preview}\n```\n\nYou can now press `Ctrl + V` anywhere on your laptop."
    except Exception as e:
        return False, f"❌ Failed to set clipboard: {e}"

def get_clipboard_content() -> Tuple[bool, str]:
    """Reads the current text on the laptop's clipboard."""
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        content = r.clipboard_get()
        r.destroy()
        if not content.strip():
            return True, "📋 Your laptop clipboard is currently empty."
        preview = content[:2000]
        truncated = f"\n\n_(Truncated, showing first 2000 characters)_" if len(content) > 2000 else ""
        return True, f"📋 *Current Laptop Clipboard Content:*\n\n```\n{preview}\n```{truncated}"
    except Exception as e:
        if "CLIPBOARD" in str(e).upper() or "selection" in str(e).lower():
            return True, "📋 Your laptop clipboard is currently empty or contains non-text data (e.g. image/file)."
        return False, f"❌ Could not read clipboard: {e}"
