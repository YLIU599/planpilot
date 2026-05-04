from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from app.schemas import AvailabilityWindow, FixedEvent, Priority, Subtask, Task, TaskType, UserPreferences
from app.scheduling.scoring import type_defaults

DAY_PATTERN = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?"
DAY_ALIASES = {
    "monday": "Mon", "mon": "Mon",
    "tuesday": "Tue", "tue": "Tue",
    "wednesday": "Wed", "wed": "Wed",
    "thursday": "Thu", "thu": "Thu",
    "friday": "Fri", "fri": "Fri",
    "saturday": "Sat", "sat": "Sat",
    "sunday": "Sun", "sun": "Sun",
}


def parse_time_token(raw: str) -> time | None:
    raw = raw.strip().lower().replace(" ", "")
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?(am|pm)?$", raw)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    suffix = m.group(3)
    if suffix == "pm" and hour != 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None



def parse_time_range_tokens(start_raw: str, end_raw: str) -> tuple[time | None, time | None]:
    """Parse a time range. If only the end has am/pm, infer the same suffix for the start.

    Example: 7-11pm -> 19:00-23:00.
    """
    start_clean = start_raw.strip().lower().replace(" ", "")
    end_clean = end_raw.strip().lower().replace(" ", "")
    end_suffix = "pm" if end_clean.endswith("pm") else "am" if end_clean.endswith("am") else ""
    if end_suffix and not (start_clean.endswith("am") or start_clean.endswith("pm")):
        start_clean = start_clean + end_suffix
    return parse_time_token(start_clean), parse_time_token(end_clean)

def _canonical_day(raw: str) -> str | None:
    return DAY_ALIASES.get(raw.strip().lower())


def _next_weekday(base: date, day_name: str) -> date:
    idx = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}[day_name]
    delta = (idx - base.weekday()) % 7
    if delta == 0:
        delta = 7
    return base + timedelta(days=delta)


def parse_availability(text: str) -> tuple[list[AvailabilityWindow], UserPreferences, list[str]]:
    assumptions: list[str] = []
    windows: list[AvailabilityWindow] = []
    prefs = UserPreferences()
    lower = text.lower()

    if "evening" in lower or "after dinner" in lower or re.search(r"7\s*(?:pm)?\s*[-–]", lower):
        prefs.prefer_evening_focus = True
    if "morning" in lower:
        prefs.prefer_morning_focus = True

    # Work style is a soft scheduling preference. The deterministic scheduler
    # still respects deadlines and dependencies first, but this changes how it
    # orders otherwise feasible blocks.
    if re.search(r"\b(batch|one task at a time|finish one|same task|single topic|集中|一次性|同一个任务)\b", lower):
        prefs.work_style = "batch"
    if re.search(r"\b(rotate|rotation|switch|variety|different topics|mix topics|change topics|换脑子|轮换|交替|不同topic)\b", lower):
        prefs.work_style = "rotate"
    stop_match = re.search(r"(?:after|past)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", lower)
    if "not" in lower and stop_match:
        parsed = parse_time_token(stop_match.group(1))
        if parsed:
            prefs.hard_stop_time = parsed
    max_match = re.search(r"(?:max|at most|no more than)\s+(\d+(?:\.\d+)?)\s*(?:hours|hrs|h)", lower)
    if max_match:
        prefs.max_daily_work_minutes = int(float(max_match.group(1)) * 60)

    # Handles both "weekdays 7-11pm" and "7-11pm on weekdays".
    weekday_patterns = [
        r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–to]+\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)(?:\s+on)?\s+weekday[s]?",
        r"weekday[s]?[^.\n;]*?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–to]+\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
    ]
    for pat in weekday_patterns:
        weekday_match = re.search(pat, lower)
        if weekday_match:
            st, en = parse_time_range_tokens(weekday_match.group(1), weekday_match.group(2))
            if st and en:
                for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
                    windows.append(AvailabilityWindow(day=d, start=st, end=en))
                break

    weekend_patterns = [
        r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–to]+\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)(?:\s+on)?\s+weekend[s]?",
        r"weekend[s]?[^.\n;]*?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–to]+\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
    ]
    for pat in weekend_patterns:
        weekend_match = re.search(pat, lower)
        if weekend_match:
            st, en = parse_time_range_tokens(weekend_match.group(1), weekend_match.group(2))
            if st and en:
                for d in ["Sat", "Sun"]:
                    windows.append(AvailabilityWindow(day=d, start=st, end=en))
                break

    # Explicit day ranges: Mon 18:00-21:00
    for match in re.finditer(r"\b(mon|tue|wed|thu|fri|sat|sun)(?:day)?\b[^\d]*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–to]+\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", lower):
        day = _canonical_day(match.group(1))
        st, en = parse_time_range_tokens(match.group(2), match.group(3))
        if day and st and en:
            windows.append(AvailabilityWindow(day=day, start=st, end=en))

    # Deduplicate.
    seen = set()
    deduped: list[AvailabilityWindow] = []
    for w in windows:
        key = (w.day, w.start, w.end)
        if key not in seen:
            deduped.append(w)
            seen.add(key)
    if not deduped:
        assumptions.append("No availability windows were parsed; default evening/weekend availability will be used by the scheduler.")
    prefs.notes = text.strip()
    return deduped, prefs, assumptions


