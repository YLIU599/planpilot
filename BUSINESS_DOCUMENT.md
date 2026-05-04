# PlanPilot Business Document

## 1. The user

PlanPilot is built for students and early-career project workers who manage several deadline-driven tasks at once. The first target user is a graduate student with weekly homework, readings, projects, part-time work, classes, and meetings. A second target user is a junior analyst, engineer, or consultant who has several project deliverables and recurring meetings but does not have a dedicated project manager.

The most concrete initial market is students in technical master's programs. They often have coding assignments, problem sets, readings, presentations, and group projects in the same week. They also usually know their deadlines, but they do not always know how long each task will take or how to break larger projects into stages.

## 2. The problem

Today, users usually solve this with a mix of Google Calendar, a to-do list, and manual judgment. That workflow breaks down for four reasons.

First, a to-do list does not understand time. It can store "Stats HW due Monday," but it does not know whether there are enough available work blocks before Monday.

Second, a calendar does not understand work structure. A coding project is not the same as reading 25 pages. A project may need ordered stages such as frontend, backend, evaluation, and writeup. A schedule that places "slides" before "modeling" is technically filled in, but not useful.

Third, planning changes after the first schedule is made. If the user only completes 30 minutes of homework instead of two hours, the plan should update remaining work and reveal whether the week is still feasible.

Fourth, users often do not know exact effort estimates. PlanPilot lets the user provide assignment details such as problem count, page count, or project deliverables. It then produces a tentative estimate, marks the confidence level, and shows the assumptions instead of hiding uncertainty.

PlanPilot is useful because it turns messy planning input into a structured, validated schedule. It does not just generate a nice-looking calendar. It checks constraints, explains risks, and replans when reality changes.

## 3. The economics

### Business model

A realistic business model is a freemium productivity product:

- Free tier: limited weekly plans and manual input
- Student Pro: $4.99 per month
- Team / cohort license: sold to student organizations, bootcamps, tutoring programs, or university support offices

The student Pro plan would unlock more saved schedules, calendar imports, repeated replanning, and better LLM-based parsing.

### Cost to serve one active user-month

For the current MVP, the most expensive part is optional LLM parsing. The deterministic scheduler, validator, and `.ics` calendar parser are normal backend code and do not require model calls.

Assumption for one active user-month:

- 30 schedule generations
- 15 replans
- 5 evaluation or analysis-style actions
- about 50 model-assisted parsing/explanation calls if LLM parsing is enabled
- average per call: 3,000 input tokens and 800 output tokens

Monthly token usage:

- Input tokens: 50 * 3,000 = 150,000 input tokens
- Output tokens: 50 * 800 = 40,000 output tokens

Using Gemini 2.5 Flash as the model, a conservative estimate is about $0.30 per 1M input tokens and $2.50 per 1M output tokens for text usage. That gives:

- Input cost: 0.15M * $0.30 = $0.045
- Output cost: 0.04M * $2.50 = $0.10
- Total model cost: about $0.15 per active user-month

Infrastructure cost is low at early scale. Cloud Run includes a free tier with 2 million requests, 180,000 vCPU-seconds, and 360,000 GiB-seconds per month in us-central1. At student-project scale, the app should remain close to free-tier usage. To be conservative, I would budget $0.05–$0.15 per active user-month for Cloud Run, logs, storage, and network overhead.

Estimated variable cost per active user-month:

| Item | Estimate |
|---|---:|
| Gemini parsing / explanation | $0.15 |
| Cloud Run + logs + storage allowance | $0.10 |
| Payment processing allowance | $0.45 |
| Total variable cost | about $0.70 |

At a $4.99 monthly price, contribution margin is about:

```text
$4.99 - $0.70 = $4.29 per paid user-month
```

That is roughly an 86% contribution margin before fixed costs.

If fixed costs are estimated at $2,000 per month for development, maintenance, support, and operational overhead, the break-even point is:

```text
$2,000 / $4.29 ≈ 466 paid users
```

This is plausible for a student productivity tool if sold through a few university programs, technical bootcamps, or student communities. The economics work best because the scheduler is mostly deterministic. The model is used only where it adds value: parsing messy input and explaining tradeoffs.

## 4. Why these technical choices

### Agent layer plus deterministic tools

The most important technical choice is separating the agent layer from the scheduling engine. A pure LLM planner is flexible but unstable. It may produce a schedule with hidden conflicts, invalid ordering, or unrealistic workloads. PlanPilot uses the agent layer for interpretation and communication, then uses deterministic tools for scheduling and validation.

This directly serves the user because students need a schedule they can trust. It also improves the economics because the system does not call the model for every scheduling decision.

### Greedy deterministic scheduler

The current scheduler is a deterministic greedy scheduler rather than a full optimization solver. This was a practical MVP choice. It is fast, explainable, easy to debug, and good enough for the short-week academic scheduling use case. A more advanced CP-SAT optimizer could be added later, but the current scheduler already supports deadlines, availability windows, task types, daily capacity, and project-stage order.

### Validation layer

PlanPilot validates calendar conflicts, task overlaps, deadline violations, dependency order, daily workload, and unscheduled work. This is essential because the product should not pretend a plan is feasible when the user does not have enough time. Risk warnings are a feature, not a failure.

### Effort estimation from assignment metadata

Users often do not know exact durations. PlanPilot estimates work from metadata such as problem count, page count, and deliverables. It also marks confidence and shows assumptions. This makes the tool more usable without pretending that estimates are certain.

The MVP intentionally does not include PDF upload. That choice reduces implementation risk and avoids storing or redistributing course materials. Users can paste brief excerpts or summaries instead. The system only needs scheduling metadata.

### `.ics` calendar import instead of full OAuth

Full Google Calendar OAuth would require consent screen setup, scopes, token storage, and production security handling. For an MVP and course demo, `.ics` import gives most of the calendar-aware scheduling value without storing user tokens. It is also easier to explain and safer to deploy.

### Cloud Run deployment

Cloud Run is a good fit because the app is a containerized FastAPI service with bursty traffic. It can scale down when unused and handle live demo traffic without managing servers. That keeps the operating cost low and matches the project’s deployment requirements.

## Bottom line

PlanPilot is commercially plausible because it addresses a real planning pain point, has a clear initial user segment, and has low variable cost. The product value comes from combining agentic interpretation with deterministic scheduling and validation. The user gets a practical schedule, not just a chatbot response.
