<!--
Sync Impact Report
==================
Version change: 1.3.1 → 1.4.0
Rationale: MINOR. Principle V's fixed domain vocabulary replaces *subreddit* with
*community* — one subreddit tracked by the product — and states where "subreddit"
remains correct. Raised as finding C1 by /speckit-analyze: every design artifact
already names the concept "community" (the spec's Key Entities, the `Community` table
in data-model.md, and contracts/rest-api.md's `/audiences/{id}/communities` route and
`community_*` error codes), so the fixed term was the outlier, and T058 would have
shipped the conflict into a route. Changing which word the constitution mandates is
materially changed guidance rather than a clarification, hence MINOR.

"Subreddit" is not banned. It stays correct where the text is about Reddit's own
object rather than the product concept: inside `backend/app/reddit/` where it wraps
PRAW (the existing `obtain_subreddit()`), in Reddit API parameters, and in prose
explaining what a community is. The prohibition applies to UI copy, API fields,
database columns, and specification artifacts.

Modified principles:
  - V. UX Consistency — vocabulary list: *subreddit* → *community*, with the scope
    in which "subreddit" remains permitted.

Added sections: none. Removed sections: none. Other principles unchanged.

No previously compliant code becomes non-compliant: the only use of "subreddit" in
application code is in `backend/app/reddit/client.py`, which the amendment names as
permitted.

Follow-up outside this file: README.md gains the vocabulary list Principle V says it
fixes, which it did not previously contain.

Deferred TODOs: none

--- Carried forward from 1.3.1 ---

Version change: 1.3.0 → 1.3.1
Rationale: PATCH. The quality gate "API changes are reflected in `README.md`" now
reads "API changes are reflected in `contracts/rest-api.md`". The gate contradicted
Principle III, which since 1.2.3 names the feature's `contracts/rest-api.md` as the
single source of truth for the HTTP surface and forbids restating that surface in
`README.md`. The 1.2.3 amendment moved the source of truth in Principle III but missed
this gate, so the first change to the HTTP surface (the audiences router, T058) would
have had to break one rule or the other. The obligation — API documentation changes in
the same change set as the API — is unchanged; only its location is corrected to match
Principle III.

Modified sections:
  - Development Workflow and Quality Gates — the API-documentation gate points at
    `contracts/rest-api.md` instead of `README.md`.

Added sections: none. Removed sections: none. Principles I–IX unchanged.

No previously compliant code becomes non-compliant: the session endpoints
(T177–T180) already updated the contract rather than the README.

Deferred TODOs: none

--- Carried forward from 1.3.0 ---

Version change: 1.2.3 → 1.3.0
Rationale: MINOR. The Technology and Data Constraints section gains guidance it did
not have: an explicit exemption to "no data may exist only in Redis" for ephemeral
operational state. The rule was written to protect the collected corpus, which costs
Reddit quota to gather and cannot be re-fetched at will, but as worded it also
condemned two categories of state whose loss costs nothing of the kind — sessions and
rate-limit counters. Read strictly, it required session rows and per-window request
counters in PostgreSQL, which no design intends and which would put a write on the
system of record in front of every single request.

The exemption is bounded by a test, not by judgment: state qualifies only if it
reconstructs itself on the next request or costs a user one ordinary action to
recreate, and only the two named instances qualify today. Anything further needs its
own amendment.

Modified sections:
  - Technology and Data Constraints — the Redis rule now states what it protects
    (system of record and collected material) and names the ephemeral exemption,
    its test, and its two instances.

Added sections: none. Removed sections: none. Principles I–IX unchanged.

No previously compliant code becomes non-compliant. The amendment legitimizes code
already shipped under T020 (sessions in `backend/app/users/auth_service.py`) and T022
(rate-limit windows in `backend/app/common/limits.py`), each of which had been
carrying the reasoning in a module docstring as a contestable reading. Those hedges
are corrected to cite this section.

Deferred TODOs: none

--- Carried forward from 1.2.3 ---

