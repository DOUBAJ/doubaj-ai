"""Typed access to settings stored in SQLite, with encrypted secrets."""
from __future__ import annotations

from ..providers.registry import PROVIDERS, create
from . import secrets

DEFAULTS = {
    "lang": "fr", "theme": "light", "provider": "anthropic", "reasoning": "standard", "mode": "general",
    "temperature": None, "length": "normal", "max_tokens": 16000, "context_chars": 300_000,
    "web_backend": "duckduckgo", "memory_enabled": True, "confirm_upload": True, "sandbox_restricted": True,
    "tts_rate": 0.0, "tts_voice": "", "stt_url": "https://api.openai.com/v1", "stt_model": "whisper-1",
    "img_url": "https://api.openai.com/v1", "img_model": "gpt-image-1", "show_workspace": True,
}


class Settings:
    def __init__(self, db):
        self.db = db

    def get(self, key: str):
        return self.db.get_setting(key, DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        self.db.set_setting(key, value)

    # secrets --------------------------------------------------------
    def get_secret(self, name: str) -> str:
        return secrets.decrypt(self.db.get_setting(f"secret:{name}", "") or "")

    def set_secret(self, name: str, value: str) -> None:
        self.db.set_setting(f"secret:{name}", secrets.encrypt(value.strip()) if value else "")

    # providers ------------------------------------------------------
    def provider_model(self, pid: str) -> str:
        return self.db.get_setting(f"model:{pid}", "") or PROVIDERS[pid].info.default_model

    def provider_base_url(self, pid: str) -> str:
        return self.db.get_setting(f"base_url:{pid}", "") or PROVIDERS[pid].info.default_base_url

    def make_provider(self, pid: str):
        return create(pid, api_key=self.get_secret(pid), base_url=self.provider_base_url(pid))

    def provider_ready(self, pid: str) -> bool:
        info = PROVIDERS[pid].info
        return (not info.needs_key) or bool(self.get_secret(pid))
