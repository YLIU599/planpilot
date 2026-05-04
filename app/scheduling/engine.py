from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.schemas import (
    AvailabilityWindow,
    ScheduleBlock,
    ScheduleRequest,
    ScheduleResponse,
    Subtask,
    Task,
    TaskType,
    UnscheduledWork,
)
from app.scheduling.scoring import compute_objective_score, slot_fit_score, task_priority_score
from app.scheduling.time_utils import DAY_TO_INDEX, combine_day_time, iter_dates, minutes_between, subtract_many
from app.scheduling.validator import validate_schedule


@dataclass
class CandidateInterval:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return minutes_between(self.start, self.end)


@dataclass
class WorkBlock:
    task: Task
    minutes: int
    sequence: int
    display_title: str
    stage_title: str | None = None
    stage_index: int | None = None
    stage_count: int | None = None
    stage_part_index: int | None = None
    stage_part_count: int | None = None


def _default_availability() -> list[AvailabilityWindow]:
    from datetime import time
    return [
        AvailabilityWindow(day="Mon", start=time(19, 0), end=time(23, 0)),
        AvailabilityWindow(day="Tue", start=time(19, 0), end=time(23, 0)),
        AvailabilityWindow(day="Wed", start=time(19, 0), end=time(23, 0)),
        AvailabilityWindow(day="Thu", start=time(19, 0), end=time(23, 0)),
        AvailabilityWindow(day="Fri", start=time(16, 0), end=time(21, 0)),
        AvailabilityWindow(day="Sat", start=time(13, 0), end=time(18, 0)),
        AvailabilityWindow(day="Sun", start=time(13, 0), end=time(18, 0)),
    ]


def build_available_intervals(req: ScheduleRequest) -> list[CandidateInterval]:
    start_date = req.current_date or date.today()
    availability = req.availability_windows or _default_availability()
    intervals: list[tuple[datetime, datetime]] = []

    for d in iter_dates(start_date, req.horizon_days):
        day_name = [name for name, idx in DAY_TO_INDEX.items() if idx == d.weekday()][0]
        for window in availability:
            if window.day != day_name:
                continue
            start = combine_day_time(d, window.start)
            end = combine_day_time(d, window.end)
            if req.preferences.hard_stop_time and end.time() > req.preferences.hard_stop_time:
                end = combine_day_time(d, req.preferences.hard_stop_time)
            if end > start:
                intervals.append((start, end))

    blockers = [(ev.start, ev.end) for ev in req.fixed_events]
    free = subtract_many(intervals, blockers)
    return [CandidateInterval(s, e) for s, e in sorted(free, key=lambda x: x[0]) if e > s]


