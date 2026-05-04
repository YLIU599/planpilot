from __future__ import annotations

import os
from datetime import date, timedelta

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.agents.explainer import build_explanation
from app.agents.replanner import replan
from app.agents.task_parser import parse_planning_input
from app.config import settings
from app.evals.runner import run_evaluation
from app.schemas import ParseResult, RawPlanningInput, ReplanRequest, ScheduleRequest, ScheduleResponse
from app.scheduling.engine import generate_schedule

app = FastAPI(title="PlanPilot: Adaptive Scheduling Agent")

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
TEMPLATE_DIR = os.path.join(FRONTEND_DIR, "templates")
OUTPUTS_DIR = os.path.join(ROOT_DIR, "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with open(os.path.join(TEMPLATE_DIR, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "app": settings.app_name,
        "model": settings.model,
        "llm_parsing_enabled": settings.enable_llm_parsing,
    }


@app.get("/api/v1/sample")
def sample_input(stage: str = Query("details", pattern="^(basic|details)$")) -> dict:
    """Return a rolling presentation demo scenario.

    ``stage=basic`` loads only calendar/availability/tasks.
    ``stage=details`` also loads assignment metadata so the presentation can
    show effort estimation and task decomposition without requiring PDF upload.
    """
    today = date.today()
    stats_due = today + timedelta(days=3)
    ai_due = today + timedelta(days=9)
    reading_due = today + timedelta(days=6)
    details = (
        "Stats HW has 5 problems. "
        "AI project requires a working frontend, backend API, evaluation script, and a short report. "
        "Reading is about 25 pages."
    ) if stage == "details" else ""
    return {
        "current_date": today.isoformat(),
        "work_style": "balanced",
        "fixed_events_text": "Mon/Wed 10:10-11:25 IEOR class\nTue 14:00-17:00 part-time work\nFri 13:00-14:00 group meeting",
        "availability_text": "I can study 7-11pm on weekdays and 2-6pm on weekends. I prefer not to study after 11pm. Max 4 hours per day.",
        "tasks_text": (
            f"Stats HW due {stats_due.isoformat()}, problem set.\n"
            f"AI project due {ai_due.isoformat()}, needs frontend, backend, evaluation, report.\n"
            f"Reading for ML class due {reading_due.isoformat()}."
        ),
        "assignment_details_text": details,
        "preference_text": "I focus better after dinner. Coding tasks need at least 90-minute blocks. I prefer doing homework soon after class when possible.",
        "horizon_days": 14,
    }


@app.post("/api/v1/parse", response_model=ParseResult)
async def parse(raw: RawPlanningInput) -> ParseResult:
    return await parse_planning_input(raw)


@app.post("/api/v1/generate-schedule", response_model=ScheduleResponse)
def schedule(req: ScheduleRequest) -> ScheduleResponse:
    return generate_schedule(req)


@app.post("/api/v1/plan")
async def plan(raw: RawPlanningInput) -> dict:
    parsed = await parse_planning_input(raw)
    req = ScheduleRequest(
        current_date=raw.current_date or date.today(),
        fixed_events=parsed.fixed_events,
        availability_windows=parsed.availability_windows,
        preferences=parsed.preferences,
        tasks=parsed.tasks,
        horizon_days=raw.horizon_days,
        strategy="planpilot",
    )
    resp = generate_schedule(req)
    explanation = build_explanation(resp)
    return {
        "parsed": parsed.model_dump(mode="json"),
        "request": req.model_dump(mode="json"),
        "response": resp.model_dump(mode="json"),
        "explanation": explanation,
    }


@app.post("/api/v1/replan", response_model=ScheduleResponse)
def replan_endpoint(req: ReplanRequest) -> ScheduleResponse:
    return replan(req)


@app.get("/api/v1/evaluate")
def evaluate() -> dict:
    return run_evaluation().model_dump(mode="json")


def cli_serve() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
    )
