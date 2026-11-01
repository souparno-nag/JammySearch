# Feature Specification: Reddit Audience Intelligence

**Feature Branch**: `001-reddit-audience-intelligence`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Read README.md in this repo and use it as the basis for the spec — focus on the what/why, not implementation details."

## Overview

JammySearch lets a researcher pick a set of Reddit communities, treat them as a single named
"audience", and then read, search, and interpret what that audience is talking about — in order to
find recurring pain points, potential leads, and content ideas without manually reading thousands of
posts.

The problem it solves: the signal a researcher wants is spread across many separate communities, it
is buried in volume, and Reddit's own interface offers no way to group communities, no way to compare
what they collectively discuss, and no way to ask a question of a community's accumulated discussion.

Scope for this specification is the single-user product described in `README.md` under Features. The
items listed in the README's **Future Scope** section are explicitly out of scope here.

## Clarifications

### Session 2026-08-14

- Q: When someone deletes their Reddit post or comment, what should JammySearch do with the copy it
  already collected? → A: Purge it from the general corpus, but keep copies the user explicitly
  bookmarked, on the reasoning that those are private saved records that are never republished.
- Q: If the database were lost tomorrow, how much of the collected history would be acceptable to
  lose? → A: At most one day. A full nightly backup is written outside the application container and
  retained on a rolling window.
- Q: When the AI provider fails partway through analysing a batch of posts, what should happen? → A:
  Process in chunks and commit each as it succeeds; on failure, stop, record the resume point, and
  show the audience as explicitly incomplete rather than as finished.
- Q: How should the system decide it lacks enough relevant material to answer a question? → A:
  Require at least a configured minimum number of retrieved passages above a configured similarity
  floor, with both values tuned against the labelled unanswerable questions in the evaluation set.
- Q: Where will the application be reachable from once running? → A: Local machine only in this
  release, but built so that later public exposure requires configuration rather than rework — no
  shortcut may depend on the local-only assumption. Clarified further: the application *code* is
  written as though it will be public; the *deployment* apparatus that costs money or operational
  effort (transport security, abuse protection, monitoring) is deliberately not built now, because
  none of it requires code changes to add later.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build an audience and read its feed (Priority: P1)

A researcher searching for the communities relevant to a market they care about finds several
communities, groups them into one named audience, and reads a single unified timeline of everything
those communities are posting — sorting it by newest or by what performed best today or this week,
and opening any post to read it in full without leaving the application.

**Why this priority**: This is the foundational loop. Without the ability to define an audience and
read its combined feed, no other capability in this product has anything to operate on. Delivered
alone, it already replaces the manual work of opening a dozen subreddit tabs in sequence.

**Independent Test**: Create an audience from three named communities, open its feed, sort it three
different ways, and read the full text of a post — all without visiting Reddit directly. Delivers
immediate value as a multi-community reader even if nothing else ships.

**Acceptance Scenarios**:

1. **Given** a researcher with no saved audiences, **When** they search for a community by name and
   add three of them to a new audience called "Designers", **Then** the audience is saved and appears
   in their list of audiences with its three member communities.
2. **Given** a saved audience, **When** the researcher opens it, **Then** they see a single combined
   timeline of posts drawn from every community in that audience, each post identified by which
   community it came from.
3. **Given** an open audience feed, **When** the researcher changes the sort to "Top this week",
   **Then** the same set of posts is reordered by that criterion without losing their place in the
   audience.
4. **Given** a post in the feed, **When** the researcher selects it, **Then** the post's full title
   and body text are readable inside the application.
5. **Given** a saved audience, **When** the researcher renames it, adds a community, or removes a
   community, **Then** the change persists and the feed reflects the new membership on next load.
6. **Given** two communities in one audience that both carry the same cross-posted content, **When**
   the feed is displayed, **Then** that content appears once rather than as duplicate entries.

---

### User Story 2 - Search an audience for specific language (Priority: P2)

A researcher who suspects a particular frustration or need exists in their audience searches for the
words people would use to express it, narrowing by time period, by which communities to include or
exclude, and by which authors to include or exclude, and reads the matching posts. By default this
searches the material already collected for their audiences; when they need to look past the
communities they track, they can widen the search to all of Reddit and accept the trade-offs that
come with it.

**Why this priority**: Search is how a hypothesis gets tested. Browsing a feed shows what is popular;
search shows whether a specific problem is being discussed and in what terms. It is the most direct
path from "I have a hunch" to evidence.

**Independent Test**: Run a keyword search restricted to one audience over the last month, then
re-run it with one community excluded and one keyword disabled, and confirm the result set changes
accordingly.

**Acceptance Scenarios**:

1. **Given** a saved audience, **When** the researcher searches it for one or more keywords, **Then**
   only posts from that audience containing those keywords are returned.
2. **Given** a search with multiple keywords, **When** the researcher disables one of them, **Then**
   results are recomputed as though that keyword had not been entered.
3. **Given** a search across an audience, **When** the researcher excludes a specific community or a
   specific author, **Then** no results from that community or author appear.
4. **Given** a search, **When** the researcher restricts it to a time period and a result limit,
   **Then** no results outside that period are returned and the count does not exceed the limit.
5. **Given** a search that matches nothing, **When** results are displayed, **Then** the researcher is
   told plainly that there were no matches and what they might change, rather than shown a blank area.
