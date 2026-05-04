from __future__ import annotations

from datetime import date, datetime, time

from app.schemas import AvailabilityWindow, FixedEvent, Priority, ScheduleRequest, Task, TaskType, UserPreferences


def build_eval_cases() -> list[tuple[str, ScheduleRequest, bool]]:
    base = date(2026, 5, 1)
    weekday_evenings = [
        AvailabilityWindow(day="Fri", start=time(18, 0), end=time(22, 0)),
        AvailabilityWindow(day="Sat", start=time(13, 0), end=time(18, 0)),
        AvailabilityWindow(day="Sun", start=time(13, 0), end=time(18, 0)),
        AvailabilityWindow(day="Mon", start=time(18, 0), end=time(22, 0)),
        AvailabilityWindow(day="Tue", start=time(18, 0), end=time(22, 0)),
    ]
    prefs = UserPreferences(max_daily_work_minutes=300, hard_stop_time=time(23, 0), prefer_evening_focus=True)

    cases: list[tuple[str, ScheduleRequest, bool]] = []

    cases.append((
        "simple_feasible_homework",
        ScheduleRequest(
            current_date=base,
            availability_windows=weekday_evenings,
            preferences=prefs,
            tasks=[Task(
                title="Simulation homework",
                deadline=datetime(2026, 5, 3, 23, 59),
                estimated_minutes=240,
                task_type=TaskType.problem_set,
                priority=Priority.high,
                min_block_minutes=90,
                max_block_minutes=120,
            )],
        ),
        True,
    ))

    cases.append((
        "calendar_conflict_avoidance",
        ScheduleRequest(
            current_date=base,
            fixed_events=[FixedEvent(title="Group meeting", start=datetime(2026, 5, 2, 14, 0), end=datetime(2026, 5, 2, 16, 0))],
            availability_windows=weekday_evenings,
            preferences=prefs,
            tasks=[Task(
                title="ML coding project",
                deadline=datetime(2026, 5, 5, 23, 59),
                estimated_minutes=420,
                task_type=TaskType.coding_project,
                priority=Priority.high,
                min_block_minutes=90,
                max_block_minutes=150,
            )],
        ),
        True,
    ))

    cases.append((
        "infeasible_tight_deadline",
        ScheduleRequest(
            current_date=base,
            availability_windows=[AvailabilityWindow(day="Fri", start=time(18, 0), end=time(20, 0))],
            preferences=UserPreferences(max_daily_work_minutes=180),
            tasks=[Task(
                title="Large report",
                deadline=datetime(2026, 5, 1, 23, 59),
                estimated_minutes=600,
                task_type=TaskType.writing,
                priority=Priority.urgent,
                min_block_minutes=60,
                max_block_minutes=120,
            )],
        ),
        False,
    ))

    cases.append((
        "mixed_task_types",
        ScheduleRequest(
            current_date=base,
            availability_windows=weekday_evenings,
            preferences=prefs,
            tasks=[
                Task(title="Reading response", deadline=datetime(2026, 5, 4, 23, 59), estimated_minutes=120, task_type=TaskType.reading, priority=Priority.medium, min_block_minutes=30, max_block_minutes=60),
                Task(title="Optimization problem set", deadline=datetime(2026, 5, 5, 23, 59), estimated_minutes=360, task_type=TaskType.problem_set, priority=Priority.high, min_block_minutes=90, max_block_minutes=120),
                Task(title="Slides rehearsal", deadline=datetime(2026, 5, 6, 12, 0), estimated_minutes=90, task_type=TaskType.presentation, priority=Priority.medium, min_block_minutes=60, max_block_minutes=90),
            ],
        ),
        True,
    ))


    cases.append((
        "preference_sensitive_evening_focus",
        ScheduleRequest(
            current_date=base,
            availability_windows=[
                AvailabilityWindow(day="Fri", start=time(9, 0), end=time(11, 0)),
                AvailabilityWindow(day="Fri", start=time(19, 0), end=time(21, 0)),
            ],
            preferences=UserPreferences(max_daily_work_minutes=240, prefer_evening_focus=True),
            tasks=[Task(
                title="Focused coding block",
                deadline=datetime(2026, 5, 2, 23, 59),
                estimated_minutes=120,
                task_type=TaskType.coding_project,
                priority=Priority.high,
                min_block_minutes=120,
                max_block_minutes=120,
            )],
        ),
        True,
    ))

    return cases