def _split_minutes(total: int, min_block: int, max_block: int) -> list[int]:
    remaining = total
    blocks: list[int] = []
    while remaining > 0:
        if remaining <= max_block:
            minutes = remaining
        else:
            minutes = max_block
        if 0 < remaining - minutes < min_block:
            minutes = max(min_block, remaining // 2)
            minutes = (minutes // 30) * 30
        minutes = max(30, min(minutes, remaining))
        if minutes % 30:
            minutes = ((minutes + 29) // 30) * 30
            minutes = min(minutes, remaining)
        blocks.append(minutes)
        remaining -= minutes
    return blocks


def make_work_blocks(task: Task) -> list[WorkBlock]:
    remaining = task.remaining_minutes
    if remaining <= 0:
        return []

    if not task.splittable:
        return [WorkBlock(task=task, minutes=remaining, sequence=1, display_title=task.title)]

    blocks: list[WorkBlock] = []
    seq = 1

    # If the parser decomposed a project into ordered subtasks, make the schedule show
    # those steps instead of opaque "part 1 / part 2" labels. This is the main v2
    # improvement: the optimizer still controls placement, but the agent/parser gives
    # the scheduler meaningful work units and dependencies.
    if task.subtasks:
        for stage_idx, sub in enumerate(task.subtasks, start=1):
            stage_minutes = sub.estimated_minutes
            # If progress was recorded against the parent task, subtract it from the
            # earliest stages first. This is simple but deterministic and keeps the
            # replanning behavior understandable.
            completed_left = max(0, task.completed_minutes - sum(s.estimated_minutes for s in task.subtasks[:stage_idx - 1]))
            if completed_left >= stage_minutes:
                continue
            stage_remaining = stage_minutes - max(0, completed_left)
            stage_parts = _split_minutes(stage_remaining, task.min_block_minutes, task.max_block_minutes)
            for part_idx, part_minutes in enumerate(stage_parts, start=1):
                display = f"{task.title} — {sub.title}"
                blocks.append(WorkBlock(
                    task=task,
                    minutes=part_minutes,
                    sequence=seq,
                    display_title=display,
                    stage_title=sub.title,
                    stage_index=stage_idx,
                    stage_count=len(task.subtasks),
                    stage_part_index=part_idx,
                    stage_part_count=len(stage_parts),
                ))
                seq += 1
        return blocks

    for minutes in _split_minutes(remaining, task.min_block_minutes, task.max_block_minutes):
        blocks.append(WorkBlock(task=task, minutes=minutes, sequence=seq, display_title=task.title))
        seq += 1
    return blocks


def _task_order(tasks: list[Task], strategy: str, now: datetime) -> list[Task]:
    if strategy == "earliest_deadline":
        return sorted(tasks, key=lambda t: (t.deadline, -t.remaining_minutes))
    return sorted(tasks, key=lambda t: (-task_priority_score(t, now), t.deadline))


def _trim_interval_to_not_before(interval: CandidateInterval, not_before: datetime | None) -> CandidateInterval | None:
    if not_before is None:
        return interval
    # If this interval ends before the previous ordered block finishes, it cannot
    # host the next block. v2 incorrectly returned the raw interval here, which
    # allowed later project stages such as Slides to appear before EDA.
    if interval.end <= not_before:
        return None
    start = max(interval.start, not_before)
    if start >= interval.end:
        return None
    return CandidateInterval(start=start, end=interval.end)


def _find_best_interval(
    intervals: list[CandidateInterval],
    block: WorkBlock,
    req: ScheduleRequest,
    strategy: str,
    not_before: datetime | None = None,
) -> tuple[int, datetime] | None:
    best: tuple[int, datetime] | None = None
    best_score = -10_000.0
    task = block.task
    horizon_start = datetime.combine(req.current_date or date.today(), datetime.min.time())

    for idx, raw_interval in enumerate(intervals):
        interval = _trim_interval_to_not_before(raw_interval, not_before)
        if interval is None or interval.minutes < block.minutes:
            continue
        candidate_start = interval.start
        candidate_end = candidate_start + timedelta(minutes=block.minutes)
        if candidate_end > task.deadline:
            continue

        score = 0.0
        hours_from_start = max(0.0, (candidate_start - horizon_start).total_seconds() / 3600)
        if strategy == "earliest_deadline":
            score -= hours_from_start
        elif strategy == "naive_equal_split":
            days_before_deadline = max(1, (task.deadline.date() - candidate_start.date()).days)
            score += days_before_deadline * 0.2
            score -= hours_from_start * 0.02
        else:
            score += slot_fit_score(task, candidate_start, req.preferences)
            buffer_minutes = int((task.deadline - candidate_end).total_seconds() // 60)
            if buffer_minutes >= req.preferences.buffer_before_deadline_minutes:
                score += 2
            else:
                score -= 5
            # Ordered project stages need stronger earlier-placement pressure than
            # ordinary tasks. This prevents the first stage from being delayed until
            # a preferred evening slot when doing so would compress all downstream
            # stages near the deadline. Personal preferences still matter, but only
            # after dependency feasibility.
            if block.stage_index:
                score -= hours_from_start * 0.16
                score += max(0, 6 - block.stage_index) * 0.15
            else:
                # If a task is due soon, do not let a soft evening preference delay
                # it unnecessarily. This makes the plan feel more human: urgent
                # homework should start earlier even if afternoon slots are less ideal.
                hours_until_deadline = max(1.0, (task.deadline - horizon_start).total_seconds() / 3600)
                early_pressure = 0.14 if hours_until_deadline <= 96 else 0.035
                score -= hours_from_start * early_pressure
            score -= idx * 0.01
        if score > best_score:
            best_score = score
            best = (idx, candidate_start)
    return best


def _place_block(intervals: list[CandidateInterval], idx: int, start: datetime, minutes: int) -> tuple[datetime, datetime]:
    interval = intervals[idx]
    end = start + timedelta(minutes=minutes)
    new_intervals: list[CandidateInterval] = []
    if interval.start < start:
        new_intervals.append(CandidateInterval(interval.start, start))
    if end < interval.end:
        new_intervals.append(CandidateInterval(end, interval.end))
    intervals.pop(idx)
    for ni in reversed(new_intervals):
        intervals.insert(idx, ni)
    intervals.sort(key=lambda x: x.start)
    return start, end


def _block_note(wb: WorkBlock) -> str:
    note_parts: list[str] = []
    if wb.task.task_type in {TaskType.coding_project, TaskType.problem_set}:
        note_parts.append("deep-work block")
    if wb.stage_index and wb.stage_count:
        note_parts.append(f"stage {wb.stage_index}/{wb.stage_count}")
        if wb.stage_part_count and wb.stage_part_count > 1:
            note_parts.append(f"block {wb.stage_part_index}/{wb.stage_part_count}")
    elif wb.sequence > 1:
        note_parts.append(f"part {wb.sequence}")
    if wb.stage_title and wb.stage_title.lower() in {"debug / buffer", "final review"}:
        note_parts.append("buffer / review")
    return ", ".join(note_parts)


def _validation_summary(validation) -> list[str]:
    metrics = validation.metrics
    lines = []
    lines.append("✅ No calendar conflicts" if metrics.get("calendar_conflicts", 0) == 0 else f"❌ {metrics['calendar_conflicts']} calendar conflict(s)")
    lines.append("✅ No task overlaps" if metrics.get("task_overlaps", 0) == 0 else f"❌ {metrics['task_overlaps']} task overlap(s)")
    lines.append("✅ All scheduled blocks meet deadlines" if metrics.get("deadline_violations", 0) == 0 else f"❌ {metrics['deadline_violations']} deadline violation(s)")
    lines.append("✅ Project stages respect dependency order" if metrics.get("dependency_violations", 0) == 0 else f"❌ {metrics['dependency_violations']} project dependency violation(s)")
    lines.append("✅ Daily workload limit respected" if metrics.get("daily_capacity_violations", 0) == 0 else f"⚠️ {metrics['daily_capacity_violations']} overloaded day(s)")
    if metrics.get("unscheduled_minutes", 0):
        lines.append(f"⚠️ {metrics['unscheduled_minutes']} minute(s) remain unscheduled")
    else:
        lines.append("✅ All required work is scheduled")
    return lines


def _day_summaries(blocks: list[ScheduleBlock]) -> list[str]:
    by_day: dict[str, list[ScheduleBlock]] = {}
    for b in blocks:
        by_day.setdefault(b.start.date().isoformat(), []).append(b)
    out = []
    for day in sorted(by_day):
        items = by_day[day]
        minutes = sum(b.minutes for b in items)
        titles = ", ".join(dict.fromkeys(b.task_title for b in items))
        out.append(f"{day}: {minutes // 60}h {minutes % 60}m across {len(items)} block(s): {titles}.")
    return out


def _rationale(req: ScheduleRequest, blocks: list[ScheduleBlock], unscheduled: list[UnscheduledWork]) -> list[str]:
    rationale = [
        "The scheduler first removes fixed calendar events from the user's available study windows.",
        "Hard constraints are handled by the scheduling engine: availability, fixed events, deadlines, minimum block sizes, and daily workload limits.",
    ]
    if any(t.subtasks for t in req.tasks):
        rationale.append("Project-style tasks are decomposed into ordered stages, so work such as EDA, modeling, writeup, and slides appears in dependency order.")
    if req.preferences.prefer_evening_focus:
        rationale.append("Evening focus preference is treated as a soft preference, so deep-work blocks are placed after dinner when feasible.")
    if any(b.task_type in {TaskType.coding_project, TaskType.problem_set} for b in blocks):
        rationale.append("Coding projects and problem sets are assigned longer deep-work blocks instead of many short fragments.")
    if req.preferences.prefer_homework_after_class:
        rationale.append("Homework-after-class preference is considered as a soft priority, but deadlines and feasibility still dominate.")
    if getattr(req.preferences, "work_style", "balanced") == "batch":
        rationale.append("Work-style preference is set to batch mode, so the scheduler tries to finish one task before switching when constraints allow it.")
    elif getattr(req.preferences, "work_style", "balanced") == "rotate":
        rationale.append("Work-style preference is set to rotate mode, so the scheduler tries to mix topics for variety while preserving project dependencies.")
    else:
        rationale.append("Work-style preference is balanced, so the scheduler keeps deep-work blocks coherent without forcing every task to be completed in one sitting.")
    if unscheduled:
        rationale.append("Some work could not fit under the current constraints; the risk panel lists the unscheduled amount and why.")
    return rationale




def _order_work_blocks(blocks: list[WorkBlock], ordered_tasks: list[Task], req: ScheduleRequest, now: datetime) -> list[WorkBlock]:
    """Order schedulable work units before placement.

    Hard feasibility is handled later by slot search and the validator. This
    ordering only reflects the user's work-style preference:
    - batch: finish the most urgent/high-priority task before switching;
    - rotate: cycle through task blocks for variety;
    - balanced: default PlanPilot behavior, which tends to keep deep work
      coherent while still considering deadlines and priorities.
    """
    task_rank = {task.id: idx for idx, task in enumerate(ordered_tasks)}
    style = getattr(req.preferences, "work_style", "balanced")
    if req.strategy == "earliest_deadline":
        return sorted(blocks, key=lambda b: (b.task.deadline, task_rank.get(b.task.id, 999), b.sequence))
    if req.strategy == "naive_equal_split":
        return sorted(blocks, key=lambda b: (b.sequence, b.task.deadline, task_rank.get(b.task.id, 999)))
    if style == "batch":
        return sorted(blocks, key=lambda b: (task_rank.get(b.task.id, 999), b.sequence, b.task.deadline))
    if style == "rotate":
        return sorted(blocks, key=lambda b: (b.sequence, b.task.deadline, -task_priority_score(b.task, now), task_rank.get(b.task.id, 999)))
    return sorted(blocks, key=lambda b: (-task_priority_score(b.task, now), b.task.deadline, task_rank.get(b.task.id, 999), b.sequence))

def generate_schedule(req: ScheduleRequest) -> ScheduleResponse:
    now = datetime.combine(req.current_date or date.today(), datetime.min.time())
    intervals = build_available_intervals(req)
    ordered_tasks = _task_order([t for t in req.tasks if t.remaining_minutes > 0], req.strategy, now)

    all_work_blocks: list[WorkBlock] = []
    for task in ordered_tasks:
        all_work_blocks.extend(make_work_blocks(task))

    all_work_blocks = _order_work_blocks(all_work_blocks, ordered_tasks, req, now)

    schedule: list[ScheduleBlock] = []
    unscheduled_by_task: dict[str, int] = {t.id: 0 for t in ordered_tasks}
    unscheduled_reasons: dict[str, str] = {}
    last_end_by_task: dict[str, datetime] = {}

    for wb in all_work_blocks:
        not_before = last_end_by_task.get(wb.task.id)
        match = _find_best_interval(intervals, wb, req, req.strategy, not_before=not_before)
        if match is None:
            unscheduled_by_task[wb.task.id] = unscheduled_by_task.get(wb.task.id, 0) + wb.minutes
            unscheduled_reasons[wb.task.id] = "No available slot before deadline that satisfies duration, order, and calendar constraints."
            continue
        idx, start_at = match
        start, end = _place_block(intervals, idx, start_at, wb.minutes)
        last_end_by_task[wb.task.id] = end
        schedule.append(ScheduleBlock(
            task_id=wb.task.id,
            task_title=wb.display_title,
            task_type=wb.task.task_type,
            start=start,
            end=end,
            minutes=wb.minutes,
            priority=wb.task.priority,
            note=_block_note(wb),
        ))

    unscheduled: list[UnscheduledWork] = []
    task_by_id = {t.id: t for t in ordered_tasks}
    for task_id, minutes in unscheduled_by_task.items():
        if minutes > 0:
            task = task_by_id[task_id]
            unscheduled.append(UnscheduledWork(
                task_id=task_id,
                task_title=task.title,
                remaining_minutes=minutes,
                reason=unscheduled_reasons.get(task_id, "Not enough feasible time blocks."),
            ))

    schedule.sort(key=lambda b: b.start)
    validation = validate_schedule(schedule, req.fixed_events, req.tasks, req.preferences, unscheduled)
    objective_score = compute_objective_score(validation.metrics)

    risk_warnings: list[str] = []
    if unscheduled:
        risk_warnings.append("Some work could not be scheduled before the deadline under current constraints.")
    if validation.metrics.get("daily_capacity_violations", 0):
        risk_warnings.append("At least one day exceeds the user's maximum daily workload.")
    if validation.metrics.get("deadline_violations", 0):
        risk_warnings.append("At least one task block falls after its deadline.")
    # Warn when a large project ends close to deadline.
    for task in req.tasks:
        task_blocks = [b for b in schedule if b.task_id == task.id]
        if task_blocks:
            final_end = max(b.end for b in task_blocks)
            buffer_minutes = int((task.deadline - final_end).total_seconds() // 60)
            if task.estimated_minutes >= 6 * 60 and 0 <= buffer_minutes < req.preferences.buffer_before_deadline_minutes * 2:
                risk_warnings.append(f"{task.title} finishes close to its deadline; consider adding extra buffer if the estimate is uncertain.")

    summary = summarize_schedule(schedule, unscheduled, validation.valid, objective_score)
    return ScheduleResponse(
        schedule=schedule,
        unscheduled=unscheduled,
        validation=validation,
        summary=summary,
        assumptions=[],
        risk_warnings=risk_warnings,
        rationale=_rationale(req, schedule, unscheduled),
        day_summaries=_day_summaries(schedule),
        validation_summary=_validation_summary(validation),
        objective_score=objective_score,
        strategy=req.strategy,
    )


def summarize_schedule(blocks: list[ScheduleBlock], unscheduled: list[UnscheduledWork], valid: bool, score: float) -> str:
    if not blocks and unscheduled:
        return "No feasible schedule could be generated under the current constraints."
    day_count = len({b.start.date() for b in blocks})
    minutes = sum(b.minutes for b in blocks)
    if unscheduled:
        unscheduled_minutes = sum(u.remaining_minutes for u in unscheduled)
        return (
            f"Generated a schedule with warnings: {minutes // 60:.0f}h {minutes % 60}m scheduled "
            f"across {day_count} day(s), with {unscheduled_minutes // 60:.0f}h {unscheduled_minutes % 60}m still unscheduled. "
            f"Objective score: {score}."
        )
    status = "valid" if valid else "with issues"
    return f"Generated a {status} schedule with {minutes // 60:.0f}h {minutes % 60}m across {day_count} day(s). Objective score: {score}."