6. **Given** a search over saved material, **When** the researcher switches the scope to all of
   Reddit, **Then** the search reaches beyond their saved communities, and they are told that those
   results are retrieved live and carry no pattern or sentiment analysis.

---

### User Story 3 - Understand an audience through topics and themes (Priority: P3)

Rather than reading posts one by one, a researcher opens an audience's analysis view and sees what
that audience collectively talks about: the recurring topics, the themes those topics fall into, and
which communities and discussions sit behind each one — then drills into a single theme to see its
sub-categories, a short description of what it covers, the patterns detected across its posts, and
whether it is being discussed more or less than it used to be.

**Why this priority**: This is the interpretation layer that turns a feed into an insight, and it is
the main reason to use this product over reading Reddit directly. It depends on there being an
audience and posts to analyze, so it follows P1.

**Independent Test**: Open the analysis view for an audience with at least a few hundred posts,
confirm topics and both kinds of themes are listed, select one theme, and confirm its description,
sub-categories, contributing communities, and detected patterns are shown.

**Acceptance Scenarios**:

1. **Given** an audience with collected posts, **When** the researcher opens its analysis view,
   **Then** they see the list of communities in the audience, the topics discussed across it, and the
   themes those discussions fall into.
2. **Given** the themes list, **When** the researcher views it, **Then** themes derived from
   engagement scoring (such as most-discussed this week, or best-performing this month) are
   distinguishable from themes derived from interpreting post content.
3. **Given** a theme, **When** the researcher selects it, **Then** they see a short plain-language
   description of what the theme covers, its sub-categories, the topics and communities it draws
   from, and the posts behind it.
4. **Given** a selected theme, **When** the researcher requests patterns, **Then** recurring patterns
   across that theme's posts are presented, along with the overall sentiment of those posts.
5. **Given** an audience with too little collected material to analyze meaningfully, **When** the
   analysis view is opened, **Then** the researcher is told what is missing and what will make it
   available, rather than shown empty or fabricated results.
6. **Given** an analysis that has already been produced for an unchanged audience, **When** the
   researcher opens it again, **Then** the same results are shown and no new analysis cost is
   incurred.
7. **Given** an audience whose posts include widely discussed threads, **When** analysis runs, **Then**
   the discussion on those threads informs the topics, themes, and patterns produced, and the
   researcher can tell which results were supported by discussion rather than post text alone.
8. **Given** a topic or an interpreted theme, **When** the researcher views it, **Then** they see how its share of the
   audience's discussion has changed over the period for which material has been collected, and how
   many distinct posts and distinct authors sit behind it.
9. **Given** a topic or theme with too little collected history to establish a direction, **When** its
   trend is requested, **Then** the researcher is told the period is too short rather than shown a
   slope drawn from a handful of points.

---

### User Story 4 - Ask a question and get a cited answer (Priority: P4)

A researcher asks a plain-language question about an audience — "what do people here complain about
most when choosing a tool?" — and receives an answer assembled from that audience's actual posts,
with the specific posts it drew on cited so the researcher can verify every claim.

**Why this priority**: This is the product's most differentiated capability, but it is only
trustworthy once there is enough collected and analyzed material behind it, so it follows P3.

**Independent Test**: Ask a question that the audience's posts genuinely answer and confirm the
response cites specific posts that support it; then ask a question the audience has no material on
and confirm the system declines rather than answering.

**Acceptance Scenarios**:

1. **Given** an audience with collected posts, **When** the researcher asks a question in plain
   language, **Then** they receive an answer drawn from posts in that audience.
2. **Given** an answer, **When** it is displayed, **Then** every answer cites the specific posts it
   was derived from, and each citation can be opened to read the source post in full.
3. **Given** a question whose retrieval does not meet the relevance threshold (FR-076), **When**
   the researcher asks it, **Then** the system states that it does not have enough relevant material
   to answer, and does not answer from general knowledge.
4. **Given** a question that takes time to answer, **When** the researcher submits it, **Then** they
   receive visible progress or partial output rather than an unexplained wait.
5. **Given** the same question asked twice of an unchanged audience, **When** both answers are
   returned, **Then** they are consistent with each other.

---

### User Story 5 - Be told when someone says the thing you are watching for (Priority: P5)

A researcher who is looking for a particular kind of post — someone asking for a tool like theirs,
someone naming a competitor, someone describing a problem they solve — writes a rule for it once and
is told inside the application whenever newly collected material matches, instead of re-running the
same search every morning. Because the same intent gets expressed in wildly different words, a rule
can match on meaning rather than on literal keywords — someone writing "anyone know a tool that
watches subreddits for me?" should be caught by a rule about Reddit monitoring without the researcher
having to anticipate that exact phrasing.

**Why this priority**: This converts the product from something a researcher visits into something
that works while they are not looking, and it is what makes finding sales leads practical — a person
publicly asking for what you sell is worth reaching within hours, not whenever the researcher next
happens to search. It needs material to be collected (P1) and search semantics to exist (P2), but
none of the interpretation layers, so it can ship before them.

**Independent Test**: Create a rule with two keywords scoped to one audience, wait for a collection
cycle that includes a matching post, and confirm the match is surfaced in the application with the
post attached — and that a non-matching post is not.

**Acceptance Scenarios**:

1. **Given** a saved audience, **When** the researcher creates a keyword rule scoped to it, **Then**
   the rule is saved and appears in their list of rules.
2. **Given** an active rule, **When** newly collected material matches it, **Then** the match is
   recorded and surfaced in the application without the researcher re-running a search.