def parse_fixed_events(text: str, current_date: date) -> tuple[list[FixedEvent], list[str]]:
    events: list[FixedEvent] = []
    assumptions: list[str] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        absolute_match = re.search(
            r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\s+"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–to]+\s*"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            lower,
        )
        if absolute_match:
            st = parse_time_token(absolute_match.group(4))
            en = parse_time_token(absolute_match.group(5))
            if st and en:
                event_day = date(int(absolute_match.group(1)), int(absolute_match.group(2)), int(absolute_match.group(3)))
                title = re.sub(
                    r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+"
                    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–to]+\s*"
                    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?",
                    "",
                    line,
                    flags=re.I,
                ).strip(" :-") or "Fixed event"
                events.append(FixedEvent(title=title, start=datetime.combine(event_day, st), end=datetime.combine(event_day, en)))
                continue
        day_match = re.search(r"\b(mon|tue|wed|thu|fri|sat|sun)(?:day)?(?:\s*/\s*(mon|tue|wed|thu|fri|sat|sun)(?:day)?)?\b", lower)
        time_match = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–to]+\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", lower)
        if not day_match or not time_match:
            continue
        days = [day_match.group(1)]
        if day_match.group(2):
            days.append(day_match.group(2))
        st = parse_time_token(time_match.group(1))
        en = parse_time_token(time_match.group(2))
        if not st or not en:
            continue
        title = re.sub(r"\b(mon|tue|wed|thu|fri|sat|sun)(?:day)?(?:\s*/\s*(mon|tue|wed|thu|fri|sat|sun)(?:day)?)?\b", "", line, flags=re.I)
        title = re.sub(r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–to]+\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?", "", title, flags=re.I).strip(" :-")
        title = title or "Fixed event"
        for d_raw in days:
            day = _canonical_day(d_raw)
            if not day:
                continue
            event_day = _next_weekday(current_date - timedelta(days=1), day)
            events.append(FixedEvent(title=title, start=datetime.combine(event_day, st), end=datetime.combine(event_day, en)))
    if text.strip() and not events:
        assumptions.append("Fixed events text was provided, but no event could be parsed. Use explicit day/time ranges for best results.")
    return events, assumptions


def infer_task_type(title: str, notes: str = "") -> TaskType:
    s = f"{title} {notes}".lower()
    if any(k in s for k in ["read", "reading", "paper"]):
        return TaskType.reading
    if any(k in s for k in ["hw", "homework", "problem", "pset", "assignment"]):
        return TaskType.problem_set
    if any(k in s for k in ["code", "coding", "model", "eda", "project", "debug"]):
        return TaskType.coding_project
    if any(k in s for k in ["write", "essay", "report", "draft"]):
        return TaskType.writing
    if any(k in s for k in ["exam", "midterm", "final", "quiz"]):
        return TaskType.exam_prep
    if any(k in s for k in ["slide", "presentation", "present"]):
        return TaskType.presentation
    if any(k in s for k in ["meeting", "group"]):
        return TaskType.group_project
    return TaskType.other


