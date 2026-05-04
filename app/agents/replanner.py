from __future__ import annotations

from difflib import SequenceMatcher

from app.agents.fallback_parser import parse_progress
from app.schemas import ProgressUpdate, ReplanRequest, ScheduleBlock, ScheduleRequest, Task
from app.scheduling.engine import generate_schedule


def _normalize_title(text: str) -> str:
    text = text.lower().strip()
    replacements = {
        "homework": "hw",
        "assignment": "hw",
        "project work": "project",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def _match_task(task_title: str, tasks: list[Task]) -> Task | None:
    target = _normalize_title(task_title)
    best: tuple[float, Task | None] = (0.0, None)
    second_best = 0.0
    for task in tasks:
        title = _normalize_title(task.title)
        score = SequenceMatcher(None, target, title).ratio()
        if target in title or title in target:
            score += 0.25
        target_tokens = set(target.split())
        title_tokens = set(title.split())
        if target_tokens and title_tokens:
            score += 0.15 * (len(target_tokens & title_tokens) / len(target_tokens | title_tokens))
        # Also match against subtask/stage names.
        for sub in task.subtasks:
            sub_title = _normalize_title(f"{task.title} {sub.title}")
            sub_score = SequenceMatcher(None, target, sub_title).ratio()
            if target in sub_title or sub_title in target:
                sub_score += 0.2
            score = max(score, sub_score)
        if score > best[0]:
            second_best = best[0]
            best = (score, task)
        else:
            second_best = max(second_best, score)
    # Avoid applying progress when the match is weak or nearly tied.
    if best[0] < 0.42:
        return None
    if second_best and best[0] - second_best < 0.05:
        return None
    return best[1]


def _format_minutes(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h 0m"
    return f"{m}m"


def apply_progress_updates(req: ReplanRequest) -> tuple[ScheduleRequest, list[str]]:
    tasks = [task.model_copy(deep=True) for task in req.original_request.tasks]
    updates = list(req.progress_updates)
    messages: list[str] = []

    for title, minutes in parse_progress(req.progress_text):
        updates.append(ProgressUpdate(task_title=title, completed_minutes=minutes))

    for update in updates:
        task = _match_task(update.task_title, tasks)
        if task:
            before = task.completed_minutes
            task.completed_minutes = min(task.estimated_minutes, task.completed_minutes + update.completed_minutes)
            applied = task.completed_minutes - before
            messages.append(
                f"Progress applied: {task.title} now has {_format_minutes(task.completed_minutes)} completed "
                f"and {_format_minutes(task.remaining_minutes)} remaining."
            )
            if applied < update.completed_minutes:
                messages.append(f"Only {_format_minutes(applied)} was applied because the task is now fully complete.")
        else:
            choices = ", ".join(t.title for t in tasks)
            messages.append(
                f"Could not confidently match progress item '{update.task_title}' to a current task. "
                f"Try one of: {choices}."
            )

    return req.original_request.model_copy(update={"tasks": tasks}), messages


def _signature(blocks: list[ScheduleBlock]) -> dict[str, tuple[str, str]]:
    # Include block id and title to avoid collapsing repeated blocks with the same title.
    return {f"{i}:{b.task_title}": (b.start.isoformat(), b.end.isoformat()) for i, b in enumerate(blocks)}


def _build_replan_changes(before: list[ScheduleBlock], after: list[ScheduleBlock], progress_messages: list[str]) -> list[str]:
    changes: list[str] = list(progress_messages)
    before_sig = _signature(before)
    after_sig = _signature(after)
    moved = 0
    added = 0
    removed = 0
    for title, slot in after_sig.items():
        if title not in before_sig:
            added += 1
        elif before_sig[title] != slot:
            moved += 1
    for title in before_sig:
        if title not in after_sig:
            removed += 1
    if moved:
        changes.append(f"{moved} scheduled block(s) moved to preserve deadlines and task order after the progress update.")
    if added:
        changes.append(f"{added} new block(s) were added for remaining work.")
    if removed:
        changes.append(f"{removed} previously scheduled block(s) were removed because that work is now complete or rescheduled.")
    if not changes:
        changes.append("No material schedule changes were needed after the progress update.")
    return changes


def replan(req: ReplanRequest):
    before = generate_schedule(req.original_request)
    has_progress_text = bool(req.progress_text and req.progress_text.strip())
    has_structured_updates = bool(req.progress_updates)

    if not has_progress_text and not has_structured_updates:
        before.replan_changes = [
            "No progress update was provided. Describe what was completed or missed, then click Replan again."
        ]
        return before

    parsed_updates = parse_progress(req.progress_text) if has_progress_text else []
    if has_progress_text and not parsed_updates and not has_structured_updates:
        before.replan_changes = [
            "A progress update was provided, but no task and time amount could be extracted. Try: 'I did 30 min of Stats HW today.'"
        ]
        return before

    updated, progress_messages = apply_progress_updates(req)
    if progress_messages and all(m.startswith("Could not confidently match") for m in progress_messages):
        before.replan_changes = progress_messages
        return before

    after = generate_schedule(updated)
    after.replan_changes = _build_replan_changes(before.schedule, after.schedule, progress_messages)
    return after
