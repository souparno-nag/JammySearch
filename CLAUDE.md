# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

JammySearch (formerly named "GummySearch", after the commercial product of that name, which ceased
operating on 2025-11-30; this project is an independent implementation and not affiliated with it) is
a Reddit intelligence / social-listening tool, currently in early scaffolding. Most of the architecture
described below (and in `README.md`) is the **planned** design, not yet implemented as application
logic.

What *is* real:

- **Phase 1 (Setup, T001–T010 of `specs/001-reddit-audience-intelligence/tasks.md`) is complete** — the
  full directory tree, `ruff` and `pytest` configured and enforcing an 80% service-layer coverage gate,
  `docker-compose.yml` (Postgres with `pgvector`, Redis), an async Alembic environment,
  `backend/app/config.py` as the sole reader of `.env` secrets, `.env.example`, a scaffolded SvelteKit
  frontend, and the `evals/` entry point stub.
- **Phase 2's common-infrastructure block (T011–T016) is complete** — `backend/app/common/` now holds
  `database.py` (async engine, session factory, shared `Base` and constraint naming convention),
  `redis.py` (shared connection pool), `exceptions.py` (the typed `AppError` hierarchy), `middleware.py`
  (the handlers rendering every error as the contract's envelope), and `pagination.py` (the `Page`
  envelope and the enforced 100-row ceiling). `backend/app/main.py` is a real FastAPI app that boots
  under `uvicorn app.main:app`, with a lifespan that closes both pools on shutdown.

