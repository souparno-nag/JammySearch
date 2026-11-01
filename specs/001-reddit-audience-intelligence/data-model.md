# Phase 1 Data Model: Reddit Audience Intelligence

**Feature**: `001-reddit-audience-intelligence`
**Date**: 2026-08-14

PostgreSQL is the system of record for everything below, including embeddings via `pgvector`. Redis
holds only derived cache entries and the Celery queue, and is reconstructible from these tables
(Constitution, Technology and Data Constraints). Every table carries `created_at` and `updated_at` as
UTC timestamps; they are omitted from the field lists for brevity.

Ownership is stated per entity because Constitution II forbids a module from querying another
module's tables directly.

---

## Collection layer — owned by `app/reddit/` and `app/feed/`

### Community

One tracked subreddit. Owned by `app/reddit/`.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `name` | text | Unique, canonical subreddit name |
| `title` / `description` | text | From the source |
| `subscriber_count` | integer | Current value; history lives in `CommunitySnapshot` |
| `created_at_source` | timestamp | Community's own creation date — drives the "new" tag |
| `over_18` | boolean | Drives the flagging in FR-051 |
| `availability` | enum | `available`, `private`, `banned`, `quarantined`, `not_found` — FR-050 |
| `last_refreshed_at` | timestamp | Surfaced per FR-013 |

**Validation**: `name` is unique and normalized to the source's canonical casing. `availability`
transitions are recorded, not overwritten silently — FR-049 and the edge case for a community
becoming unavailable both depend on knowing when it changed.

### CommunitySnapshot

One recording of a community's statistics at a point in time. Owned by `app/reddit/`.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `community_id` | uuid → Community | Indexed with `captured_at` |
| `captured_at` | timestamp | Daily cadence |
| `subscriber_count` | integer | |
| `posts_in_period` | integer | |
| `active_user_count` | integer | Nullable — not always exposed by the source |

**Why it exists**: the source has no history endpoint. This table *is* the history (FR-037, FR-038),
and a missed day is permanently unrecoverable — which is why R3 makes this job independent of
audience collection.

### Post

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `source_id` | text | Unique; the source's own identifier |
| `community_id` | uuid → Community | |
| `title` / `body` | text | Captured text, retained for FR-043 even if removed at source |
| `author_name` | text | Nullable for deleted accounts |
| `posted_at` | timestamp | |
| `score` / `comment_count` | integer | Engagement, drives R5's threshold and scoring themes |
| `crosspost_parent_id` | text | Nullable; deterministic cross-post collapse (R4) |
| `content_hash` | text | Normalized-text hash for verbatim repost detection (R4) |
| `availability` | enum | `available`, `deleted`, `removed` |
| `edited_at_source` | timestamp | Nullable; set by the re-check when the source reports an edit, so the captured text is shown as possibly out of date |
| `flagged_adult` | boolean | FR-051 |

**Validation**: `source_id` unique. FR-011 collapses on `crosspost_parent_id` first, then
`content_hash`; both are indexed.

**Purge semantics (FR-068)**: when `availability` becomes `deleted` or `removed`, `title` and `body`
are cleared and `purged_at` is set. Every other field survives as a tombstone. The row is never
deleted, because `DiscussionBucket` denominators and historical counts are computed from it —
removing it would silently rewrite a past week's trend. `content_hash` is retained so a later repost
of the same text is still recognised as a duplicate.

### Comment

Top-level comments only, and only for posts above the engagement threshold (FR-027, R5).

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `source_id` | text | Unique |
| `post_id` | uuid → Post | |
| `body` | text | |
| `author_name` | text | Nullable |
| `posted_at` | timestamp | |
| `score` | integer | |

**Validation**: nested replies are not stored in this release (spec, Out of Scope). A comment's
existence implies its parent post met the threshold, which is what FR-027b reports on. Comments
follow the same purge semantics as posts (FR-068).

---

## Audience layer — owned by `app/audiences/`

### Audience

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `user_id` | uuid → User | |
| `name` | text | Unique per user |
| `origin` | enum | `user_created` or `copied_from_starter` |
| `starter_source_id` | uuid | Nullable; records which starter set it came from |

**Validation**: FR-005 caps membership at 50 communities. FR-004 forbids the same community twice.
FR-006's copy semantics mean `starter_source_id` is provenance only — later edits to a starter
audience must not propagate, so no live foreign-key relationship is used for content.

### AudienceCommunity

Join between `Audience` and `Community`, with a unique constraint on the pair (FR-004).

### StarterAudience

The shipped, product-authored set (FR-006). Read-only to the user; saving produces a full copy as a
new `Audience`.

---

## Retrieval layer — owned by `app/ai/`

### ContentChunk

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `post_id` | uuid → Post | |
| `comment_id` | uuid → Comment | Nullable; set when the chunk is comment text |
| `text` | text | The embedded span |
| `embedding` | vector | pgvector column, indexed |
| `embedding_model_id` | text | Pinned identifier — Constitution VII |