3. **Given** an existing rule, **When** the researcher edits its keywords, pauses it, or deletes it,
   **Then** the change applies from the next evaluation onward and matches already recorded are left
   intact.
4. **Given** a recorded match, **When** the researcher opens it, **Then** they can read the full post,
   see which rule matched it, and act on it — saving it and setting its status — without leaving the
   alert view.
5. **Given** a rule written so broadly that it matches a large share of collected material, **When**
   matches accumulate, **Then** the researcher is told the rule is matching very broadly and offered
   the chance to narrow it, rather than being flooded silently.
6. **Given** a rule whose audience includes a community that has become unavailable, **When**
   evaluation runs, **Then** the rule continues to work across the remaining communities and the
   researcher is told which one is no longer contributing.
7. **Given** a rule that describes an intent rather than listing keywords, **When** a post expresses
   that intent in wording the rule never mentions, **Then** the post is matched, and the match states
   that it was found by meaning rather than by a literal term.
8. **Given** meaning-based matching is unavailable — the retrieval capability is not yet built, is
   failing, or the material has not been processed for it — **When** evaluation runs, **Then**
   keyword matching continues to work and the researcher is told that meaning-based matching is not
   currently active, rather than silently receiving fewer matches.

**Note**: Alerts are in-app only in this release; see FR-063.

---

### User Story 6 - Discover communities worth tracking (Priority: P6)

A researcher who does not yet know which communities matter browses for them: searching by name,
description, or topic; sorting by size, by activity, or by growth; filtering to a size band; reading
at-a-glance tags that say how big, how new, and how active a community is; and viewing how a
community's membership and posting volume have changed over time. They can also browse starter
audiences rather than assembling one from scratch, and when they create a new audience they are
offered similar communities to add.

**Why this priority**: This accelerates the first step of the P1 loop but does not block it — a
researcher who already knows their communities can skip it entirely.

**Independent Test**: Search for communities on a topic, filter to a size band, sort by activity,
inspect the tags and history graph on one result, and add it to an audience directly from the
results.

**Acceptance Scenarios**:

1. **Given** the discovery view, **When** the researcher searches by name, description, or topic,
   **Then** matching communities are listed with their basic statistics.
2. **Given** a list of communities, **When** the researcher sorts by size, by activity, or by growth
   and filters to a membership band, **Then** only communities matching those criteria are shown, in
   the requested order.
3. **Given** a community in the results, **When** it is displayed, **Then** it carries tags
   indicating its size band, whether it is newly created, and its activity level.
4. **Given** a community, **When** the researcher views its history, **Then** membership and posting
   volume over time are plotted for the period for which history has been collected.
5. **Given** insufficient collected history for a community, **When** its history or growth ranking is
   requested, **Then** the researcher is told how much history exists rather than shown a misleading
   trend.
6. **Given** a community in the results, **When** the researcher adds it to an audience, **Then** they
   can add it to an existing audience or create a new one, and on creating a new one they are offered
   similar communities to include.
7. **Given** the starter audiences list, **When** the researcher browses it, **Then** they can
   inspect what communities each contains and save a copy as their own editable audience.

---

### User Story 7 - Keep a record of what was found (Priority: P7)

A researcher who finds a post that evidences something worth acting on — or a person worth
contacting — saves it, attaches their own note, and marks where it stands, then returns later to
review everything they have saved and what they have already acted on.

**Why this priority**: Research without retention is wasted. It is small, but without it every
insight has to be rediscovered.

**Independent Test**: Bookmark a post from a feed and from a search result, add a note to one, and
retrieve both from the saved list in a later session.

**Acceptance Scenarios**:

1. **Given** any post shown in a feed, a search result, or a theme, **When** the researcher bookmarks
   it, **Then** it is saved and remains retrievable in a later session.
2. **Given** a bookmarked post, **When** the researcher writes a private note on it, **Then** the note
   is stored with the bookmark and visible when it is next opened.
3. **Given** a bookmarked post that has since been deleted at the source, **When** the researcher
   opens their bookmark, **Then** the text captured at the time of saving is still readable, marked as
   no longer available at the source.
4. **Given** a bookmark representing a person worth contacting, **When** the researcher sets its
   status, **Then** the status persists and can be changed later as the situation moves on.
5. **Given** a list of bookmarks, **When** the researcher filters by status, **Then** only posts in
   that state are shown, so what has already been acted on stays separate from what has not.

---

### User Story 8 - See what the analysis costs and how fresh it is (Priority: P8)

A researcher can see, for any audience and across the whole product, how much the automated analysis
has cost, how quickly it responds, how much of it was served from previously computed results, and
how recently each audience's material was last refreshed.

**Why this priority**: It protects the researcher from unknowingly running up cost, and it tells them
whether what they are looking at is current — which determines whether they can trust a conclusion.
It is a supporting capability, not a reason to open the product.

**Independent Test**: Run an analysis and an Ask on an audience, then confirm the usage view reflects
the spend, the response time, the proportion served from previous results, and the last-refreshed
time for that audience.

**Acceptance Scenarios**:

1. **Given** analysis has run on an audience, **When** the researcher opens the usage view, **Then**
   they see the cost incurred, the volume processed, and the response times, for that audience and in
   aggregate.
2. **Given** repeated work on unchanged material, **When** the usage view is opened, **Then** the
   researcher can see what proportion of results were reused rather than recomputed.