def parse_deadline(text: str, current_date: date) -> datetime | None:
    lower = text.lower()
    # ISO-like date
    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", lower)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 23, 59)
    # Month day like May 6
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})\b", lower)
    if m:
        month = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"].index(m.group(1)[:3]) + 1
        year = current_date.year
        d = date(year, month, int(m.group(2)))
        if d < current_date:
            d = date(year + 1, month, int(m.group(2)))
        return datetime.combine(d, time(23, 59))
    # due Sunday / next Wednesday
    m = re.search(r"(?:due\s+)?(next\s+)?(mon|tue|wed|thu|fri|sat|sun)(?:day)?", lower)
    if m:
        day = _canonical_day(m.group(2))
        if day:
            base = current_date if m.group(1) else current_date - timedelta(days=1)
            return datetime.combine(_next_weekday(base, day), time(23, 59))
    # in N days
    m = re.search(r"in\s+(\d+)\s+days?", lower)
    if m:
        return datetime.combine(current_date + timedelta(days=int(m.group(1))), time(23, 59))
    return None




def _clean_subtask_name(raw: str) -> str:
    name = raw.strip().strip(" .,-;:")
    name = re.sub(r"\b(and|then|also|maybe)\b", "", name, flags=re.I).strip(" .,-;:")
    aliases = {
        "eda": "EDA",
        "exploratory data analysis": "EDA",
        "model": "Modeling",
        "models": "Modeling",
        "modeling": "Modeling",
        "modelling": "Modeling",
        "train models": "Modeling",
        "training": "Modeling",
        "writeup": "Writeup",
        "write-up": "Writeup",
        "report": "Writeup",
        "writing": "Writeup",
        "slides": "Slides",
        "slide": "Slides",
        "presentation": "Slides",
        "final review": "Final Review",
        "debug": "Debug / Buffer",
        "debugging": "Debug / Buffer",
    }
    return aliases.get(name.lower(), name[:1].upper() + name[1:])


def _extract_subtask_names(line: str) -> list[str]:
    lower = line.lower()
    match = re.search(r"(?:needs?|requires?|including|with)\s+([^.;\n]+)", line, flags=re.I)
    if not match:
        return []
    raw = match.group(1)
    # Stop before deadline/estimate fragments if the sentence is messy.
    raw = re.split(r"\b(?:due|estimated|estimate|takes?)\b", raw, flags=re.I)[0]
    pieces = re.split(r",|/|→|->|;|\band\b", raw)
    names = []
    seen = set()
    for piece in pieces:
        name = _clean_subtask_name(piece)
        if not name or len(name) < 2:
            continue
        key = name.lower()
        if key not in seen:
            names.append(name)
            seen.add(key)
    # Only treat as a decomposition if there are at least two concrete steps.
    return names if len(names) >= 2 else []


def _allocate_subtask_minutes(names: list[str], total_minutes: int) -> list[int]:
    if not names:
        return []
    weights = []
    for name in names:
        n = name.lower()
        if "eda" in n:
            weights.append(0.20)
        elif "model" in n or "debug" in n:
            weights.append(0.35)
        elif "write" in n or "report" in n:
            weights.append(0.30)
        elif "slide" in n or "presentation" in n or "review" in n:
            weights.append(0.15)
        else:
            weights.append(1.0)
    total_w = sum(weights) or len(names)
    raw_minutes = [max(30, int(round(total_minutes * w / total_w / 30) * 30)) for w in weights]
    diff = total_minutes - sum(raw_minutes)
    # Adjust in 30-minute increments while preserving positive durations.
    i = 0
    while diff != 0 and raw_minutes:
        idx = i % len(raw_minutes)
        if diff > 0:
            raw_minutes[idx] += 30
            diff -= 30
        elif raw_minutes[idx] > 30:
            raw_minutes[idx] -= 30
            diff += 30
        i += 1
        if i > 100:
            break
    # Final correction if total is not a multiple of 30.
    if sum(raw_minutes) != total_minutes:
        raw_minutes[-1] += total_minutes - sum(raw_minutes)
        raw_minutes[-1] = max(30, raw_minutes[-1])
    return raw_minutes



def _count_from_patterns(text: str, patterns: list[str]) -> int | None:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return int(m.group(1))
    return None




