"""Anthropic Claude provider (official `anthropic` SDK, streaming)."""
from __future__ import annotations

import re
from typing import Iterator

from .base import CancelToken, ChatRequest, Provider, ProviderInfo, StreamEvent

EFFORT = {"fast": "low", "standard": "medium", "deep": "high"}
# Models that answer refusals with a server-side fallback model (beta).
_FALLBACK_MODELS = ("claude-fable-5", "claude-opus-5", "claude-sonnet-5-5")


def _version(model: str) -> tuple[int, int]:
    m = re.search(r"-(\d+)(?:-(\d+))?(?:$|-\d{8})", model)
    if not m:
        return (0, 0)
    major = int(m.group(1))
    if major > 50:  # matched a date, not a version
        return (0, 0)
    minor = int(m.group(2)) if m.group(2) and len(m.group(2)) < 3 else 0
    return (major, minor)


def _modern(model: str) -> bool:
    """Claude 4.6+ / 5.x: adaptive thinking + effort, no sampling params."""
    if "fable" in model or "mythos" in model:
        return True
    return _version(model) >= (4, 6)


class AnthropicProvider(Provider):
    info = ProviderInfo(
        id="anthropic", label="Anthropic Claude", needs_key=True,
        default_model="claude-opus-5-5",
        suggested_models=["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2"],
        help="console.anthropic.com → API Keys",
    )

    def _client(self):
        import anthropic
        kw = {"api_key": self.api_key, "max_retries": 2}
        if self.base_url:
            kw["base_url"] = self.base_url
        return anthropic.Anthropic(**kw)

    def list_models(self) -> list[str]:
        try:
            return [m.id for m in self._client().models.list(limit=100)]
        except Exception:
            return super().list_models()

    @staticmethod
    def _content(msg) -> list | str:
        if not msg.images:
            return msg.text
        blocks = [{"type": "image", "source": {"type": "base64", "media_type": im["media_type"], "data": im["data"]}}
                  for im in msg.images]
        blocks.append({"type": "text", "text": msg.text or "."})
        return blocks

    def stream_chat(self, req: ChatRequest, cancel: CancelToken) -> Iterator[StreamEvent]:
        import anthropic
        params: dict = {
            "model": req.model,
            "max_tokens": max(req.max_tokens, 1024),
            "system": req.system,
            "messages": [{"role": m.role, "content": self._content(m)} for m in req.messages],
        }
        extra_headers: dict = {}
        extra_body: dict = {}
        if _modern(req.model):
            params["thinking"] = {"type": "adaptive", "display": "summarized"}
            params["output_config"] = {"effort": EFFORT.get(req.reasoning, "medium")}
            if req.model.startswith(_FALLBACK_MODELS):
                extra_headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
                extra_body["fallbacks"] = "default"
        elif req.temperature is not None:
            params["temperature"] = req.temperature
        try:
            with self._client().messages.stream(**params, extra_headers=extra_headers or None,
                                                 extra_body=extra_body or None) as stream:
                for event in stream:
                    if cancel.cancelled:
                        break
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            yield StreamEvent("text", event.delta.text)
                        elif event.delta.type == "thinking_delta":
                            yield StreamEvent("thinking", event.delta.thinking)
                if cancel.cancelled:
                    yield StreamEvent("done")
                    return
                final = stream.get_final_message()
                if final.stop_reason == "refusal":
                    yield StreamEvent("error", "The model declined this request (refusal).")
                    return
                usage = {"input": final.usage.input_tokens, "output": final.usage.output_tokens}
                yield StreamEvent("done", usage=usage)
        except anthropic.AuthenticationError:
            yield StreamEvent("error", "Invalid Anthropic API key (401).")
        except anthropic.NotFoundError:
            yield StreamEvent("error", f"Model not found: {req.model}")
        except anthropic.RateLimitError:
            yield StreamEvent("error", "Rate limit reached (429). Please wait and retry.")
        except anthropic.APIStatusError as e:
            yield StreamEvent("error", f"Anthropic API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            yield StreamEvent("error", "Cannot reach the Anthropic API (check your internet connection).")