3. **Given** any audience, **When** the researcher views it, **Then** they can tell when its material
   was last refreshed from the source.
4. **Given** a configured spending limit has been reached, **When** the researcher requests further
   analysis, **Then** the request is refused with a clear explanation rather than silently continuing
   to spend.

---

### Edge Cases

- **Community is private, banned, quarantined, or does not exist** when a researcher tries to add it
  to an audience — the researcher is told which of these applies rather than getting a generic error.
- **Community becomes unavailable after being added** to an audience — the audience keeps working,
  the affected community is marked unavailable, and previously collected posts remain readable.
- **Audience is empty** or contains a single community — the feed and analysis views behave sensibly
  rather than erroring, and analysis states when there is too little material to be meaningful.
- **Audience is very large** (many dozens of communities) — the feed remains usable and the researcher
  is told if the audience exceeds the supported size.
- **Source is unavailable or refusing requests** — previously collected material remains browsable and
  the researcher is told that the data is not current rather than shown an empty product.
- **Post is deleted or removed by moderators** after being collected — its text is purged from the
  general corpus on the next availability re-check, while its non-content metadata remains so counts
  and trends are unaffected. If the researcher had bookmarked it, their private copy survives and is
  marked as no longer available at the source.
- **Post is edited** after being collected — the researcher sees what was captured, marked with its
  current status at the source.
- **A purged post is still cited by an existing answer or theme** — the citation resolves to a
  tombstone stating the material is no longer available, rather than breaking or silently vanishing
  from the record of what the analysis was based on.
- **Author's account is deleted** — posts remain attributable to a deleted account without breaking
  author-based filtering.
- **Same content cross-posted** across several communities in one audience, or reposted verbatim by
  different authors — the researcher is not shown the same thing repeatedly.
- **Search matches an enormous number of posts** — results are limited and paged, and the researcher
  is told the result set was truncated.
- **Ask question is nonsensical, empty, or unrelated** to the audience — the system declines clearly
  rather than producing a confident irrelevant answer.
- **A question retrieves one strong match and nothing else** — it is refused, because a single
  passage does not meet the minimum count in FR-076. One incidental keyword match must not be enough
  to carry an otherwise unsupported answer.
- **Ask question would require material outside the audience** — the system says so instead of
  answering from general knowledge.
- **Content retrieved from the source attempts to manipulate the analysis** by containing
  instruction-like text — such text is treated as content to be analyzed, never as direction.
- **Growth and history views requested before enough history has accumulated** — the researcher is
  told how much history exists and when the view becomes meaningful.
- **Adult or graphic content** appears in a tracked community — the researcher can tell before opening
  a post that it is flagged as such.
- **Posts are not in English** — they are still collected and displayed, and analysis states where its
  interpretation is less reliable.
- **A search widened to all of Reddit is slow, rate-limited, or refused by the source** — the
  researcher is told what happened and offered their saved-material results instead of being left with
  nothing.
- **No post in an audience meets the engagement threshold** for comment collection — analysis proceeds
  on post text alone and says so, rather than appearing to have considered discussion it never saw.
- **A heavily discussed post carries thousands of top-level comments** — collection is bounded and the
  researcher can tell that only part of the discussion was considered.
- **One post satisfies several alert rules at once** — the researcher is not shown the same post over
  and over; they can see which rules it matched.
- **An alert rule never matches anything** — the researcher can tell the rule is active but idle,
  rather than being unable to distinguish "nothing matched" from "not running".
- **An intent rule matches something the researcher considers irrelevant** — the match shows that it
  was found by meaning and how close it was, so the researcher can raise the rule's threshold rather
  than concluding the feature is broken.
- **An intent rule is created before the retrieval capability exists** — the rule is accepted and its
  keyword portion works immediately; the researcher is told intent matching will begin once retrieval
  is available, rather than the rule appearing to work while matching nothing.
- **Collection was interrupted for part of a trend period** — the gap is visible in any trend shown,
  so a drop in collected volume is not mistaken for a drop in discussion.
- **The database is lost or corrupted** — recovery restores the most recent nightly backup. Up to a
  day of collection is lost; the community snapshot series shows a one-day gap that cannot be
  backfilled, and any posts that have since fallen outside what the source will serve are gone.
- **The AI provider is unavailable, slow, or rate-limiting** during a batch analysis — completed
  chunks are kept, the audience is marked as partially analysed with the proportion done, and the run
  resumes from its recorded position rather than starting over.
- **The AI provider fails midway through answering a question** — the researcher is told the answer
  could not be completed, and the partial text is neither shown as an answer nor saved as one.
- **The application is started bound to a non-local interface without the explicit exposure setting**
  — it refuses to start and explains why, rather than silently becoming reachable from the network.

## Requirements *(mandatory)*

### Functional Requirements

Requirement identifiers are stable and unique. They are not contiguous in document order —
requirements added after the first draft keep the next free number rather than renumbering
everything that follows them.

#### Audiences

- **FR-001**: Users MUST be able to create a named audience consisting of one or more Reddit
  communities.
- **FR-002**: Users MUST be able to rename an audience, add communities to it, and remove communities
  from it, with changes persisting across sessions.
- **FR-003**: Users MUST be able to delete an audience, and MUST be warned that saved analysis for it
  will no longer be reachable.
- **FR-004**: The system MUST prevent an audience from containing the same community twice.
- **FR-005**: The system MUST enforce a documented maximum number of communities per audience and tell
  the user when they reach it.