Rationale: PATCH. Principle III now names the feature's `contracts/rest-api.md` as
the single source of truth for the HTTP surface, rather than `README.md`. Raised by
finding D1 of the cross-artifact analysis: the contract file did not exist when the
principle was written, and requiring the same API surface to be maintained in two
places guarantees drift. The obligation is unchanged — the contract must still be
updated in the same change set — only its target moves, so no previously compliant
code becomes non-compliant.

--- Carried forward from 1.2.2 ---

Two clarifications raised by the Constitution Check in
specs/001-reddit-audience-intelligence/plan.md. Neither adds, removes, nor
redefines a principle; both state precisely what an existing principle already
meant, so no previously compliant code becomes non-compliant.

Clarified principles:
  - V. UX Consistency — the fixed domain vocabulary now enumerates the terms this
    product actually uses, adding "alert rule", "alert match", and "status". These
    are new concepts introduced by the alerts and lead-tracking capabilities, not
    synonyms for existing terms, so the prohibition on synonyms is unchanged. The
    list is also stated to be extensible by amendment rather than closed, which is
    what it was already treated as.
  - VI. Performance and Efficiency — the latency budgets are now explicitly
    server-side p95 for the API response, measured at the application boundary.
    This resolves an apparent conflict with the end-to-end, user-perceived targets
    in the feature specification (SC-003, SC-004), which were never measuring the
    same thing. Both sets of numbers stand; the layer each applies to is now named.

Deferred TODOs: none

--- Carried forward from 1.2.1 ---

Project renamed: GummySearch → JammySearch. The original name belonged to a
commercial product that ceased operating on 2025-11-30; this project is an
independent implementation and is not affiliated with it.

--- Carried forward from 1.2.0 ---

Added principles:
  - VII. Deterministic and Bounded AI Behavior (determinism, prompt versioning,
    structured output, memory and context state management)
  - VIII. AI Guardrails and Safety (untrusted-content handling, prompt injection,
    output validation, PII, spend caps)
  - IX. AI Evaluation, Retrieval Quality, and Observability (labeled eval set,
    regression gate, retrieval metrics, per-call telemetry)

Modified sections:
  - Technology and Data Constraints: Pinecone replaced by pgvector inside
    PostgreSQL; eval tooling added
  - VI. Performance and Efficiency: external-service list updated for pgvector
  - Development Workflow and Quality Gates: AI-specific gates added

Unchanged principles: I, II, III, IV, V (text intact; numbering unchanged)

Removed sections: none

Deferred TODOs: none
-->

# JammySearch Constitution

## Core Principles

### I. Reddit Data Layer Isolation (NON-NEGOTIABLE)

The `backend/app/reddit/` module is the only code permitted to import PRAW or issue requests to the
Reddit API. Every other module — `audiences/`, `feed/`, `ai/`, `alerts/`, `users/`, and all Celery
workers — MUST consume Reddit data through this layer's wrapper functions and normalized Pydantic
schemas. Raw PRAW objects MUST NOT cross the module boundary; the data layer converts them into
project-owned schemas first. Caching, retry, and rate-limit handling live inside this layer and
nowhere else.

Rationale: Reddit imposes hard API quotas that are trivially exhausted by uncoordinated callers.
A single choke point is what makes quota accounting, caching, and future API migrations possible at
all — once a second module calls PRAW directly, none of those guarantees hold.

### II. Modular Boundaries and Code Quality

The backend is organized as modules (`reddit`, `audiences`, `feed`, `ai`, and later `alerts` and
`users`), each owning its own `router.py` / service layer / `models.py` / `schemas.py`. Cross-module
access MUST go through the owning module's service functions. A module MUST NOT query another
module's SQLAlchemy tables directly, and MUST NOT import another module's ORM models except for
declared foreign-key relationships. Genuinely shared helpers belong in `app/common/`, not in
whichever module happened to need them first.

Within a module, the following standards are enforced:

- Every function and method signature MUST carry type hints; `Any` requires an inline justification.
- All code MUST pass `ruff` lint and format checks before it is considered complete.
- Business logic lives in the service layer. Routers parse, delegate, and return — a router
  containing branching business rules or database queries MUST be refactored.