def _meaningful_tokens(text: str) -> set[str]:
    stop = {
        "the", "a", "an", "and", "or", "of", "for", "to", "due", "next", "has", "have",
        "requires", "require", "needs", "need", "is", "about", "estimated", "estimate", "class",
        "hw", "homework", "project", "assignment", "task", "work"
    }
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_+.-]*", text.lower())
    aliases = {"stats": "stats", "stat": "stats", "ai": "ai", "ml": "ml", "reading": "reading", "read": "reading"}
    return {aliases.get(t, t) for t in tokens if len(t) > 1 and t not in stop}


def _scoped_assignment_details(line: str, assignment_details: str) -> str:
    """Return only the assignment-detail sentences that appear relevant to this task line.

    Details refine the estimate for the matching task; they must not override
    every task globally. For example, "Reading is about 25 pages" should not
    turn an AI project into a reading task.
    """
    if not assignment_details.strip():
        return ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", assignment_details.strip()) if s.strip()]
    line_tokens = _meaningful_tokens(line)
    selected: list[str] = []
    line_lower = line.lower()
    for sent in sentences:
        sent_tokens = _meaningful_tokens(sent)
        overlap = line_tokens & sent_tokens
        sent_lower = sent.lower()
        if overlap:
            selected.append(sent)
            continue
        if "read" in line_lower and re.search(r"\b(reading|pages?)\b", sent_lower):
            selected.append(sent)
            continue
        if re.search(r"\b(hw|homework|problem set|problem)\b", line_lower) and re.search(r"\b(problems?|questions?|exercises?)\b", sent_lower):
            selected.append(sent)
            continue
        if "project" in line_lower and re.search(r"\b(frontend|backend|api|evaluation|script|report|deliverable|rubric|stages?)\b", sent_lower):
            selected.append(sent)
            continue
    return " ".join(selected)