- **FR-006**: The system MUST ship with a fixed set of **starter audiences**, authored and maintained
  as part of the product, which a user can inspect and save as their own editable copy. Saving a copy
  MUST NOT alter the original, and later changes to a shipped audience MUST NOT alter copies a user
  has already saved.
- **FR-007**: When a user creates a new audience, the system MUST suggest additional communities
  related to those already chosen.

#### Feed

- **FR-008**: The system MUST present the posts of all communities in an audience as one combined
  timeline, with each post attributed to its source community.
- **FR-009**: Users MUST be able to sort a feed by newest, by top today, and by top this week.
- **FR-010**: Users MUST be able to read a post's full title and body text within the application,
  without being redirected to the source.
- **FR-011**: The system MUST detect and collapse cross-posted and duplicate content so the same
  material is presented once per feed.
- **FR-012**: The system MUST page the feed rather than loading an unbounded number of posts.
- **FR-013**: The system MUST show, for any audience, when its material was last refreshed from the
  source.

#### Search

- **FR-014**: Users MUST be able to search for one or more keywords within a selected audience.
- **FR-015**: Users MUST be able to disable an individual keyword within a search without deleting it,
  and have results recomputed accordingly.
- **FR-016**: Users MUST be able to restrict a search by time period, by result limit, and by sort
  order (newest, top, or most active).
- **FR-017**: Users MUST be able to include or exclude specific communities within the searched
  audience.
- **FR-018**: Users MUST be able to include or exclude specific authors.
- **FR-019**: The system MUST offer two selectable search scopes:
  - **Saved material** — a single audience, or every community across all of the user's saved
    audiences. This scope MUST be the default on every new search.
  - **All of Reddit** — a search of the source itself at query time, reaching beyond the communities
    the user has saved.
  The system MUST make clear which scope is active, and MUST state, when the all-of-Reddit scope is
  selected, that results are retrieved live, may be slower, and are subject to the source's own
  limits.
- **FR-020**: Search results MUST always present the matching posts. When the interpretation
  capability is available, results over saved material MUST additionally present the patterns and
  overall sentiment detected across them. When it is not — because it has not been built yet, is
  failing, or the material has not been interpreted — results MUST state that analysis is unavailable
  rather than silently omitting it. Results from the all-of-Reddit scope never carry analysis and
  MUST say so.

#### Analysis

- **FR-021**: The system MUST present, for an audience, the communities it contains, the topics
  discussed across it, and the themes those discussions fall into.
- **FR-022**: The system MUST distinguish themes derived from engagement scoring from themes derived
  from interpreting post content.
- **FR-023**: Selecting a theme MUST reveal a plain-language description of it, its sub-categories,
  the topics and communities contributing to it, and the posts behind it.
- **FR-024**: The system MUST be able to present recurring patterns detected across the posts of a
  theme, and the sentiment of those posts.
- **FR-053**: The system MUST present, for any topic or interpreted theme, how its share of the
  audience's discussion has changed over the period for which material has been collected. A scored
  theme's membership is itself defined by a time window, so a share-of-discussion trend is not
  meaningful for it, and the system MUST say so rather than draw one.
- **FR-054**: The system MUST present the number of distinct posts and the number of distinct authors
  behind a topic or theme, so a user can distinguish a concern held widely from one person raising the
  same point repeatedly.
- **FR-055**: The system MUST state the period any trend covers, and MUST NOT present a direction of
  travel when the collected period is too short to support one.
- **FR-072**: Analysis MUST process material in chunks, committing each chunk's results before
  beginning the next, so that an interruption costs at most the chunk in progress.
- **FR-073**: When analysis is interrupted, the system MUST record how far it got and resume from
  that point on the next attempt. Material already analysed MUST NOT be re-analysed or re-charged.
- **FR-074**: An audience whose analysis is incomplete MUST be presented as incomplete, stating how
  much of its material has been analysed, rather than showing partial results as though they were
  complete.
- **FR-075**: A question that fails partway through being answered MUST surface the failure. A
  truncated answer MUST NOT be presented as a finished one, and MUST NOT be stored as though it were.
- **FR-025**: The system MUST state when an audience holds too little material for analysis to be
  meaningful, rather than presenting weak results as confident ones.
- **FR-026**: Repeating an analysis over unchanged material MUST return the same result and MUST NOT
  incur additional cost.
- **FR-027**: The system MUST analyse post content, and MUST additionally collect and analyse the
  top-level comments of those posts that meet a configured engagement threshold. Replies below the top
  level are not collected in this release.
- **FR-027a**: The engagement threshold governing which posts have their comments collected MUST be
  configurable, and its current value MUST be discoverable by the user, so they can tell how deep the
  discussion behind any result goes.
- **FR-027b**: Analysis results MUST indicate whether comment material contributed to them, so a user
  can distinguish a conclusion drawn from post text alone from one supported by discussion.

#### Ask

- **FR-028**: Users MUST be able to ask a plain-language question scoped to a single audience.
- **FR-029**: Every answer MUST cite the specific posts it was derived from, and each citation MUST be
  openable to read the source post.
- **FR-030**: The system MUST decline to answer when retrieval does not meet the relevance threshold
  defined in FR-076, and MUST NOT answer from knowledge outside the audience's collected posts.