**Validation**: exactly one of `post_id` / `comment_id` origin is authoritative for citation.
`embedding_model_id` is stored per row so a model change is detectable rather than silently mixing
vector spaces — re-embedding is required when it changes.

**Purge (FR-068)**: chunks are **deleted outright** when their source is purged, not tombstoned. A
vector derived from removed content still encodes that content, so leaving it in the index would
defeat the purge — purged material must become unretrievable, not merely unreadable.

---

## Interpretation layer — owned by `app/ai/`

### Topic and Theme

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `audience_id` | uuid → Audience | |
| `label` | text | |
| `description` | text | Themes only — FR-023 |
| `kind` | enum | Themes only: `scored` or `interpreted` — FR-022 |
| `scored_definition` | enum | Scored themes only: `top_week`, `discussed_week`, `top_month`, `discussed_month` (R20) |
| `parent_theme_id` | uuid | Nullable; interpreted-theme sub-categories. A scored theme's sub-categories are the interpreted themes its posts belong to, derived at read time (R20) |
| `prompt_version` / `model_id` | text | Constitution VII provenance; null for scored themes, which involve no model |
| `derived_from_comments` | boolean | FR-027b |

### ThemePost / TopicPost

Join tables linking an interpretation to the posts behind it, each carrying `post_language` (ISO 639-1, from the theme-tagging output; R23). These are what make citations and
distinct-author counts (FR-054) computable.

### DiscussionBucket

Pre-aggregated trend storage (R6, FR-053–FR-055).

| Field | Type | Notes |
|---|---|---|
| `topic_id` / `theme_id` | uuid | One of the two |
| `bucket_start` | timestamp | Fixed-width period |
| `post_count` | integer | |
| `audience_post_count` | integer | Denominator — makes the stored figure a *share* |
| `distinct_author_count` | integer | FR-054 |
| `collection_coverage` | float | 0–1; makes a collection gap visible rather than reading as decline |

**Why `audience_post_count` is stored**: without the denominator alongside the numerator, a trend
cannot distinguish "this grew" from "we collected more" — the failure R6 exists to prevent.

### Pattern

A recurring observation across a theme's or search result's posts, with provenance fields as above.

### AnalysisRun

Tracks a chunked, resumable interpretation pass (FR-072–FR-074, R15).

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `audience_id` | uuid → Audience | |
| `state` | enum | `running`, `interrupted`, `complete` |
| `cursor` | text | Position reached — the field that makes this resumable rather than restartable |
| `items_total` / `items_done` | integer | Drives the completion proportion shown to the user |
| `prompt_version` / `model_id` | text | Provenance for the run |
| `last_error` | text | Nullable; why it stopped |

**State transitions**: `running → interrupted` on failure, `interrupted → running` on resume,
`running → complete` when the cursor reaches the end. An audience with an `interrupted` run MUST be
presented as partially analysed (FR-074), never as finished with fewer results.

**Why the cursor is persisted**: without it, "resume" degrades into "restart", which re-spends on
material already interpreted. The inference cache keyed on `(content_hash, prompt_version, model_id)`
is the second line of defence — even a retried chunk incurs no new charge (FR-073).

### AskSession and AskTurn

Conversation state persisted per Constitution VII — never in process memory. Each turn is answered
independently: no prior turn enters the prompt (R19), which is also what lets FR-032 hold — the same
question against unchanged material assembles the same context every time.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `audience_id` | uuid → Audience | |
| `question` / `answer` | text | |
| `outcome` | enum | `answered`, `refused`, `failed` — FR-030, FR-075, SC-007 |
| `passages_above_floor` | integer | How many retrieved passages cleared the similarity floor |
| `prompt_version` / `model_id` | text | |

**Why `outcome` is three-valued**: a refusal and a failure look identical to a naive boolean, but they
mean opposite things — a refusal is the system working correctly (FR-030), a failure is the provider
breaking (FR-075). Conflating them would corrupt the SC-007 refusal measurement by counting outages
as correct refusals. `passages_above_floor` is stored so a refusal decision can be audited against
the threshold that produced it (FR-076).

### AskCitation

Links an `AskTurn` to the `ContentChunk` and `Post` it drew on (FR-029). An answer with `refused =
false` and no citations is invalid and must fail validation rather than being displayed.

---

## Alerts layer — owned by `app/alerts/`

### AlertRule

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `user_id` / `audience_id` | uuid | |
| `name` | text | |
| `keywords` | text[] | Nullable when the rule is intent-only |
| `match_mode` | enum | `keyword`, `intent`, or `both` — FR-083 |
| `intent_text` | text | Nullable; the plain-language description of what to watch for |
| `intent_embedding` | vector | Nullable; pgvector column, computed once when `intent_text` is set or changed |
| `similarity_threshold` | float | Nullable; per-rule override of the configured default — FR-084 |
| `state` | enum | `active` or `paused` — FR-056 |
| `last_evaluated_at` | timestamp | Nullable; distinguishes an active rule that matched nothing from one that is not running |

