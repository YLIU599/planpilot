# PlanPilot: Adaptive Scheduling Agent

PlanPilot is an adaptive scheduling agent for academic and project work. It converts messy user input about tasks, deadlines, calendar constraints, availability, and work preferences into a validated weekly schedule. When progress changes, it replans the remaining work.

- Live demo: https://planpilot-407136000438.us-central1.run.app
- GitHub repo: https://github.com/YLIU599/planpilot
- Business document: [BUSINESS_DOCUMENT.md](BUSINESS_DOCUMENT.md)

---

## Why PlanPilot

Real planning is not just a to-do list. Students and project workers need to account for:

- fixed events such as classes, meetings, and work shifts
- deadlines and task dependencies
- different task types such as reading, problem sets, and coding projects
- uncertain effort estimates
- personal preferences such as focus time, block size, and task-switching style
- progress changes after the original plan is created

PlanPilot addresses this by combining agentic task interpretation with deterministic scheduling and validation tools.

---

## Core workflow

```text
User input
  ↓
Task parser / effort estimator
  ↓
Preference and constraint extractor
  ↓
Deterministic scheduler tool
  ↓
Schedule validator tool
  ↓
Risk explanation and replanning
  ↓
Final schedule
```

The LLM-facing layer is responsible for understanding messy user input and explaining tradeoffs. The deterministic tools enforce hard constraints such as deadlines, dependency order, calendar conflicts, and daily capacity.

---

## Current features

### Planning inputs

- Natural-language tasks and deadlines
- Fixed calendar events
- Availability windows
- Work preferences
- Work style options: Balanced, Batch, Rotate
- Optional assignment details such as problem count, page count, rubric notes, or deliverables
- Optional `.ics` calendar import from Google Calendar, Apple Calendar, or Outlook exports

### Scheduling logic

- Task-type-aware scheduling
- Project-stage decomposition, for example: Frontend, Backend, Evaluation, Writeup
- Dependency-order validation, so later stages cannot appear before earlier stages
- Longer deep-work blocks for problem sets and coding projects
- Smaller blocks for reading and lighter work
- Replanning after progress updates

### Validation and explanation

The web UI reports:

- first recommended block
- weekly schedule
- validation summary
- risk warnings
- planning assumptions
- parsed task table
- replan changes

### Evaluation

The app includes a repeatable evaluator comparing PlanPilot against simple baselines:

- earliest-deadline-first
- naive equal-split scheduling

Metrics include objective score, conflict count, deadline violations, dependency-order violations, and unscheduled minutes.

---

## Class concepts used

PlanPilot uses the following concepts from IEOR 4576.

| Course concept | How PlanPilot uses it | File references |
|---|---|---|
| Agent loop / orchestration | The app follows a parse → schedule → validate → replan loop rather than returning a one-shot chatbot response. | `app/main.py`, `app/agents/task_parser.py`, `app/agents/replanner.py` |
| Tool calling pattern | The agent layer delegates reliable operations to deterministic tools: scheduler, validator, effort estimator, calendar parser, and evaluator. | `app/scheduling/engine.py`, `app/scheduling/validator.py`, `app/agents/fallback_parser.py`, `app/evals/runner.py` |
| Structured outputs / schemas | Inputs, parsed tasks, schedule blocks, validation results, and replanning outputs are represented with typed Pydantic schemas. | `app/schemas.py` |
| Guardrails / validation | The validator catches calendar conflicts, overlaps, deadline violations, daily capacity violations, dependency-order violations, and unscheduled work. | `app/scheduling/validator.py` |
| Context, state, and replanning | The app keeps the original structured request, applies progress updates, and regenerates the remaining schedule from updated state. | `frontend/static/app.js`, `app/agents/replanner.py` |
| Evaluation | PlanPilot is tested against simple baseline schedulers with repeatable metrics instead of relying only on visual inspection. | `app/evals/runner.py`, `docs/EVALUATION.md`, `tests/` |
| Production deployment | The app is packaged as a FastAPI + Docker service and deployed publicly on Cloud Run. | `Dockerfile`, `cloudbuild.yaml`, `docs/DEPLOYMENT.md` |

