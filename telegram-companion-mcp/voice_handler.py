import os
import sys
import base64
import httpx
from pathlib import Path
from typing import Tuple, Optional

async def transcribe_telegram_voice(file_bytes: bytes, mime_type: str = "audio/ogg") -> Tuple[Optional[str], Optional[str]]:
    """
    Transcribes Telegram voice note (.oga/.ogg) using Gemini or Whisper API.
    Returns: (transcribed_text, error_message)
    """
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    # 1. Try Google Gemini (Native Multimodal Audio)
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            audio_b64 = base64.b64encode(file_bytes).decode("utf-8")
            
            prompt_text = "Listen carefully to this audio voice message and transcribe the user's spoken words exactly. Return ONLY the transcribed text, nothing else."
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inline_data": {
                                "mime_type": "audio/ogg",
                                "data": audio_b64
                            }
                        }
                    ]
                }]
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                if "error" in data:
                    return None, f"Gemini error: {data['error'].get('message')}"
                
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                transcript = parts[0].get("text", "").strip()
                if transcript:
                    return transcript, None
        except Exception as e:
            pass

    # 2. Try OpenAI Whisper API
    if openai_key:
        try:
            url = "https://api.openai.com/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {openai_key}"}
            files = {"file": ("voice.ogg", file_bytes, "audio/ogg")}
            data = {"model": "whisper-1"}

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=headers, files=files, data=data)
                res_data = resp.json()
                if "error" in res_data:
                    return None, f"Whisper error: {res_data['error'].get('message')}"
                transcript = res_data.get("text", "").strip()
                if transcript:
                    return transcript, None
        except Exception as e:
            return None, f"OpenAI Whisper error: {e}"

    return None, "❌ To enable voice notes, add `GEMINI_API_KEY` or `OPENAI_API_KEY` to your `.env` configuration file."
