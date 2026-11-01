---

description: "Task list for Reddit Audience Intelligence"
---

# Tasks: Reddit Audience Intelligence

**Input**: Design documents from `/specs/001-reddit-audience-intelligence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Test tasks are included and are **not optional here**. Constitution IV requires
service-layer logic to be written test-first, forbids any test contacting Reddit or a model provider,
and sets an 80% service-layer coverage floor.

**Organization**: Tasks are grouped by user story so each can be implemented, tested, and delivered
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: Which user story the task belongs to (US1–US8)
- Every task names an exact file path
- Task IDs are stable and unique but not contiguous in document order. Tasks added after the first
  draft take the next free number rather than renumbering everything below them; execute in document
  order, not numeric order.
- T181–T200 were added on 2026-11-01 to resolve `/speckit-analyze` findings C3–C6: retrieval
  measurement, missing test-first tasks, the context budget, and untrusted-text handling. T201–T204
  resolve findings H3 (secret redaction) and H1 (scored themes). Findings H2, M1–M10, and L1–L5 were
  resolved by amending existing task descriptions rather than adding tasks.

## Path Conventions

Web application per plan.md: `backend/app/`, `backend/workers/`, `backend/tests/`, `frontend/src/`,
`evals/` at the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and tooling

- [X] T001 Create the backend, workers, tests, frontend, and evals directory tree per plan.md
- [X] T002 Add FastAPI, PRAW, Celery, SQLAlchemy, Alembic, Pydantic, pgvector, and the LLM provider SDK to requirements.txt
- [X] T003 [P] Configure ruff lint and format rules in backend/pyproject.toml
- [X] T004 [P] Configure pytest, pytest-asyncio, and a hard-failing 80% service-layer coverage gate in backend/pyproject.toml so every run enforces Constitution IV rather than deferring it
- [X] T005 [P] Create docker-compose.yml at repo root with PostgreSQL plus the pgvector extension and Redis
- [X] T006 Initialize Alembic in backend/alembic/ with an async migration environment
- [X] T007 [P] Create backend/app/config.py reading all settings from .env — the only module permitted to read secrets
- [X] T008 [P] Create .env.example documenting Reddit credentials, provider credentials, the pinned model identifier, and the exposure flag
- [X] T009 Initialize the SvelteKit application (adapter-static, SSR off — R10) in frontend/
- [X] T010 [P] Create the evals/ tree with datasets/, results/, and a run_eval.py entry point

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infrastructure every user story depends on

**⚠️ CRITICAL**: No user story work begins until this phase completes.

### Common infrastructure

- [X] T011 Implement the async engine and session factory in backend/app/common/database.py
- [X] T012 [P] Implement the Redis connection pool in backend/app/common/redis.py
- [X] T013 [P] Define typed exception classes in backend/app/common/exceptions.py
- [X] T014 Implement error-envelope middleware translating typed exceptions to the shared error shape in backend/app/common/middleware.py
- [X] T015 [P] Implement the shared pagination envelope and max page size in backend/app/common/pagination.py
- [X] T016 Create the FastAPI application and router registration in backend/app/main.py

### Deployment posture (FR-078–FR-081)

> Built now because every one of these is cheap first and a migration later.

- [X] T017 [P] Write failing tests for the startup bind guard in backend/tests/unit/test_bind_guard.py
- [X] T018 Implement the loopback-by-default bind guard that refuses a non-local interface without the explicit exposure flag in backend/app/main.py
- [X] T019 [P] Write failing tests for credential hashing and session expiry in backend/tests/unit/test_auth_service.py
- [X] T020 Implement hashed credential storage, expiring and invalidatable sessions in backend/app/users/auth_service.py
- [X] T021 Implement the current_user dependency in backend/app/dependencies.py
- [X] T022 Implement server-side rate limiting applied to every paid-call endpoint in backend/app/common/limits.py

> **T177–T180 were added after T022 shipped**, and belong to this block rather than to the end of the
> file — they take the next free IDs per the numbering rule above and run here in document order.
> T017–T022 built everything needed to *carry* a session but nothing that *issues* one:
> `contracts/rest-api.md` required every endpoint to be authenticated and contracted no route to sign
> in, so `CurrentUser` was unsatisfiable over HTTP and T058 was blocked.

- [X] T177 Amend the API contract with the session endpoints in specs/001-reddit-audience-intelligence/contracts/rest-api.md
- [X] T178 [P] Write failing tests for the session endpoints in backend/tests/integration/test_auth_routes.py
- [X] T179 Implement the client-keyed rate limiter for unauthenticated endpoints in backend/app/common/limits.py
- [X] T180 Implement the sign-in, sign-out, and current-session routes in backend/app/users/router.py

> **T201–T202 were added after T180 shipped** (analysis finding H3). FR-079 forbids secrets in
> responses, logs, or anything the client can read, and no test held the code to it. The log
> statements were clean, but `Settings` held every secret as a plain `str`, so any `repr` of it, or an
> accidental log of it, printed them in full.

- [X] T201 [P] Write failing tests asserting secrets never appear in settings output, sign-in logs, or session logs in backend/tests/unit/test_secret_redaction.py and backend/tests/integration/test_auth_logging.py
- [ ] T202 Hold secret settings as SecretStr and unwrap them only at their point of use in backend/app/config.py

### Reddit data layer (Constitution I)

- [ ] T023 [P] Write failing tests for rate limiting, retry, and quota accounting in backend/tests/unit/test_reddit_client.py
- [ ] T024 [P] Define normalized Pydantic types in backend/app/reddit/schemas.py — PRAW objects stop here
- [ ] T025 [P] Implement quota budgeting and remaining-budget reporting in backend/app/reddit/quota.py
- [ ] T026 [P] Implement Redis caching with explicit TTLs, counting cache hits so Reddit calls avoided are reportable (Constitution IX), in backend/app/reddit/cache.py
- [ ] T027 Implement the rate-limited, quota-accounted PRAW client in backend/app/reddit/client.py
- [ ] T028 Write an architecture test asserting no module outside backend/app/reddit/ imports praw in backend/tests/unit/test_module_boundaries.py

### Telemetry and spend control

- [ ] T029 [P] Define UsageRecord, InferenceCache, SpendLedger, and BackupRun models in backend/app/ops/models.py
- [ ] T030 [P] Write failing tests for spend-ceiling enforcement before a call in backend/tests/unit/test_spend_ledger.py
- [ ] T031 Implement record_usage and check_spend_allowed in backend/app/ops/service.py
- [ ] T032 Create the Alembic migration for the ops tables in backend/alembic/versions/

### Base entities

- [ ] T033 [P] Define Community and CommunitySnapshot models in backend/app/reddit/models.py
- [ ] T034 [P] Define Post and Comment models with availability and purged_at fields in backend/app/feed/models.py
- [ ] T035 Create the Alembic migration for base entities and the pgvector extension in backend/alembic/versions/

### Background work

- [ ] T036 Configure the Celery application in backend/workers/celery_app.py
- [ ] T037 Define the Celery Beat schedule registry in backend/workers/schedules.py

### Snapshot collection — start immediately (R3, FR-038)

> This job accumulates the only history the product will ever have. Every day it is not running is a
> permanently missing data point, so it ships before the UI that consumes it.

- [ ] T038 [P] Write failing tests for daily statistics capture in backend/tests/unit/test_snapshot_task.py
- [ ] T039 Implement the daily community statistics snapshot in backend/workers/tasks/snapshot.py
- [ ] T040 Register the snapshot task on the daily Beat schedule in backend/workers/schedules.py

### Durability (FR-070, FR-071)

> Build before there is data worth losing. The common failure is an unrestorable backup, not a
> missing one.

- [ ] T041 [P] Write failing tests for backup record creation and retention pruning in backend/tests/unit/test_backup_task.py
- [ ] T042 Implement the nightly dump to a volume outside the container with rolling retention in backend/workers/tasks/backup.py
- [ ] T043 Write the documented restore procedure and verification script in scripts/verify_restore.sh
- [ ] T044 Register the backup task on the nightly Beat schedule in backend/workers/schedules.py

### Frontend foundation (R10, Constitution V)

- [ ] T045 [P] Define design tokens with light and dark palettes in frontend/src/design/tokens.ts
- [ ] T046 [P] Implement the shared four-state data wrapper (loading, empty, error, populated) in frontend/src/components/DataView.svelte
- [ ] T047 Implement the typed API client with shared pagination and error handling in frontend/src/services/client.ts

**Checkpoint**: Foundation ready — user story work can begin.

---

## Phase 3: User Story 1 — Build an audience and read its feed (Priority: P1) 🎯 MVP

**Goal**: A researcher groups communities into a named audience and reads one deduplicated timeline
across all of them, sorted and readable in-app.

**Independent Test**: Create an audience from three communities, open its feed, sort it three ways,
read a post in full, and confirm cross-posted content appears once — without visiting Reddit.

### Tests for User Story 1

- [ ] T048 [P] [US1] Contract tests for the audiences endpoints in backend/tests/integration/test_audiences_api.py
- [ ] T049 [P] [US1] Contract tests for the feed endpoint in backend/tests/integration/test_feed_api.py
- [ ] T050 [P] [US1] Unit tests for the 50-community cap and duplicate rejection in backend/tests/unit/test_audience_service.py
- [ ] T051 [P] [US1] Unit tests for cross-post and verbatim-repost collapsing in backend/tests/unit/test_dedup.py
- [ ] T052 [P] [US1] Integration test covering create audience through populated feed in backend/tests/integration/test_audience_feed_journey.py
- [ ] T182 [P] [US1] Unit tests for starter-audience copy-on-save — the copy and the original stay independent in both directions (FR-006) — in backend/tests/unit/test_starter_service.py
- [ ] T183 [P] [US1] Unit tests for related-community suggestions — ranked by R22's term overlap, never suggesting a community already in the audience or one that is unavailable — in backend/tests/unit/test_suggestions.py
- [ ] T198 [P] [US1] Write failing tests for untrusted-text rendering — markup shown as text, URLs as click-only links, images never embedded (R10) — in frontend/src/components/untrusted-text.test.ts

### Implementation for User Story 1

- [ ] T053 [P] [US1] Define Audience, AudienceCommunity, and StarterAudience models in backend/app/audiences/models.py
- [ ] T054 [US1] Create the Alembic migration for audience tables in backend/alembic/versions/
- [ ] T055 [US1] Implement audience CRUD enforcing the 50-community cap and no duplicates in backend/app/audiences/service.py
- [ ] T056 [US1] Implement starter-audience browsing and copy-on-save with no live link in backend/app/audiences/starter_service.py
- [ ] T057 [US1] Implement related-community suggestions per R22 in backend/app/audiences/suggestions.py
- [ ] T058 [US1] Implement audience routes with per-condition errors for unavailable communities in backend/app/audiences/router.py
- [ ] T059 [P] [US1] Implement cross-post and content-hash deduplication in backend/app/feed/dedup.py
- [ ] T060 [US1] Implement feed aggregation, sorting, and pagination, carrying the audience's last_refreshed_at (FR-013), in backend/app/feed/feed_service.py
- [ ] T061 [US1] Implement feed and single-post routes in backend/app/feed/router.py
- [ ] T062 [US1] Implement post ingestion with dedup and persistence in backend/workers/tasks/ingest.py
- [ ] T063 [US1] Register per-audience ingestion on the Beat schedule with rate-derived cadence, reporting when the derived cadence cannot meet SC-014's 15 minutes within quota, in backend/workers/schedules.py
- [ ] T064 [P] [US1] Author the shipped starter audiences seed data in backend/scripts/seed_starter_audiences.py
- [ ] T065 [P] [US1] Build the audience list and creation screens, with the deletion warning that saved analysis becomes unreachable (FR-003), in frontend/src/routes/audiences/
- [ ] T066 [US1] Build the feed view using the four-state wrapper, showing when the audience was last refreshed (FR-013), in frontend/src/routes/audiences/[id]/feed/+page.svelte
- [ ] T199 [US1] Implement the untrusted-text renderer, and pin svelte/no-at-html-tags to error explicitly, in frontend/src/components/untrusted-text.ts and frontend/eslint.config.js
- [ ] T067 [US1] Build the in-app post preview, rendering body text only through the untrusted-text renderer (R10), in frontend/src/components/PostPreview.svelte

### Deletion obligations — created by this story (FR-067–FR-069)

> US1 is where material is first collected, so it is where the obligation to honour deletion begins.

- [ ] T068 [P] [US1] Write failing tests for purge, tombstone retention, and bookmark exemption in backend/tests/unit/test_purge.py
- [ ] T069 [US1] Implement batched availability checking in backend/app/reddit/availability.py
- [ ] T070 [US1] Implement the re-check and purge task clearing text while retaining tombstones, and recording edits at the source in edited_at_source, in backend/workers/tasks/recheck.py
- [ ] T071 [US1] Register the availability re-check on the Beat schedule in backend/workers/schedules.py

### Degraded operation and content flagging for User Story 1 (FR-049, FR-051, SC-012)

- [ ] T172 [P] [US1] Write failing integration tests for browsing and searching with the source unavailable in backend/tests/integration/test_degraded_mode.py
- [ ] T173 [US1] Implement degraded-mode serving from collected material with an explicit staleness notice in backend/app/feed/feed_service.py
- [ ] T174 [US1] Capture the adult-content flag on ingestion and surface it before a post is opened in backend/app/feed/models.py and frontend/src/components/PostPreview.svelte

**Checkpoint**: US1 is independently shippable and is the MVP.

---

## Phase 4: User Story 2 — Search an audience (Priority: P2)

**Goal**: Keyword search across an audience with filters, plus an explicitly-marked widened scope.

**Independent Test**: Search an audience over a month, disable a keyword, exclude a community and an
author, and confirm the result set changes accordingly.

### Tests for User Story 2

- [ ] T072 [P] [US2] Contract tests for the search endpoint across all three scopes in backend/tests/integration/test_search_api.py
- [ ] T073 [P] [US2] Unit tests for keyword enable/disable and include/exclude filters in backend/tests/unit/test_search_service.py
- [ ] T074 [P] [US2] Unit test asserting live-scope results are never persisted into the corpus in backend/tests/unit/test_live_search_isolation.py

### Implementation for User Story 2

- [ ] T075 [US2] Implement saved-material search with keyword, time, author, and community filters, sort order and result limit (FR-016), and deleted-account authors filterable as one value, in backend/app/feed/search_service.py
- [ ] T076 [P] [US2] Implement the widened all-of-Reddit search path in backend/app/reddit/search.py
- [ ] T077 [US2] Implement search routes defaulting to saved-material scope in backend/app/feed/router.py
- [ ] T078 [US2] Build the search screen using the four-state wrapper, with scope selector and live-results warning, in frontend/src/routes/search/+page.svelte

---

## Phase 5: User Story 3 — Topics, themes, and trends (Priority: P3)

**Goal**: Interpret an audience into topics and themes with descriptions, patterns, sentiment, and a
direction of travel over time.

**Independent Test**: Open analysis for an audience with a few hundred posts, drill into a theme, view
its patterns and trend, and confirm a fresh audience reports insufficient material instead of
inventing results.

### Evaluation harness first (Constitution IX)

> The labeled sets are a prerequisite of the AI work, not a follow-up to it — without them the first
> prompt change ships unmeasured.

- [ ] T079 [P] [US3] Label a theme and topic reference sample in evals/datasets/themes.jsonl
- [ ] T080 [P] [US3] Label a sentiment reference sample in evals/datasets/sentiment.jsonl
- [ ] T081 [US3] Implement the scoring harness reporting model and baseline side by side in evals/run_eval.py

### Tests for User Story 3

- [ ] T082 [P] [US3] Contract tests for the analysis and trends endpoints in backend/tests/integration/test_analysis_api.py
- [ ] T083 [P] [US3] Unit tests asserting temperature 0, pinned model, and cache key composition in backend/tests/unit/test_ai_adapter.py
- [ ] T084 [P] [US3] Unit tests for share-of-discussion, collection coverage, distinct post and author counts (FR-054), and R6's minimum period for a direction in backend/tests/unit/test_trends.py
- [ ] T085 [P] [US3] Unit tests for chunked commit, cursor advance, and resume without re-charge in backend/tests/unit/test_analysis_runner.py
- [ ] T196 [P] [US3] Write failing tests asserting the adapter refuses an over-budget context before any provider call, using R19's estimate, in backend/tests/unit/test_context_budget.py
- [ ] T200 [P] [US3] Write failing tests asserting prompt assembly omits author fields and masks u/ mentions before any provider call (R1) in backend/tests/unit/test_prompt_privacy.py
- [ ] T184 [P] [US3] Unit tests for theme tagging and topic extraction against a mocked adapter — interpreted themes, sub-categories, post linkage, per-post language (R23), and schema-invalid output surfaced rather than salvaged — in backend/tests/unit/test_theme_service.py
- [ ] T185 [P] [US3] Unit tests for sentiment scoring against a mocked adapter in backend/tests/unit/test_sentiment_service.py
- [ ] T186 [P] [US3] Unit tests for pattern detection against a mocked adapter in backend/tests/unit/test_pattern_service.py
- [ ] T187 [P] [US3] Unit tests asserting the non-LLM topic baseline is deterministic for a fixed corpus in backend/tests/unit/test_baseline.py
- [ ] T203 [P] [US3] Write failing tests for scored themes — community-relative ranking, window boundaries, deterministic tie-breaks, templated descriptions, sub-categories from interpreted themes, and no adapter call (R20) — in backend/tests/unit/test_scored_themes.py

### Comment collection for User Story 3 (FR-027, FR-027a, FR-027b)

> Analysis reads discussion, not just headlines — pain points concentrate in replies. Collection is
> placed here rather than in US1 because nothing before this story consumes comments, and unlike
> community snapshots, comments can be backfilled for posts still held.

- [ ] T166 [P] [US3] Write failing tests for relative engagement threshold selection across differently sized communities in backend/tests/unit/test_comment_threshold.py
- [ ] T167 [US3] Implement the community-relative engagement threshold in backend/app/reddit/comment_threshold.py
- [ ] T168 [US3] Implement threshold-gated top-level comment collection in backend/workers/tasks/comments.py
- [ ] T169 [US3] Chain comment collection after post ingestion in backend/workers/schedules.py

### Implementation for User Story 3

- [ ] T086 [US3] Implement the single LLM adapter with pinned model, temperature 0, schema validation, telemetry, an enforced input token budget (R19), and username masking (R1) in backend/app/ai/adapter.py
- [ ] T087 [P] [US3] Author versioned prompt templates in backend/app/ai/prompts/
- [ ] T088 [P] [US3] Define Topic, Theme, ThemePost, TopicPost, Pattern, DiscussionBucket, and AnalysisRun models in backend/app/ai/models.py
- [ ] T089 [US3] Create the Alembic migration for interpretation tables in backend/alembic/versions/
- [ ] T090 [US3] Implement theme tagging and topic extraction, recording each post's language from the structured output (R23), in backend/app/ai/theme_service.py
- [ ] T091 [P] [US3] Implement sentiment scoring in backend/app/ai/sentiment_service.py
- [ ] T092 [P] [US3] Implement pattern detection in backend/app/ai/pattern_service.py
- [ ] T093 [P] [US3] Implement the non-LLM topic extraction baseline in backend/app/ai/baseline.py
- [ ] T204 [US3] Implement scored themes, reading posts through feed's service functions and run before interpretation regardless of spend or model availability (R20), in backend/app/ai/scored_theme_service.py and backend/workers/tasks/analyze.py
- [ ] T094 [US3] Implement share-of-discussion aggregation with coverage tracking and distinct post and author counts (FR-054) in backend/app/ai/trends.py
- [ ] T095 [US3] Implement the chunked, cursor-resumable analysis runner in backend/app/ai/runner.py
- [ ] T096 [US3] Implement analysis routes exposing analysis_state, sufficiency per R6's threshold, and non_english_share (R23) in backend/app/ai/router.py
- [ ] T097 [US3] Implement the analysis worker task chaining from ingestion in backend/workers/tasks/analyze.py
- [ ] T098 [US3] Build the analysis and theme-detail screens using the four-state wrapper, with partial-state rendering and a reduced-reliability flag above R23's non-English share, in frontend/src/routes/audiences/[id]/analysis/+page.svelte
- [ ] T099 [US3] Build the trend chart showing coverage gaps rather than smoothing them in frontend/src/components/TrendChart.svelte
- [ ] T170 [US3] Populate and expose derived_from_comments on topics and themes in backend/app/ai/theme_service.py and backend/app/ai/router.py
- [ ] T171 [US3] Wire pattern and sentiment into saved-material search responses, signalling availability per FR-020, in backend/app/feed/search_service.py

---

## Phase 6: User Story 4 — Ask with citations (Priority: P4)

**Goal**: Plain-language questions answered from the audience's own material, with citations and an
honest refusal when the material does not support an answer.

**Independent Test**: Ask an answerable question and verify cited posts; ask an unanswerable one and
verify refusal rather than a general-knowledge answer.

### Tests for User Story 4

- [ ] T100 [P] [US4] Label question-to-post relevance including unanswerable questions in evals/datasets/retrieval.jsonl
- [ ] T181 [US4] Extend the scoring harness with retrieval recall at k and claim traceability over evals/datasets/retrieval.jsonl, per R12, in evals/run_eval.py
- [ ] T101 [P] [US4] Contract tests for the ask endpoint covering answered, refused, and failed outcomes in backend/tests/integration/test_ask_api.py
- [ ] T102 [P] [US4] Unit tests for the refusal gate at the minimum-count and floor boundaries in backend/tests/unit/test_retrieval_gate.py
- [ ] T103 [P] [US4] Unit test asserting retrieved text is delimited as untrusted and never followed as instructions in backend/tests/unit/test_prompt_injection.py
- [ ] T104 [P] [US4] Unit test asserting a mid-stream failure is not stored or shown as an answer in backend/tests/unit/test_ask_failure.py
- [ ] T188 [P] [US4] Unit tests for paragraph-aware chunking — paragraph boundaries, the hard size ceiling with sentence splitting (R19), and the model identifier recorded per chunk — in backend/tests/unit/test_chunking.py
- [ ] T189 [P] [US4] Unit tests asserting chunk purge removes every chunk of purged material and nothing else in backend/tests/unit/test_chunk_purge.py
- [ ] T197 [P] [US4] Write failing tests for Ask context assembly — no prior turns, passages admitted whole in rank order within the budget, and startup validation that the gate's minimum count fits (R19) — in backend/tests/unit/test_ask_context.py

### Implementation for User Story 4

- [ ] T105 [P] [US4] Define ContentChunk with a pgvector column and model identifier in backend/app/ai/chunk_models.py
- [ ] T106 [US4] Create the Alembic migration for chunks and the vector index in backend/alembic/versions/
- [ ] T107 [US4] Implement paragraph-aware chunking and embedding in backend/app/ai/embedding_service.py
- [ ] T108 [US4] Implement the embedding worker task in backend/workers/tasks/embed.py
- [ ] T109 [US4] Implement chunk purging when source material is purged in backend/app/ai/purge.py
- [ ] T110 [US4] Implement the deterministic refusal gate with configurable count and floor in backend/app/ai/retrieval.py
- [ ] T111 [P] [US4] Define AskSession, AskTurn with three-valued outcome, and AskCitation in backend/app/ai/ask_models.py
- [ ] T112 [US4] Implement the streamed, cited Ask pipeline — structured claims each naming their passages (R12), context assembled under R19's budget with no prior turns — in backend/app/ai/ask_service.py
- [ ] T113 [US4] Implement ask routes with streaming and outcome reporting in backend/app/ai/router.py
- [ ] T114 [US4] Build the Ask screen using the four-state wrapper, rendering citations (purged sources as tombstones), refusals, and failures distinctly, with answer text only through the untrusted-text renderer (R10), in frontend/src/routes/audiences/[id]/ask/+page.svelte

---

## Phase 7: User Story 5 — Keyword alerts (Priority: P5)

**Goal**: Standing rules evaluated against newly collected material, surfaced in-app.

**Independent Test**: Create a rule, run a collection cycle containing a match, and confirm it appears
with the rule and matched terms named — and that editing the rule leaves the match intact.

### Tests for User Story 5

- [ ] T115 [P] [US5] Contract tests for rule lifecycle and match listing in backend/tests/integration/test_alerts_api.py
- [ ] T116 [P] [US5] Unit test asserting matches survive rule edit and deletion in backend/tests/unit/test_alert_persistence.py
- [ ] T117 [P] [US5] Unit tests for broad-match detection at R8's threshold and degraded-community handling in backend/tests/unit/test_alert_evaluation.py
- [ ] T176 [P] [US5] Test, on FakeClock rather than wall-clock time, that the ingestion cadence plus the evaluation stage surfaces a match within 15 minutes of collection per SC-014, in backend/tests/integration/test_alert_latency.py
- [ ] T190 [P] [US5] Unit tests for match listing — one post matched by several rules appears once, naming every rule it matched — in backend/tests/unit/test_match_service.py

### Implementation for User Story 5

- [ ] T118 [P] [US5] Define AlertRule and AlertMatch models with soft deletion in backend/app/alerts/models.py
- [ ] T119 [US5] Create the Alembic migration for alert tables in backend/alembic/versions/
- [ ] T120 [US5] Implement rule lifecycle management in backend/app/alerts/rule_service.py
- [ ] T121 [US5] Implement new-batch-only evaluation with broad-match reporting, recording last_evaluated_at so an idle rule reads as active rather than broken, in backend/app/alerts/evaluation_service.py
- [ ] T122 [US5] Implement match listing grouped so one post appears once in backend/app/alerts/match_service.py
- [ ] T123 [US5] Implement alert routes in backend/app/alerts/router.py
- [ ] T124 [US5] Insert alert evaluation into the ingestion chain in backend/workers/tasks/alerts.py
- [ ] T125 [US5] Build the rules and matches screens using the four-state wrapper, with act-in-place controls, in frontend/src/routes/alerts/

### Intent matching for User Story 5 (FR-082–FR-085)

> Additive to keyword matching, never a replacement. Keyword rules must keep working when the
> retrieval capability is absent or failing, so US5 still ships standalone if US4 has not been built.

- [ ] T157 [P] [US5] Label an intent-paraphrase reference set with positive paraphrases and unrelated controls in evals/datasets/alert_intents.jsonl
- [ ] T158 [P] [US5] Write failing tests for paraphrase recall and the false-positive ceiling in backend/tests/unit/test_intent_matching.py
- [ ] T159 [P] [US5] Write failing tests asserting keyword matching survives when embeddings are unavailable in backend/tests/unit/test_alert_degradation.py
- [ ] T160 [US5] Extend AlertRule with match_mode, intent_text, intent_embedding, and similarity_threshold in backend/app/alerts/models.py
- [ ] T161 [US5] Create the Alembic migration for intent fields and the rule vector index in backend/alembic/versions/
- [ ] T162 [US5] Implement intent embedding on rule create and edit, with recomputation when intent_text changes, in backend/app/alerts/intent_service.py
- [ ] T163 [US5] Implement intent matching against new material with keyword-only fallback in backend/app/alerts/evaluation_service.py
- [ ] T164 [US5] Surface match_mode, similarity, and intent_matching_active in routes and the alerts screens in backend/app/alerts/router.py and frontend/src/routes/alerts/

---

## Phase 8: User Story 6 — Community discovery (Priority: P6)

**Goal**: Find communities worth tracking by search, ranking, tags, and accumulated history.

**Independent Test**: Search by topic, filter by size band, sort by activity, inspect tags and
history, and add a result to an audience.

### Tests for User Story 6

- [ ] T126 [P] [US6] Contract tests for discovery and history endpoints in backend/tests/integration/test_discovery_api.py
- [ ] T127 [P] [US6] Unit tests for size, newness, and activity tag derivation per R21 in backend/tests/unit/test_community_tags.py
- [ ] T128 [P] [US6] Unit test asserting insufficient history returns a period rather than a trend in backend/tests/unit/test_history_guard.py
- [ ] T191 [P] [US6] Unit tests for ranking by size, activity, and growth (R21's coverage rule included) with membership-band and time-window filters in backend/tests/unit/test_ranking_service.py
- [ ] T192 [P] [US6] Unit tests for history series assembly from snapshots, including gaps left by missed snapshot days, in backend/tests/unit/test_history_service.py

### Implementation for User Story 6

- [ ] T129 [US6] Implement community search by name, description, and topic in backend/app/reddit/discovery_service.py
- [ ] T130 [US6] Implement ranking by size, activity, and growth (R21) with membership-band and time-window filters (FR-035) in backend/app/reddit/ranking_service.py
- [ ] T131 [P] [US6] Implement tag derivation in backend/app/reddit/tags.py
- [ ] T132 [US6] Implement history series assembly from snapshots in backend/app/reddit/history_service.py
- [ ] T133 [US6] Implement discovery routes in backend/app/reddit/router.py
- [ ] T134 [US6] Build the discovery screen using the four-state wrapper, with tags, filters, and add-to-audience, in frontend/src/routes/communities/

---

## Phase 9: User Story 7 — Bookmarks and lead tracking (Priority: P7)

**Goal**: Bookmark posts with private notes and a status, filterable by state.

**Independent Test**: Bookmark from feed, search, and an alert match; set a status; filter by it;
confirm a bookmark of deleted material still shows captured text.

### Tests for User Story 7

- [ ] T135 [P] [US7] Contract tests for bookmark CRUD and status filtering in backend/tests/integration/test_bookmarks_api.py
- [ ] T136 [P] [US7] Unit test asserting captured content survives source deletion and is destroyed with the bookmark in backend/tests/unit/test_bookmark_capture.py
- [ ] T193 [P] [US7] Unit tests for bookmark notes and status transitions, including the status filter, in backend/tests/unit/test_bookmark_service.py

### Implementation for User Story 7

- [ ] T137 [P] [US7] Define the Bookmark model with captured content and status in backend/app/users/models.py
- [ ] T138 [US7] Create the Alembic migration for bookmarks in backend/alembic/versions/
- [ ] T139 [US7] Implement bookmark capture, notes, and status transitions in backend/app/users/bookmark_service.py
- [ ] T140 [US7] Implement bookmark routes with status filtering in backend/app/users/router.py
- [ ] T141 [US7] Build the bookmarks screen using the four-state wrapper, with status controls and a destructive-delete warning, in frontend/src/routes/bookmarks/

---

## Phase 10: User Story 8 — Cost and freshness transparency (Priority: P8)

**Goal**: Make spend, latency, reuse, quota, freshness, and measured accuracy visible.

**Independent Test**: Run an analysis and an Ask, then confirm the usage view reflects spend, reuse,
and last-refreshed time — and that exhausting a ceiling fails clearly.

### Tests for User Story 8

- [ ] T142 [P] [US8] Contract tests for every /ops surface in backend/tests/integration/test_ops_api.py
- [ ] T143 [P] [US8] Unit test asserting an exhausted ceiling refuses rather than continuing to spend in backend/tests/unit/test_spend_ceiling_enforcement.py
- [ ] T194 [P] [US8] Unit tests for usage, quota, Reddit-calls-avoided, and freshness aggregation, per audience and in aggregate, in backend/tests/unit/test_summary_service.py
- [ ] T195 [P] [US8] Unit tests for published evaluation results — latest run per capability, model and baseline side by side — in backend/tests/unit/test_ops_evaluation_service.py

### Implementation for User Story 8

- [ ] T144 [US8] Implement usage, quota, Reddit-calls-avoided, and freshness aggregation in backend/app/ops/summary_service.py
- [ ] T145 [P] [US8] Implement surfaces for the retrieval refusal threshold, the comment engagement threshold, and backup status, reporting each as not yet available until its owning story lands, in backend/app/ops/status_service.py
- [ ] T146 [P] [US8] Implement published evaluation results reporting, stating when no evaluation has run yet, in backend/app/ops/evaluation_service.py
- [ ] T147 [US8] Implement ops routes in backend/app/ops/router.py
- [ ] T148 [US8] Build the transparency dashboard using the four-state wrapper in frontend/src/routes/ops/

---

## Phase 11: Polish & Cross-Cutting Concerns

- [ ] T149 [P] Verify README still links to contracts/rest-api.md rather than restating the API surface, per Constitution III
- [ ] T175 [P] Measure the duplicate rate over a real corpus against SC-011's 2% ceiling in backend/scripts/measure_dedup.py
- [ ] T150 [P] Tune the refusal threshold against the labeled unanswerable set and record before/after scores in evals/results/
- [ ] T151 [P] Tune the comment engagement threshold against observed collection volume in backend/app/config.py
- [ ] T152 Confirm the coverage gate from T004 has been enforcing throughout and was never bypassed or lowered
- [ ] T153 [P] Confirm all endpoints paginate, avoid N+1 queries, and meet the server-side p95 budgets, measured with an audience at the 50-community maximum (SC-013)
- [ ] T154 [P] Perform and document a real restore from a real backup per scripts/verify_restore.sh
- [ ] T155 [P] Write the demo corpus seeding script in backend/scripts/seed_demo_corpus.py
- [ ] T156 Execute all twelve quickstart.md scenarios end to end and record the results
- [ ] T165 [P] Tune the alert intent similarity threshold against evals/datasets/alert_intents.jsonl and record before/after recall and false-positive rates in evals/results/

---

## Dependencies

### Story completion order

```text
Setup (T001–T010)
   └─> Foundational (T011–T047, T177–T180, T201–T202)  ⚠️ blocks everything
          ├─> US1 (P1)  ──> US2 (P2)      # search needs the corpus US1 collects
          │      │
          │      ├────────> US3 (P3) ──> US4 (P4)   # Ask needs interpretation + chunks
          │      ├────────> US5 (P5)                # alerts need ingestion, not analysis
          │      ├────────> US6 (P6)                # discovery needs snapshots (from Foundational)
          │      └────────> US7 (P7)
          └─> US8 (P8)                              # core needs telemetry only; T145/T146 degrade until US3/US4