- **FR-076**: The decision to answer or refuse MUST be made by requiring at least a configured
  minimum number of retrieved passages scoring above a configured similarity floor. Both the minimum
  count and the floor MUST be configurable, and their current values MUST be discoverable.
- **FR-077**: The minimum count and similarity floor MUST be tuned against the labelled unanswerable
  questions in the evaluation set. Changing either value counts as a retrieval change and MUST be
  accompanied by an evaluation run with before-and-after scores.
- **FR-031**: The system MUST show progress or partial output while an answer is being produced.
- **FR-032**: The same question asked twice against unchanged material MUST produce consistent
  answers.
- **FR-033**: Text retrieved from Reddit MUST be treated strictly as material to be analysed and never
  as instructions that change system behaviour.

#### Alerts

- **FR-056**: Users MUST be able to create keyword rules scoped to an audience, and to list, edit,
  pause, resume, and delete them.
- **FR-057**: The system MUST evaluate active rules against newly collected material and record
  matches, without the user re-running a search.
- **FR-058**: Recorded matches MUST be surfaced within the application, each identifying the rule that
  matched and the post that matched it.
- **FR-059**: Editing, pausing, or deleting a rule MUST NOT alter or remove matches already recorded.
- **FR-060**: The system MUST tell the user when a rule is matching an unusually high share of
  collected material, and offer them the chance to narrow it.
- **FR-061**: A rule whose audience contains an unavailable community MUST continue evaluating the
  remaining communities, and the user MUST be told which one is no longer contributing.
- **FR-062**: A post reached from a match MUST be readable in full and actionable in place — saveable,
  and settable to a status — without leaving the alert view.
- **FR-063**: Alerts MUST be surfaced inside the application only. Outbound delivery channels are out
  of scope for this release.
- **FR-082**: Users MUST be able to define a rule by describing the intent they are watching for, and
  the system MUST match material expressing that intent even when it shares no keyword with the
  rule's wording.
- **FR-083**: Each rule MUST declare its matching mode — literal keywords, intent, or both — and each
  recorded match MUST state which mode produced it, so the researcher can tell why a post was
  surfaced and can judge whether to trust it.
- **FR-084**: Intent matching MUST use a configurable similarity threshold whose current value is
  discoverable, tuned against a labelled set of intent paraphrases. Changing it counts as a retrieval
  change and MUST be accompanied by an evaluation run.
- **FR-085**: Intent matching MUST degrade gracefully. When the retrieval capability is unavailable or
  material has not yet been prepared for it, keyword matching MUST continue unaffected and the
  researcher MUST be told that intent matching is not currently active. A rule MUST NOT silently
  return fewer matches than it otherwise would.

#### Community discovery

- **FR-034**: Users MUST be able to search for communities by name, description, or topic and see
  their basic statistics.
- **FR-035**: Users MUST be able to rank communities by size, by activity, and by growth, and to
  filter by membership band and by time window.
- **FR-036**: The system MUST label each community with its size band, whether it is newly created,
  and its activity level.
- **FR-037**: The system MUST plot a community's membership and posting volume over time for the
  period for which history has been collected.
- **FR-038**: The system MUST record community statistics on a recurring schedule so that history
  accumulates from the earliest possible date.
- **FR-039**: The system MUST state how much history exists when a growth or history view is requested
  with insufficient data, rather than presenting a misleading trend.
- **FR-040**: Users MUST be able to add a community to an existing audience, or create a new audience
  from it, directly from discovery results.

#### Saving and records

- **FR-041**: Users MUST be able to bookmark any post shown anywhere in the product and retrieve their
  bookmarks in a later session.
- **FR-042**: Users MUST be able to attach a private note to a bookmarked post.
- **FR-043**: Bookmarked posts MUST remain readable from captured content if the original is later
  removed at the source, and MUST be marked as no longer available.
- **FR-064**: Users MUST be able to set a status on a bookmark — at minimum new, contacted, and
  dismissed — and change it at any time.
- **FR-065**: Users MUST be able to filter their bookmarks by status, so what has been acted on stays
  separable from what has not.
- **FR-066**: Status and notes MUST be private to the user and MUST NOT be transmitted to the source or
  be visible to anyone else.

#### Deletion at the source

- **FR-067**: The system MUST re-check the availability of previously collected material on a
  recurring schedule, so that deletions and moderator removals are detected in the background rather
  than only when a user happens to open the item.
- **FR-068**: On detecting that a post or comment has been deleted or removed at the source, the
  system MUST purge its captured text — including any derived representations used for retrieval —
  from the general corpus, while retaining the non-content metadata (identifier, timestamps,
  engagement figures, source community) that counts and trends depend on.
- **FR-069**: Material the user has explicitly bookmarked is exempt from FR-068 and remains readable
  from its captured text per FR-043, marked as no longer available at the source. Exempt copies MUST
  remain private to the user, MUST NOT be republished, shared, or exported to any third party, and
  MUST be destroyed if the bookmark is deleted.

#### Transparency and limits

- **FR-044**: The system MUST report the cost, volume processed, and response times of automated
  analysis, both per audience and in aggregate.
- **FR-045**: The system MUST report what proportion of results were reused from previous work rather
  than recomputed.
- **FR-046**: The system MUST enforce a configurable spending limit and refuse further analysis with a
  clear explanation when it is reached, rather than continuing to spend.
- **FR-047**: The system MUST publish the measured accuracy of its automated interpretation against a
  known-correct reference set, so a user can judge how much to trust it.

