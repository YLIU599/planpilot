from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# LiteLLM uses VERTEX_PROJECT. Prior projects used VERTEX_PROJECT_ID.
if os.getenv("VERTEX_PROJECT_ID") and not os.getenv("VERTEX_PROJECT"):
    os.environ["VERTEX_PROJECT"] = os.environ["VERTEX_PROJECT_ID"]


@dataclass(frozen=True)
class Settings:
    app_name: str = "PlanPilot"
    model: str = os.getenv("MODEL", "vertex_ai/gemini-2.5-flash")
    vertex_project_id: str | None = os.getenv("VERTEX_PROJECT_ID") or os.getenv("VERTEX_PROJECT")
    vertex_location: str = os.getenv("VERTEX_LOCATION", "us-central1")
    enable_llm_parsing: bool = os.getenv("ENABLE_LLM_PARSING", "false").lower() in {"1", "true", "yes", "y"}
    default_timezone: str = os.getenv("DEFAULT_TIMEZONE", "America/New_York")


settings = Settings()
