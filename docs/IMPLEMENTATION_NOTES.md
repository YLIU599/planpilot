# Implementation Notes

## Model setup

The app can use Gemini through LiteLLM + Vertex AI. It also has deterministic fallback parsers so the demo does not depend on live API calls.

Default model:

```text
vertex_ai/gemini-2.5-flash
```

Environment variables:

```text
VERTEX_PROJECT_ID
VERTEX_LOCATION
MODEL
ENABLE_LLM_PARSING
```

## Why fallback parsing exists

For live demos, reliability matters. If Vertex credentials are unavailable or the model response is not valid JSON, the app still works using regex/rule-based parsing.

## Scheduler design

The scheduler is intentionally deterministic. This makes it possible to test:

- no calendar conflicts;
- no task overlaps;
- no invalid schedules;
- deadline feasibility;
- effect of progress updates.

The LLM/agent layer is used where language understanding and user interaction matter.

## Future improvements

- Google Calendar OAuth.
- `.ics` file import.
- OR-Tools CP-SAT optimizer.
- More robust dependency handling.
- Actual task completion state persistence by user/session.
- Calendar export.
- Work project mode.

## v2 updates

This version adds the following demo-facing improvements:

1. **Ordered project stages**: The fallback parser detects phrases such as `needs EDA, modeling, writeup, slides` and converts them into ordered subtasks. The schedule now displays meaningful blocks like `ML project — EDA` instead of opaque `ML project part 1` labels.
2. **Chronological block ordering**: The scheduler now enforces a `not_before` constraint per parent task, so later parts/stages cannot be placed before earlier parts/stages.
3. **Cleaner validation summary**: The UI now shows user-facing checks for calendar conflicts, task overlaps, deadline violations, workload limits, and unscheduled work. Raw JSON is kept behind a collapsible debug panel.
4. **Plan rationale panel**: The API response now includes rationale lines explaining how hard constraints, soft preferences, and task-type rules affected the plan.
5. **Replanning change summary**: Progress updates now return explicit change messages showing applied progress and how many blocks moved, appeared, or disappeared.

The deterministic scheduler remains the reliability layer. The agent/parser layer is responsible for messy user input, stage decomposition, preference extraction, explanation, and replanning interpretation.


## v3 updates

This version fixes the main v2 reliability issue: project-stage dependency ordering.

1. **Real dependency-order enforcement**: `_trim_interval_to_not_before()` now rejects intervals that end before the previous block finishes. v2 accidentally allowed a later project stage to use a slot before an earlier stage.
2. **Earlier placement pressure for ordered stages**: decomposed project stages now receive a stronger earlier-placement penalty so the first stage is not delayed too close to the deadline merely to satisfy an evening preference.
3. **Dependency validator**: `validate_schedule()` now checks chronological project-stage order and increments `dependency_violations` if a later stage appears before an earlier stage.
4. **Clearer stage notes**: repeated work inside one stage is labeled as `stage x/y, block a/b`, which is more natural than showing the same `step x/y` multiple times.
5. **Regression tests**: tests now cover ordered project scheduling and validator detection of a deliberately invalid project-stage schedule.


### v4 Notes

The UI now exposes a user work-style preference: balanced, batch, or rotate. This is intentionally a soft preference, not a hard rule. The scheduler still prioritizes hard constraints first: fixed calendar events, availability, deadlines, task dependencies, and daily capacity. Empty progress updates are now handled explicitly so the replanning path does not silently return the same schedule without explanation.

## v5 notes

### Missing effort estimates

Users may omit `estimated hours` in task input. The fallback parser estimates effort with transparent heuristics:

- reading: default 2h, or page-count based when available
- problem set: default 5h, or roughly 1h per parsed problem
- coding/project: default 10h, or stage-based when deliverables are named
- writing: default 4h, or page-count based when available
- presentation: default 3h, or slide-count based when available

Every inferred estimate is labeled as system-generated with a confidence level and rationale. Low-confidence estimates are surfaced as planning assumptions / optional clarification prompts.

### Assignment details field

The web UI includes an optional assignment details text area. It is meant for short summaries of assignment instructions, deliverables, rubrics, problem counts, or page counts. It is not a file upload feature.

