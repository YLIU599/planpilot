from datetime import date, datetime, time

from app.schemas import AvailabilityWindow, FixedEvent, Priority, ScheduleBlock, ScheduleRequest, Task, TaskType, UserPreferences
from app.scheduling.engine import generate_schedule


def test_scheduler_avoids_fixed_event_conflict():
    req = ScheduleRequest(
        current_date=date(2026, 5, 1),
        fixed_events=[FixedEvent(title="Meeting", start=datetime(2026, 5, 1, 19, 0), end=datetime(2026, 5, 1, 20, 0))],
        availability_windows=[AvailabilityWindow(day="Fri", start=time(18, 0), end=time(22, 0))],
        preferences=UserPreferences(max_daily_work_minutes=240),
        tasks=[Task(title="Homework", deadline=datetime(2026, 5, 1, 23, 59), estimated_minutes=120, task_type=TaskType.problem_set, priority=Priority.high, min_block_minutes=60, max_block_minutes=120)],
    )
    resp = generate_schedule(req)
    assert resp.validation.metrics["calendar_conflicts"] == 0
    assert resp.validation.metrics["task_overlaps"] == 0


def test_infeasible_case_has_unscheduled_work():
    req = ScheduleRequest(
        current_date=date(2026, 5, 1),
        availability_windows=[AvailabilityWindow(day="Fri", start=time(18, 0), end=time(19, 0))],
        tasks=[Task(title="Large project", deadline=datetime(2026, 5, 1, 23, 59), estimated_minutes=600, task_type=TaskType.coding_project)],
    )
    resp = generate_schedule(req)
    assert resp.unscheduled
    assert resp.validation.metrics["unscheduled_minutes"] > 0

from app.schemas import Subtask
from app.scheduling.validator import validate_schedule


def test_project_subtasks_are_scheduled_in_dependency_order():
    task = Task(
        title="ML project",
        deadline=datetime(2026, 5, 6, 23, 59),
        estimated_minutes=480,
        task_type=TaskType.coding_project,
        min_block_minutes=90,
        max_block_minutes=150,
        subtasks=[
            Subtask(title="EDA", estimated_minutes=120),
            Subtask(title="Modeling", estimated_minutes=150),
            Subtask(title="Writeup", estimated_minutes=120),
            Subtask(title="Slides", estimated_minutes=90),
        ],
    )
    req = ScheduleRequest(
        current_date=date(2026, 5, 1),
        availability_windows=[
            AvailabilityWindow(day="Fri", start=time(19, 0), end=time(23, 0)),
            AvailabilityWindow(day="Sat", start=time(14, 0), end=time(18, 0)),
            AvailabilityWindow(day="Sun", start=time(14, 0), end=time(18, 0)),
            AvailabilityWindow(day="Mon", start=time(19, 0), end=time(23, 0)),
            AvailabilityWindow(day="Tue", start=time(19, 0), end=time(23, 0)),
            AvailabilityWindow(day="Wed", start=time(19, 0), end=time(23, 0)),
        ],
        preferences=UserPreferences(prefer_evening_focus=True, max_daily_work_minutes=240),
        tasks=[task],
    )
    resp = generate_schedule(req)
    stage_order = {"eda": 1, "modeling": 2, "writeup": 3, "slides": 4}
    seen = []
    for block in resp.schedule:
        lower = block.task_title.lower()
        for name, idx in stage_order.items():
            if name in lower:
                seen.append(idx)
                break
    assert seen == sorted(seen)
    assert resp.validation.metrics["dependency_violations"] == 0


def test_validator_catches_project_dependency_order_violation():
    task = Task(
        title="ML project",
        deadline=datetime(2026, 5, 6, 23, 59),
        estimated_minutes=240,
        task_type=TaskType.coding_project,
        subtasks=[
            Subtask(title="EDA", estimated_minutes=60),
            Subtask(title="Modeling", estimated_minutes=60),
            Subtask(title="Writeup", estimated_minutes=60),
            Subtask(title="Slides", estimated_minutes=60),
        ],
    )
    blocks = [
        # Invalid: Slides appears before EDA.
        ScheduleBlock(
            task_id=task.id,
            task_title="ML project — Slides",
            task_type=TaskType.coding_project,
            start=datetime(2026, 5, 2, 14, 0),
            end=datetime(2026, 5, 2, 15, 0),
            minutes=60,
            priority=Priority.medium,
        ),
        ScheduleBlock(
            task_id=task.id,
            task_title="ML project — EDA",
            task_type=TaskType.coding_project,
            start=datetime(2026, 5, 2, 15, 0),
            end=datetime(2026, 5, 2, 16, 0),
            minutes=60,
            priority=Priority.medium,
        ),
    ]
    result = validate_schedule(blocks, [], [task], UserPreferences())
    assert result.metrics["dependency_violations"] == 1
    assert not result.valid


def test_rotate_work_style_interleaves_independent_tasks_when_feasible():
    req = ScheduleRequest(
        current_date=date(2026, 5, 1),
        availability_windows=[
            AvailabilityWindow(day="Fri", start=time(18, 0), end=time(23, 0)),
            AvailabilityWindow(day="Sat", start=time(13, 0), end=time(18, 0)),
        ],
        preferences=UserPreferences(max_daily_work_minutes=300, work_style="rotate"),
        tasks=[
            Task(title="Problem set", deadline=datetime(2026, 5, 3, 23, 59), estimated_minutes=240, task_type=TaskType.problem_set, min_block_minutes=120, max_block_minutes=120),
            Task(title="Reading", deadline=datetime(2026, 5, 3, 23, 59), estimated_minutes=120, task_type=TaskType.reading, min_block_minutes=60, max_block_minutes=60),
        ],
    )
    resp = generate_schedule(req)
    titles = [b.task_title for b in resp.schedule[:3]]
    assert len(set(titles)) > 1
