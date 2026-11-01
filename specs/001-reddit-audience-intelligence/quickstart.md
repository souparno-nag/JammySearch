# Quickstart & Validation Guide: Reddit Audience Intelligence

**Feature**: `001-reddit-audience-intelligence`
**Date**: 2026-08-14

How to bring the system up and prove each user story actually works. This is a validation guide —
implementation belongs in `tasks.md`. Scenarios are ordered by user-story priority, so P1 can be
validated long before the later stories exist.

## Prerequisites

- Docker and Docker Compose (PostgreSQL with the `pgvector` extension, Redis)
- Python 3.11 with the project virtualenv at the repository root
- Node for the frontend
- Reddit API credentials in `.env` at the repository root: `REDDIT_CLIENT_ID`,
  `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`
- Model provider credentials in `.env`, plus the **explicitly pinned** model identifier — a floating
  alias is prohibited (Constitution VII)

## Bring it up

```bash
source reddit-env/bin/activate
pip install -r requirements.txt

docker compose up -d          # PostgreSQL + pgvector, Redis
alembic upgrade head          # Schema — never create_all() against a real database

uvicorn app.main:app --reload                     # API
celery -A workers.celery_app worker --loglevel=info   # Workers
celery -A workers.celery_app beat --loglevel=info     # Scheduler

cd frontend && npm install && npm run dev
```

Seed the shipped starter audiences and a demo corpus so the product is not empty on first open:

```bash
python -m scripts.seed_starter_audiences
python -m scripts.seed_demo_corpus --audience "SaaS Founders"
```

> A reviewer who can see a populated audience within a minute of `docker compose up` will forgive a
> great deal. An empty product is the most common reason a working project reads as unfinished.

## Checks that must pass before any change is complete

```bash
pytest                                  # Full suite; no test may contact Reddit or a model provider
pytest --cov=app --cov-report=term      # Service-layer coverage must stay at or above 80%
ruff check . && ruff format --check .   # Lint and format
python evals/run_eval.py                # Required on any prompt, model, chunking, or retrieval change
```

---

## Scenario 1 — Audience and feed (User Story 1, P1)

1. Sign in.
2. Search for three communities by name and create an audience "Designers" from them.
3. Trigger a collection cycle (or wait for Beat).
4. Open the audience feed.

**Expect**: a single timeline drawn from all three communities, each post labeled with its source
community; sorting by new / top today / top week reorders without losing place; opening a post shows
full title and body in-app; the audience shows a `last_refreshed_at`.

**Also verify**: add a fourth community and remove one — the feed reflects it on next load. Add a
private or nonexistent community and confirm the error names *which* condition applies (FR-050), not
a generic failure.

**Dedup check**: find content cross-posted between two communities in the audience and confirm it
appears once (FR-011).

## Scenario 2 — Search (User Story 2, P2)

1. Search the audience for two keywords over the last month.
2. Disable one keyword; confirm results recompute as if it were never entered.
3. Exclude one community, then one author; confirm both disappear from results.
4. Search for a nonsense string.

