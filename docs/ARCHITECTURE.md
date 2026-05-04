# Architecture

## Components

| Component | Type | Purpose |
|---|---|---|
| Task Parser | Agent + fallback parser | Convert messy task text into structured tasks |
| Preference Parser | Agent + fallback parser | Extract availability and study/work preferences |
| Scheduler | Deterministic tool | Generate feasible schedule blocks |
| Validator | Deterministic guardrail | Check conflicts, deadlines, capacity, dependency order, and unscheduled work |
| Replanner | Agentic control logic | Apply progress updates and regenerate plan |
| Explainer | Agentic/output layer | Explain schedule rationale and risks |
| Evaluator | Deterministic benchmark | Compare PlanPilot with simple baselines |

## Control flow

```text
POST /api/v1/plan
  raw inputs
    ↓
  parse_planning_input()
    ↓
  ScheduleRequest
    ↓
  generate_schedule()
    ↓
  validate_schedule()
    ↓
  build_explanation()
    ↓
  UI response
```

## Scheduling engine

The MVP uses a 30-minute grid. It:

1. builds available intervals from weekly availability;
2. subtracts fixed calendar events;
3. converts tasks into work blocks;
4. ranks tasks by urgency, priority, type, and remaining work;
5. places blocks into feasible slots;
6. validates the result, including project-stage dependency order.

## Why not pure LLM scheduling?

Hard constraints must be enforced reliably. Calendar conflicts, deadline violations, and daily capacity limits are deterministic correctness issues. The scheduler and validator handle these constraints, while the agent handles interpretation, personalization, and replanning.


## v3 dependency-order invariant

For tasks with decomposed subtasks, the generated schedule must satisfy:

```text
EDA finishes before Modeling starts
Modeling finishes before Writeup starts
Writeup finishes before Slides starts
```

The scheduler enforces this with per-task `not_before` constraints, and the validator independently checks chronological stage order from the rendered schedule blocks. This gives the demo both proactive scheduling correctness and a defensive guardrail.
