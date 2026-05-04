from __future__ import annotations

from datetime import date
from typing import Any

from app.agents.fallback_parser import parse_availability, parse_fixed_events, parse_tasks
from app.agents.llm_client import complete_json
from app.schemas import AvailabilityWindow, FixedEvent, ParseResult, RawPlanningInput, Task, UserPreferences

SYSTEM_PROMPT = """You convert messy scheduling inputs into strict JSON for a scheduling agent.
Return JSON only. Do not add markdown.
Schema:
{
  "fixed_events": [{"title": str, "start": "YYYY-MM-DDTHH:MM:SS", "end": "YYYY-MM-DDTHH:MM:SS", "event_type": str}],
  "availability_windows": [{"day": "Mon|Tue|Wed|Thu|Fri|Sat|Sun", "start": "HH:MM:SS", "end": "HH:MM:SS"}],
  "preferences": {"hard_stop_time": "HH:MM:SS|null", "work_style": "balanced|batch|rotate", "max_daily_work_minutes": int, "prefer_evening_focus": bool, "prefer_morning_focus": bool, "prefer_homework_after_class": bool, "buffer_before_deadline_minutes": int, "notes": str},
  "tasks": [{"title": str, "deadline": "YYYY-MM-DDTHH:MM:SS", "estimated_minutes": int, "completed_minutes": 0, "task_type": "reading|problem_set|coding_project|writing|exam_prep|presentation|group_project|admin_task|other", "priority": "low|medium|high|urgent", "splittable": bool, "min_block_minutes": int, "max_block_minutes": int, "subtasks": [{"title": str, "estimated_minutes": int, "depends_on": [str]}], "notes": str, "estimate_source": "user|system", "estimate_confidence": "low|medium|high", "estimate_rationale": str}],
  "assumptions": [str],
  "clarification_questions": [str]
}
Rules:
- Use the provided current_date to resolve relative dates.
- If effort is missing, infer a tentative estimate from task type, deliverables, and optional assignment details; mark estimate_source="system" and add an assumption.
- Ask a clarification question only for missing information that blocks scheduling.
- Coding/project/problem-set tasks should usually require 90+ minute blocks.
- Reading/admin tasks can use 30-60 minute blocks.
- Use work_style="batch" when the user wants to finish one task/topic before switching, work_style="rotate" when the user wants variety or topic switching, and work_style="balanced" otherwise.
- If a project description names stages such as EDA, modeling, writeup, slides, debugging, or final review, return those as ordered subtasks with approximate minute allocations.
"""


async def parse_planning_input(raw: RawPlanningInput) -> ParseResult:
    current_date = raw.current_date or date.today()
    user_payload = raw.model_dump(mode="json")
    llm_json = await complete_json(SYSTEM_PROMPT, str(user_payload))
    if llm_json:
        try:
            return ParseResult(
                fixed_events=[FixedEvent.model_validate(x) for x in llm_json.get("fixed_events", [])],
                availability_windows=[AvailabilityWindow.model_validate(x) for x in llm_json.get("availability_windows", [])],
                preferences=UserPreferences.model_validate({**llm_json.get("preferences", {}), "work_style": raw.work_style or llm_json.get("preferences", {}).get("work_style", "balanced")}),
                tasks=[Task.model_validate(x) for x in llm_json.get("tasks", [])],
                assumptions=llm_json.get("assumptions", []),
                clarification_questions=llm_json.get("clarification_questions", []),
                parser_mode="llm",
            )
        except Exception:
            pass

    availability, prefs, avail_assumptions = parse_availability(raw.availability_text + "\n" + raw.preference_text)
    if raw.work_style:
        prefs.work_style = raw.work_style
    fixed_events, event_assumptions = parse_fixed_events(raw.fixed_events_text, current_date)
    tasks, task_assumptions, questions = parse_tasks(raw.tasks_text, current_date, raw.assignment_details_text)
    return ParseResult(
        fixed_events=fixed_events,
        availability_windows=availability,
        preferences=prefs,
        tasks=tasks,
        assumptions=avail_assumptions + event_assumptions + task_assumptions,
        clarification_questions=questions,
        parser_mode="fallback",
    )
