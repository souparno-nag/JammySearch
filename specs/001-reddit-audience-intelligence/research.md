# Phase 0 Research: Reddit Audience Intelligence

**Feature**: `001-reddit-audience-intelligence`
**Date**: 2026-08-14
**Purpose**: Resolve every open decision in the plan's Technical Context before design begins.

The constitution (`.specify/memory/constitution.md`) already pins most of the stack — Python 3.11,
FastAPI, PRAW, Celery with Redis, SQLAlchemy with Alembic, Pydantic, PostgreSQL with `pgvector`,
pytest, and ruff. Those are not re-litigated here. What follows are the decisions the constitution
leaves open, plus the ones the specification's requirements force.

---

## R1. LLM provider and model pinning

**Decision**: Access the model through a single internal adapter in `app/ai/` that exposes
`complete()` and `embed()` and hides the vendor SDK from every call site. Pin an explicit model
identifier in configuration, never a floating alias. LangChain is the orchestration layer behind the
adapter — not a general multi-agent framework like CrewAI, which is built for tool-calling delegation
between autonomous agents and is the wrong shape for single-shot structured completions and RAG.
`complete()` is backed by Groq (`langchain-groq`) against an open-weight chat model; `embed()` is
backed by a local HuggingFace `sentence-transformers` model (`langchain-huggingface`), run in-process
with no network call and no API key. Both were chosen over OpenAI/Anthropic for zero per-token cost at
single-user scale. The adapter is what makes switching either one later — including back to a paid
provider — a configuration change rather than a refactor.

**Rationale**: Constitution VII forbids provider aliases that silently re-point, and requires the
model identifier to be recorded with every result. An adapter is what makes that enforceable in one
place, and it is what allows the evaluation harness (R12) to run the same eval set against two
providers to justify a choice with numbers rather than preference. LangChain is already named in the
constitution's Technology and Data Constraints, so routing both providers through it needs no
amendment. Running embeddings locally also fits R17's local-first deployment posture better than a
third external network dependency alongside Reddit and Groq would.

**Concrete model identifiers and per-token prices are deliberately not recorded here.** They move
faster than this document will be revised, and a stale price in a design artifact is worse than no
price. Verify current identifiers and pricing at the moment of pinning, and record the chosen values
in configuration plus the plan's Complexity Tracking if they constrain anything. Groq's free tier is
still a rate limit, not an unlimited allowance — FR-046's spend ceiling and FR-080's server-side
enforcement apply to request/token volume even at zero marginal cost.

**Alternatives considered**: Calling the vendor SDK directly from each service — rejected, it
scatters the model identifier across the codebase and makes Constitution VII's telemetry
requirement (IX) impossible to satisfy centrally. A general-purpose multi-provider abstraction
library — rejected as premature; LangChain already covers current needs without a second dependency.
CrewAI for orchestration — rejected; its agent-delegation model solves a problem this feature does not
have. OpenAI for embeddings and completions, as originally named in `README.md` — rejected on cost
grounds; revisit only if local embedding quality or Groq's rate limits measurably block a story. The
hosted HuggingFace Inference API instead of local `sentence-transformers` — rejected for now to avoid
a third external network dependency and its own rate limits; local inference costs nothing but CPU
time and keeps embedding fully offline.

**Usernames never reach the provider** (Constitution VIII). No feature in this specification needs an
author's identity to interpret content: distinct-author counts (FR-054) are computed in SQL, and
citations reference posts, not people. Prompt assembly in the adapter therefore never includes author
fields, and masks `u/<name>` mentions inside post and comment text to `u/[user]` with a fixed pattern
before any `complete()` call. The masking is applied to *input*, so it is not the output parsing that
Constitution VII prohibits. Local `embed()` is exempt because no text leaves the process. A future
call site that genuinely needs a username must say why at the call site, per Constitution VIII.

---

## R2. Embedding and chunking strategy