def _round_up_to_slot(minutes: int, slot: int = 30) -> int:
    return max(slot, ((minutes + slot - 1) // slot) * slot)

def _estimate_effort_minutes(task_type: TaskType, line: str, subtask_names: list[str], assignment_details: str = "") -> tuple[int, str, str]:
    """Estimate effort when the user did not provide hours.

    The goal is not perfect prediction; it is a transparent fallback that keeps
    the scheduler usable while marking uncertainty for the user. Assignment
    details are expected to be scoped to this task before calling this function.
    """
    line_lower = line.lower()
    details_lower = assignment_details.lower()
    text = f"{line}\n{assignment_details}".lower()
    confidence = "low"
    rationale = "No explicit effort estimate was provided; used task-type defaults."

    pages = _count_from_patterns(text, [r"(\d+)\s*pages?", r"(\d+)\s*-\s*page"])
    problems = _count_from_patterns(text, [r"(\d+)\s*(?:problems?|questions?|exercises?)"])
    slides = _count_from_patterns(text, [r"(\d+)\s*slides?"])

    if task_type == TaskType.reading:
        if pages:
            minutes = max(60, min(360, _round_up_to_slot(pages * 4)))
            confidence = "medium"
            rationale = f"Estimated from {pages} page(s) at roughly 4 minutes per page, rounded to a schedulable block."
        else:
            minutes = 120
            rationale = "Defaulted reading work to 2 hours because no page count was provided."
    elif task_type == TaskType.problem_set:
        if problems:
            minutes = max(120, min(720, problems * 60))
            confidence = "medium"
            rationale = f"Estimated from {problems} problem(s) at roughly 1 hour per problem."
        else:
            minutes = 300
            rationale = "Defaulted problem-set work to 5 hours because no problem count was provided."
    elif task_type == TaskType.coding_project:
        if subtask_names:
            weights = []
            for name in subtask_names:
                n = name.lower()
                if any(k in n for k in ["frontend", "backend", "api", "model", "evaluation", "eda", "write", "report", "script"]):
                    weights.append(150)
                elif any(k in n for k in ["slides", "review"]):
                    weights.append(90)
                else:
                    weights.append(120)
            minutes = max(360, min(1200, sum(weights)))
            confidence = "medium"
            rationale = f"Estimated from {len(subtask_names)} project stage(s): {', '.join(subtask_names)}."
        else:
            minutes = 600
            rationale = "Defaulted project work to 10 hours because no stages or estimate were provided."
    elif task_type == TaskType.writing:
        if pages:
            minutes = max(180, min(720, pages * 60))
            confidence = "medium"
            rationale = f"Estimated writing effort from {pages} page(s) at roughly 1 hour per page."
        else:
            minutes = 240
            rationale = "Defaulted writing work to 4 hours because no page count was provided."
    elif task_type == TaskType.presentation:
        if slides:
            minutes = max(120, min(480, slides * 20))
            confidence = "medium"
            rationale = f"Estimated from {slides} slide(s) at roughly 20 minutes per slide."
        else:
            minutes = 180
            rationale = "Defaulted presentation work to 3 hours because no slide count was provided."
    elif task_type == TaskType.exam_prep:
        minutes = 480
        rationale = "Defaulted exam-prep work to 8 hours because no target study duration was provided."
    else:
        minutes = 120
        rationale = "Defaulted task to 2 hours because no estimate or known task type was provided."

    if any(k in text for k in ["hard", "difficult", "complex", "final project", "full report", "rubric"]):
        minutes = int(round(minutes * 1.25 / 30) * 30)
        rationale += " Increased estimate because the description suggests higher complexity."
    if any(k in line_lower for k in ["short", "quick", "simple", "brief"]) or (
        task_type in {TaskType.reading, TaskType.writing, TaskType.presentation} and any(k in details_lower for k in ["short", "quick", "simple", "brief"])
    ):
        minutes = max(30, int(round(minutes * 0.75 / 30) * 30))
        rationale += " Reduced estimate because the description suggests a shorter task."

    return max(30, minutes), confidence, rationale

def parse_tasks(text: str, current_date: date, assignment_details: str = "") -> tuple[list[Task], list[str], list[str]]:
    tasks: list[Task] = []
    assumptions: list[str] = []
    questions: list[str] = []
    lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip(" -•\t")]
    if not lines and text.strip():
        # Split on semicolons as fallback.
        lines = [p.strip() for p in re.split(r";|\n", text) if p.strip()]

    for line in lines:
        deadline = parse_deadline(line, current_date)
        if not deadline:
            assumptions.append(f"No deadline parsed for '{line[:40]}...'; defaulted to 7 days from current date.")
            deadline = datetime.combine(current_date + timedelta(days=7), time(23, 59))

        scoped_details = _scoped_assignment_details(line, assignment_details)
        # Infer primarily from the task line. Scoped details may refine ambiguous
        # tasks, but global assignment details must not override every task.
        task_type = infer_task_type(line, scoped_details)
        subtask_names = _extract_subtask_names(line)
        if not subtask_names and scoped_details:
            if any(key in line.lower() for key in ["project", "report", "presentation", "coding", "code"]):
                subtask_names = _extract_subtask_names(scoped_details)

        hours_match = re.search(r"(?:estimated|estimate|takes?|about|~)?\s*(\d+(?:\.\d+)?)\s*(?:hours|hrs|hr|h)\b", line.lower())
        if hours_match:
            minutes = int(float(hours_match.group(1)) * 60)
            estimate_source = "user"
            estimate_confidence = "high"
            estimate_rationale = "User provided an explicit effort estimate."
        else:
            minutes, estimate_confidence, estimate_rationale = _estimate_effort_minutes(task_type, line, subtask_names, scoped_details)
            estimate_source = "system"
            assumptions.append(
                f"Estimated effort for '{line[:40]}...' as {minutes // 60}h {minutes % 60}m "
                f"({estimate_confidence} confidence). {estimate_rationale}"
            )
            if estimate_confidence == "low":
                questions.append(f"Optional: provide a more precise time estimate for '{line[:40]}...' if you know it.")

        default_splittable, default_min, default_max = type_defaults(task_type)
        if "continuous" in line.lower() or "one block" in line.lower() or "cannot split" in line.lower():
            default_splittable = False
        block_match = re.search(r"(\d+(?:\.\d+)?)[- ]?\s*(?:hour|hr|h)[- ]?blocks?", line.lower())
        min_block = int(float(block_match.group(1)) * 60) if block_match else default_min
        priority = Priority.medium
        if "urgent" in line.lower():
            priority = Priority.urgent
        elif "high" in line.lower() or "important" in line.lower():
            priority = Priority.high
        elif "low" in line.lower():
            priority = Priority.low

        title = line
        title = re.sub(r"due\s+(?:on\s+)?20\d{2}[-/]\d{1,2}[-/]\d{1,2}", "", title, flags=re.I)
        title = re.sub(r"due\s+(?:next\s+)?\w+", "", title, flags=re.I)
        title = re.sub(r"estimated\s+\d+(?:\.\d+)?\s*(?:hours|hrs|hr|h)", "", title, flags=re.I)
        title = re.sub(r"\d+(?:\.\d+)?\s*(?:hours|hrs|hr|h)", "", title, flags=re.I)
        title = re.sub(r"needs?\s+.*$", "", title, flags=re.I)
        title = re.sub(r",\s*,+", ",", title)
        title = re.sub(r"\s+,", ",", title)
        title = title.strip(" ,.-")
        title = title or line[:50]

        total_minutes = max(30, minutes)
        subtasks: list[Subtask] = []
        if subtask_names:
            allocations = _allocate_subtask_minutes(subtask_names, total_minutes)
            previous_id: str | None = None
            for name, mins in zip(subtask_names, allocations):
                sub = Subtask(title=name, estimated_minutes=max(30, mins), depends_on=[previous_id] if previous_id else [])
                subtasks.append(sub)
                previous_id = sub.id

        tasks.append(Task(
            title=title,
            deadline=deadline,
            estimated_minutes=total_minutes,
            task_type=task_type,
            priority=priority,
            splittable=default_splittable,
            min_block_minutes=min_block,
            max_block_minutes=max(default_max, min_block),
            subtasks=subtasks,
            notes=line,
            estimate_source=estimate_source,
            estimate_confidence=estimate_confidence,
            estimate_rationale=estimate_rationale,
        ))
    if not tasks:
        questions.append("Please provide at least one task with a deadline. Effort estimates are optional; PlanPilot can infer tentative estimates.")
    return tasks, assumptions, questions

def _parse_duration_text(raw: str) -> int | None:
    raw = raw.lower().strip()
    total = 0
    found = False

    for value, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|hr|h)\b", raw):
        total += int(round(float(value) * 60))
        found = True
    for value, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(minutes?|mins?|min|m)\b", raw):
        total += int(round(float(value)))
        found = True
    if re.search(r"half\s+an?\s+hour", raw):
        total += 30
        found = True
    return total if found and total > 0 else None