#### Access and resilience

- **FR-048**: The system MUST require a user to sign in, and MUST keep each user's audiences,
  bookmarks, and notes private to them.
- **FR-049**: The system MUST remain usable from previously collected material when the source is
  unavailable, and MUST tell the user that what they are seeing is not current.
- **FR-050**: The system MUST tell the user which specific condition applies when a community cannot
  be added — nonexistent, private, banned, or quarantined.
- **FR-051**: The system MUST flag posts marked as adult or graphic at the source before the user
  opens them.
- **FR-052**: Errors shown to users MUST state what failed and what the user can do next.
- **FR-070**: The system MUST produce a complete backup of its stored data on a daily schedule,
  written to storage outside the application container, and MUST retain a rolling window of those
  backups rather than only the most recent one.
- **FR-071**: The restore procedure MUST be documented and MUST have been performed successfully at
  least once against a real backup. A backup that has never been restored is not evidence of
  recoverability.
- **FR-078**: The application MUST bind to the local machine by default and MUST NOT be reachable
  from a public network in this release. Exposing it beyond the local machine MUST require an
  explicit configuration change rather than being possible by accident.
- **FR-079**: Credential storage, session handling, and secret management MUST be built to a standard
  that would remain sound under public exposure. No measure may rely on the local-only assumption —
  stored credentials are hashed, sessions expire and can be invalidated, and secrets never appear in
  responses, logs, or anything the client can read.
- **FR-080**: Spend ceilings (FR-046) and request rate limits MUST be enforced on the server as
  controls in their own right, never as interface conveniences, so that they remain effective if the
  deployment is later exposed.
- **FR-081**: The following are explicitly NOT required in this release, because each sits at the
  deployment layer and can be introduced without changing application code: transport security and
  certificates, network-level abuse or brute-force protection, external uptime and security
  monitoring, and hardened hosting. Building them now is out of scope, and their absence MUST NOT be
  compensated for by weakening FR-079 or FR-080.

### Key Entities

- **Community**: A single Reddit subreddit being tracked. Carries a name, description, membership
  count, activity level, creation date, and derived tags for size, newness, and activity.
- **Community Snapshot**: A recording of one community's statistics at a point in time. Accumulating
  these is what makes growth and history views possible.
- **Audience**: A user-named group of communities, treated as a single unit for reading, searching,
  and analysis. Either user-created or a saved copy of a starter audience.
- **Post**: A single piece of content collected from a community, with its title, body, author,
  timestamp, engagement figures, source community, and current availability at the source. When it
  becomes unavailable at the source, the text is purged and the remaining non-content fields persist
  as a record that it existed, so historical counts stay stable.
- **Comment**: A top-level reply to a post that met the engagement threshold, with its text, author,
  timestamp, and engagement figures. Contributes to analysis alongside posts.
- **Topic**: A subject discussed across an audience, derived from its posts and their collected
  discussion.
- **Theme**: A grouping of discussion within an audience, either derived from engagement scoring or
  from interpreting content. Has a description, sub-categories, and contributing topics, communities,
  and posts.
- **Pattern**: A recurring observation detected across the posts of a theme or a search result.
- **Question and Answer**: A user's plain-language question about an audience, the answer produced,
  and the posts cited as its support.
- **Alert Rule**: A user's standing rule scoped to an audience, which can be active or paused, and
  which is evaluated against newly collected material rather than run on demand. It carries a
  matching mode — literal keywords, an intent description, or both — and, for intent matching, a
  similarity threshold.
- **Alert Match**: A record that a particular post satisfied a particular rule, and when — retained
  independently of the rule that produced it. Records which matching mode fired and, for intent
  matches, how close the match was.
- **Bookmark**: A post the user has chosen to keep, with captured content, an optional private note, and a status
  recording where the researcher has got to with it.
- **Usage Record**: A record of the cost, volume, response time, and reuse of one unit of automated
  analysis, used to produce the transparency views.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from signing in to reading a populated audience feed in under 5
  minutes without consulting documentation.
- **SC-002**: A researcher unfamiliar with a market can identify at least three distinct recurring
  pain points in a newly created audience within 15 minutes of first opening it.
- **SC-003**: 95% of audience feed loads present results within 2 seconds.
- **SC-004**: 95% of searches over saved material present results within 3 seconds. Searches widened
  to all of Reddit are exempt from this target, and the interface tells the user so before they run
  one.
- **SC-005**: Answers to questions begin appearing within 5 seconds of asking.
- **SC-006**: At least 90% of cited posts in an answer are judged relevant to the question by a human
  reviewer.
- **SC-007**: The system declines to answer on 100% of a held-out set of questions that the audience's
  material genuinely cannot support, with no fabricated answers.
- **SC-008**: Automated theme and sentiment labelling agrees with human labelling on at least 75% of a
  held-out reference sample, and this figure is published.
- **SC-009**: Repeating any analysis or question over unchanged material returns the same result and
  incurs no additional cost, verified across 100% of repeat requests.
- **SC-010**: A user can determine the total cost of analysing an audience, and when that audience was
  last refreshed, within two interactions from the audience view.
- **SC-011**: Duplicate and cross-posted content accounts for less than 2% of items presented in any
  feed or result set.
- **SC-012**: When the source is unavailable, at least the most recent 7 days of previously collected
  material remains browsable and searchable.
- **SC-013**: An audience of up to the supported maximum number of communities remains within the feed
  and search timings above.