**State transitions**: `active ⇄ paused`; deletion is soft, because FR-059 requires matches to
survive rule deletion.

**Validation**: a rule MUST carry keywords when `match_mode` is `keyword` or `both`, and
`intent_text` when it is `intent` or `both`. `intent_embedding` is recomputed whenever `intent_text`
changes — a stale embedding would silently match the rule's *previous* meaning.

**Degradation (FR-085)**: `intent_embedding` may be null because embedding infrastructure does not
yet exist (US4 not built) or is failing. In that state a `both` rule still evaluates its keywords,
and an `intent`-only rule is reported as not currently active. It is never treated as a rule that
matched nothing — those are different facts and the researcher must be able to tell them apart.

### AlertMatch

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `rule_id` | uuid → AlertRule | Retained after the rule is deleted |
| `post_id` | uuid → Post | |
| `matched_at` | timestamp | |
| `matched_terms` | text[] | Which keywords fired — FR-058; empty for intent-only matches |
| `matched_mode` | enum | `keyword` or `intent` — which mode produced this match (FR-083) |
| `similarity` | float | Nullable; how close an intent match was, so a surprising match can be judged |

**Validation**: unique on `(rule_id, post_id)` so re-evaluation cannot duplicate a match. The edge
case of one post matching several rules is handled at read time by grouping on `post_id`, so the
researcher sees the post once with all matching rules listed.

---

## User layer — owned by `app/users/`

### User

Single-user deployment (R11). Credentials from configuration; no self-service registration.

### Bookmark

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `user_id` / `post_id` | uuid | Unique together |
| `note` | text | Private — FR-042, FR-066 |
| `status` | enum | `new`, `contacted`, `dismissed` — FR-064 |
| `captured_title` / `captured_body` | text | Snapshot at save time — FR-043 |

**State transitions**: `new ⇄ contacted ⇄ dismissed`, freely reversible (FR-064). Status and note are
never transmitted to the source (FR-066).

**Why content is captured**: FR-043 requires a bookmark to stay readable after the original is
removed, so the text is copied at save time rather than referenced.

**Purge exemption (FR-069)**: a bookmark's captured text survives the purge that clears the
underlying `Post`. This is the one place removed content persists, and it is bounded by three rules —
the copy stays private to the user, is never republished, exported, or shared, and is destroyed when
the bookmark is deleted. Deleting a bookmark is therefore a destructive operation on the last
remaining copy, not merely the removal of a reference.

---

## Observability layer — owned by `app/ops/`

### UsageRecord

One row per external call — model or Reddit (Constitution VI and IX).

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `service` | enum | `model` or `reddit` |
| `feature` | text | Calling feature name |
| `audience_id` | uuid | Nullable; enables per-audience attribution |
| `model_id` / `prompt_version` | text | Nullable for Reddit calls |
| `input_tokens` / `output_tokens` | integer | Nullable for Reddit calls |
| `cost` | numeric | Computed at call time |
| `latency_ms` | integer | |
| `cache_hit` | boolean | Feeds FR-045 and the cache-hit surface |

### InferenceCache

Keyed on `(content_hash, prompt_version, model_id)` per Constitution VII, so an unchanged input never
produces a second charge or a different answer. This is what makes FR-026, FR-032, and SC-009
satisfiable.

### SpendLedger

Rolling per-request and per-day totals backing the ceilings in FR-046. Checked *before* a call is
made, not after, and enforced server-side as a control in its own right rather than as an interface
convenience (FR-080).

### RetrievalSettings

The configured refusal gate (FR-076): the minimum count of passages required and the similarity floor
they must clear. Held as configuration rather than per-row data, but surfaced through `/ops` so the
current values are discoverable, and versioned alongside prompt versions because changing either
counts as a retrieval change requiring an evaluation run (FR-077).

### BackupRun

One record per backup attempt (FR-070, FR-071): when it ran, where it was written, its size, whether
it succeeded, and when it was last verified by an actual restore. The verification timestamp is the
point of the table — a backup that has never been restored is not evidence of recoverability.

---

## Entity relationship summary

```text
User ──< Audience ──< AudienceCommunity >── Community ──< CommunitySnapshot
             │                                   │
             │                                   └──< Post ──< Comment
             │                                          │
             ├──< AlertRule ──< AlertMatch >────────────┤
             │                                          │
             ├──< Topic/Theme ──< ThemePost >───────────┤
             │         └──< DiscussionBucket            │
             │                                          │
             ├──< AskSession ──< AskTurn ──< AskCitation ──> ContentChunk
             │                                          │
             └──< Bookmark >────────────────────────────┘

StarterAudience ··(copied at save time, no live link)··> Audience
UsageRecord / InferenceCache / SpendLedger — written by every external call path
```