- **Phase 2's deployment-posture block (T017–T022) is complete** — `main.py` carries the startup bind
  guard (loopback by default; a non-local bind without `ALLOW_REMOTE_EXPOSURE` refuses to start and
  explains why, and it reads uvicorn's `--host` rather than only configuration).
  `backend/app/users/auth_service.py` holds scrypt credential hashing plus expiring, invalidatable
  sessions stored in Redis under a *digest* of the token. `backend/app/dependencies.py` exposes
  `CurrentUser`, resolved from an `HttpOnly` cookie. `backend/app/common/limits.py` enforces
  fixed-window request rate limits per caller and per bucket, refusing rather than advising (FR-080).

- **The session endpoints (T177–T180) are complete.** These four tasks were added to the
  deployment-posture block after T022 shipped, because T017–T022 built everything needed to *carry* a
  session and nothing that *issues* one. `contracts/rest-api.md` gained a "Sessions" section, and
  `backend/app/users/router.py` now serves `POST` / `GET` / `DELETE /auth/session` — **the only three
  endpoints exempt from requiring a session, and the contract states that list is exhaustive.**
  `backend/app/users/schemas.py` holds their Pydantic models. This is the first router registered in
  `main.py`.

The rest of Phase 2 (T023–T047) has not started: no ORM models or migrations, no Celery, no telemetry,
and the Reddit data layer still only has `client.py`. The only HTTP endpoints that exist are the three
session routes above; the audiences router arrives with T058. There is intentionally no health-check
endpoint, because `contracts/rest-api.md` does not contract one (Constitution III).

**`AUTH_PASSWORD_HASH` is empty in a fresh checkout, which means nobody can sign in.** That is
fail-closed by design, not a bug — an unconfigured credential must never read as "no credential
required". Generate one with the documented one-liner in `.env.example`. The test suite supplies its own
hashed credential through a fixture, so it never depends on a local `.env`.

Check what actually exists under `backend/app/` before assuming a module is present. Each implemented
task has a beginner-oriented writeup in `docs/tasks/T<id>.md` explaining what it added and why.

The binding engineering standards live in `.specify/memory/constitution.md` and take precedence over
this file and over `README.md` wherever they disagree. Read it before planning work — it governs
module boundaries, testing, UX consistency, performance budgets, and AI determinism, guardrails, and
evaluation.

JammySearch is built first as a portfolio project and as a single-user market-research tool. Billing,
subscription tiers, plan gating, team workspaces, and outbound integrations are explicitly deferred
future scope — do not build them.

## Environment setup

The project uses a Python 3.11 virtualenv named `reddit-env` at the repo root (gitignored).

```bash
source reddit-env/bin/activate
pip install -r requirements.txt
```

`requirements.txt` now lists the full Phase 1 stack: `praw`, FastAPI + `uvicorn`, `celery[redis]`,
`sqlalchemy` + `alembic` + `asyncpg` + `pgvector`, `pydantic` + `pydantic-settings`, `langchain` +
`langchain-groq` + `langchain-huggingface` + `sentence-transformers`, `python-dotenv`, `ruff`, and
`pytest` + `pytest-asyncio` + `pytest-cov`, plus `redis` (imported directly by `app/common/redis.py`
rather than relied on transitively via `celery[redis]`) and `httpx` (required by
`fastapi.testclient`). Add new dependencies here in the same change that imports them (Constitution,
Technology and Data Constraints).

The virtualenv bakes absolute paths into `reddit-env/bin/*`, so **moving or renaming the repository
directory breaks it** — `source reddit-env/bin/activate` will silently put a nonexistent directory on
`PATH` and every tool will appear missing. This already happened once, on the `GummySearch` →
`JammySearch` rename. Either recreate the venv, or repoint it:

```bash
grep -rl "/old/path" reddit-env/ | xargs sed -i 's|/old/path|/new/path|g'
```

All settings — including secrets — are read from `.env` at the repo root, and **only**
`backend/app/config.py` is permitted to read them (other modules import `settings` from there). See
`.env.example` for the full, documented list: Reddit credentials, `DATABASE_URL`, `REDIS_URL`, Groq
chat-completion settings (`GROQ_API_KEY`, `GROQ_MODEL` — pinned explicitly, never a floating alias),
the local embedding model name, and `ALLOW_REMOTE_EXPOSURE` (FR-078's deployment exposure flag,
defaults to `false`).

Build, lint, and test commands, run from `backend/` with `reddit-env` active:

```bash
ruff check . && ruff format --check .          # lint + format, per backend/pyproject.toml
pytest                                          # full suite; --cov=app with an 80% fail-under gate
alembic upgrade head                            # apply migrations (none exist yet)
uvicorn app.main:app --reload                   # run the API (no endpoints yet, /openapi.json works)
```

`pyproject.toml` sets `pythonpath = ["."]` under `[tool.pytest.ini_options]` so tests can `import app.*`
without an installed package or a `sys.path`-editing `conftest.py`.

`docker-compose.yml` at the repo root brings up Postgres (with `pgvector`) and Redis, both bound to
`127.0.0.1` only:

```bash
docker compose up -d
```

Compose derives its project name from the directory, so the `GummySearch` → `JammySearch` rename
orphaned the original `gummysearch-*` containers and volumes: they kept holding ports 5432 and 6379
while `docker compose ps` from `JammySearch/` reported nothing. **Resolved on 2026-08-16**, while the
database was still empty, with `docker compose -p gummysearch down -v && docker compose up -d`. The
containers are now `jammysearch-postgres-1` and `jammysearch-redis-1` on fresh `jammysearch_*`
volumes.

The diagnostic worth keeping from this and from T005: in `docker compose ps`, a bare `5432/tcp` with
no `host:port->` arrow means the port publish failed while the container still reports healthy — not
that the container is down.

The frontend (`frontend/`, SvelteKit — see below) has its own toolchain:

```bash
cd frontend
npm run dev      # dev server
npm run build    # production static build (adapter-static)
npm run lint     # eslint + prettier --check
npm run test     # vitest
```

## Architecture

### Planned backend stack

- FastAPI (async web framework)
- PRAW for the Reddit API
- Celery + Redis for the job queue / scheduled ingestion
- SQLAlchemy + Alembic for ORM and migrations
- LangChain as the orchestration layer for the RAG "Ask" pipeline and embeddings, decided over
  CrewAI (wrong shape — built for multi-agent tool delegation, not single-shot structured
  completions). Chat completions go through **Groq** (`langchain-groq`, an open-weight model, pinned
  explicitly — never a floating alias); embeddings run **locally** via a HuggingFace
  `sentence-transformers` model (`langchain-huggingface`), no API key or network call. Both were
  chosen over OpenAI/Anthropic for zero per-token cost at single-user scale — see `research.md` R1.
- PostgreSQL with the `pgvector` extension as the vector store (deliberately *not* a separate managed
  vector database — see the constitution's Technology and Data Constraints)
- Pydantic for validation

### Planned frontend stack

- **SvelteKit**, configured with `adapter-static` and SSR explicitly off (`export const ssr = false`
  in the root layout) — ships as a pure client-side SPA consuming the backend's REST API, with a
  fallback page (`fallback: 'index.html'`) so runtime-dynamic routes like `/audiences/[id]/feed`
  still resolve client-side even though nothing is server-rendered. Chosen over Next.js because none
  of Next's SSR/ISR/edge-middleware capabilities have a consumer in this design — see `research.md`
  R10 for the full comparison against Next.js and bare Vite+React.
- TypeScript, ESLint + Prettier (the frontend's equivalent of `ruff`), Vitest (the frontend's
  equivalent of `pytest`) — all configured by the SvelteKit scaffold in `frontend/`.
- File-based routing under `frontend/src/routes/` (SvelteKit's own convention — no router library).

### Modular design

The backend is organized around 6 modules, each intended to own its own `router.py` / `service.py` /
`models.py` / `schemas.py` under `backend/app/<module>/`:

1. **`reddit/`** — Reddit Data Layer. The *only* module allowed to talk to the Reddit API (via PRAW). All
   other modules must go through this layer rather than calling PRAW directly. Owns caching, rate
   limiting, and scheduled data refreshes. `backend/app/reddit/client.py` currently has
   `setup_reddit_client()` and `obtain_subreddit()`.
2. **`audiences/`** — Audience Management. CRUD for user-defined groups of communities ("audiences"),
   the shipped starter audiences, and related-community suggestions.
3. **`feed/`** — Feed & Search Engine. Aggregates posts across an audience's subreddits, handles advanced
   keyword/boolean search, filtering, dedup, and cross-post detection. Consumes the Reddit Data Layer, not
   Reddit directly.
4. **`ai/`** — AI & Analysis Engine. Theme tagging, topic extraction, sentiment analysis, pattern
   detection, and the RAG-based "Ask" feature (embed locally via sentence-transformers → pgvector
   similarity search → LLM completion via Groq, through LangChain). All model calls use pinned
   models, temperature 0, versioned prompt files, and schema-validated structured output, and emit
   cost/latency telemetry.
5. **`alerts/`** — Alerts, Notifications & Integrations. Keyword alert rules, email digests, Slack/Discord
   webhooks, brand mention tracking, cron-driven checks.
6. **`users/`** — User & Workspace Management. Auth, subscription/plan gating, team workspaces, bookmarks,
   shareable report generation. Determines what features a user's plan allows.

Cross-cutting rule from the design: **no module besides `reddit/` should call the Reddit API directly** —
everything else consumes cached/normalized data through the Reddit Data Layer.

### Shared infrastructure in `app/common/` (built, T011–T016)

These exist now, and new module code is expected to use them rather than reinvent equivalents:

- **`database.py`** — the one process-wide async engine, `session_factory`, and `get_session()`, the
  FastAPI dependency that owns the transaction boundary (commit on success, rollback and re-raise on
  failure). Services must not commit independently. Every ORM model inherits from its `Base`, which
  carries a constraint naming convention so Alembic can always name what it drops.
- **`redis.py`** — the shared client and pool. `get_redis()` returns the *shared* client rather than
  yielding a per-request one; closing it would tear down the pool for every other caller.
- **`exceptions.py`** — the `AppError` hierarchy. Raise these rather than `HTTPException`. Pass a
  specific `code` to a general class (`ConflictError(..., code="audience_limit_reached")`) instead of
  adding domain subclasses to `common/`.
- **`middleware.py`** — `install_error_handling(app)`. Every error response is built here, never in a
  router. Raw exception text never reaches a client; unhandled exceptions log a traceback server-side
  and return a generic 500.
- **`pagination.py`** — `PageParams` and the generic `Page[T]` envelope, with a 100-row ceiling that
  **rejects** rather than clamps. Every collection endpoint returns a `Page`.

- **`limits.py`** — `consume_rate_limit`, plus the `rate_limit(...)` and `paid_call_rate_limit(...)`
  dependencies. Attach one to any endpoint that can trigger a paid call. It **refuses**; it never
  merely reports remaining allowance, because FR-080 requires a client that ignores the check to still
  be bound by it. `signin_rate_limit()` is the variant for endpoints with no signed-in caller — it keys
  on the client address because `rate_limit` resolves `CurrentUser` first, and it deliberately ignores
  `X-Forwarded-For`, which a caller can set to mint a fresh subject per attempt.

Two conventions set by that work: declare FastAPI dependencies as `Annotated[Dep, Depends()]` rather
than `= Depends()` in an argument default (`ruff` B008), and never add an endpoint that
`contracts/rest-api.md` does not contract — including a convenience health check.

### Auth and request gating (built, T017–T022, T177–T180)

- **`app/users/auth_service.py`** — `hash_password` / `verify_password` (scrypt from the standard
  library, deliberately not bcrypt or argon2, which sit outside the constitution's committed stack and
  would need the amendment procedure), `authenticate` against the configured credential, and the
  session lifecycle. An empty `AUTH_PASSWORD_HASH` denies everyone: an unconfigured credential fails
  closed rather than reading as "no credential required".
- **`app/dependencies.py`** — `CurrentUser`. Write `user: CurrentUser` on a route and authentication
  is handled; every failure mode returns the same 401 so a caller cannot probe which tokens existed.
- **`app/users/router.py`** — `POST` / `GET` / `DELETE /auth/session`, with their Pydantic models in
  `app/users/schemas.py`. Sign-in returns the username and expiry and puts the token **only** in an
  `HttpOnly` cookie, never in the body. Every sign-in failure — wrong password, unknown username,
  unconfigured credential — returns a byte-identical 401. Sign-out is not behind `CurrentUser` (an
  already-expired session must still be able to sign out) and returns 204 either way.
- Sessions are stored in Redis under a SHA-256 digest of the token, so a leaked dump or backup yields
  no usable session, and expiry is checked by the application as well as by the Redis TTL. Constitution
  v1.3.0 explicitly permits this: sessions and rate-limit windows are named as ephemeral operational
  state, exempt from "no durable data may exist only in Redis". Nothing else may claim that exemption
  without amending the constitution.

Tests mock Redis with `FakeRedis` and `FakeClock` from `backend/tests/conftest.py` — use those rather
than writing a new stand-in, and pass `now` explicitly instead of sleeping (Constitution IV).

### Data flow (planned)

Post ingestion runs as a Celery Beat-scheduled task chain:
`ingest.py` (PRAW fetch + dedup + write to Postgres + update Redis cache) → `embed.py` (chunk + embed to
pgvector) → `analyze.py` (theme/sentiment tagging) → `alerts.py` (keyword match).

The "Ask" feature (`ai/ask_service.py`) follows: embed query locally (sentence-transformers) → pgvector
similarity search → fetch full post context from Postgres → LangChain prompt construction → Groq
completion → structured response with source posts.

See `README.md` for the full planned folder structure, API route table, and architecture diagrams.