- Diagnostic output MUST use structured logging. `print` statements are prohibited outside scripts.
- Commented-out code, unreachable branches, and unused imports MUST be deleted rather than left in
  place; version control is the record of what was removed.
- Public service functions MUST have a docstring stating what they return and which external systems
  they touch.

Rationale: The architecture is designed so modules can be extracted into separate services later.
Direct table access silently destroys that option and turns every schema change into a cross-module
break. The quality rules exist because this codebase is meant to be read by contributors who did not
write it — untyped signatures and business logic hidden in routers are what make that impossible.

### III. Contract-First Interfaces

Every HTTP endpoint MUST declare Pydantic request and response models; returning bare dicts or ORM
instances from a router is prohibited. Route paths, methods, and payload shapes MUST match the API
contract in the active feature's `contracts/rest-api.md`, which is the single source of truth for the
HTTP surface, and any change to that surface MUST update the contract in the same change set. The
same API surface MUST NOT be documented in detail in a second location — duplicated documentation
drifts, and a drifted API document is worse than none. `README.md` links to the contract rather than
restating it.
Errors MUST be raised as the typed exceptions defined in `app/common/exceptions.py` and translated to
HTTP responses by shared middleware rather than by ad-hoc handling in individual routes.

Rationale: The frontend and the generated OpenAPI docs are both downstream of these contracts.
Undocumented drift between code and README turns the documented API into misinformation.

### IV. Testing Standards

Service-layer logic — search and filtering, deduplication and cross-post detection, alert rule
evaluation — MUST have tests written before the implementation, and those tests MUST fail before the
code exists. Thin glue code (router wiring, config loading, migrations) is exempt from test-first but
not from the rules below.

- Tests MUST NOT call the Reddit API, any LLM provider, or any other external network service. Those
  boundaries MUST be mocked, with shared fixtures declared in `conftest.py` under `backend/tests/`.
- Tests MUST be deterministic. Wall-clock time, randomness, and iteration order MUST be frozen,
  seeded, or sorted — a test that fails intermittently MUST be fixed or deleted, never retried.
- Unit tests live in `backend/tests/unit/` and integration tests in `backend/tests/integration/`.
  Integration tests are REQUIRED for anything crossing a module boundary or touching the database.
- Each test asserts one behavior and is named for the behavior it protects, not the function it
  calls.
- Service-layer line coverage MUST NOT drop below 80%. A change that lowers it below that floor is
  incomplete.
- The full suite MUST pass before a change is complete. A skipped or disabled test MUST carry a
  comment linking the follow-up task that will re-enable it.

Rationale: This system's core value is filtering and ranking correctness, which is invisible in
manual testing — a subtly wrong dedup or alert rule looks exactly like a correct one. Networked tests
would additionally burn the very API quota Principle I exists to protect, and a flaky suite is worse
than no suite because it teaches the team to ignore red.

### V. UX Consistency

The product surface MUST behave the same way everywhere, on both sides of the API.

- Domain vocabulary is fixed by `README.md`: *audience*, *community*, *topic*, *theme*, *pattern*,
  *bookmark*, *alert rule*, *alert match*, and *status*. These terms MUST be used consistently in UI
  copy, API fields, database columns, and documentation. A *community* is one subreddit tracked by
  the product. "Subreddit" remains correct only where the text is about Reddit's own object rather
  than the product concept — inside `backend/app/reddit/` where it wraps PRAW, in Reddit API
  parameters, and in prose explaining what a community is — and MUST NOT name the product concept in
  UI copy, API fields, database columns, or specification artifacts. Introducing a synonym for an existing
  concept is prohibited. A genuinely new concept MAY be given a new term, but that term MUST be added
  to this list and to `README.md` by amendment in the same change set that introduces it — the
  prohibition is on inventing a second word for something already named, not on naming something new.
- Every view that loads remote data MUST define all four states — loading, empty, error, and
  populated. Shipping a view without a designed empty and error state is incomplete.
- Errors surfaced to users MUST state what failed and what the user can do next. Raw exception text,
  stack traces, and bare status codes MUST NOT reach the interface.