```

### Hard dependencies

- US2, US3, US5, US6, US7 all require US1's ingestion to have collected material.
- US5's **keyword** matching has no AI dependency and can ship immediately after US1. Its **intent**
  matching (T157–T164) needs the embedding infrastructure from US4 (T105–T108). The two modes are
  deliberately separable: build US5 early for keyword alerts, and switch intent matching on once US4
  lands. This preserves US1 → US2 → US5 as a complete, AI-free, genuinely useful product.
- US4 requires US3's adapter and prompt infrastructure, plus its own chunk and retrieval work.
- US8's usage, quota, and freshness surfaces (T144) depend only on Foundational telemetry and can be
  built at any point after it. T145 and T146 report values owned by later stories (the comment
  threshold from US3, the refusal threshold from US4, evaluation results from T081), and must report
  each one as not yet available until its story lands, rather than waiting for them.
- **Cross-story file dependency**: T171 (US3) modifies `backend/app/feed/search_service.py`, which
  T075 (US2) creates. This is intended — FR-020 makes search analysis conditional, so US2 ships the
  search path and US3 adds analysis to it once the interpretation layer exists. T171 must not run
  before T075.
- US6's history views require Foundational's snapshot task to have been running for weeks — build the
  UI whenever, but expect it to display nothing meaningful until history accrues.

## Parallel Execution Examples

**Foundational**: T012, T013, T015 (distinct common modules); T024, T025, T026 (distinct reddit
modules); T029 and T033, T034 (distinct model files); T045, T046 (distinct frontend files).

**US1**: T048–T052, T182, T183, and T198 all touch different test files and can be written together. T053 and T059 are
independent. T064, T065 are independent of backend work.

**US3**: T079, T080 are pure labeling and parallelize with each other and with T082–T085 and T184–T187, T196, T200, T203. T091, T092,
T093 touch separate service files.

**US4**: T100–T104, T188, T189, and T197 parallelize fully; T181 follows T100, whose labels it scores. T105 and T111 are separate model files.

**Polish**: T149, T150, T151, T153, T154, T155 are mutually independent.

## Implementation Strategy

**MVP is Phase 1 through Phase 3** — Setup, Foundational, and US1. That yields a working multi-
community reader with deduplication, deletion handling, snapshot collection, and nightly backups. It
is genuinely demonstrable on its own and is the correct place to stop and evaluate.

**Then increment by story.** Each subsequent phase leaves the system shippable. US2 and US5 are the
cheapest next wins; US3 and US4 are the most differentiating and the most expensive.

**Two things run ahead of their story on purpose.** The snapshot task (T038–T040) sits in Foundational
because its output is a function of elapsed time — every day it is not running is permanently lost.
The evaluation datasets (T079, T080, T100) come before the AI services they measure, because
Constitution IX's regression gate is meaningless if the first prompt ships unmeasured.

**Order within a story**: tests → models → migration → services → routes → workers → frontend.
