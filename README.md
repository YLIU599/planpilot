# PlanPilot: Adaptive Scheduling Agent

PlanPilot is an agentic scheduling system for academic and project work. It converts messy user inputs about tasks, deadlines, fixed calendar events, availability, and work preferences into a validated personalized schedule. When progress changes, it replans the remaining work.

Live demo URL: `TO_BE_FILLED_AFTER_CLOUD_RUN_DEPLOYMENT`

GitHub repo: `TO_BE_FILLED_AFTER_PUSH`

---

## Core idea

PlanPilot is not a generic calendar or to-do app. The system uses an agentic workflow:

1. Parse messy natural-language planning inputs.
2. Extract tasks, deadlines, task types, availability, and preferences.
3. Build a structured scheduling problem.
4. Call a deterministic scheduler tool.
5. Validate the schedule against hard constraints.
6. Explain the plan and replan when progress changes.

The deterministic scheduler is a tool. The agent remains responsible for task understanding, preference extraction, clarification, interpretation of validation failures, and replanning.

---

## What the current MVP supports

- Natural-language task entry with fallback parser.
- Optional Gemini / Vertex AI parsing via LiteLLM.
- Fixed calendar events, availability windows, and preferences.
- Task-type aware scheduling:
  - reading
  - problem sets
  - coding projects
  - writing
  - exam prep
  - presentations
  - group projects
  - admin tasks
- Hard-constraint validation:
  - calendar conflicts
  - task overlaps
  - deadline violations
  - daily capacity violations
  - unscheduled work
- Dynamic replanning from progress updates.
- Ordered project-stage decomposition for inputs such as `needs EDA, modeling, writeup, slides`.
- Dependency-order validation so later stages such as slides cannot appear before earlier stages such as EDA.
- Clean validation summary, plan rationale, and replan-change explanation in the web UI.
- Baseline evaluation against simpler scheduling strategies.
- FastAPI backend and static web frontend.
- Dockerfile for Cloud Run deployment.

---

## Architecture

```text
User input
  ↓
Task Parser Agent / fallback parser
  ↓
Preference + Constraint Extractor
  ↓
Schedule Problem Builder
  ↓
Deterministic Scheduler Tool
  ↓
Schedule Validator Tool
  ↓
Risk Critic / Replanner
  ↓
Final schedule + explanation
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for details.

---

## Local setup on Windows 11

Open PowerShell:

```powershell
cd "D:\##Columbia\#SPRING26\IEORE4576 Agentic AI\###Final Proj\planpilot"
```

Install dependencies:

```powershell
uv sync
```

Run without LLM parsing first:

```powershell
$env:ENABLE_LLM_PARSING="false"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000
```

The app starts blank for demo clarity. Use **Load full demo** or the example buttons to preload a scenario.

---

## Optional Vertex AI / Gemini setup

This app is designed to run even without LLM parsing. To enable Gemini parsing through LiteLLM + Vertex AI, first make sure your GCP application default credentials are set:

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Then run:

```powershell
$env:VERTEX_PROJECT_ID="YOUR_PROJECT_ID"
$env:VERTEX_LOCATION="us-central1"
$env:MODEL="vertex_ai/gemini-2.5-flash"
$env:ENABLE_LLM_PARSING="true"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

If the Vertex call fails, the app falls back to deterministic parsing rather than breaking the demo.

---

## API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Web UI |
| `/healthz` | GET | Health check |
| `/api/v1/sample` | GET | Sample planning input |
| `/api/v1/parse` | POST | Parse raw planning text |
| `/api/v1/generate-schedule` | POST | Generate schedule from structured input |
| `/api/v1/plan` | POST | Parse + schedule + explain |
| `/api/v1/replan` | POST | Apply progress update and replan |
| `/api/v1/evaluate` | GET | Run evaluator |

---

## Run evaluation

```powershell
uv run python -m app.evals.runner
```

This writes:

```text
outputs/evaluation_results.json
```

The evaluator compares PlanPilot against two baselines:

1. `earliest_deadline`
2. `naive_equal_split`

Metrics include conflict count, deadline violations, dependency-order violations, unscheduled minutes, objective score, and validity rate.

---

## Docker local test

```powershell
docker build -t planpilot .
docker run --rm -p 8080:8080 -e PORT=8080 planpilot
```

Open:

```text
http://localhost:8080
```

---

## Cloud Run deployment

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

Short version:

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com

gcloud artifacts repositories create planpilot-repo `
  --repository-format=docker `
  --location=us-central1 `
  --description="PlanPilot Docker repository"

gcloud builds submit --tag "us-central1-docker.pkg.dev/YOUR_PROJECT_ID/planpilot-repo/planpilot:latest"

gcloud run deploy planpilot `
  --image "us-central1-docker.pkg.dev/YOUR_PROJECT_ID/planpilot-repo/planpilot:latest" `
  --region us-central1 `
  --platform managed `
  --allow-unauthenticated `
  --set-env-vars VERTEX_PROJECT_ID=YOUR_PROJECT_ID,VERTEX_LOCATION=us-central1,MODEL=vertex_ai/gemini-2.5-flash,ENABLE_LLM_PARSING=false
