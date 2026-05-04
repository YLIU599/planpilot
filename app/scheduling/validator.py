from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

from app.schemas import FixedEvent, ScheduleBlock, Task, UnscheduledWork, UserPreferences, ValidationResult, ValidationViolation
from app.scheduling.time_utils import minutes_between, overlaps


def validate_schedule(
    blocks: list[ScheduleBlock],
    fixed_events: list[FixedEvent],
    tasks: list[Task],
    preferences: UserPreferences,
    unscheduled: list[UnscheduledWork] | None = None,
) -> ValidationResult:
    violations: list[ValidationViolation] = []
    metrics = {
        "calendar_conflicts": 0,
        "task_overlaps": 0,
        "deadline_violations": 0,
        "daily_capacity_violations": 0,
        "dependency_violations": 0,
        "unscheduled_minutes": sum(u.remaining_minutes for u in (unscheduled or [])),
        "fragmentation_penalty": 0,
        "preference_bonus": 0,
        "preference_misses": 0,
        "scheduled_minutes": sum(b.minutes for b in blocks),
    }

    task_by_id = {t.id: t for t in tasks}

    # Calendar conflicts.
    for block in blocks:
        for ev in fixed_events:
            if overlaps(block.start, block.end, ev.start, ev.end):
                metrics["calendar_conflicts"] += 1
                violations.append(ValidationViolation(
                    type="calendar_conflict",
                    severity="error",
                    block_id=block.id,
                    task_id=block.task_id,
                    message=f"{block.task_title} overlaps fixed event '{ev.title}'.",
                ))

    # Task block overlaps.
    sorted_blocks = sorted(blocks, key=lambda b: b.start)
    for i, a in enumerate(sorted_blocks):
        for b in sorted_blocks[i + 1:]:
            if b.start >= a.end:
                break
            if overlaps(a.start, a.end, b.start, b.end):
                metrics["task_overlaps"] += 1
                violations.append(ValidationViolation(
                    type="task_overlap",
                    severity="error",
                    block_id=a.id,
                    message=f"{a.task_title} overlaps {b.task_title}.",
                ))

    # Deadline violations and min block checks.
    by_task: dict[str, list[ScheduleBlock]] = defaultdict(list)
    for block in blocks:
        by_task[block.task_id].append(block)
        task = task_by_id.get(block.task_id)
        if task and block.end > task.deadline:
            metrics["deadline_violations"] += 1
            violations.append(ValidationViolation(
                type="deadline_violation",
                severity="error",
                block_id=block.id,
                task_id=block.task_id,
                message=f"{block.task_title} is scheduled after its deadline.",
            ))
        if task and block.minutes < task.min_block_minutes and block.minutes != task.remaining_minutes:
            metrics["fragmentation_penalty"] += 1
            violations.append(ValidationViolation(
                type="short_block",
                severity="warning",
                block_id=block.id,
                task_id=block.task_id,
                message=f"{block.task_title} has a block shorter than its preferred minimum.",
            ))

    # Daily capacity.
    minutes_by_day: dict[date, int] = defaultdict(int)
    for block in blocks:
        minutes_by_day[block.start.date()] += block.minutes
    for day, minutes in minutes_by_day.items():
        if minutes > preferences.max_daily_work_minutes:
            metrics["daily_capacity_violations"] += 1
            violations.append(ValidationViolation(
                type="daily_capacity_violation",
                severity="error",
                message=(
                    f"{day.isoformat()} has {minutes} scheduled minutes, "
                    f"above the {preferences.max_daily_work_minutes}-minute daily limit."
                ),
            ))

    # Dependency checks for decomposed project subtasks.
    # The scheduler displays project stages in the task title, for example
    # "ML project — EDA" and "ML project — Modeling". A valid schedule must
    # never move from a later stage back to an earlier stage in chronological
    # order. This catches the v2 failure mode where Slides could appear before
    # EDA while the validator still showed all green checks.
    for task in tasks:
        if not task.subtasks:
            continue
        stage_order = {sub.title.strip().lower(): idx for idx, sub in enumerate(task.subtasks, start=1)}
        max_seen_stage = 0
        max_seen_title = ""
        for block in sorted(by_task.get(task.id, []), key=lambda b: (b.start, b.end)):
            title_lower = block.task_title.lower()
            current_stage = None
            current_title = None
            for stage_title, stage_idx in stage_order.items():
                if stage_title in title_lower:
                    current_stage = stage_idx
                    current_title = stage_title
                    break
            if current_stage is None:
                continue
            if current_stage < max_seen_stage:
                metrics["dependency_violations"] += 1
                violations.append(ValidationViolation(
                    type="dependency_order_violation",
                    severity="error",
                    block_id=block.id,
                    task_id=task.id,
                    message=(
                        f"{task.title} dependency order violated: "
                        f"stage '{current_title}' is scheduled after a later stage '{max_seen_title}'."
                    ),
                ))
            if current_stage > max_seen_stage:
                max_seen_stage = current_stage
                max_seen_title = current_title or "later stage"

    # Preference score.
    for block in blocks:
        deep = block.task_type.value in {"coding_project", "problem_set", "writing"}
        if preferences.prefer_evening_focus:
            if 18 <= block.start.hour <= 22:
                metrics["preference_bonus"] += 1
            elif deep:
                metrics["preference_misses"] += 1
        if preferences.prefer_morning_focus:
            if 8 <= block.start.hour <= 12:
                metrics["preference_bonus"] += 1
            elif deep:
                metrics["preference_misses"] += 1

    valid = not any(v.severity == "error" for v in violations)
    return ValidationResult(valid=valid, violations=violations, metrics=metrics)