PDF upload was intentionally deferred. For a class project, the safer design is to avoid storing, redistributing, or committing course PDFs. The MVP only extracts scheduling metadata from user-provided summaries.

### Progress update parsing

The replanner supports minute-level progress updates such as:

- `I completed 30 min of Stats HW today`
- `I did 0.5h of AI project`
- `I did 1h 30 min of report writing`
- `I worked on reading for half an hour`

The parser deduplicates overlapping regex matches so `30 min` is not counted twice.


## v6 targeted fixes

- The UI now defaults the current date to the user's local current date instead of a hard-coded demo date.
- The sample endpoint also returns the server's current date so relative deadlines move with the demo date.
- Assignment details are scoped to the matching task before effort estimation. For example, a reading page count no longer turns problem sets or coding projects into reading tasks.
- If work cannot fit under the current constraints, the summary now says the schedule has warnings rather than calling it fully valid.
- Regression tests were added for assignment-detail scoping and effort estimation.

## v7 Targeted Improvements

- Replaced fixed sample deadlines with rolling explicit dates relative to the current date. This keeps the default demo feasible even when the app is opened on a later day.
- Added a more human urgency adjustment in the scheduler: tasks due soon are not delayed just to satisfy soft evening-focus preferences.
- Added an at-a-glance output panel with plan status, scheduled time, unscheduled time, days planned, and the first recommended work block.
- Added recommended next steps based on the generated plan, unscheduled work, risk warnings, and system-generated effort estimates.
- Added small UI guidance for replanning examples and clarified that the current date is auto-filled but editable.

## v8 UI and calendar-import polish

- Removed course-specific title text from the main UI so the demo looks like a product rather than a class scaffold.
- Added optional `.ics` calendar import. Users can export a Google Calendar / Apple Calendar `.ics` file and import it locally in the browser. The client converts VEVENT entries into fixed-event text lines; no OAuth or server-side file storage is required.
- Added absolute-date fixed-event parsing on the backend so imported calendar rows such as `2026-05-04 10:10-11:25 IEOR class` block the correct date.
- Reworked weekly schedule rendering with day-level totals, task-type color accents, duration labels, and clearer stage/block notes.

Google Calendar OAuth is left as future work. The `.ics` importer is intentionally lower risk for a live class demo because it avoids OAuth scopes, consent-screen setup, token storage, and production credential management.

## v9 polish

- Moved the weekly schedule higher in the output panel so the demo shows the product result sooner.
- Forced schedule date labels to English (`en-US`) so recorded demos do not depend on the browser locale.
- Added a visible imported-calendar preview and included imported `.ics` events directly in the planning request, not only in the textarea.
- Added textarea auto-resizing so imported events and custom tasks are easier to inspect.
- Improved the evaluation UI: `Run eval` now shows PlanPilot vs. baseline scores as cards instead of only raw JSON.
- Kept Google Calendar OAuth out of MVP. `.ics` import is a lower-risk, privacy-preserving calendar path that needs no OAuth token storage.


## v10 demo polish

- Starts with blank inputs and instructional placeholders instead of prefilled sample values.
- Adds staged demo buttons so the instructor can see the system progress from basic scheduling to effort estimation and calendar constraints.
- Moves Generate schedule, Run eval, and Replan into a sticky action bar at the top of the input panel.
- Groups inputs into collapsible Calendar & availability, Tasks & effort details, and Preferences sections to reduce scrolling.
- Updates the rolling sample to a demo-oriented Stats HW / AI project / Reading scenario.


## v11 submission UI polish

- Removed the large presentation-flow panel from the app UI and replaced it with a small Quick examples strip.
- Increased the default height of the progress-update textarea in the sticky action area.
- Kept the app suitable for GitHub submission by using neutral product/demo wording instead of presentation-specific wording.


## v12 UI action hotfix

- Fixed a frontend event-listener typo that prevented Generate schedule from sending a POST request after loading an example.
- Replaced long placeholder examples with shorter, neutral prompts to keep the blank start visibly empty.
- Verified Python syntax and regression tests: 13 passed.
