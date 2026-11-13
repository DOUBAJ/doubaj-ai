"""Provider abstraction. Every AI backend implements the same interface, so the UI never
depends on a specific vendor. New providers only need to subclass `Provider` and be
registered in `registry.py`."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Iterator


@dataclass
class ChatMessage:
    role: str                      # "user" | "assistant"
    text: str
    images: list[dict] = field(default_factory=list)  # [{"media_type": "image/png", "data": b64}]


@dataclass
class ChatRequest:
    model: str
    system: str
    messages: list[ChatMessage]
    reasoning: str = "standard"     # "fast" | "standard" | "deep"
    temperature: float | None = None
    max_tokens: int = 8192


@dataclass
class StreamEvent:
    kind: str                      # "text" | "thinking" | "done" | "error"
    text: str = ""
    usage: dict | None = None


class CancelToken:
    def __init__(self) -> None:
        self._ev = threading.Event()

    def cancel(self) -> None:
        self._ev.set()

    @property
    def cancelled(self) -> bool:
        return self._ev.is_set()


@dataclass
class ProviderInfo:
    id: str
    label: str
    needs_key: bool
    default_base_url: str = ""
    default_model: str = ""
    suggested_models: list[str] = field(default_factory=list)
    local: bool = False
    supports_vision: bool = True
    help: str = ""


class Provider:
    info: ProviderInfo

    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        self.api_key = api_key
        self.base_url = base_url or self.info.default_base_url

    def stream_chat(self, req: ChatRequest, cancel: CancelToken) -> Iterator[StreamEvent]:
        raise NotImplementedError

    def list_models(self) -> list[str]:
        return list(self.info.suggested_models)

    def test_connection(self, model: str) -> tuple[bool, str]:
        """Send a tiny request. Returns (ok, message)."""
        try:
            req = ChatRequest(model=model, system="Reply with the single word: OK",
                              messages=[ChatMessage("user", "ping")], reasoning="fast", max_tokens=200)
            out = ""
            for ev in self.stream_chat(req, CancelToken()):
                if ev.kind == "text":
                    out += ev.text
                elif ev.kind == "error":
                    return False, ev.text
            return True, out.strip()[:200] or "OK"
        except Exception as e:  # noqa: BLE001
            return False, str(e)


def collect(provider: Provider, req: ChatRequest, on_text: Callable[[str], None] | None = None) -> str:
    """Utility: run a request to completion and return the text."""
    out = []
    for ev in provider.stream_chat(req, CancelToken()):
        if ev.kind == "text":
            out.append(ev.text)
            if on_text:
                on_text(ev.text)
        elif ev.kind == "error":
            raise RuntimeError(ev.text)
    return "".join(out)
