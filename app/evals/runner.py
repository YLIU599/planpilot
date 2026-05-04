from __future__ import annotations

import json
from pathlib import Path

from app.evals.cases import build_eval_cases
from app.evals.metrics import aggregate_results
from app.schemas import EvaluationResult
from app.scheduling.engine import generate_schedule


def run_evaluation():
    results: list[EvaluationResult] = []
    for case_name, req, expected_feasible in build_eval_cases():
        for strategy in ["planpilot", "earliest_deadline", "naive_equal_split"]:
            run_req = req.model_copy(deep=True, update={"strategy": strategy})
            resp = generate_schedule(run_req)
            results.append(EvaluationResult(
                case_name=case_name,
                strategy=strategy,
                valid=resp.validation.valid and (not resp.unscheduled if expected_feasible else True),
                objective_score=resp.objective_score,
                metrics=resp.validation.metrics,
                violations=resp.validation.violations,
            ))
    return aggregate_results(results)


def main() -> None:
    summary = run_evaluation()
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "evaluation_results.json"
    path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps(summary.aggregate, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
