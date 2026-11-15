import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import httpx

import session_manager

# Ensure stdout uses UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def find_active_conversation_id() -> Optional[str]:
    """Dynamically finds the active Antigravity conversation ID using session_manager."""
    meta = session_manager.get_active_session()
    return meta.get("conv_id")

class BaseAIBackend:
    async def generate_reply(self, user_message: str, context: Dict[str, Any]) -> str:
        raise NotImplementedError

class AntigravityBackend(BaseAIBackend):
    def __init__(self):
        # Look for agy executable across Windows, Mac, Linux
        candidate_paths = [
            Path.home() / ".gemini" / "bin" / "agy.exe",
            Path.home() / ".gemini" / "bin" / "agy",
            Path("/usr/local/bin/agy"),
            Path("/usr/bin/agy"),
        ]
        self.agy_exe = None
        for p in candidate_paths:
            if p.exists():
                self.agy_exe = p
                break

    async def generate_reply(self, user_message: str, context: Dict[str, Any]) -> str:
        clean_msg = user_message.strip()

        # Handle session switching commands directly from Telegram
        if clean_msg.lower() in ["/chats", "/projects", "/sessions", "chats", "projects"]:
            return session_manager.format_sessions_list()

        if clean_msg.lower().startswith(("/switch", "switch ")):
            parts = clean_msg.split(maxsplit=1)
            hint = parts[1].strip() if len(parts) > 1 else ""
            if not hint:
                return "💡 Please specify a project number or name: `/switch <number>` (Send `/chats` to list)"
            ok, switch_msg = session_manager.switch_session_by_hint(hint)
            return switch_msg

        if clean_msg.lower() in ["/current", "/active", "current project", "active project", "current chat"]:
            meta = session_manager.get_active_session()
            ws_name = Path(meta.get("workspace", "Antigravity")).name if meta.get("workspace") != "Unknown" else meta.get("title", "Antigravity")
            return (
                f"🎯 *Currently Connected Project:*\n\n"
                f"• **Project:** `{ws_name}`\n"
                f"• **Folder:** `{meta.get('workspace')}`\n"
                f"• **Topic:** _{meta.get('title')}_\n"
                f"• **Session ID:** `{meta.get('conv_id')}`\n"
                f"• **Last Active:** {meta.get('last_active_str')}\n\n"
                f"_To switch project, send:_ `/chats`"
            )

        meta = session_manager.get_active_session()
        conv_id = meta.get("conv_id")
        if not conv_id:
            return "❌ No active Antigravity session found on this laptop. Please open Antigravity or type `/chats`."
        if not self.agy_exe or not self.agy_exe.exists():
            return "❌ Antigravity CLI (`agy`) not found. Please verify Antigravity installation."

        ws_name = Path(meta.get("workspace", "Antigravity")).name if meta.get("workspace") != "Unknown" else meta.get("title", "Antigravity")
        content = f"[User via Mobile Telegram]: {user_message}"
        try:
            proc = await asyncio.create_subprocess_exec(
                str(self.agy_exe),
                "agentapi",
                "send-message",
                conv_id,
                content,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                return f"⚠️ Error sending to agent: {err_msg[:200]}"
            # Antigravity's lifecycle hook (forward_reply_hook.py) will deliver the full response
            return f"⚡ *Delivered to [{ws_name}].* Working on it..."
        except Exception as e:
            return f"❌ Execution error: {e}"

class GeminiBackend(BaseAIBackend):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    async def generate_reply(self, user_message: str, context: Dict[str, Any]) -> str:
        if not self.api_key:
            return "❌ Missing GEMINI_API_KEY in configuration."

        system_instruction = (
            f"You are Friday, a helpful remote developer assistant connected to the user's laptop via Telegram.\n"
            f"Workspace Root: {context.get('dev_root', 'Not specified')}\n"
            f"Current working path: {context.get('current_dir', 'Not specified')}\n"
            f"Give concise, practical answers formatted in clean Telegram Markdown."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_instruction}\n\nUser request: {user_message}"}]}]
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                resp = await client.post(url, json=payload)
                data = resp.json()
                if "error" in data:
                    return f"❌ Gemini API Error: {data['error'].get('message', 'Unknown error')}"
                reply = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return reply or "No response generated."
            except Exception as e:
                return f"❌ Network error calling Gemini: {e}"

class OpenAIBackend(BaseAIBackend):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    async def generate_reply(self, user_message: str, context: Dict[str, Any]) -> str:
        if not self.api_key:
            return "❌ Missing OPENAI_API_KEY in configuration."

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": f"You are Friday, a remote developer assistant. Workspace: {context.get('dev_root')}. Format for Telegram markdown."
                },
                {"role": "user", "content": user_message}
            ]
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                data = resp.json()
                if "error" in data:
                    return f"❌ OpenAI Error: {data['error'].get('message')}"
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                return f"❌ Network error calling OpenAI: {e}"

class ClaudeBackend(BaseAIBackend):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model = model

    async def generate_reply(self, user_message: str, context: Dict[str, Any]) -> str:
        if not self.api_key:
            return "❌ Missing ANTHROPIC_API_KEY in configuration."

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "system": f"You are Friday, a remote dev assistant. Workspace: {context.get('dev_root')}. Format for Telegram markdown.",
            "messages": [{"role": "user", "content": user_message}]
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                data = resp.json()
                if "error" in data:
                    return f"❌ Claude Error: {data['error'].get('message')}"
                return data["content"][0]["text"]
            except Exception as e:
                return f"❌ Network error calling Claude: {e}"

class OllamaBackend(BaseAIBackend):
    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.2"):
        self.host = host.rstrip("/")
        self.model = model

    async def generate_reply(self, user_message: str, context: Dict[str, Any]) -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": f"Workspace: {context.get('dev_root')}\nUser: {user_message}",
            "stream": False
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(url, json=payload)
                data = resp.json()
                return data.get("response", "No response from Ollama.")
            except Exception as e:
                return f"❌ Cannot connect to Ollama at `{self.host}`. Make sure Ollama is running. ({e})"

def get_backend_instance(backend_name: str) -> BaseAIBackend:
    name = (backend_name or "antigravity").lower().strip()
    if name == "gemini":
        return GeminiBackend(
            api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        )
    elif name == "openai":
        return OpenAIBackend(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        )
    elif name == "claude":
        return ClaudeBackend(
            api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            model=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
        )
    elif name == "ollama":
        return OllamaBackend(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama3.2")
        )
    else:
        # Default: Antigravity
        return AntigravityBackend()