**Decision**: Embed at post granularity for short posts, and split longer posts on paragraph
boundaries with a target chunk size well inside the embedding model's context window and a small
overlap. Store one row per chunk in `pgvector` with a reference back to the owning post. Comments
collected under FR-027 are embedded as their own chunks, tagged with their parent post.

**Rationale**: Reddit posts are mostly short — a title plus a few paragraphs — so per-post embedding
is adequate for the majority and avoids fragmenting an argument that spans a whole post. Paragraph
splitting for the long tail preserves semantic units better than fixed character windows. Keeping
comments as separate chunks with a parent reference is what lets FR-027b report whether a result was
supported by discussion or by post text alone.

**Alternatives considered**: Fixed-size character chunking with overlap everywhere — rejected, it
cuts mid-sentence and produces chunks that retrieve poorly. Embedding whole comment threads as one
unit — rejected, it destroys the attribution needed for citations (FR-029).

---

## R3. Reddit API quota budgeting and collection cadence

**Decision**: Treat quota as a first-class budget owned by `app/reddit/`. Every outbound call passes
through a single rate-limited client that records its cost. Collection runs on a Celery Beat schedule
per audience, with the interval derived from the audience's observed posting rate rather than fixed —
quiet audiences are polled less often. A daily community-statistics snapshot job (FR-038) runs
independently of audience collection and is never skipped, because its value is purely a function of
uninterrupted history.

**Rationale**: Constitution I makes `app/reddit/` the only place quota can be accounted for, and
Constitution VI requires per-call telemetry. Uniform polling wastes quota on dormant communities and
starves active ones. Separating the snapshot job matters because a missed snapshot is permanently
lost — there is no backfill for it — whereas a missed post fetch self-heals on the next cycle.

**Alternatives considered**: Fixed uniform polling for all audiences — rejected as quota-wasteful.
Polling on user request only — rejected, it makes alerts (FR-057) impossible, since alerts depend on
material arriving without anyone asking.

---

## R4. Duplicate and cross-post detection

**Decision**: Two-stage. First, exact identity — Reddit exposes a canonical identifier for a
cross-post's origin, so genuine cross-posts collapse deterministically without any similarity
computation. Second, near-duplicate detection over title plus body using a normalized-text hash for
verbatim reposts. Similarity-based clustering is explicitly not used at this stage.

**Rationale**: FR-011 requires collapsing duplicates and SC-011 sets a measurable ceiling of 2%. The
overwhelming majority of duplication in an aggregated feed is true cross-posting, which is exactly
identifiable and therefore free of false positives. Reaching for embeddings-based similarity first
would risk collapsing two genuinely distinct posts that happen to discuss the same topic, which is a
much worse failure for a research tool than showing an occasional repeat.

**Alternatives considered**: Embedding similarity with a threshold — rejected for this release as
over-engineered and risky; revisit only if SC-011 is measured as failing. Title-only matching —
rejected, too many legitimately distinct posts share a title.

---

## R5. Comment collection engagement threshold

**Decision**: Start conservative — collect top-level comments only for posts in the upper tail of
engagement within their own community over the collection window, rather than against a fixed global
number. Make the threshold configurable per FR-027a and expose its current value. Record, from day
one, how many posts qualify and what that costs, so the threshold can be tuned against evidence.

**Rationale**: A fixed global score is wrong across communities of different sizes — a score of 50 is
exceptional in a 5,000-member community and unremarkable in a 2M-member one. A relative threshold
adapts automatically. The specification's Assumptions already commit to starting conservative because
beginning permissive risks exhausting quota before the value of comments is demonstrated.

**Alternatives considered**: Fixed absolute score threshold — rejected, does not transfer across
community sizes. Collecting comments for every post — rejected as roughly an order of magnitude more
volume, which is why the spec's Q3 decision chose the middle path.

---

## R6. Topic and theme trend computation

**Decision**: Compute a theme's or topic's *share of discussion* per time bucket — its post count in
the bucket divided by the audience's total post count in that bucket — rather than raw counts. Store
per-bucket aggregates rather than recomputing over raw posts on every view. Record collection
coverage per bucket so that a gap in collection is visibly distinguishable from a genuine decline.

