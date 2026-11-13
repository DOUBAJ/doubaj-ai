"""Providers that speak the OpenAI Chat Completions protocol:
OpenAI, Google Gemini (official OpenAI-compatible endpoint), Ollama, llama.cpp server,
LM Studio, and any other compatible service."""
from __future__ import annotations

from typing import Iterator

from .base import CancelToken, ChatRequest, Provider, ProviderInfo, StreamEvent

REASONING_EFFORT = {"fast": "low", "standard": "medium", "deep": "high"}


class OpenAICompatProvider(Provider):
    info = ProviderInfo(
        id="openai", label="OpenAI", needs_key=True,
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-5",
        suggested_models=["gpt-5", "gpt-5-mini", "gpt-4.1", "gpt-4o", "o4-mini"],
        help="platform.openai.com → API keys",
    )
    send_reasoning_effort = True

    def _client(self):
        from openai import OpenAI
        return OpenAI(api_key=self.api_key or "not-needed", base_url=self.base_url, max_retries=1, timeout=600)

    def list_models(self) -> list[str]:
        try:
            ids = sorted(m.id for m in self._client().models.list())
            return ids or super().list_models()
        except Exception:
            return super().list_models()

    def _is_reasoning_model(self, model: str) -> bool:
        m = model.lower()
        return m.startswith(("o1", "o3", "o4", "gpt-5"))

    @staticmethod
    def _content(msg):
        if not msg.images:
            return msg.text
        parts = [{"type": "text", "text": msg.text or "."}]
        for im in msg.images:
            parts.append({"type": "image_url",
                          "image_url": {"url": f"data:{im['media_type']};base64,{im['data']}"}})
        return parts

    def build_params(self, req: ChatRequest) -> dict:
        msgs = [{"role": "system", "content": req.system}] if req.system else []
        msgs += [{"role": m.role, "content": self._content(m)} for m in req.messages]
        params: dict = {"model": req.model, "messages": msgs, "stream": True}
        if self.send_reasoning_effort and self._is_reasoning_model(req.model):
            params["reasoning_effort"] = REASONING_EFFORT.get(req.reasoning, "medium")
            params["max_completion_tokens"] = req.max_tokens
        else:
            params["max_tokens"] = req.max_tokens
            if req.temperature is not None:
                params["temperature"] = req.temperature
        return params

    def stream_chat(self, req: ChatRequest, cancel: CancelToken) -> Iterator[StreamEvent]:
        import openai
        try:
            stream = self._client().chat.completions.create(**self.build_params(req))
            usage = None
            for chunk in stream:
                if cancel.cancelled:
                    stream.close()
                    break
                if getattr(chunk, "usage", None):
                    usage = {"input": chunk.usage.prompt_tokens, "output": chunk.usage.completion_tokens}
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                rc = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                if rc:
                    yield StreamEvent("thinking", rc)
                if delta.content:
                    yield StreamEvent("text", delta.content)
            yield StreamEvent("done", usage=usage)
        except openai.AuthenticationError:
            yield StreamEvent("error", f"Invalid API key for {self.info.label} (401).")
        except openai.NotFoundError as e:
            yield StreamEvent("error", f"Model or endpoint not found ({req.model}): {e.message}")
        except openai.RateLimitError:
            yield StreamEvent("error", "Rate limit / quota reached (429).")
        except openai.APIStatusError as e:
            yield StreamEvent("error", f"{self.info.label} error {e.status_code}: {e.message}")
        except openai.APIConnectionError:
            yield StreamEvent("error", f"Cannot connect to {self.info.label} at {self.base_url}. "
                                       + ("Is the local server running?" if self.info.local else
                                          "Check your internet connection."))


class GeminiProvider(OpenAICompatProvider):
    info = ProviderInfo(
        id="gemini", label="Google Gemini", needs_key=True,
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_model="gemini-2.5-flash",
        suggested_models=["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
        help="aistudio.google.com → Get API key",
    )

    def _is_reasoning_model(self, model: str) -> bool:
        return "2.5" in model or "3" in model

    def build_params(self, req):
        p = super().build_params(req)
        if "max_completion_tokens" in p:  # Gemini expects max_tokens
            p["max_tokens"] = p.pop("max_completion_tokens")
        return p

    def list_models(self) -> list[str]:
        ids = super().list_models()
        return [i.replace("models/", "") for i in ids]


class OllamaProvider(OpenAICompatProvider):
    info = ProviderInfo(
        id="ollama", label="Ollama (local / hors ligne)", needs_key=False, local=True,
        default_base_url="http://localhost:11434/v1",
        default_model="llama3.2",
        suggested_models=["llama3.2", "qwen2.5:7b", "mistral", "gemma3", "llava"],
        help="ollama.com → install, then: ollama pull llama3.2",
    )
    send_reasoning_effort = False

    def list_models(self) -> list[str]:
        """Use Ollama's native API to also return sizes."""
        try:
            import httpx
            root = self.base_url.rstrip("/").removesuffix("/v1")
            data = httpx.get(root + "/api/tags", timeout=5).json()
            return [m["name"] for m in data.get("models", [])] or super().list_models()
        except Exception:
            return super().list_models()

    def model_details(self) -> list[dict]:
        import httpx
        root = self.base_url.rstrip("/").removesuffix("/v1")
        data = httpx.get(root + "/api/tags", timeout=5).json()
        return data.get("models", [])


class LlamaCppProvider(OpenAICompatProvider):
    info = ProviderInfo(
        id="llamacpp", label="llama.cpp server (local)", needs_key=False, local=True,
        default_base_url="http://localhost:8080/v1",
        default_model="local-model",
        suggested_models=["local-model"],
        help="llama-server -m model.gguf --port 8080",
    )
    send_reasoning_effort = False


class LMStudioProvider(OpenAICompatProvider):
    info = ProviderInfo(
        id="lmstudio", label="LM Studio (local)", needs_key=False, local=True,
        default_base_url="http://localhost:1234/v1",
        default_model="local-model", suggested_models=["local-model"],
        help="LM Studio → Developer → Start server",
    )
    send_reasoning_effort = False


class CustomCompatProvider(OpenAICompatProvider):
    info = ProviderInfo(
        id="custom", label="OpenAI-compatible (custom)", needs_key=False,
        default_base_url="https://openrouter.ai/api/v1",
        default_model="", suggested_models=[],
        help="Any service exposing /v1/chat/completions (OpenRouter, Groq, Mistral, DeepSeek...)",
    )
    send_reasoning_effort = False
