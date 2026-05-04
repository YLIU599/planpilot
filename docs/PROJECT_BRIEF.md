# Project Brief

## Working title

**PlanPilot: Adaptive Scheduling Agent**

## One-line description

PlanPilot converts messy task lists, deadlines, calendar events, availability rules, and personal work preferences into a validated personalized schedule, then dynamically replans as the user reports progress.

## Motivation

Academic and project planning is not just sorting by deadline. Real schedules must account for:

- fixed calendar events;
- deadlines;
- estimated workload;
- task type;
- minimum block length;
- task dependencies;
- available work windows;
- user preferences;
- fatigue and daily capacity;
- progress updates;
- infeasible situations.

PlanPilot treats scheduling as an agentic planning problem with deterministic validation.

## MVP scope

The MVP focuses on academic scheduling for students. Future versions can support work projects, meeting-aware planning, and business experiment scheduling.

## Why this is agentic

The LLM is not used to blindly generate a schedule. It handles parts that are hard for ordinary algorithms:

- converting vague natural-language tasks into structured tasks;
- inferring task type and scheduling rules;
- extracting user preferences;
- asking clarification questions;
- interpreting validation failures;
- explaining tradeoffs;
- replanning after progress updates.

The deterministic scheduler is a tool called by the agentic workflow. This makes the system reliable and testable.


### v4 Notes

The UI now exposes a user work-style preference: balanced, batch, or rotate. This is intentionally a soft preference, not a hard rule. The scheduler still prioritizes hard constraints first: fixed calendar events, availability, deadlines, task dependencies, and daily capacity. Empty progress updates are now handled explicitly so the replanning path does not silently return the same schedule without explanation.


## v6 targeted fixes

- The UI now defaults the current date to the user's local current date instead of a hard-coded demo date.
- The sample endpoint also returns the server's current date so relative deadlines move with the demo date.
- Assignment details are scoped to the matching task before effort estimation. For example, a reading page count no longer turns problem sets or coding projects into reading tasks.
- If work cannot fit under the current constraints, the summary now says the schedule has warnings rather than calling it fully valid.
- Regression tests were added for assignment-detail scoping and effort estimation.