def _clean_progress_title(raw: str) -> str:
    title = raw.strip().lower()
    title = re.sub(r"\b(today|tonight|yesterday|this morning|this afternoon|this evening)\b", "", title)
    title = re.sub(r"\b(on|for)\s*$", "", title)
    return title.strip(" .,-;:")


def parse_progress(progress_text: str) -> list[tuple[str, int]]:
    updates: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    text = progress_text.lower()

    patterns = [
        # I only completed 30 min of Stats HW today.
        r"(?:finished|completed|did|worked on)\s+((?:\d+(?:\.\d+)?\s*(?:hours?|hrs?|hr|h|minutes?|mins?|min|m)\b\s*)+|half\s+an?\s+hour)\s+(?:of\s+)?([^.,;\n]+)",
        # I worked on Stats HW for 30 min.
        r"(?:finished|completed|did|worked on)\s+([^.,;\n]+?)\s+for\s+((?:\d+(?:\.\d+)?\s*(?:hours?|hrs?|hr|h|minutes?|mins?|min|m)\b\s*)+|half\s+an?\s+hour)",
        # 30 min of Stats HW
        r"((?:\d+(?:\.\d+)?\s*(?:hours?|hrs?|hr|h|minutes?|mins?|min|m)\b\s*)+|half\s+an?\s+hour)\s+of\s+([^.,;\n]+)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if pattern.startswith(r"(?:finished|completed|did|worked on)\s+([^.,"):
                title_raw, duration_raw = match.group(1), match.group(2)
            else:
                duration_raw, title_raw = match.group(1), match.group(2)
            minutes = _parse_duration_text(duration_raw)
            title = _clean_progress_title(title_raw)
            if not minutes or not title:
                continue
            key = (title, minutes)
            if key not in seen:
                seen.add(key)
                updates.append(key)
    return updates
