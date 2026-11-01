# REST API Contract: Reddit Audience Intelligence

**Feature**: `001-reddit-audience-intelligence`
**Date**: 2026-08-14

This file is the **single source of truth** for the HTTP surface. Per Constitution III, any change to
that surface MUST update this file in the same change set, and the surface MUST NOT be documented in
detail anywhere else — `README.md` links here rather than restating it. Every endpoint MUST declare
Pydantic request and response models; returning bare dicts or ORM instances from a router is
prohibited.

## Cross-cutting conventions

**Pagination envelope** — every collection response uses the same shape, so clients handle all
endpoints identically (Constitution V):

```json
{
  "items": [],
  "page": 1,
  "page_size": 25,
  "total": 0,
  "has_more": false
}
```

`page_size` has an enforced maximum; unbounded queries are prohibited (Constitution VI).

**Error envelope** — produced by shared middleware from typed exceptions, never assembled in a
router. Messages state what failed and what the user can do next (FR-052); stack traces and raw
exception text never reach the client (Constitution V).

```json
{
  "error": {
    "code": "audience_limit_reached",
    "message": "This audience already has 50 communities. Remove one before adding another.",
    "details": {}
  }
}
```

**Timestamps** — all UTC ISO 8601, localized only at render time (Constitution V).

**Freshness** — any response derived from collected material carries `last_refreshed_at` (FR-013).

**Auth** — session-based, single user (R11). All endpoints require an authenticated session **except
the three session endpoints below**: `POST /auth/session` and `DELETE /auth/session` are open by
necessity, and `GET /auth/session` is open so that an unauthenticated caller receives a `401` rather
than being unable to ask. That list is exhaustive — no other endpoint may be exempted without amending
this file. There is no registration endpoint. Sessions expire and can be invalidated, and credentials
are stored hashed, because the application is written to public-exposure standard even though it binds
to loopback in this release (FR-078, FR-079).

**Limits** — spend ceilings and request rate limits are enforced server-side on every endpoint that
can trigger a paid call, never by the client (FR-080). A client that omits the check must not be able
to exceed them.

---

## Sessions (FR-048, FR-079)

Not part of any user story: every story depends on being signed in, so these are cross-cutting. They
are the only endpoints that establish or end a session, and the only ones exempt from carrying one.

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `POST` | `/auth/session` | Sign in; sets the `HttpOnly` session cookie | FR-048, FR-079 |
| `DELETE` | `/auth/session` | Sign out, invalidating the session immediately | FR-079 |
| `GET` | `/auth/session` | The current session's username and expiry | FR-048 |

`POST` carries `{"username": ..., "password": ...}` and returns `{"username": ..., "expires_at": ...}`.

**The session token appears only in the `Set-Cookie` header, never in a response body**, because
FR-079 requires secrets to be unreadable by the client:

```
Set-Cookie: jammysearch_session=<token>; HttpOnly; SameSite=Lax; Path=/; Max-Age=<session TTL>
```

`Secure` is deliberately absent: this release serves plain HTTP on loopback, and FR-081 defers
transport security to the deployment layer. It becomes **mandatory** the moment `ALLOW_REMOTE_EXPOSURE`
is used, since without it the cookie would travel in clear text — a change to this contract and to the
route, not a deployment setting.

Failure behaviour, all of it load-bearing rather than incidental:

- A wrong password, an unknown username, and an unconfigured `AUTH_PASSWORD_HASH` MUST return the
  **same** `401` with code `not_authenticated` and the same message. Distinguishing them would tell an
  unauthenticated caller which usernames exist, or that the deployment has no credential set.
- Sign-in **attempts** are rate-limited, and exceeding the allowance returns `429` with code
  `rate_limited` and `retry_after_seconds`. Attempts are counted regardless of outcome, not failures
  only: the control must bound the endpoint even for a caller who ignores what it returns. The limit is
  keyed on the calling client rather than on a session, since sign-in is where no session exists yet.
  FR-081 defers *network-level* brute-force protection; this is an application-level control and stays.
- `DELETE` returns `204` whether or not the cookie named a live session — reporting the difference would
  confirm that a token was valid. It is therefore idempotent.
- `GET` without a cookie, or with an expired, unknown, or invalidated one, returns the standard `401`.
  The client uses this on load to decide whether to show the sign-in screen, instead of provoking a
  `401` on a data route.