---

## Local setup

Open PowerShell from the project root:

```powershell
cd "D:\##Columbia\#SPRING26\IEORE4576 Agentic AI\###Final Proj\planpilot"
```

Install dependencies:

```powershell
uv sync
```

Run the app:

```powershell
$env:ENABLE_LLM_PARSING="false"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000
```

The app starts with blank inputs. Use the **Quick examples** buttons to preload a scenario.

---

## Optional Vertex AI / Gemini parsing

PlanPilot is designed to run without LLM parsing for demo reliability. To enable Gemini parsing through LiteLLM and Vertex AI:

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project ieor-4576-agentic

$env:VERTEX_PROJECT_ID="ieor-4576-agentic"
$env:VERTEX_LOCATION="us-central1"
$env:MODEL="vertex_ai/gemini-2.5-flash"
$env:ENABLE_LLM_PARSING="true"

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

If the Vertex call fails, the app can fall back to deterministic parsing instead of breaking the demo.

---

## Main API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Web UI |
| `/healthz` | GET | Health check |
| `/api/v1/sample` | GET | Load sample planning input |
| `/api/v1/parse` | POST | Parse planning input |
| `/api/v1/plan` | POST | Parse, schedule, validate, and explain |
| `/api/v1/replan` | POST | Apply progress update and replan |
| `/api/v1/evaluate` | GET | Run evaluation |

---

## Run evaluation locally

```powershell
uv run python -m app.evals.runner
```

This writes:

```text
outputs/evaluation_results.json
```

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

The current live demo is deployed at:

```text
https://planpilot-407136000438.us-central1.run.app
```

Deployment variables used for the current project:

```powershell
$PROJECT_ID = "ieor-4576-agentic"
$REGION = "us-central1"
$REPO = "planpilot-repo"
$SERVICE = "planpilot"
$IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/${SERVICE}:latest"
```

Build and deploy:

```powershell
gcloud builds submit --tag $IMAGE

gcloud run deploy $SERVICE `
  --image $IMAGE `
  --region $REGION `
  --platform managed `
  --allow-unauthenticated `
  --set-env-vars "VERTEX_PROJECT=ieor-4576-agentic,VERTEX_PROJECT_ID=ieor-4576-agentic,GOOGLE_CLOUD_PROJECT=ieor-4576-agentic,VERTEX_LOCATION=us-central1,AGENT_MODEL=vertex_ai/gemini-2.5-flash,MODEL=vertex_ai/gemini-2.5-flash,ENABLE_LLM_PARSING=false"
```

For the final demo, `ENABLE_LLM_PARSING=false` is recommended for stability. Gemini parsing can be enabled later after verifying service account permissions and quota.

---

## Demo flow

Recommended flow:

1. Start from the blank page.
2. Use **Quick examples → Add details**.
3. Generate a schedule.
4. Show weekly schedule, validation summary, planning assumptions, and parsed task table.
5. Use **Quick examples → Add calendar** and regenerate to show calendar-aware scheduling.
6. Enter a progress update, for example:

```text
I only completed 30 min of Stats HW today.
```

7. Replan and show the updated remaining work and risk warnings.
8. Run evaluation to show PlanPilot compared against baseline schedulers.

---

## Project limitations and future work

- The deterministic scheduler is a greedy scheduler, not a full CP-SAT optimizer.
- Full Google Calendar OAuth is not included in the MVP. The current app uses `.ics` import to avoid storing user calendar tokens.
- The fallback parser is intentionally simple. LLM parsing can improve flexible natural-language handling.
- Drag-and-drop calendar editing is future work.
- More advanced effort estimation could use historical completion data, but the MVP avoids storing sensitive user history.
