"""
Provider-agnostic LLM access. One function, four backends.

The user asked which API to use. Rather than hard-coding one, this layer
speaks to whichever key is present, so the same code runs on:

    Anthropic   (ANTHROPIC_API_KEY)      — best reasoning + instruction following
    OpenAI      (OPENAI_API_KEY)         — strongest strict-JSON enforcement
    Gemini      (GEMINI_API_KEY)         — cheapest frontier, huge context
    OpenRouter  (OPENROUTER_API_KEY)     — one key for everything, 20+ free models
    generic     (LLM_BASE_URL)           — any OpenAI-compatible endpoint

Every call logs which provider/model was requested and which actually ran.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

log = logging.getLogger("engineer.llm")

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-5-mini",
    "gemini": "gemini-2.5-flash",
    "openrouter": "anthropic/claude-sonnet-4.5",
    "generic": "local-model",
}

_JSON_HINT = ("Respond with a single JSON object and nothing else — no prose, "
              "no markdown fence, no commentary before or after.")


class LLMError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
def detect_provider() -> Optional[str]:
    for var, prov in (
        ("OPENROUTER_API_KEY", "openrouter"),
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("OPENAI_API_KEY", "openai"),
        ("GEMINI_API_KEY", "gemini"),
        ("GOOGLE_API_KEY", "gemini"),
    ):
        if os.environ.get(var):
            return prov
    if os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_API_KEY"):
        return "generic"
    return None


def _http(url: str, headers: dict, payload: dict, timeout: float = 240.0) -> dict:
    try:
        import httpx
    except ImportError:  # pragma: no cover - stdlib fallback
        import urllib.request
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={**headers, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    with httpx.Client(timeout=timeout) as c:
        r = c.post(url, headers={**headers, "Content-Type": "application/json"},
                   json=payload)
        if r.status_code >= 400:
            raise LLMError(f"HTTP {r.status_code}: {r.text[:400]}")
        return r.json()


class LLM:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None,
                 temperature: float = 0.4, max_tokens: int = 16000):
        self.provider = provider or detect_provider()
        self.model = model or os.environ.get("LLM_MODEL") or \
            DEFAULT_MODELS.get(self.provider or "", "local-model")
        self.temperature = temperature
        self.max_tokens = max_tokens
        if not self.provider:
            raise LLMError(
                "No LLM key found. Set one of: OPENROUTER_API_KEY, "
                "ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY — "
                "or LLM_BASE_URL + LLM_API_KEY + LLM_MODEL."
            )
        self.key = self._key()

    def _key(self) -> str:
        return {
            "openrouter": "OPENROUTER_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "generic": "LLM_API_KEY",
        }[self.provider] and os.environ.get({
            "openrouter": "OPENROUTER_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "generic": "LLM_API_KEY",
        }[self.provider], "") or ""

    # -- single entry point -------------------------------------------------
    def complete(self, system: str, user: str, json_mode: bool = False,
                 max_tokens: Optional[int] = None) -> str:
        mt = max_tokens or self.max_tokens
        sys_txt = system + (("\n\n" + _JSON_HINT) if json_mode else "")
        log.info("llm.call provider=%s model=%s json=%s", self.provider, self.model, json_mode)
        if self.provider == "anthropic":
            text = self._anthropic(sys_txt, user, mt, json_mode)
        elif self.provider == "gemini":
            text = self._gemini(sys_txt, user, mt, json_mode)
        else:
            text = self._openai_compat(sys_txt, user, mt, json_mode)
        log.info("llm.done provider=%s model=%s chars=%d", self.provider, self.model, len(text))
        return text

    # -- backends -----------------------------------------------------------
    def _anthropic(self, system, user, mt, json_mode):
        url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
        payload = {
            "model": self.model,
            "max_tokens": mt,
            "temperature": self.temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = _http(url, {"x-api-key": self.key, "anthropic-version": "2023-06-01"}, payload)
        used = data.get("model") or self.model
        if used != self.model:
            log.warning("llm.model_mismatch requested=%s used=%s", self.model, used)
        return "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")

    def _gemini(self, system, user, mt, json_mode):
        base = os.environ.get("GEMINI_BASE_URL",
                              "https://generativelanguage.googleapis.com/v1beta")
        url = f"{base}/models/{self.model}:generateContent?key={self.key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": mt,
                **({"responseMimeType": "application/json"} if json_mode else {}),
            },
        }
        data = _http(url, {}, payload)
        try:
            return "".join(p.get("text", "") for c in data["candidates"]
                           for p in c["content"]["parts"])
        except Exception as e:
            raise LLMError(f"Gemini response unreadable: {data}"[:400]) from e

    def _openai_compat(self, system, user, mt, json_mode):
        if self.provider == "openrouter":
            url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        elif self.provider == "generic":
            url = os.environ["LLM_BASE_URL"].rstrip("/")
        else:
            url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        url = url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        # newer OpenAI models use max_completion_tokens
        payload["max_tokens" if self.provider != "openai" else "max_completion_tokens"] = mt
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.key}"}
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = os.environ.get("APP_URL", "https://fabrix.app")
            headers["X-Title"] = "Fabrix Engineer"
        data = _http(url, headers, payload)
        used = (data.get("model") or self.model)
        if used != self.model:
            log.warning("llm.model_mismatch requested=%s used=%s", self.model, used)
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMError(f"OpenAI-compatible response unreadable: {data}"[:400]) from e


# ---------------------------------------------------------------------------
def extract_json(text: str) -> dict:
    """Pull the first complete JSON object out of a model reply."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    start = t.find("{")
    if start < 0:
        raise LLMError("no JSON object in the reply")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])
    raise LLMError("JSON object was truncated")
