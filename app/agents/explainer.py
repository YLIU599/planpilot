from __future__ import annotations

from collections import defaultdict

from app.schemas import ScheduleResponse


def build_explanation(resp: ScheduleResponse) -> dict:
    by_day = defaultdict(list)
    for block in resp.schedule:
        by_day[block.start.date().isoformat()].append(block)

    day_summaries = []
    for day in sorted(by_day):
        blocks = by_day[day]
        minutes = sum(b.minutes for b in blocks)
        titles = ", ".join(dict.fromkeys(b.task_title for b in blocks))
        day_summaries.append(f"{day}: {minutes // 60}h {minutes % 60}m scheduled across {len(blocks)} block(s): {titles}.")

    rationale = [
        "Hard constraints are checked first: fixed events, availability windows, deadlines, and daily workload limits.",
        "Deep-work tasks such as coding projects and problem sets are assigned longer blocks when possible.",
        "Urgent and high-priority tasks receive higher scheduling priority, but the validator prevents calendar conflicts.",
    ]
    if resp.unscheduled:
        rationale.append("Some tasks could not be fully scheduled; the risk panel lists the remaining work and reason.")

    return {
        "day_summaries": day_summaries,
        "rationale": rationale,
        "risk_warnings": resp.risk_warnings,
    }
