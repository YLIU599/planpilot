from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class TaskType(str, Enum):
    reading = "reading"
    problem_set = "problem_set"
    coding_project = "coding_project"
    writing = "writing"
    exam_prep = "exam_prep"
    presentation = "presentation"
    group_project = "group_project"
    admin_task = "admin_task"
    other = "other"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


PRIORITY_WEIGHTS = {
    Priority.low: 1,
    Priority.medium: 2,
    Priority.high: 3,
    Priority.urgent: 4,
}


class FixedEvent(BaseModel):
    title: str
    start: datetime
    end: datetime
    event_type: str = "fixed"

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: datetime, info):
        start = info.data.get("start")
        if start and v <= start:
            raise ValueError("FixedEvent.end must be after start")
        return v


class AvailabilityWindow(BaseModel):
    day: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start: time
    end: time

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: time, info):
        start = info.data.get("start")
        if start and v <= start:
            raise ValueError("AvailabilityWindow.end must be after start")
        return v


class UserPreferences(BaseModel):
    hard_stop_time: time | None = None
    work_style: Literal["balanced", "batch", "rotate"] = "balanced"
    max_daily_work_minutes: int = Field(default=240, ge=30, le=900)
    prefer_evening_focus: bool = False
    prefer_morning_focus: bool = False
    prefer_homework_after_class: bool = True
    preserve_existing_schedule: bool = True
    buffer_before_deadline_minutes: int = Field(default=60, ge=0, le=1440)
    notes: str = ""


class Subtask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    estimated_minutes: int = Field(ge=30)
    depends_on: list[str] = Field(default_factory=list)


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    deadline: datetime
    estimated_minutes: int = Field(ge=30)
    completed_minutes: int = Field(default=0, ge=0)
    task_type: TaskType = TaskType.other
    priority: Priority = Priority.medium
    splittable: bool = True
    min_block_minutes: int = Field(default=60, ge=30)
    max_block_minutes: int = Field(default=120, ge=30)
    subtasks: list[Subtask] = Field(default_factory=list)
    notes: str = ""
    estimate_source: Literal["user", "system"] = "user"
    estimate_confidence: Literal["low", "medium", "high"] = "high"
    estimate_rationale: str = ""

    @field_validator("max_block_minutes")
    @classmethod
    def max_block_at_least_min(cls, v: int, info):
        min_block = info.data.get("min_block_minutes")
        if min_block and v < min_block:
            raise ValueError("max_block_minutes must be >= min_block_minutes")
        return v

    @property
    def remaining_minutes(self) -> int:
        return max(0, self.estimated_minutes - self.completed_minutes)


class RawPlanningInput(BaseModel):
    current_date: date | None = None
    work_style: Literal["balanced", "batch", "rotate"] = "balanced"
    fixed_events_text: str = ""
    availability_text: str = ""
    tasks_text: str = ""
    assignment_details_text: str = ""
    preference_text: str = ""
    horizon_days: int = Field(default=10, ge=1, le=31)


class ParseResult(BaseModel):
    fixed_events: list[FixedEvent] = Field(default_factory=list)
    availability_windows: list[AvailabilityWindow] = Field(default_factory=list)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    tasks: list[Task] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    parser_mode: str = "fallback"


class ScheduleRequest(BaseModel):
    current_date: date | None = None
    fixed_events: list[FixedEvent] = Field(default_factory=list)
    availability_windows: list[AvailabilityWindow] = Field(default_factory=list)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    tasks: list[Task] = Field(default_factory=list)
    horizon_days: int = Field(default=10, ge=1, le=31)
    strategy: Literal["planpilot", "earliest_deadline", "naive_equal_split"] = "planpilot"


class ScheduleBlock(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    task_title: str
    task_type: TaskType
    start: datetime
    end: datetime
    minutes: int
    priority: Priority
    note: str = ""


class UnscheduledWork(BaseModel):
    task_id: str
    task_title: str
    remaining_minutes: int
    reason: str


class ValidationViolation(BaseModel):
    type: str
    severity: Literal["info", "warning", "error"]
    message: str
    task_id: str | None = None
    block_id: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    violations: list[ValidationViolation] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ScheduleResponse(BaseModel):
    schedule: list[ScheduleBlock]
    unscheduled: list[UnscheduledWork]
    validation: ValidationResult
    summary: str
    assumptions: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    day_summaries: list[str] = Field(default_factory=list)
    validation_summary: list[str] = Field(default_factory=list)
    replan_changes: list[str] = Field(default_factory=list)
    objective_score: float = 0.0
    strategy: str = "planpilot"


class ProgressUpdate(BaseModel):
    task_title: str
    completed_minutes: int = Field(ge=0)


class ReplanRequest(BaseModel):
    original_request: ScheduleRequest
    progress_text: str = ""
    progress_updates: list[ProgressUpdate] = Field(default_factory=list)


class EvaluationCase(BaseModel):
    name: str
    request: ScheduleRequest
    expected_feasible: bool = True
    notes: str = ""


class EvaluationResult(BaseModel):
    case_name: str
    strategy: str
    valid: bool
    objective_score: float
    metrics: dict[str, Any]
    violations: list[ValidationViolation]


class EvaluationSummary(BaseModel):
    results: list[EvaluationResult]
    aggregate: dict[str, Any]