- Shared UI elements MUST come from the common component library and design tokens. A one-off color,
  spacing value, or bespoke copy of an existing component is prohibited.
- All timestamps MUST be stored and transmitted as UTC ISO 8601 and localized only at render time.
- List responses MUST use the shared pagination envelope, and error responses the shared error shape,
  so clients handle every endpoint identically.
- Interactive elements MUST be keyboard reachable and meet WCAG AA contrast.

Rationale: JammySearch asks users to reason across many subreddits at once, so the interface is the
analysis tool — inconsistent naming between a filter and its results, or a feed that renders blank
when a fetch fails, reads to the user as missing data rather than as a UI defect, and corrupts the
conclusions they draw.

### VI. Performance and Efficiency

Every outbound call to a paid or rate-limited service — the Reddit API, and LLM embedding and
completion endpoints — MUST pass through a caching layer keyed on its inputs, and MUST have a defined
TTL or explicit invalidation rule. Inference results (theme tags, sentiment scores, embeddings) MUST
be persisted and reused rather than recomputed per request.

Work placement and query rules:

- Bulk fetching and bulk analysis MUST run as Celery tasks, never inline in a request handler.
- Any endpoint returning a collection MUST paginate and MUST enforce a maximum page size. Unbounded
  queries are prohibited.
- Database access MUST avoid N+1 patterns: related data is fetched with explicit joins or eager
  loading. Columns used for filtering, sorting, or foreign keys MUST be indexed, and vector columns
  MUST have an appropriate pgvector index.
- Request paths MUST NOT perform blocking I/O; the async SQLAlchemy session and async clients are
  required.

Latency budgets, measured at p95 under expected load. These are **server-side budgets for the API
response, measured at the application boundary** — they exclude network transit and client render:

- Cached aggregated feed reads: under 500 ms.
- Advanced search queries over collected material: under 1 s. Searches that reach an external source
  live at request time are exempt, because their latency is not the application's to control; such a
  search MUST tell the user it is live before it runs.
- RAG "Ask" queries: MUST be streamed or asynchronous, with first response under 5 s.

End-to-end, user-perceived targets are set per feature in that feature's specification and are
necessarily looser than these, since they include transit and render. Where the two appear to
disagree, they are measuring different layers rather than contradicting each other; a feature MUST
NOT relax a server-side budget by restating it as an end-to-end one.

A change that pushes an endpoint past its budget MUST either be optimized or ship with the regression
and its justification recorded in the change description.

Rationale: Reddit quota and LLM spend are the two limits that decide whether this product can run at
all, and recomputation is the default failure mode of a RAG pipeline. The latency budgets exist
because the feed is a browsing surface — users scan it continuously, so a slow feed is experienced as
a broken feed regardless of how correct the results are.

### VII. Deterministic and Bounded AI Behavior

Model calls are treated as versioned, reproducible functions, not as opaque magic.

- Sampling temperature MUST be 0 for every classification, extraction, and tagging call. Any call
  using a non-zero temperature MUST document why variability is desirable at that call site.
- Model identifiers MUST be pinned explicitly in configuration. Provider aliases that silently
  re-point to a new model version are prohibited.
- Prompts MUST live in versioned template files under `app/ai/prompts/`, never as inline string
  literals at the call site. Every prompt carries a version identifier that is recorded with each
  result it produces.
- All model output that the system consumes programmatically MUST be requested as structured output
  validated against a Pydantic schema. Parsing free-form prose with regexes or string splitting is
  prohibited. A response failing schema validation is an error to be retried or surfaced, never
  best-effort salvaged.
- Inference results MUST be cached and persisted keyed on the tuple of (input content hash, prompt
  version, model identifier), so an unchanged input never produces a second charge or a different
  answer.
- Context sent to a model MUST be assembled explicitly and bounded by an enforced token budget.
  Implicit or globally accumulated context is prohibited.
- Conversational state for the "Ask" feature MUST be persisted in PostgreSQL as an explicit,
  inspectable record of turns. It MUST NOT live in process memory, and history included in a prompt
  MUST be truncated or summarized by a documented, deterministic policy.