**Expect**: results confined to the audience; the empty case explains what to change rather than
rendering blank (Constitution V's four states); results carry patterns and sentiment.

**Scope check**: switch scope to `all_reddit`. Confirm results reach beyond saved communities, are
marked live, and explicitly state that pattern and sentiment analysis is unavailable (FR-019,
FR-020). Confirm the default on a fresh search is back to saved material.

## Scenario 3 — Topics, themes, trends (User Story 3, P3)

1. Open the analysis view for an audience with at least a few hundred collected posts.
2. Select one theme; request its patterns.
3. Open the trends view.

**Expect**: topics and both theme kinds listed, scored themes distinguishable from interpreted ones;
theme detail shows description, sub-categories, contributing topics and communities, and its posts;
trends show share of discussion with distinct post and author counts.

**Negative checks**: on a brand-new audience, analysis must say material is insufficient rather than
producing confident output (FR-025). On a short collection period, trends must return
`trend_available: false` rather than a slope (FR-055).

**Determinism check**: reopen the analysis unchanged. Same results, and `/ops/usage` shows no new
spend (FR-026, SC-009).

## Scenario 4 — Ask (User Story 4, P4)

1. Ask a question the audience genuinely answers.
2. Ask one it cannot possibly answer.
3. Ask the first question a second time.

**Expect**: (1) a streamed answer citing specific openable posts; (2) an explicit refusal — no answer
from general knowledge (FR-030, SC-007); (3) an answer consistent with the first, with no new spend.

**Guardrail check**: seed a post whose body contains instruction-like text ("ignore previous
instructions and…"). Ask a question that retrieves it. The answer must treat it as material to
analyze, never as direction (FR-033, Constitution VIII).

**Threshold check**: ask a question that retrieves exactly one strong match and nothing else. It must
be refused, because one passage does not meet the minimum count (FR-076). Confirm the response
reports `passages_above_floor` so the decision is auditable, and that
`GET /ops/retrieval-settings` shows the values that produced it.

**Failure check**: with the provider unreachable, ask a question mid-stream. The response must come
back with `outcome: failed`, not `refused` — and no partial text may be shown or stored (FR-075).
Confirm the failed turn does not appear in the SC-007 refusal statistics.

## Scenario 5 — Alerts (User Story 5, P5)

1. Create a rule with two keywords scoped to an audience.
2. Run a collection cycle that includes a matching post.
3. Edit the rule's keywords, then delete it.

**Expect**: the match appears in-app within 15 minutes of collection (SC-014), naming the rule and the
terms that fired; a non-matching post does not appear; editing and deleting the rule leaves recorded
matches intact (FR-059).

**Intent check**: create a rule describing an intent ("someone looking for a tool to monitor
subreddits") using no keywords. Seed a post phrasing that need entirely differently. It must match,
and the match must report `matched_mode: intent` with its `similarity` (FR-082, FR-083).

**Degradation check**: disable the embedding capability and re-run evaluation. Keyword rules must
keep matching, and intent rules must report `intent_matching_active: false` — never appear to be
working while silently matching nothing (FR-085).

**Also verify**: a deliberately broad rule reports `matching_broadly` and offers narrowing (FR-060).
A rule whose audience contains an unavailable community keeps working and names the degraded one
(FR-061). A post matching two rules appears once with both listed.

## Scenario 6 — Discovery (User Story 6, P6)

Search communities by topic, filter to a size band, sort by activity, inspect tags and history, add
one to an audience from the results.

**Expect**: tags for size, newness, activity; history plotted only for the collected period, with
`history_available: false` and the period length when too short (FR-039).

> **Start the snapshot job on day one.** `snapshot.py` accumulates the only history this product will
> ever have — the source exposes none — so a day not collected is permanently lost. This scenario
> stays unverifiable for weeks regardless of when the UI is built.

## Scenario 7 — Bookmarks (User Story 7, P7)

Bookmark from the feed, from a search result, and from an alert match. Add a note. Set status to
`contacted`. Filter by status. Confirm a bookmark of a since-deleted post still shows captured text
marked unavailable (FR-043).

## Scenario 8 — Transparency (User Story 8, P8)

Open `/ops/usage` after running an analysis and an Ask.

**Expect**: cost, tokens, latency, and cache hit rate, per audience and in aggregate; Reddit calls
used versus avoided; current spend ceilings and consumption.

**Ceiling check**: set a low daily ceiling, exhaust it, and confirm further analysis fails with a
clear message rather than continuing to spend (FR-046).

**Published accuracy**: `/ops/evaluation` reports agreement against the labeled set alongside the
non-LLM baseline (FR-047, SC-008, Constitution IX).

## Scenario 9 — Deletion propagation (FR-067–FR-069)

1. Collect a post, confirm it appears in the feed, in search, and as an Ask citation.
2. Bookmark it.
3. Delete it at the source (use a post you control), then run the availability re-check.

**Expect**: the post disappears from feeds, search, and analysis material; its text is gone from
storage; its non-content row survives so historical counts are unchanged; its embedding chunks are
deleted so it can no longer be retrieved. Your bookmark still shows the captured text, marked as no
longer available at the source (FR-069).

**Retrieval check**: re-ask the question that previously cited it. The purged material must not be
retrievable — verifying that chunks were deleted, not merely that text was blanked.

**Citation check**: open the earlier answer that cited it. The citation must resolve to a tombstone
explaining the material is gone, not break and not silently vanish from the record.

**Bookmark deletion check**: delete the bookmark. The captured text must be destroyed — it was the
last remaining copy.

## Scenario 10 — Backup and restore (FR-070, FR-071, SC-018)

1. Let the nightly backup run, then check `GET /ops/backups`.
2. Restore the most recent dump into a scratch database.
3. Compare row counts on community snapshots and bookmarks.

**Expect**: a backup exists outside the application container, a rolling window is retained, and the
restore reproduces the irreplaceable tables intact. `GET /ops/backups` reports when a restore was
last actually verified — not merely when a dump was last written.

> Run this before you have data worth losing, not after. The usual failure is not a missing backup
> but an unrestorable one, and you only find out at the worst possible moment.

## Scenario 11 — Analysis interruption and resume (FR-072–FR-074, SC-019)

1. Start an analysis run over a few hundred posts.
2. Make the provider fail partway (revoke the key or block the host).
3. Note the audience state, then restore access and re-run.

**Expect**: chunks completed before the failure are kept; the audience reports `analysis_state:
partial` with `items_done` and `items_total`, and the interface renders it as visibly incomplete; the
resumed run starts from the recorded cursor rather than the beginning.

**Cost check**: compare `/ops/usage` before and after the resume. Material analysed before the
interruption must incur no new spend (SC-019).

## Scenario 12 — Deployment posture (FR-078–FR-081, SC-020)

1. Start the application normally — confirm it binds to loopback only and is unreachable from another
   machine.
2. Attempt to start it bound to a non-local interface without the explicit exposure setting.
3. Set the exposure flag and start again.

**Expect**: (2) refuses to start and explains why, rather than silently becoming reachable; (3)
succeeds with no code change — which is the whole of SC-020.

**Hardening check**: confirm stored credentials are hashed, that a session expires and can be
invalidated, and that no secret appears in any response, log line, or client-side bundle (FR-079).
Confirm spend ceilings hold when the request is made directly, bypassing the interface (FR-080).

**Scope check**: transport security, abuse protection, and external monitoring are deliberately
absent (FR-081). Their absence is correct here and is not a finding.

---

## Definition of done for this feature

- All twelve scenarios pass, including every negative, guardrail, and resilience check.
- Test suite green; service-layer coverage at or above 80%; ruff clean.
- `python evals/run_eval.py` reports theme and sentiment agreement at or above 75% against the
  labeled set, with the baseline comparison recorded.
- No PRAW import outside `backend/app/reddit/`; no cross-module table access.
- `README.md` links to `contracts/rest-api.md` rather than restating the API surface, and no route or
  payload detail has crept back into it (Constitution III).
- A restore has actually been performed from a real backup, not just written (FR-071).
- Purged material is unretrievable, not merely unreadable — verified by re-running a query that
  previously retrieved it.
- The application refuses to bind a non-local interface without the explicit exposure setting.
