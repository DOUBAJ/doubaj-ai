"""Speech-to-text and image generation through external services (optional).
Text-to-speech is done offline with Qt (Windows voices) in the UI layer."""
from __future__ import annotations

import base64
import time
from pathlib import Path


def transcribe(audio_path: str, api_key: str, base_url: str = "https://api.openai.com/v1",
               model: str = "whisper-1", language: str | None = None) -> str:
    """OpenAI-compatible /audio/transcriptions (OpenAI Whisper, Groq whisper-large-v3, local servers...)."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key or "not-needed", base_url=base_url, timeout=120)
    with open(audio_path, "rb") as f:
        kw = {"model": model, "file": f}
        if language:
            kw["language"] = language
        res = client.audio.transcriptions.create(**kw)
    return getattr(res, "text", str(res))


def generate_image(prompt: str, api_key: str, out_dir: Path, base_url: str = "https://api.openai.com/v1",
                   model: str = "gpt-image-1", size: str = "1024x1024") -> Path:
    """OpenAI-compatible /images/generations. Returns the saved PNG path."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=300)
    res = client.images.generate(model=model, prompt=prompt, size=size, n=1)
    item = res.data[0]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"image_{int(time.time())}.png"
    if getattr(item, "b64_json", None):
        path.write_bytes(base64.b64decode(item.b64_json))
    elif getattr(item, "url", None):
        import httpx
        path.write_bytes(httpx.get(item.url, timeout=60).content)
    else:
        raise RuntimeError("No image returned by the service")
    return path