**Rationale**: FR-053 asks for change over time and FR-055 forbids showing a direction when the period
is too short. Raw counts conflate "this topic grew" with "we collected more that week", which would
make the trend actively misleading — the exact failure the specification's edge case about
interrupted collection calls out. Share-of-discussion normalizes that away. Distinct-author counts
(FR-054) are stored alongside, because a topic carried by one prolific poster is not a trend.

**Alternatives considered**: Raw post counts per bucket — rejected, indistinguishable from collection
volume changes. On-the-fly computation over raw posts — rejected, it scales badly and violates
Constitution VI's prohibition on unbounded queries in request paths.

---

## R7. Non-LLM baseline

**Decision**: Implement a classical baseline for topic extraction — term-frequency scoring with
stopword and boilerplate removal, clustered into topics — in `app/ai/baseline.py`. Run it against the
same evaluation set as the model path and report both scores together.

**Rationale**: Constitution IX requires a non-LLM baseline for at least one extraction task and
requires the model's measured advantage over it to be reported. Topic extraction is the right task to
baseline because it is the one where a classical method is genuinely competitive — which makes the
comparison informative rather than a formality. If the baseline wins, that is a real finding and a
real cost saving.

**Alternatives considered**: Baselining sentiment instead — rejected; a lexicon-based sentiment
baseline is a weaker comparison and less likely to change any decision. Skipping the baseline —
prohibited by Constitution IX.

---

## R8. Alert evaluation

**Decision**: Evaluate alert rules as a stage in the ingestion chain, immediately after new material
is persisted and before analysis. Match against the newly written batch only, never by re-scanning
history. Persist matches as their own records so they survive rule edits and deletion, per FR-059.

**Rationale**: FR-057 requires evaluation without the user re-running a search, and SC-014 sets a
15-minute surfacing target which is bounded by collection cadence rather than by matching cost.
Matching only the new batch keeps the work proportional to arrival volume. Persisting matches
independently of rules is what makes FR-059 satisfiable — a match is a historical fact, not a view
over a rule.

**Alternatives considered**: A periodic job that re-runs each rule as a search over all history —
rejected, cost grows with corpus size rather than arrival rate, and it produces duplicate matches.
Evaluating at read time when the user opens the alerts view — rejected, it cannot meet SC-014 and
defeats the purpose of a standing rule.

---

## R9. The "all of Reddit" search scope

**Decision**: Implement the widened scope (FR-019) as a distinct path in `app/reddit/` that queries
the source's own search endpoint at request time, clearly separated from the saved-material search in
`app/feed/`. Results are returned without pattern or sentiment analysis, marked as live, and are not
persisted into the audience corpus. Apply a per-request quota charge and a short result cap.

**Rationale**: These are two different capabilities wearing one control, and the specification
already requires the interface to say so. Keeping them as separate code paths prevents the live path
from silently inheriting assumptions — pagination, dedup, analysis — that only hold for collected
material. Not persisting the results keeps the corpus meaning "material we chose to track", which is
what every trend and analysis figure depends on.

**Alternatives considered**: Persisting live results into the corpus — rejected, it would pollute
audience statistics and trends with material the user never chose to track. A single unified search
service handling both — rejected, the two have different latency, cost, and correctness properties.

---

## R10. Frontend

**Decision**: SvelteKit, configured with `adapter-static` so it ships as a pure client-side SPA with
server-side rendering explicitly turned off, consuming the REST contract in `contracts/`. File-based
routing under `frontend/src/routes/` replaces the `pages/` tree this document originally named under
Next.js — the routing convention is equivalent (`routes/audiences/[id]/feed/+page.svelte` mirrors
`pages/audiences/[id]/feed.tsx`), only the file extension and directory name change, from `.tsx` under
`pages/` to `.svelte` under `routes/`. Design tokens and a shared component library established before
feature screens, so Constitution V's prohibition on one-off colors and spacing is enforceable from the
first screen rather than retrofitted.