## Audiences — User Story 1

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `GET` | `/audiences` | List the user's audiences | FR-001 |
| `POST` | `/audiences` | Create an audience | FR-001, FR-004, FR-005 |
| `GET` | `/audiences/{id}` | Audience detail with member communities | FR-001 |
| `PATCH` | `/audiences/{id}` | Rename | FR-002 |
| `DELETE` | `/audiences/{id}` | Delete, with warning that analysis becomes unreachable | FR-003 |
| `POST` | `/audiences/{id}/communities` | Add a community | FR-002, FR-004, FR-005, FR-050 |
| `DELETE` | `/audiences/{id}/communities/{name}` | Remove a community | FR-002 |
| `GET` | `/audiences/starter` | Browse the shipped starter set | FR-006 |
| `POST` | `/audiences/starter/{id}/copy` | Save an editable copy | FR-006 |
| `GET` | `/audiences/{id}/suggestions` | Related communities to add | FR-007 |

`POST /audiences/{id}/communities` returns `409` with a specific `code` distinguishing
`community_not_found`, `community_private`, `community_banned`, and `community_quarantined` — FR-050
requires the user to be told which applies, not given a generic failure.

## Feed — User Story 1

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `GET` | `/audiences/{id}/feed` | Combined paginated timeline | FR-008, FR-011, FR-012 |
| `GET` | `/posts/{id}` | Full post title and body | FR-010 |

Query parameters: `sort` (`new`, `top_today`, `top_week` — FR-009), `page`, `page_size`.

Each item carries its source community (FR-008) and `flagged_adult` (FR-051). Cross-posts and
verbatim reposts are collapsed before the page is assembled (FR-011).

Posts purged after deletion at the source (FR-068) are excluded from feeds and search results
entirely. `GET /posts/{id}` for a purged post returns `200` with `availability` set and no text —
a tombstone rather than a `404` — so that a citation held by an existing answer or theme resolves to
an explanation instead of breaking (see the corresponding edge case in the spec).

## Search — User Story 2

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `POST` | `/search` | Search with filters | FR-014 – FR-020 |

Request carries: `scope` (`audience`, `all_saved`, `all_reddit` — FR-019, defaulting to `audience`),
`audience_id`, `keywords` each with an `enabled` flag (FR-015), `time_period`, `limit`, `sort`
(FR-016), `include_communities` / `exclude_communities` (FR-017), `include_authors` /
`exclude_authors` (FR-018).

Response always carries `scope_used`, the matching posts, and `analysis_available`.

For saved-material scopes, `analysis_available: true` means the response also carries the detected
`patterns` and `sentiment` (FR-020). It is `false` — with a stated reason — when the interpretation
capability has not been built yet, is failing, or the material has not been interpreted. The client
MUST surface that reason; silently omitting analysis is prohibited.

For `all_reddit`, `analysis_available` is always `false` and `live` is `true`; the client must
surface that results are live, may be slower, and carry no analysis (FR-019, FR-020). `all_reddit` is
exempt from SC-004's latency target.

## Analysis — User Story 3

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `GET` | `/audiences/{id}/analysis/topics` | Topics across the audience | FR-021 |
| `GET` | `/audiences/{id}/analysis/themes` | Themes, `kind` distinguishing scored from interpreted | FR-021, FR-022 |
| `GET` | `/audiences/{id}/analysis/themes/{theme_id}` | Description, sub-categories, contributing topics and communities, posts | FR-023 |
| `GET` | `/audiences/{id}/analysis/themes/{theme_id}/patterns` | Patterns and sentiment | FR-024 |
| `GET` | `/audiences/{id}/analysis/trends` | Share of discussion over time | FR-053 – FR-055 |

Trend responses carry per-bucket `share`, `distinct_post_count`, `distinct_author_count`, and
`collection_coverage`, plus the `period_covered`. When the collected period is too short, the
response returns `trend_available: false` with the period length rather than a direction (FR-055).
For a scored theme, `trend_available` is always `false` with reason `window_defined`, because its
membership is set by a time window rather than accumulated over one (FR-053, R20).

All analysis responses carry `derived_from_comments` (FR-027b) and, when material is insufficient,
`sufficient: false` with what is missing (FR-025). Topics and themes also carry `non_english_share`, the
share of their interpreted posts in a language other than English, so the client can flag reduced
reliability (spec edge case on non-English posts; R23).

Every analysis response also carries an `analysis_state` block — `state` (`complete`, `partial`, or
`none`), `items_done`, and `items_total` (FR-074). A `partial` state MUST be rendered as visibly
incomplete; presenting partial results as final is prohibited, since the researcher cannot otherwise
distinguish "this audience discusses three themes" from "we have analysed a third of it".

## Ask — User Story 4

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `POST` | `/audiences/{id}/ask` | Ask a question; streamed response | FR-028 – FR-032 |
| `GET` | `/audiences/{id}/ask/{turn_id}` | Retrieve a past answer with citations | FR-029 |

Streamed per Constitution VI and FR-031. Every response carries `outcome`, which is one of:

| `outcome` | Meaning | Body |
|---|---|---|
| `answered` | Retrieval met the threshold and an answer was produced | Answer text plus a non-empty `citations` array, each openable in full (FR-029) |
| `refused` | Fewer than the required number of passages cleared the similarity floor (FR-076) | Plain explanation, no answer text — answering from general knowledge is prohibited (FR-030) |
| `failed` | The provider errored or timed out mid-answer (FR-075) | Failure explanation; any partial text is discarded, not shown or stored |

`refused` and `failed` MUST NOT be collapsed into a single error state. A refusal is the system
working correctly; a failure is the provider breaking. Conflating them corrupts the SC-007 refusal
measurement by counting outages as correct refusals.

Refusal responses also carry `passages_above_floor` so the decision can be audited against the
threshold that produced it.

## Alerts — User Story 5

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `GET` | `/alerts/rules` | List rules | FR-056 |
| `POST` | `/alerts/rules` | Create a rule scoped to an audience | FR-056 |
| `PATCH` | `/alerts/rules/{id}` | Edit keywords, pause, or resume | FR-056, FR-059 |
| `DELETE` | `/alerts/rules/{id}` | Delete; recorded matches survive | FR-059 |
| `GET` | `/alerts/matches` | Matches, grouped so one post appears once | FR-058 |
| `POST` | `/alerts/matches/{id}/read` | Mark seen | FR-058 |

Rule requests carry `match_mode` (`keyword`, `intent`, or `both`), `keywords`, `intent_text`, and an
optional `similarity_threshold` (FR-082–FR-084). Validation rejects a rule missing the fields its mode
requires.

Rule responses carry `intent_matching_active` — false when the retrieval capability is unavailable or
the rule's intent has not been embedded yet. A rule in that state still evaluates keywords, and the
client MUST surface the degraded status rather than presenting the rule as fully operational
(FR-085).

Match responses list every rule a post matched and the `matched_terms` that fired (FR-058), plus
`matched_mode` and, for intent matches, `similarity` — so a surprising match can be judged and the
rule's threshold raised rather than the feature being written off. They embed enough post content to
be actionable in place (FR-062). A rule matching an unusually high share
of material returns `matching_broadly: true` so the client can offer to narrow it (FR-060). A rule
whose audience contains an unavailable community still evaluates and reports
`degraded_communities` (FR-061).

Delivery is in-app only; there are no outbound-channel endpoints (FR-063).

## Community discovery — User Story 6

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `GET` | `/communities/search` | Search by name, description, topic | FR-034 |
| `GET` | `/communities/ranked` | Rank by size, activity, or growth with filters | FR-035 |
| `GET` | `/communities/{name}` | Detail with size, newness, and activity tags | FR-036 |
| `GET` | `/communities/{name}/history` | Membership and posting volume over time | FR-037, FR-039 |

History returns `history_available: false` with the collected period length when there is too little
to plot (FR-039) rather than a misleading line.

## Bookmarks — User Story 7

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `GET` | `/bookmarks` | List, filterable by `status` | FR-041, FR-065 |
| `POST` | `/bookmarks` | Save a post, capturing its content | FR-041, FR-043 |
| `PATCH` | `/bookmarks/{id}` | Update note or status | FR-042, FR-064 |
| `DELETE` | `/bookmarks/{id}` | Remove | FR-041 |

Bookmarks of posts removed at the source return captured content with `source_available: false`
(FR-043). Notes and status are never transmitted to the source (FR-066).

## Operations and transparency — User Story 8

| Method | Path | Purpose | Requirements |
|---|---|---|---|
| `GET` | `/ops/usage` | Cost, tokens, latency, cache hit rate in aggregate | FR-044, FR-045 |
| `GET` | `/ops/usage/{audience_id}` | The same, scoped to one audience | FR-044 |
| `GET` | `/ops/quota` | Reddit calls used versus avoided by caching | FR-045 |
| `GET` | `/ops/limits` | Current spend ceilings and consumption against them | FR-046 |
| `GET` | `/ops/evaluation` | Published accuracy against the labeled reference set | FR-047, SC-008 |
| `GET` | `/ops/retrieval-settings` | Current minimum passage count and similarity floor | FR-076 |
| `GET` | `/ops/backups` | Last backup time, retention window, last verified restore | FR-070, FR-071 |
| `GET` | `/ops/freshness` | Last collection and last availability re-check per audience | FR-013, FR-067 |

When a spend ceiling is reached, the analysis and Ask endpoints return `429` with code
`spend_limit_reached` and a clear explanation rather than continuing to spend (FR-046).

---

## Documentation rule

This file is the only place the HTTP surface is described in detail. `README.md` carries a link and a
one-paragraph overview; it MUST NOT reproduce routes, request shapes, or response shapes. Constitution
III (v1.2.3) forbids maintaining the same API surface in two locations, because duplicated API
documentation reliably drifts and a drifted API document is worse than none.