```

Enable `ENABLE_LLM_PARSING=true` after verifying Cloud Run service account has Vertex AI access.

---

## Recommended demo script

1. Click **1. Basic demo** or **Load full demo** to preload the demo scenario.
2. Click **Generate schedule**.
3. Show parsed tasks, schedule blocks, validation metrics, and risk warnings.
4. Enter progress update:

```text
I only completed 1 hour of ML project today.
```

5. Click **Replan from progress**.
6. Show how remaining work shifts while constraints remain checked.
7. Click **Run eval** to show repeatable evaluation metrics.

---

## v3 reliability fixes

- Project stages are now truly scheduled in dependency order, not just labeled in order.
- The scheduler no longer allows earlier intervals before the previous project stage has finished.
- Project-stage placement uses stronger early-placement pressure to avoid compressing all downstream stages near the deadline.
- The validator now catches dependency-order violations and reports them in the validation summary.
- Stage labels now distinguish stage order from repeated blocks inside the same stage, for example `stage 2/4, block 1/2`.

## Project limitations

- The fallback parser is intentionally simple; LLM parsing improves flexible natural-language handling.
- The scheduler is a deterministic greedy scheduler, not a full CP-SAT optimizer.
- Google Calendar OAuth is not included in MVP; manual fixed-event input is used for reliability.
- `.ics` import and drag-and-drop calendar editing are planned future extensions.


## v4 UX / Planning Updates

- Added a **Work style** control: balanced, batch, or rotate. This lets the user state whether they prefer to stay on one task or mix topics for variety. The scheduler treats this as a soft preference; deadlines, dependencies, and calendar conflicts remain hard constraints.
- Added an onboarding guide in the UI to make clear that the sample is editable and users can replace it with their own classes, meetings, assignments, or work projects.
- Added explicit handling for empty or unparseable progress updates during replanning.
- The default behavior is **balanced**: tasks are splittable unless the user says otherwise, but deep-work tasks are kept in coherent blocks and project stages still respect dependency order.

## v5 effort-estimation updates

- Progress updates now support minute-level durations without double counting, including `30 min`, `0.5h`, `1h 30 min`, and `half an hour`.
- Tasks no longer require explicit `estimated hours`. If the user omits an estimate, PlanPilot infers a tentative workload from task type, problem/page counts, named deliverables, and optional assignment details.
- System-generated estimates are marked with `estimate_source=system`, `estimate_confidence`, and an `estimate_rationale`.
- The UI now includes an optional **assignment details / prompt** field where users can paste a short summary of requirements, deliverables, rubric items, page counts, or problem counts.
- PDF upload is intentionally not included in the MVP. This avoids storing or redistributing potentially copyrighted course materials. Users can paste brief excerpts or summaries instead; the system only needs scheduling metadata.


## v6 targeted fixes

- The UI now defaults the current date to the user's local current date instead of a hard-coded demo date.
- The sample endpoint also returns the server's current date so relative deadlines move with the demo date.
- Assignment details are scoped to the matching task before effort estimation. For example, a reading page count no longer turns problem sets or coding projects into reading tasks.
- If work cannot fit under the current constraints, the summary now says the schedule has warnings rather than calling it fully valid.
- Regression tests were added for assignment-detail scoping and effort estimation.


## Calendar import

The demo supports optional `.ics` import from Google Calendar, Apple Calendar, or Outlook exports. The browser parses the file locally and appends fixed-event lines to the calendar input box. This avoids OAuth setup and does not store uploaded calendar files. Full Google Calendar OAuth can be added later as a production extension.


## v9 demo polish

- Weekly schedule now appears earlier in the output panel for the 4-minute demo flow.
- Schedule dates render in English regardless of browser locale.
- `.ics` imports show a visible preview and are included automatically as fixed calendar events during scheduling.
- Evaluation output is summarized as cards comparing PlanPilot with simple baselines.
- Full Google Calendar OAuth is intentionally left as future work; the MVP uses `.ics` import to avoid handling calendar tokens.

### v10 demo-ready UI

- The app now starts blank instead of auto-loading sample content, so placeholders explain what to enter.
- Added sticky top controls for **Generate schedule**, **Run eval**, and **Replan**, reducing the need to scroll during a 4-minute demo.
- Added example buttons: **1. Basic demo**, **2. Add details**, and **3. Add calendar blockers**.
- Collapsed related inputs into Calendar & availability, Tasks & effort details, and Preferences sections.
- The rolling demo now uses an academic/project workload that shows task parsing, effort estimation, scheduling, validation, and replanning in a single scenario.


## v11 submission UI polish

- The app opens with empty inputs and placeholders, not preloaded sample text.
- The quick example loader is now a small neutral strip rather than a large presentation-flow panel.
- The sticky action area keeps Generate schedule, Run eval, progress update, and Replan visible near the top.
- The progress update input is taller by default so examples are readable without resizing.


## v12 UI action hotfix

- Fixed the Generate schedule button event handler in the compressed input layout.
- Simplified blank-state placeholders so the app opens as a clean, empty planning workspace rather than appearing prefilled.
- Kept the sticky action area compact while preserving a taller progress-update box for replanning examples.