**Rationale**: Constitution V requires all four view states (loading, empty, error, populated) on
every data-loading view and requires shared components. Both are dramatically cheaper to establish
first than to retrofit. The four-state requirement in particular is best expressed as a single shared
wrapper component that every data view uses. SvelteKit was chosen over Next.js because this feature's
frontend is a pure client of the FastAPI REST API — none of Next's SSR, ISR, or edge-middleware
capabilities are used, since all business logic lives in the backend per Constitution II. Svelte
compiles components to plain JS with no virtual-DOM runtime shipped to the browser, and its built-in
reactivity (`$state`, stores) covers the shared UI state this project needs (current audience, active
filters) without an added state-management dependency the way a bare React SPA would need one.
`adapter-static` keeps the SSR machinery off entirely rather than paying for a capability this
single-user, locally-deployed tool does not use.

**Alternatives considered**: Next.js, the original choice — superseded once the SSR/ISR/edge features
it offers turned out to have no consumer in this design; kept only the parts (file-based routing,
TypeScript, a build tool) that a lighter stack provides too. Vite + bare React — rejected in favor of
Svelte for the same "lightest stack that still does the job" reasoning: no virtual-DOM runtime, and no
added state-management library needed. Plain Vite + Svelte without SvelteKit — rejected only for
convenience; it is marginally lighter still, but SvelteKit's file-based router is a closer match to
this project's existing planned route tree and avoids hand-wiring a router library for the same
practical effect. Server-rendered templates from FastAPI — rejected, it contradicts the README and
makes the four-state UX requirement awkward. Deferring the design system until several screens exist —
rejected, that is precisely how one-off styling accumulates.

**Untrusted text is rendered as text** (Constitution VIII). Reddit post and comment bodies, and model
output such as Ask answers, pass through one shared renderer in `frontend/src/components/` that emits
escaped plain text with line breaks preserved. URLs become links that load only when clicked and carry
`rel="noopener noreferrer nofollow"`. Images are never embedded; an image URL is shown as a link.
`{@html}` is banned project-wide: `svelte/no-at-html-tags` is already `error` in the recommended
Svelte lint config, and `frontend/eslint.config.js` pins it explicitly so that a later config change
cannot drop it silently and let the renderer be bypassed. Reddit bodies are Markdown, and
showing them unformatted is the accepted cost for this release. Rendering Markdown later requires an
HTML sanitizer, which is a new dependency, and a revision of this section. Building it as a pure
function rather than a component is also what lets it be tested under the existing node-environment
Vitest setup without adding component-testing dependencies.

---

## R11. Authentication

**Decision**: Session-based sign-in for a single user, with credentials in configuration and no
self-service registration. No roles, no tenancy scoping in queries.

**Rationale**: FR-048 requires sign-in and privacy of the user's data; the spec's Assumptions state
sign-in exists to protect one person's data rather than to separate tenants. Building tenancy now
would tax every query for a capability the Future Scope explicitly defers. Registration endpoints for
a single-user system are surface area with no user.

**Alternatives considered**: Full OAuth2 with registration and refresh flows — rejected as
disproportionate and explicitly deferred by the README's Future Scope. No authentication at all —
rejected, FR-048 requires it and the deployment is network-reachable.

---

## R12. Evaluation dataset construction

**Decision**: Build three labeled sets, committed to `evals/datasets/`: theme and topic labels on a
sample of posts, sentiment labels on the same sample, and question-to-relevant-post mappings for
retrieval — the last including a deliberate subset of **unanswerable** questions, because SC-007
requires measuring correct refusal and refusal cannot be measured without questions that should be
refused.

**Rationale**: Constitution IX requires a labeled set covering known-hard cases and requires
before-and-after scores on any prompt, model, chunking, or retrieval change. SC-008 publishes a 75%
agreement floor and FR-047 requires publishing the figure. None of that is possible without the sets
existing first, which makes this a prerequisite of the AI work rather than a follow-up to it.

**Retrieval is scored directly** (Constitution IX), not inferred from answer quality. The harness
reports two retrieval figures over the answerable questions in `retrieval.jsonl`:

- **Recall at k** — the share of a question's labelled relevant posts that appear among the posts of
  the top *k* retrieved passages, averaged over answerable questions. *k* is the retrieval depth Ask is
  configured with, so the number describes what Ask actually sees.
- **Claim traceability** — the share of answer claims that rest on a retrieved, relevant passage.
  Ask's structured output (Constitution VII) is a list of claims, each naming the passage ids it rests
  on. A claim is traceable when at least one passage it names was retrieved for that question and
  belongs to a post labelled relevant. A claim naming no passage, or only passages that were not
  retrieved, is untraceable.

Unanswerable questions are excluded from both figures and scored instead by refusal rate (SC-007). The
API contract is unaffected: the answer text is assembled from the claims, and `citations` is their
union.

**Alternatives considered**: Model-generated labels — rejected, scoring a model against its own
output measures nothing. Deferring the eval set until after the AI features work — rejected, it
inverts Constitution IX's regression gate and means the first prompt change ships unmeasured. Judging
traceability with a second model — rejected, it is non-deterministic and charges per evaluation run.

---

## R13. Deletion detection and purge

**Decision**: A scheduled re-check task in `app/reddit/availability.py` re-fetches previously
collected items in age-ordered batches and compares availability. On detecting a deletion or removal,
purge the text from `Post`/`Comment` and delete the corresponding `ContentChunk` rows, while
retaining non-content fields as a tombstone. Bookmarked items are exempt and keep their captured copy
(FR-069).

**Rationale**: FR-067 requires detection in the background rather than at read time, because a
researcher who never opens an item would otherwise never trigger the purge. Retaining non-content
metadata keeps `DiscussionBucket` denominators stable — deleting the row outright would silently
rewrite history and make a past week's trend change after the fact. Deleting the chunks matters as
much as purging the text: a vector derived from removed content is still derived from it.

**Alternatives considered**: Purging at read time when an item is opened — rejected, it leaves
removed content in the retrieval index indefinitely. Deleting rows entirely — rejected, it corrupts
historical counts and trends. Re-checking everything on every cycle — rejected as quota-prohibitive;
age-ordered batching spends the quota where deletions are most likely.

---

## R14. Backup and restore

**Decision**: A nightly `pg_dump` written to a volume outside the application container, retained on
a rolling window, run as a Celery Beat task in `workers/tasks/backup.py`. A separate, less frequent
verification step restores the most recent dump into a scratch database and asserts row counts on the
irreplaceable tables.

**Rationale**: SC-018 sets a 24-hour recovery point objective, and FR-071 requires the restore to
have actually been performed — an untested backup is a belief, not a control. The verification step
exists because the common failure is not a missing dump but an unusable one. Excluding the embeddings
table is the designated escape valve if dump size becomes a problem, since embeddings are the only
large component that is deterministically regenerable from text that is retained.

**Alternatives considered**: Continuous write-ahead-log archiving — rejected, its tighter recovery
window does not justify the operational surface for a single-user tool. Backing up only snapshots and
bookmarks — rejected on inspection: the source will not serve a community's history beyond its
listing limits, so the post corpus is substantially irreplaceable too, and both embeddings and
persisted inference results cost real money to regenerate.

---

## R15. Chunked, resumable analysis

**Decision**: `app/ai/runner.py` processes analysis in fixed-size chunks, committing each chunk's
results in its own transaction and advancing a persisted cursor on an `AnalysisRun` record. On
failure the run is marked interrupted with its cursor intact; the next attempt resumes from there.
Audiences expose their completion proportion so partial state is visible rather than implied.

**Rationale**: FR-072–FR-074 require exactly this shape. The cursor is what separates "resume" from
"restart", and Constitution VII's inference cache — keyed on content hash, prompt version, and model
identifier — is what guarantees the no-double-charge property in FR-073 even if a chunk is retried
after partial success. Surfacing completion proportion is what stops a half-analysed audience from
being read as a fully analysed one with fewer themes.

