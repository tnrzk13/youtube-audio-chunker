"""Extract topic themes from video titles using an LLM provider."""

from __future__ import annotations

import json
import logging

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
Analyze these YouTube video titles and extract 2-5 distinct topic themes.
For each topic, provide a short name and a YouTube search query that would
find similar videos from any channel.

Video titles:
{titles}

Respond with ONLY a JSON array. Each element must have:
- "name": short topic name (2-4 words)
- "search_query": YouTube search query to find similar videos (3-6 words)

Example: [{{"name": "predictive history", "search_query": "predictive history documentary"}}]
"""


_DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}


def extract_topics_from_titles(
    titles: list[str],
    api_key: str,
    provider: str = "anthropic",
    model: str | None = None,
) -> list[dict]:
    if not titles:
        return []

    resolved_model = model or _DEFAULT_MODELS.get(provider, "")
    prompt = _EXTRACTION_PROMPT.format(
        titles="\n".join(f"- {t}" for t in titles)
    )

    try:
        if provider == "openai":
            raw = _call_openai(api_key, prompt, resolved_model)
        else:
            raw = _call_anthropic(api_key, prompt, resolved_model)
        return _parse_topics_response(raw)
    except Exception as exc:
        log.exception("Topic extraction failed (provider=%s)", provider)
        error_msg = _extract_api_error(exc)
        if error_msg:
            raise RuntimeError(error_msg) from exc
        return []


def _call_anthropic(api_key: str, prompt: str, model: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _call_openai(api_key: str, prompt: str, model: str) -> str:
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def _extract_api_error(exc: Exception) -> str | None:
    """Extract a user-facing message from API errors, or None for transient failures."""
    msg = str(exc).lower()
    if "credit" in msg or "billing" in msg or "balance" in msg:
        return "API account has insufficient credits. Check your billing at the provider's console."
    if "authentication" in msg or "auth" in msg or "invalid.*key" in msg or "api key" in msg:
        return "Invalid API key. Check your key in Settings."
    if "rate" in msg and "limit" in msg:
        return "Rate limited by the API. Try again in a moment."
    if "not found" in msg or "does not exist" in msg:
        model_hint = "model" if "model" in msg else ""
        return f"API error: {exc}" if model_hint else None
    return None


def _parse_topics_response(raw: str) -> list[dict]:
    try:
        # Strip markdown code fences if present
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[1]  # remove ```json line
            stripped = stripped.rsplit("```", 1)[0]  # remove closing ```
        data = json.loads(stripped)
        if not isinstance(data, list):
            return []
        return [
            {"name": item["name"], "search_query": item["search_query"]}
            for item in data
            if isinstance(item, dict) and "name" in item and "search_query" in item
        ]
    except (json.JSONDecodeError, KeyError):
        return []
