# Implementation Plan: Reddit Audience Intelligence

**Branch**: `001-reddit-audience-intelligence` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-reddit-audience-intelligence/spec.md`

**Revision**: Regenerated after the clarification session of 2026-08-14, which added fifteen
requirements (FR-067–FR-081) covering deletion propagation, durability, analysis resilience, the
retrieval refusal threshold, and deployment posture. Constitution v1.2.2 also resolved the two gate
conditions this plan previously carried.

## Summary

Build JammySearch's core product: a researcher groups Reddit communities into named audiences, reads
and searches their combined material, has it interpreted into topics and themes with trends, asks
plain-language questions answered with citations, and is alerted when new material matches a standing
rule.

The technical approach is a **modular monolith** in Python — FastAPI for the API surface, PRAW behind
a single isolating data layer, Celery for all collection and analysis, PostgreSQL as system of record
with `pgvector` for retrieval, and a SvelteKit frontend (static SPA, SSR off — see R10). All model access goes through one internal
adapter with a pinned model identifier, versioned prompt files, and schema-validated output, and
every model call and Reddit call emits a cost and latency record.

The clarification session added a **resilience spine** that cuts across every story: material is
purged when deleted at the source but survives in the user's own bookmarks; the database is backed up
nightly because most of its contents cannot be re-fetched; analysis commits in chunks and resumes
from where it stopped; and the application is written as though it will be publicly exposed while
being deployed only locally.

Alerts match on literal keywords and on intent, as independently operable modes (R18). Keeping them
separable is what preserves US1 → US2 → US5 as a complete, AI-free path to a useful product, with
intent matching switching on once the retrieval work in US4 lands.

Delivery is sequenced by the specification's eight prioritized user stories. P1 (audience plus feed)
is independently shippable and is the foundation everything else consumes.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript (frontend)

**Primary Dependencies**: FastAPI, PRAW, Celery, SQLAlchemy, Alembic, Pydantic, pgvector, LangChain
behind an internal adapter (Groq for completions, a local `sentence-transformers` model for embeddings —
R1), SvelteKit (adapter-static)

**Storage**: PostgreSQL as system of record, including embeddings via the `pgvector` extension. Redis
as cache and Celery broker, treated as fully reconstructible from PostgreSQL.

**Testing**: pytest with pytest-asyncio; ruff for lint and format. All external services mocked —
no test may contact Reddit or a model provider (Constitution IV).

**Target Platform**: Linux server, containerized. Bound to the local machine only (FR-078); exposure
beyond it is a configuration change, not a code change (SC-020).

**Project Type**: Web application — backend plus frontend.

**Performance Goals**: Constitution VI's budgets are server-side p95 at the application boundary —
feed under 500 ms, search over collected material under 1 s, Ask first response under 5 s. The
specification's SC-003 to SC-005 are the end-to-end user-perceived equivalents and are necessarily
looser. Searches reaching the source live are exempt from the search budget.

**Constraints**: Reddit API quota is the binding external limit on collection breadth and cadence,
and it cannot supply history beyond its listing limits — which is why the corpus is treated as
irreplaceable rather than as a rebuildable cache. Model spend is capped per request and per day
(FR-046, FR-080). Recovery point objective of 24 hours (SC-018). Single user — no tenancy scoping.

**Scale/Scope**: One user. Up to 50 communities per audience (FR-005). 8 user stories, 87 functional
requirements, 21 success criteria.

All Phase 0 unknowns are resolved in [research.md](./research.md); no `NEEDS CLARIFICATION` items
remain.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

Evaluated against constitution **v1.4.0**, re-checked on 2026-11-01 after the `/speckit-analyze`
remediation. v1.3.0's ephemeral-state exemption and v1.3.1's API-docs gate both pass without change.

| # | Principle | Gate | Status |
|---|-----------|------|--------|
| I | Reddit Data Layer Isolation | PRAW imported only in `backend/app/reddit/`; no raw PRAW object crosses a module boundary; the widened search path and the availability re-check both live here | **PASS** |
| II | Modular Boundaries and Code Quality | Modules own their routers, services, models, schemas; no cross-module table access; typed signatures; ruff clean; no business logic in routers | **PASS** |
| III | Contract-First Interfaces | Every endpoint has Pydantic request and response models; `contracts/rest-api.md` is the single source of truth for the HTTP surface and is updated in the same change set as any change to it; the surface is not restated elsewhere | **PASS** — constitution v1.2.3 moved the canonical location here from `README.md`, which now links rather than duplicates |
| IV | Testing Standards | Test-first for all service logic; unit and integration split; deterministic; 80% service-layer coverage floor; externals mocked | **PASS** |
| V | UX Consistency | Four view states everywhere; shared components and tokens before feature screens; UTC ISO 8601; shared pagination and error envelopes | **PASS** — v1.2.2 added *alert rule*, *alert match*, and *status* to the fixed vocabulary; v1.4.0 fixed *community* (one subreddit) in place of *subreddit*, matching every artifact; *bookmark* is used throughout, never "saved post" |
| VI | Performance and Efficiency | Caching with defined TTLs on paid or rate-limited calls; inference persisted; bulk work in Celery; mandatory pagination; no N+1; no blocking I/O in request paths | **PASS** — v1.2.2 scoped the budgets to server-side p95, resolving the apparent conflict with SC-003/SC-004 |
| VII | Deterministic and Bounded AI | Temperature 0; pinned model identifier; versioned prompt files; Pydantic-validated structured output; cache keyed on (content hash, prompt version, model id); Ask state persisted; per-call token budget enforced by the adapter; Ask turns answered without prior context (R19) | **PASS** — FR-073's no-recharge-on-resume is satisfied by the same cache key |
| VIII | AI Guardrails and Safety | Retrieved text delimited and labelled untrusted (FR-033); model output never constructs an operation; output escaped; spend ceilings enforced server-side (FR-046, FR-080); explicit refusal below threshold (FR-030, FR-076); usernames masked before provider calls (R1); untrusted text rendered as escaped text with `{@html}` lint-banned (R10) | **PASS** |
| IX | AI Evaluation and Observability | Labelled sets committed before AI features ship; regression gate on prompt, model, chunking, or retrieval changes — now explicitly including the refusal threshold (FR-077); retrieval scored directly by recall at k and claim traceability (R12); non-LLM baseline; telemetry on every call | **PASS** |

**Post-design re-check**: re-evaluated after Phase 1. No violations. The two conditions carried by
the previous revision of this plan are both resolved by constitution v1.2.2, and Complexity Tracking
is consequently empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-reddit-audience-intelligence/
├── plan.md              # This file
├── spec.md              # Feature specification (with Clarifications section)
├── research.md          # Phase 0 output — R1–R23
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── rest-api.md
│   └── module-interfaces.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/               # All schema changes ship as migrations
├── app/
│   ├── main.py                     # App init, router registration, bind guard (FR-078)
│   ├── config.py                   # Settings from .env; the only place secrets are read
│   ├── dependencies.py             # Shared FastAPI dependencies
│   │
│   ├── reddit/                     # Module 1 — the ONLY module importing PRAW
│   │   ├── client.py               # Rate-limited, quota-accounted client
│   │   ├── search.py               # Widened "all of Reddit" scope (R9)
│   │   ├── availability.py         # Deletion / removal re-check (R13, FR-067)
│   │   ├── cache.py                # Redis caching with defined TTLs
│   │   ├── schemas.py              # Normalized types; PRAW objects stop here
│   │   └── quota.py                # Quota budgeting and telemetry
│   │
│   ├── audiences/                  # Module 2 — audiences, starter set, suggestions
│   ├── feed/                       # Module 3 — aggregation, dedup, search over saved material
│   ├── ai/                         # Module 4 — topics, themes, patterns, sentiment, Ask
│   │   ├── adapter.py              # Single LLM access point; pinned model id
│   │   ├── baseline.py             # Non-LLM topic extraction (Constitution IX)
│   │   ├── retrieval.py            # Threshold gate for refusal (R16, FR-076)
│   │   ├── runner.py               # Chunked, resumable analysis (R15, FR-072–074)
│   │   ├── telemetry.py            # Per-call cost / latency / cache-hit records
│   │   ├── trends.py               # Share-of-discussion aggregates (R6)
│   │   └── prompts/                # Versioned prompt files, never inline
│   │
│   ├── alerts/                     # Module 5 — rules, matches (in-app only)
│   │   ├── rule_service.py         # Rule lifecycle
│   │   ├── intent_service.py       # Rule intent embedding, recomputed on edit (R18)
│   │   └── evaluation_service.py   # Keyword + intent matching with degradation (FR-085)
│   ├── users/                      # Module 6 — auth, bookmarks, notes, lead status
│   ├── ops/                        # Usage, cost, quota, freshness, thresholds
│   └── common/                     # database, redis, exceptions, middleware, pagination
│
├── workers/
│   ├── celery_app.py
│   ├── tasks/
│   │   ├── ingest.py               # Fetch + dedup + persist
│   │   ├── comments.py             # Threshold-gated comment collection (R5)
│   │   ├── snapshot.py             # Daily community stats — never skipped (R3)
│   │   ├── recheck.py              # Availability re-check + purge (R13)
│   │   ├── backup.py               # Nightly dump + restore verification (R14)
│   │   ├── alerts.py               # Evaluate rules against the new batch (R8)
│   │   ├── embed.py                # Chunk + embed into pgvector (R2)
│   │   └── analyze.py              # Chunked, resumable interpretation (R15)
│   └── schedules.py
│
└── tests/
    ├── unit/
    └── integration/

evals/                              # Constitution IX
├── datasets/                       # Labeled: themes, sentiment, retrieval (incl. unanswerable)
├── run_eval.py                     # Also tunes the refusal threshold (R16)
└── results/

frontend/                             # SvelteKit, adapter-static — SSR off (R10)
├── src/
│   ├── design/                     # Tokens + primitives, established before screens (R10)
│   ├── components/                 # Shared components incl. the four-state data wrapper (*.svelte)
│   ├── routes/                     # File-based routing, e.g. routes/audiences/[id]/feed/+page.svelte
│   └── services/                   # Generated/typed API client
└── tests/
```

**Structure Decision**: Web application with `backend/` and `frontend/` at the repository root,
matching the layout documented in `README.md`. The backend is a modular monolith: boundaries are
enforced in code per Constitution II so extraction into services stays possible, but a single
deployable is correct at this scale.

Three directories depart from the README's tree, all deliberate. `backend/app/ops/` gives the
transparency surfaces (FR-044–FR-047) and the configured thresholds a home rather than scattering
them. Top-level `evals/` sits outside `backend/` because it is a measurement artifact of the project,
not application code. And `workers/tasks/recheck.py` and `backup.py` are new in this revision —
neither existed before the clarification session, and both are unglamorous jobs that protect data
nothing else can restore.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified.

No violations. The two conditions carried by the previous revision — the latency budget conflict and
the fixed-vocabulary gap — were resolved by constitution v1.2.2 rather than justified as deviations.
