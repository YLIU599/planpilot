from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

STATE_DIR = Path("outputs/state")
STATE_DIR.mkdir(parents=True, exist_ok=True)


def create_session() -> str:
    session_id = str(uuid4())
    save_session(session_id, {})
    return session_id


def load_session(session_id: str) -> dict[str, Any]:
    path = STATE_DIR / f"{session_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(session_id: str, data: dict[str, Any]) -> None:
    path = STATE_DIR / f"{session_id}.json"
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
