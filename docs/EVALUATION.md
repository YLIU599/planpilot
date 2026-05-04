# Evaluation Plan

PlanPilot includes a repeatable scheduler evaluation harness.

## Baselines

- `earliest_deadline`: schedules work by nearest deadline.
- `naive_equal_split`: spreads blocks in a simple sequence across available slots.
- `planpilot`: uses task urgency, priority, task type, buffer preference, and slot preference scoring.

## Test cases

Synthetic cases cover:

- simple feasible homework;
- calendar conflict avoidance;
- infeasible tight deadline;
- mixed task types;
- deep-work block placement;
- daily capacity limits.

## Metrics

Hard validity metrics:

- calendar conflicts;
- task overlaps;
- deadline violations;
- daily capacity violations;
- unscheduled minutes.

Quality metrics:

- objective score;
- preference bonus;
- fragmentation penalty;
- number of scheduled blocks;
- number of unscheduled tasks.

## Run

```powershell
uv run python -m app.evals.runner
```

Output:

```text
outputs/evaluation_results.json
```

The API also exposes:

```text
GET /api/v1/evaluate
```
