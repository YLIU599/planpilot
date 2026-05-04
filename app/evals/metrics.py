from __future__ import annotations

from statistics import mean

from app.schemas import EvaluationResult, EvaluationSummary, ScheduleResponse


def response_to_metrics(resp: ScheduleResponse) -> dict:
    metrics = dict(resp.validation.metrics)
    metrics["objective_score"] = resp.objective_score
    metrics["valid"] = resp.validation.valid
    metrics["scheduled_blocks"] = len(resp.schedule)
    metrics["unscheduled_tasks"] = len(resp.unscheduled)
    return metrics


def aggregate_results(results: list[EvaluationResult]) -> EvaluationSummary:
    if not results:
        return EvaluationSummary(results=[], aggregate={})
    by_strategy: dict[str, list[EvaluationResult]] = {}
    for r in results:
        by_strategy.setdefault(r.strategy, []).append(r)
    aggregate = {}
    for strategy, rows in by_strategy.items():
        aggregate[strategy] = {
            "cases": len(rows),
            "valid_rate": sum(1 for r in rows if r.valid) / len(rows),
            "avg_objective_score": round(mean(r.objective_score for r in rows), 2),
            "total_calendar_conflicts": sum(r.metrics.get("calendar_conflicts", 0) for r in rows),
            "total_deadline_violations": sum(r.metrics.get("deadline_violations", 0) for r in rows),
            "total_unscheduled_minutes": sum(r.metrics.get("unscheduled_minutes", 0) for r in rows),
        }
    return EvaluationSummary(results=results, aggregate=aggregate)
