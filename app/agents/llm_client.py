from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings

try:
    from litellm import acompletion  # type: ignore
except Exception:  # pragma: no cover - fallback path for minimal local tests
    acompletion = None


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


async def complete_json(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> dict[str, Any] | None:
    if not settings.enable_llm_parsing or acompletion is None:
        return None
    try:
        resp = await acompletion(
            model=settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        content = resp["choices"][0]["message"]["content"]
        return _extract_json(content)
    except Exception:
        return None