**Alternatives considered**: All-or-nothing transactions per run — rejected, one late failure discards
the whole run's spend. Skip-and-continue leaving holes — rejected, it produces silently incomplete
analysis, which is worse than visibly incomplete analysis. Unbounded retry with backoff — rejected as
the primary strategy since it burns spend during a real outage, though bounded retry within a chunk
remains appropriate for transient errors.

---

## R16. Retrieval refusal threshold

**Decision**: Refusal is decided by a deterministic gate in `app/ai/retrieval.py`: answer only when at
least *N* retrieved passages score above a similarity floor *F*. Both are configuration values,
exposed through `/ops`, and tuned against the labelled unanswerable questions in the evaluation set.
Changing either is a retrieval change and triggers the Constitution IX regression gate.

**Rationale**: FR-076 and FR-077 require this to be measurable rather than emergent. Requiring
multiple supporting passages rather than one strong match is what prevents a single incidental
keyword hit from carrying an unsupported answer — the failure mode SC-007 exists to measure. Keeping
the gate deterministic means refusal behaviour is reproducible and testable, which a model
self-assessment would not be.

**Alternatives considered**: A single top-score cutoff — rejected as brittle across differently worded
questions. Asking the model whether the material answers the question — rejected as non-deterministic
and weakest precisely where the model is confidently wrong. A two-stage gate plus model check —
deferred; it roughly doubles per-question cost and latency, and should only be adopted if the
evaluation set shows the deterministic gate failing.

---

## R17. Deployment posture

**Decision**: Bind to loopback by default, with a startup guard that refuses to bind a non-local
interface unless an explicit exposure setting is present. Application-layer security is built to
public-exposure standard now — hashed credentials, expiring and invalidatable sessions, secrets never
present in responses or logs, all limits enforced server-side. Deployment-layer protections are not
built.

**Rationale**: FR-078–FR-081 draw the line at cost. The application-layer measures are near-free when
done first and expensive to retrofit — changing a credential storage scheme after data exists is a
migration, not an edit. The deployment-layer measures (transport security, abuse protection,
monitoring) carry real monetary and operational cost and can be added later without touching
application code, which is exactly why deferring them is safe. FR-081 names them explicitly so their
absence is a recorded decision rather than an oversight, and so nobody over-builds from FR-079.

**Alternatives considered**: Full public-exposure readiness now — rejected, it front-loads cost for a
deployment that does not exist. Local-only with no forward design — rejected, the shortcuts it
permits (plain credentials, non-expiring sessions, client-enforced limits) are precisely the ones
that become migrations later.

---

## R18. Intent-based alert matching

**Decision**: Alert rules carry a matching mode — keyword, intent, or both. Intent rules store the
researcher's plain-language description and a vector computed from it once, recomputed whenever the
description changes. Evaluation compares the new material batch against stored rule vectors using the
same pgvector index that serves Ask, gated by a configurable per-rule similarity threshold. Keyword
matching remains fully functional and independent when the vector path is unavailable.

**Rationale**: A keyword rule cannot catch the same intent expressed in different words, which is
precisely the case that matters for finding leads — someone asking for a tool by describing their
problem rather than naming the category. The embedding infrastructure already exists for retrieval
(R2), so the marginal cost is one vector per rule and one similarity comparison per incoming post.

Keeping the two modes independent is deliberate and load-bearing: it preserves US5 as a story that
can ship without any AI work, which in turn preserves an AI-free path to a genuinely useful product
(US1 → US2 → US5). Coupling them would have made lead-finding wait on the most expensive story in the
project.

**Degradation is a requirement, not a nicety** (FR-085). An alert that silently stops matching is
worse than one that never existed, because the researcher assumes coverage they do not have. When the
vector path is unavailable the keyword half continues and the rule reports itself partially active.

**Alternatives considered**: Replacing keyword matching with intent matching entirely — rejected, it
makes US5 depend on US4 and removes the exact-term precision that keyword rules give for brand and
competitor monitoring. Asking a model per rule per post whether it matches — rejected as
prohibitively expensive at ingestion volume, and non-deterministic where reproducibility matters.
Expanding a rule into synonyms with a model at creation time — rejected as a strictly worse
approximation of what an embedding already does.

