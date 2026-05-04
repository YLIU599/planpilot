from __future__ import annotations

from datetime import datetime

from app.schemas import Priority, Task, TaskType, UserPreferences, PRIORITY_WEIGHTS


def type_defaults(task_type: TaskType) -> tuple[bool, int, int]:
    """Return (splittable, min_block_minutes, max_block_minutes) defaults."""
    if task_type == TaskType.reading:
        return True, 30, 60
    if task_type == TaskType.problem_set:
        return True, 90, 120
    if task_type == TaskType.coding_project:
        return True, 90, 150
    if task_type == TaskType.writing:
        return True, 60, 120
    if task_type == TaskType.exam_prep:
        return True, 45, 90
    if task_type == TaskType.presentation:
        return True, 60, 120
    if task_type == TaskType.group_project:
        return True, 60, 120
    if task_type == TaskType.admin_task:
        return True, 30, 60
    return True, 60, 120


def task_priority_score(task: Task, now: datetime) -> float:
    hours_until_deadline = max(1.0, (task.deadline - now).total_seconds() / 3600)
    urgency = 168 / hours_until_deadline  # grows as deadline approaches within a week
    priority = PRIORITY_WEIGHTS.get(task.priority, 2) * 5
    deep_work_bonus = 2 if task.task_type in {TaskType.coding_project, TaskType.problem_set} else 0
    remaining_bonus = min(6, task.remaining_minutes / 60)
    return urgency + priority + deep_work_bonus + remaining_bonus


def slot_fit_score(task: Task, start: datetime, preferences: UserPreferences) -> float:
    score = 0.0
    hour = start.hour + start.minute / 60

    if preferences.prefer_evening_focus and task.task_type in {TaskType.coding_project, TaskType.problem_set, TaskType.writing}:
        if 18 <= hour <= 22:
            score += 4
        elif hour < 12:
            score -= 1

    if preferences.prefer_morning_focus and task.task_type in {TaskType.coding_project, TaskType.problem_set, TaskType.writing}:
        if 8 <= hour <= 12:
            score += 4
        elif hour >= 20:
            score -= 1

    if preferences.hard_stop_time and start.time() >= preferences.hard_stop_time:
        score -= 100

    # Prefer not to put difficult deep-work tasks in tiny late-day slots.
    if task.task_type in {TaskType.coding_project, TaskType.problem_set} and hour >= 21.5:
        score -= 2

    # Short administrative tasks fit well in awkward windows.
    if task.task_type == TaskType.admin_task and (hour < 10 or hour >= 20):
        score += 1

    return score


def compute_objective_score(validation_metrics: dict) -> float:
    score = 100.0
    score -= 20 * validation_metrics.get("calendar_conflicts", 0)
    score -= 20 * validation_metrics.get("task_overlaps", 0)
    score -= 25 * validation_metrics.get("deadline_violations", 0)
    score -= 15 * validation_metrics.get("daily_capacity_violations", 0)
    score -= 10 * validation_metrics.get("dependency_violations", 0)
    score -= 0.05 * validation_metrics.get("unscheduled_minutes", 0)
    score -= 1.5 * validation_metrics.get("fragmentation_penalty", 0)
    score -= 2.0 * validation_metrics.get("preference_misses", 0)
    score += 0.5 * validation_metrics.get("preference_bonus", 0)
    return round(max(0.0, score), 2)
