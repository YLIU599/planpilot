from datetime import date

from app.agents.fallback_parser import parse_availability, parse_tasks


def test_parse_weekday_availability():
    windows, prefs, assumptions = parse_availability("I can study 7-11pm on weekdays and 2-6pm on weekends. Max 4 hours per day.")
    assert len(windows) >= 7
    assert prefs.max_daily_work_minutes == 240


def test_parse_tasks_basic():
    tasks, assumptions, questions = parse_tasks("Simulation HW due Sunday, estimated 6 hours, problem set.", date(2026, 5, 1))
    assert len(tasks) == 1
    assert tasks[0].estimated_minutes == 360
    assert tasks[0].task_type == "problem_set"


def test_parse_work_style_preferences():
    _, batch_prefs, _ = parse_availability("I prefer to finish one task at a time before switching.")
    assert batch_prefs.work_style == "batch"
    _, rotate_prefs, _ = parse_availability("I like to switch between different topics for variety.")
    assert rotate_prefs.work_style == "rotate"

from app.agents.fallback_parser import parse_progress


def test_parse_progress_minutes_without_double_counting():
    assert parse_progress("I only completed 30 min of Stats HW today.") == [("stats hw", 30)]


def test_parse_progress_mixed_hours_and_minutes():
    assert parse_progress("I did 1h 30 min of AI project today.") == [("ai project", 90)]


def test_missing_effort_estimate_gets_system_estimate():
    tasks, assumptions, questions = parse_tasks("AI project due next Thursday, needs frontend, backend, evaluation, report.", date(2026, 5, 1))
    assert tasks[0].estimated_minutes == 600
    assert tasks[0].estimate_source == "system"
    assert tasks[0].estimate_confidence == "medium"
    assert [s.title for s in tasks[0].subtasks] == ["Frontend", "Backend", "Evaluation", "Writeup"]
    assert assumptions


def test_assignment_details_are_scoped_per_task():
    text = """Stats HW due Monday, problem set.
AI project due next Thursday, needs frontend, backend, evaluation, report.
Reading for ML class due Tuesday."""
    details = "Stats HW has 5 problems. AI project requires a working frontend, backend API, evaluation script, and a short report. Reading is about 25 pages."
    tasks, assumptions, questions = parse_tasks(text, date(2026, 5, 1), details)
    by_title = {t.title: t for t in tasks}
    stats = by_title["Stats HW, problem set"]
    ai = by_title["AI project"]
    reading = by_title["Reading for ML class"]
    assert stats.task_type == "problem_set"
    assert stats.estimated_minutes == 300
    assert ai.task_type == "coding_project"
    assert ai.estimated_minutes == 600
    assert [s.title for s in ai.subtasks] == ["Frontend", "Backend", "Evaluation", "Writeup"]
    assert reading.task_type == "reading"
    assert reading.estimated_minutes == 120

from datetime import datetime
from app.agents.fallback_parser import parse_fixed_events


def test_parse_absolute_date_fixed_event_from_calendar_import():
    events, assumptions = parse_fixed_events("2026-05-04 10:10-11:25 IEOR class", date(2026, 5, 3))
    assert len(events) == 1
    assert events[0].title == "IEOR class"
    assert events[0].start == datetime(2026, 5, 4, 10, 10)
    assert events[0].end == datetime(2026, 5, 4, 11, 25)