- **SC-014**: A post matching an active alert rule is surfaced to the researcher within 15 minutes of
  that post being collected.
- **SC-015**: For any topic or interpreted theme, its direction of travel over the collected period and the number of
  distinct authors behind it are reachable within two interactions from the analysis view.
- **SC-016**: A researcher can tell, for any bookmark, whether they have already acted on it,
  without opening it.
- **SC-017**: Text of material deleted at the source is purged from the general corpus within 24
  hours of the deletion being detected, and no purged text appears in any feed, search result, or
  analysis output thereafter.
- **SC-018**: A total loss of the running database can be recovered from backup with no more than 24
  hours of collected material lost, demonstrated by an actual restore rather than by the existence of
  a backup file.
- **SC-019**: After an interrupted analysis run is resumed, the material analysed before the
  interruption is not analysed again and incurs no further cost, verified across 100% of resumed
  runs.
- **SC-020**: Making the application reachable beyond the local machine requires only a configuration
  change and no code change, demonstrated by binding it to a non-local interface in a test
  environment.
- **SC-021**: An intent-based rule matches at least 70% of held-out paraphrases of that intent, while
  matching no more than 10% of unrelated control posts, measured against a labelled paraphrase set.

## Assumptions

- **Single user.** Per the README's Future Scope, there is no team, no sharing, no roles, and no
  subscription tiers. Sign-in exists to protect one person's data, not to separate tenants.
- **Local deployment, code written for eventual exposure.** The application runs on the local machine
  only in this release. The dividing line is cost: measures that live in application code and are
  cheaper to do correctly the first time — hashed credentials, expiring sessions, secrets kept out of
  responses and logs, server-side limits — are required now and cost effectively nothing. Measures
  that live in the deployment and carry real monetary or operational cost — transport security, abuse
  protection, monitoring — are deferred, because adding them later requires no code rework.
- **Public communities only.** Private and restricted communities cannot be tracked; the product only
  reads content that is publicly visible.
- **Maximum audience size of 50 communities** is assumed for FR-005 in the absence of a stated limit.
  This bounds feed and analysis cost while comfortably exceeding realistic research use.
- **Starter audiences are authored by the product's maintainer** and shipped as fixed content.
  Keeping them useful is an ongoing editorial task, not an automated one, and a shipped audience can
  go stale as communities rise and fall.
- **The engagement threshold for comment collection starts conservative** and is tuned by observation
  once real collection volume is known. Beginning permissive risks exhausting the source's limits
  before the value of the extra discussion has been demonstrated.
- **Widening a search to all of Reddit is a deliberate, occasional act**, not the normal path. The
  default scope stays on saved material precisely because that is where results are fast, analysable,
  and free of per-query source cost.
- **Alerts are evaluated per collection cycle, not continuously.** Alert latency is therefore bounded
  by how often material is refreshed, and SC-014's 15-minute target is a target for the refresh
  cadence as much as for the matching itself.
- **Lead status is personal workflow state, not customer relationship management.** It records where
  the researcher has got to with a post. Contact history, pipelines, and outreach itself stay outside
  the product.
- **Backups protect against loss of the running system, not against gaps in the source.** The source
  will not serve a community's history beyond its own listing limits, so material that was never
  collected — or that was lost and has since aged out — cannot be recovered by any means. This is why
  the corpus is treated as irreplaceable rather than as a cache that can be rebuilt on demand.
- **Topic and theme trends inherit the same cold start as community growth.** A direction of travel
  cannot be shown until material has been collected across enough of a period to establish one, and
  the product says so rather than drawing a slope through too few points.
- **Retention of collected material follows ordinary practice** for this kind of tool: collected posts
  are kept for as long as the audience exists, and community snapshots are kept indefinitely because
  their whole value is historical depth.
- **English is the primary language** of the audiences being researched. Other languages are collected
  and displayed but interpretation quality is not guaranteed.
- **The user accepts a cold start on history.** Growth and trend views are unavailable until the
  product has been recording community statistics for long enough, as the source exposes no history.
- **Analysis is not real-time.** Material is refreshed on a schedule; the product shows when it was
  last refreshed rather than promising live data. Live push updates are out of scope per the README.
- **Reddit's terms of use and rate limits govern collection.** Content is collected within the
  allowances of the source's public interface, and the product's usefulness is bounded by them.
- **Automated interpretation is assistive, not authoritative.** The product's own published accuracy
  figures (FR-047) define how far its conclusions should be trusted, and citations exist so every
  claim can be checked against source material.

## Dependencies

- Access to Reddit's public content, under its terms of use and its rate limits, for all collected
  material.
- An automated language-interpretation capability for topic extraction, theme tagging, sentiment,
  pattern detection, and question answering.
- A reference set of human-labelled posts, without which SC-008 and FR-047 cannot be satisfied.

## Out of Scope

Carried directly from the README's Future Scope section:

- Billing, subscription tiers, and plan-based feature gating
- Team workspaces, shared audiences, and role-based permissions
- Outbound integrations: Slack, Discord, and scheduled email digests
- Publicly shareable generated reports
- Content performance insights and product reviews (undefined; require their own specification)
- Live push updates to an open feed

Deferred by decision during specification:

- **Full comment trees.** Only top-level comments on posts meeting the engagement threshold are
  collected in this release. Collecting nested replies is a candidate for a later release, once the
  collection cost of top-level comments is understood in practice.