Rationale: An LLM feature that returns a different answer to the same question is not debuggable,
not testable, and not trustworthy for research conclusions. Pinning the model, versioning the prompt,
and keying the cache on all three inputs is what makes a regression attributable to a specific change
rather than to chance.

### VIII. AI Guardrails and Safety

Reddit content is untrusted third-party input, and it flows directly into model prompts.

- Post and comment text incorporated into a prompt MUST be clearly delimited and labeled as untrusted
  data, and system instructions MUST state that content inside those delimiters is never to be
  followed as instructions. Retrieved content MUST NOT be concatenated into the instruction section
  of a prompt.
- Model output MUST NOT be used to construct database queries, shell commands, file paths, HTTP
  requests, or any other executable action. Model output selects among application-defined options;
  it never authors an operation.
- Model output rendered in the UI MUST be escaped or sanitized before display. Links and images
  originating from model output or from Reddit content MUST NOT be auto-loaded from arbitrary hosts.
- Reddit usernames and any personally identifying content MUST NOT be sent to a model provider unless
  the feature demonstrably requires it, and the requirement MUST be documented at the call site.
- Every AI feature MUST enforce a per-request and per-day spend and token ceiling. Exceeding a
  ceiling fails the request with a clear user-facing message rather than continuing to spend.
- The "Ask" feature MUST return an explicit "not enough relevant material to answer" response when
  retrieval quality falls below its configured threshold. Answering from model world-knowledge
  instead of retrieved posts is prohibited, since the user is asking about a specific community.

Rationale: A tool whose entire input is anonymous internet text is the textbook setting for prompt
injection, and the blast radius is decided entirely by what model output is permitted to touch.
Constraining output to a choice among predefined options — rather than to an action — is what keeps a
malicious post from becoming a malicious operation.

### IX. AI Evaluation, Retrieval Quality, and Observability

AI features are held to measured quality, not to impressions.

- A labeled evaluation set MUST exist in the repository for every AI capability that ships — at
  minimum theme tagging, sentiment scoring, and "Ask" retrieval. It MUST be versioned alongside the
  code and MUST cover known-hard cases, not only easy ones.
- Changing a prompt, a model, a chunking strategy, or a retrieval parameter MUST be accompanied by an
  evaluation run against that set, with before-and-after scores recorded in the change description.
  A change that lowers a headline metric MUST NOT ship without a written justification.
- A non-LLM baseline MUST be maintained for at least one extraction task, and the LLM's measured
  advantage over that baseline MUST be reported. Where the baseline is competitive, the cheaper path
  is preferred.
- Retrieval MUST be measured directly, not inferred from answer quality: recall at k against the
  labeled set, and the proportion of answer claims traceable to a retrieved source. Every "Ask"
  answer MUST cite the specific posts it drew from.
- Every model call MUST emit a structured telemetry record containing at least: feature name, model
  identifier, prompt version, input and output token counts, computed cost, wall-clock latency, cache
  hit or miss, and the calling audience or user.
- Aggregate AI cost, latency, cache hit rate, and Reddit API calls avoided by caching MUST be
  queryable and surfaced in the application, not merely recoverable from raw logs.

Rationale: Calling a model API is not a skill; knowing whether the output is any good is. Without a
labeled set and a regression gate, prompt changes are indistinguishable from prompt drift, and
retrieval failures masquerade as model failures. Surfacing cost and cache telemetry makes the
efficiency work of Principle VI visible rather than merely claimed.

## Technology and Data Constraints

The backend targets Python 3.11 using the project virtualenv at the repository root. The committed
stack is FastAPI, PRAW, Celery with Redis, SQLAlchemy with Alembic, Pydantic, PostgreSQL with the
`pgvector` extension as the vector store, and an LLM provider SDK with LangChain or LlamaIndex for the
RAG pipeline. Testing and tooling are standardized on `pytest` with `pytest-asyncio`, and on `ruff`
for lint and formatting. Introducing a dependency outside this list requires the amendment procedure
below; adding a package that is already part of the committed stack does not.

