---
title: "PlanPilot Business Document"
geometry: margin=0.7in
fontsize: 10pt
---

# PlanPilot Business Document

**GitHub:** https://github.com/YLIU599/planpilot  
**Live demo:** https://planpilot-407136000438.us-central1.run.app

## 1. The user

PlanPilot is built for students and early-career project workers who manage several deadline-driven tasks at the same time. The initial target user is a graduate student in a technical program with homework, readings, projects, classes, meetings, and part-time work. A secondary user is a junior analyst, engineer, consultant, or bootcamp participant who has project deliverables but no dedicated project manager.

The first concrete market is technical master's students. They often know what is due, but they do not always know how much time each task will take, which tasks need long focus blocks, or how to recover when they fall behind. They also use several disconnected tools: a calendar, a to-do list, class websites, and personal judgment. PlanPilot sits between those tools by turning messy planning input into a validated schedule.

## 2. The problem

Today, most users plan manually. They put classes and meetings in Google Calendar, keep assignments in a to-do app, and mentally decide when to work. That breaks down for four reasons.

First, a to-do list does not understand time. It can store “Stats HW due Monday,” but it does not know whether there are enough available work blocks before Monday.

Second, a calendar does not understand work structure. Reading 25 pages is different from solving a problem set, and both are different from a coding project. A project may have ordered stages such as frontend, backend, evaluation, and writeup. A plan that schedules the writeup before the evaluation is not useful, even if the calendar is filled.

Third, real planning changes. If a user only finishes 30 minutes of homework instead of two hours, the plan should update remaining work and show whether the week is still feasible.

Fourth, users often do not know exact effort estimates. PlanPilot lets users provide lightweight assignment details such as problem count, page count, or project deliverables. It then infers a tentative workload, marks confidence, and shows assumptions. This avoids pretending the estimate is certain.

The core value is not just generating a nice calendar. PlanPilot parses messy input, builds a structured scheduling problem, checks constraints, explains risks, and replans when reality changes.

## 3. The economics

A realistic business model is a freemium productivity product:

- **Free tier:** limited weekly plans, manual input, and basic replanning
- **Student Pro:** $4.99 per month for saved plans, repeated replanning, calendar import, and stronger LLM parsing
- **Team / cohort license:** sold to bootcamps, tutoring programs, student organizations, or university support offices

Back-of-envelope for one active paid user-month:

- 30 schedule generations
- 15 replans
- 5 evaluation or analysis actions
- about 50 model-assisted parsing or explanation calls if LLM parsing is enabled
- average model call: 3,000 input tokens and 800 output tokens

Estimated monthly token usage:

- Input tokens: 50 x 3,000 = 150,000
- Output tokens: 50 x 800 = 40,000

Using Gemini 2.5 Flash as a representative low-cost model, the model cost is roughly on the order of cents per active user-month. Using a conservative estimate of $0.30 per 1M input tokens and $2.50 per 1M output tokens:

| Item | Calculation | Cost |
|---|---:|---:|
| Input tokens | 0.15M x $0.30 | $0.045 |
| Output tokens | 0.04M x $2.50 | $0.100 |
| Model subtotal |  | about $0.15 |

Infrastructure cost is also low at early scale. Cloud Run has a free tier for requests, CPU-seconds, and memory-seconds. At course-project or early pilot scale, PlanPilot should stay close to free-tier usage. To be conservative, I would budget about $0.10 per active user-month for Cloud Run, logs, storage, and network overhead.

Estimated variable cost per active paid user-month:

| Item | Estimate |
|---|---:|
| Gemini parsing / explanation | $0.15 |
| Cloud Run + logs + storage allowance | $0.10 |
| Payment processing allowance | $0.45 |
| **Total variable cost** | **about $0.70** |

At a $4.99 monthly price, contribution margin is about:

```text
$4.99 - $0.70 = $4.29 per paid user-month
```

That is about an 86% contribution margin before fixed costs. If fixed costs are $2,000 per month for maintenance, support, and operations, break-even is:

```text
$2,000 / $4.29 = about 466 paid users
```

This is plausible for a niche student productivity tool if distributed through technical student communities, tutoring programs, or bootcamps. The economics work because the system does not use the LLM for every scheduling decision. Most scheduling, validation, and calendar parsing are deterministic tools.

## 4. Why these technical choices

**Agent layer plus deterministic tools.** A pure LLM planner is flexible but unreliable. It can produce hidden calendar conflicts, invalid stage ordering, or unrealistic workloads. PlanPilot uses the agent layer for interpretation and communication, then calls deterministic tools for scheduling and validation. This directly addresses the user need: students need a plan they can trust, not just a plausible-sounding response.

**Greedy deterministic scheduler.** The current scheduler is not a full CP-SAT optimizer. That is intentional for the MVP. It is fast, explainable, easy to debug, and strong enough for short-week academic planning. It supports deadlines, availability windows, daily capacity, task types, and ordered project stages. A full optimizer can be added later if the product expands to larger teams or more complex constraints.

**Validation layer.** PlanPilot checks calendar conflicts, overlapping tasks, deadline violations, dependency order, daily workload, and unscheduled work. This matters commercially because the product should not hide infeasible plans. Risk warnings are part of the value: they tell users when they need to add availability, reduce scope, or revise an estimate.

**Effort estimation from metadata.** Users often do not know exact durations. PlanPilot estimates from scheduling metadata such as problem count, page count, and deliverables. It marks confidence and shows the rationale. The MVP intentionally does not include PDF upload. This avoids storing or redistributing course materials. Users can paste brief excerpts or summaries instead; the system only needs metadata, not the full assignment file.

**.ics calendar import instead of full OAuth.** Full Google Calendar OAuth would require consent screen setup, scopes, token storage, refresh handling, and production security work. For an MVP, `.ics` import gives most of the calendar-aware scheduling value without storing user tokens. It is safer and easier to deploy.

**Cloud Run deployment.** Cloud Run is a good fit because PlanPilot is a containerized FastAPI app with bursty usage. It can scale down when unused and handle demo or pilot traffic without server management. That keeps operating cost low and matches the project’s deployment requirement.

## Bottom line

PlanPilot is commercially plausible because it solves a real planning pain point for a concrete initial user segment. The product value comes from combining agentic interpretation with deterministic scheduling and validation. The user gets a practical, checked schedule rather than a generic chatbot answer.

## Sources

- Google AI pricing for Gemini models: https://ai.google.dev/gemini-api/docs/pricing
- Google Cloud Run pricing and free tier: https://cloud.google.com/run/pricing