---

## R19. Context budget and Ask history

**Decision**: Every `complete()` call site declares an input token budget, read from configuration.
The adapter estimates the assembled context's size before the call and **refuses** an over-budget
request with a typed error rather than truncating it silently. The estimate is deterministic and
deliberately conservative: UTF-8 byte length divided by 3, rounded up. That overcounts English text
and is roughly exact for multi-byte scripts. Telemetry records the provider-reported counts, not the
estimate.

Ask assembles context in a fixed order: system instructions, then retrieved passages admitted whole in
rank order until the budget is reached, then the question. A passage is never cut mid-text. Question
length is capped by the request schema, so the fixed parts are bounded. Chunks have a hard size ceiling
(R2's target enforced as a maximum, with an oversized paragraph split at sentence boundaries).
Configuration is validated at startup so that the refusal gate's minimum passage count *N* (R16) always
fits inside the Ask budget. A gate that passes can therefore never be undone by the budget.

**Ask history policy: no prior turns enter the prompt.** Each question is answered from retrieval
alone. Turns are still persisted per Constitution VII, so the record stays inspectable, but they are
history for the user, not context for the model.

**Rationale**: Constitution VII requires context to be "bounded by an enforced token budget" and history
to follow "a documented, deterministic policy". The contract makes Ask single-shot (no session in the
request), and FR-032 requires the same question against unchanged material to answer consistently.
Prior turns in the prompt would make the answer depend on what was asked before, which breaks FR-032
directly. Refusing rather than truncating keeps an over-budget request visible as a configuration
defect instead of a quietly degraded answer.

**Alternatives considered**: An exact tokenizer for the pinned model — rejected for now; it adds a
dependency outside the committed stack to make exact a number that only needs to be a safe ceiling.
Summarising prior turns into the prompt — rejected; it costs a model call per question and makes
answers depend on conversation order. A sliding window of the last few turns — rejected for the same
FR-032 reason; revisit only if follow-up questions become a specified capability.

---

## Resolved Technical Context

| Item | Resolution |
|------|------------|
| Language/Version | Python 3.11 (constitution) |
| Backend framework | FastAPI (constitution) |
| Reddit access | PRAW, confined to `app/reddit/` (Constitution I) |
| Storage | PostgreSQL as system of record; `pgvector` for embeddings; Redis as cache and broker |
| Background work | Celery with Celery Beat |
| LLM access | Single internal adapter over LangChain; Groq for completions, local `sentence-transformers` for embeddings; explicitly pinned model identifiers (R1) |
| Frontend | SvelteKit (adapter-static, SSR off) with a design-token system established first (R10) |
| Testing | pytest, pytest-asyncio, ruff; externals always mocked (Constitution IV) |
| Target platform | Linux server, containerized |
| Project type | Web application — backend plus frontend |
| Auth | Single-user session sign-in (R11), built to public-exposure standard (R17) |
| Deployment | Loopback-bound with a startup guard; exposure is configuration, not code (R17) |
| Durability | Nightly dump outside the container, with periodic verified restore (R14) |
| Deletion handling | Scheduled availability re-check; purge text and chunks, keep tombstone (R13) |
| Analysis resilience | Chunked commits with a persisted cursor; resume, never restart (R15) |
| Refusal | Deterministic gate: minimum passage count above a similarity floor (R16) |
| Alert matching | Keyword and intent modes, independently operable; intent reuses pgvector (R18) |
| Context budget | Per-call input budget enforced by the adapter; Ask answers each question without prior turns (R19) |
| Untrusted text | Usernames masked before provider calls (R1); Reddit and model text rendered as escaped text, `{@html}` lint-banned (R10) |
| Scale | One user; up to 50 communities per audience; 8 user stories; 83 functional requirements |

No `NEEDS CLARIFICATION` items remain.