A dedicated managed vector database MUST NOT be introduced while `pgvector` meets the project's
recall and latency requirements at current data volume. Removing an external service that is not
needed is preferred over adding one that is not yet justified.

Every new dependency MUST be added to `requirements.txt` in the same change that imports it. Secrets
and credentials MUST be read from `.env` via configuration objects — hardcoded keys and direct
`os.environ` reads scattered through modules are prohibited, and `.env` MUST remain gitignored.

PostgreSQL is the system of record, and it holds the embeddings. Redis is a cache and Celery broker
and MUST be treated as reconstructible from PostgreSQL, so no durable data may exist only in Redis.
This rule governs the system of record and all collected material — posts, comments, communities,
embeddings, and analysis results — none of which may be re-fetched at will, because Principle I exists
precisely to protect the quota that collecting them costs.

**Ephemeral operational state is exempt** and MAY live only in Redis. State qualifies as ephemeral only
if it reconstructs itself on the next request, or if a user recreates it with a single ordinary action;
losing all of it MUST cost no collected material and no user-authored data. Two instances qualify, and
they are named here so the exemption is a test rather than an interpretation:

- **Session entries** (`backend/app/users/auth_service.py`) — losing every session costs one sign-in.
- **Rate-limit windows** (`backend/app/common/limits.py`) — a lost counter is refilled by the next
  request in the window.

Anything else claiming this exemption requires an amendment naming it. A durable record kept only in
Redis because it happens to be convenient there remains prohibited.

All schema changes MUST ship as Alembic migrations — never as manual DDL or as `create_all()` against a
real database. Database access from request handlers MUST use the async SQLAlchemy session; blocking
I/O in an async path is prohibited.

## Development Workflow and Quality Gates

Feature work follows the Spec Kit flow: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
`/speckit-implement`. Plans MUST state which modules they touch and MUST call out any new
cross-module dependency explicitly.

Before a change is considered complete:

- The full test suite passes, new business logic arrived with tests first, and service-layer coverage
  stayed at or above 80%.
- `ruff` lint and format checks pass, and all new signatures are typed.
- No new direct Reddit API call exists outside `backend/app/reddit/`.
- No new cross-module ORM or table access exists.
- API changes are reflected in `contracts/rest-api.md`.
- New dependencies are in `requirements.txt`.
- New user-facing views define loading, empty, error, and populated states, and use existing domain
  vocabulary and shared components.
- New or changed endpoints paginate, avoid N+1 queries, and meet their latency budget.
- Any change to a prompt, model, chunking strategy, or retrieval parameter ships with before-and-after
  evaluation scores in the change description.
- New model call sites use pinned models, versioned prompt files, schema-validated structured output,
  and emit the required telemetry record.
- Any deviation from these principles is recorded in the change description with its justification.

Simplicity is the default: build for the current requirement, not an anticipated one. A new
abstraction layer, a new service, or a new external dependency MUST be justified by a present need,
not a projected one.

## Governance

This constitution supersedes conflicting practices, prior conventions, and habit. Where it conflicts
with `CLAUDE.md` or `README.md`, this document wins and the other file MUST be corrected.

Amendments are made by editing this file through `/speckit-constitution`. Every amendment MUST record
the version change, the affected principles, and the rationale in the Sync Impact Report at the top of
this file. Versioning is semantic:

- **MAJOR** — a principle is removed or redefined in a way that invalidates existing compliant code.
- **MINOR** — a principle or section is added, or existing guidance is materially expanded.
- **PATCH** — clarifications, wording, and non-semantic refinements.

Compliance is reviewed at every code review and at each `/speckit-plan` step, where the plan MUST be
checked against these principles before tasks are generated. A violation may ship only when its
justification is written into the change description and a follow-up task to remove it is recorded;
undocumented violations MUST be reverted or fixed rather than grandfathered. `CLAUDE.md` remains the
source of runtime development guidance and MUST stay consistent with this constitution.

**Version**: 1.4.0 | **Ratified**: 2026-08-14 | **Last Amended**: 2026-11-01
