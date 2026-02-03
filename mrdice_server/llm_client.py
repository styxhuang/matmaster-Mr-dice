import json
from typing import Optional

import requests

from .config import get_llm_config


class LlmError(RuntimeError):
    pass


def _resolve_api_base(provider: str, api_base: Optional[str]) -> str:
    if api_base:
        return api_base.rstrip("/")
    if provider == "deepseek":
        return "https://api.deepseek.com/v1"
    if provider == "openai":
        return "https://api.openai.com/v1"
    raise LlmError(f"Unknown provider: {provider}")


def chat_json(system: str, user: str, timeout: int = 30) -> str:
    """
    Call an OpenAI-compatible chat completion endpoint.
    Returns the assistant message content (string).
    """
    cfg = get_llm_config()
    if not cfg["api_key"]:
        raise LlmError("LLM_API_KEY is not set")

    api_base = _resolve_api_base(cfg["provider"], cfg["api_base"])
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LlmError(f"LLM request failed: {exc}") from exc
