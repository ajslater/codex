# Browser cache-busting / mtime / `?ts=` system — audit & simplification plan

## Goal

Audit the mtime + `?ts=` cache-busting machinery (frontend + backend), remove
dead/over-built code, and simplify it while keeping the most common case
working: **viewing the browser in publisher/series mode, a comic is added or
removed, and because of `order_by`/filters one group's cover must change on
screen.**

## TL;DR verdict

The system works but has accreted into **three overlapping timestamp
computations** feeding a **delivery layer that discards almost all of that
precision**. The most expensive piece (per-card aggregation) and the most
"fine-grained" piece (the `scope` payload) do work the actual refresh path
never uses. There is a real architectural inconsistency at the center:
**the browser deliberately distrusts the `collection.updated_at` column that
`TimestampUpdater` exists to maintain — while OPDS and the reader trust it.**
One of those two positions is redundant.

## How it works today

Three independently-computed timestamps:

| # | Timestamp | Computed in | Consumed by | Cost |
|---|-----------|-------------|-------------|------|
| 1 | Per-card `mtime` = max over **every child comic's** `updated_at` (+ bookmarks) | `card.py:114` `JsonGroupArray` → Python max in `serializers/browser/mixins.py:42` | the per-cover `?ts=`, route/download cache-bust | **High** — DISTINCT JSON array of all child timestamps per card, parsed in Python |
| 2 | Page-level `mtime` = `Greatest(Max(comic.updated_at), Max(bookmark.updated_at), Max(custom_cover.updated_at))` | `views/browser/collection_mtime.py:132`, 5s-TTL cache | refresh **gate** + browser-query cachalot buster | Moderate (separate query, cached) |
| 3 | Collection row `updated_at`, bumped to `Now()` after import | `librarian/scribe/timestamp_update.py` | **OPDS feeds + reader arc list only — never the browser** | `bulk_update` per collection model per import |

Representative cover is chosen separately again by a correlated subquery that
re-applies the current sort (`views/browser/annotate/cover.py:84`) — that is the
"dynamic sort" cover, recomputed every query.

Delivery: a change broadcasts `LIBRARY_CHANGED` to the **`ALL`** group (every
client) carrying `{mtime, scope}`. The frontend dispatcher
(`frontend/src/stores/socket.js:196`) reads **only `mtime`**, never `scope`, and
calls `loadMtimes(mtime)` (`frontend/src/stores/browser.js:945`), which reloads
the **entire current page**.

## Findings

### Dead / useless code
- **`payload.scope` is built everywhere, read nowhere.** Every factory in
  `librarian/notifier/tasks.py` assembles `libraryIds`/`collection`/`ids`/… and
  the frontend never references `.scope`. The "fine-grained" machinery is fully
  plumbed server-side and completely unused client-side.
- **`SESSION_ENDED`** (`choices/notifications.py:37`) — no emitter, no handler,
  no `Notifications` counterpart, not in `NOTIFICATION_TYPE_MAP`. Pure dead.
- **The hint "no-op if matches" branch** (`browser.js:951-954`) is effectively
  unreachable: the hint is `library.updated_at` (a *scan* time) and `page.mtime`
  is `Greatest(Max(comic.updated_at)…)` (a *content* aggregate). Different
  sources → never equal → `library.changed` always full-reloads. (The no-hint
  probe path gates correctly because it compares same-source values.)
- **`TimestampUpdater` output is dead weight w.r.t. the browser.** It runs a
  `bulk_update` across six collection models every import to maintain
  `collection.updated_at`, and the browser never reads that column
  (`card.py:110-113` traverses to `comic.updated_at` instead). Only OPDS
  (`opds/v1/entry/entry.py:96`, `opds/v1/entry/links.py:66`,
  `opds/v2/feed/publications.py:114`) and reader arcs (`reader/arcs.py:84`)
  read it.

### Timestamp correctness (browser + dynamic-sort covers)
- The browser does **not** rely on `collection.updated_at`; it re-derives
  freshness from child comics every query. In the common case the cover swaps
  because the **`cover_pk` subquery picks a different representative comic** —
  `?ts=` is *not* what swaps it; the changed `cover_pk` (different URL path) is.
  `?ts=` only matters for "same representative comic re-imported with new art."
- This all hinges on a **full page reload** being triggered (it always is).
- `TimestampUpdater` has real gaps (only bite OPDS/reader since the browser
  ignores it): last-comic-deleted collection isn't bumped
  (`timestamp_update.py:51` `child_count > 0` guard); Volume custom-cover changes
  skipped (`timestamp_update.py:42`); no trigger/signal backstop if a future
  bulk path forgets `updated_at`.

### Granularity
Simultaneously **too fine and too coarse**: cache-busting at the finest grain
(per-card max over all descendants, per-image `?ts=`) while the refresh signal
is the coarsest (`ALL` clients, reload whole page). The `scope` payload that
would bridge them is computed then discarded. (Note: for a single-library
install almost every change *is* relevant, so coarse reload is near-optimal
there; coarse-reload waste mainly hurts multi-library / scoped-subtree views.)

## Plan (ordered by alignment × value × safety)

### Stage 1 — Delete dead code (safe, do first)  ✅ DONE
- [x] Remove `SESSION_ENDED` from `WebsocketMessages`; regenerate choices JSON.
- [x] Verified: regeneration changes only the (gitignored) `websocket-messages.json`;
      ruff/format clean; import smoke confirms all 9 `Notifications` still resolve.

### Stage 2 — Collapse the three timestamps (biggest simplification)  ⟵ PROTOTYPE DONE, DECIDE
The main event. Make every browser reload cheaper.

#### Prototype findings (non-destructive, read-only)

**Feasibility of dropping the per-card `JsonGroupArray`→Python-max: GO.**
The card GROUP BY already computes inline child-relation aggregates that coexist
without row-multiplication:
- `child_count = Count(rel + "pk", distinct=True)` — `distinct=True` neutralizes
  the comic×bookmark×folders join multiplication (`order.py:298`).
- Collections already get inline `Max/Min("comic__<field>")` **order** aggregates
  in the *same* query (`order.py:337-339`, `:559`). `Max` is idempotent under
  row duplication, so it needs no `distinct`.
- Precedent: `reader/arcs.py:97-106` already replaced this exact
  `JsonGroupArray`+Python-`strptime` pattern with a plain `Max("updated_at")`.
- The page-level `Greatest(Max(comic__updated_at), Max(bookmark…), Max(custom_cover…))`
  already works (`collection_mtime.py:146`) — proving the folded expression is valid.

So the "ORM won't aggregate aggregates" comment (`mixins.py:44`) reflects the
*serializer-side* reduction, **not** a hard ORM limit. Two viable replacements:

- **Option C — inline SQL `Max` from live comics (recommended first):** replace
  the per-card `JsonGroupArray(comic__updated_at)` + Python max with the same
  `Greatest(Max(comic__updated_at), <per-user bookmark max>, Max(custom_cover…))`
  expression the page-level mtime uses — inline per card. Eliminates the JSON
  array materialization **and** the Python ISO-parse loop; unifies #1 and #2 on
  one helper. **Keeps the current self-correcting "read live comics" semantics —
  no new dependency on `TimestampUpdater`.** Lowest risk, in-repo precedent.
- **Option B — read `collection.updated_at` (bigger simplification, later):**
  drop the comic join entirely and read the column (which already folds
  `custom_cover`). Unifies browser with OPDS/reader. **But** trades self-correcting
  freshness for dependence on `TimestampUpdater`, whose gaps must be hardened
  first (last-comic-deleted `child_count>0` guard `timestamp_update.py:51`; Volume
  custom-cover skip `:42`; no trigger/signal backstop).

**Recommendation: GO on Option C** (cheap, safe, no new dependency), and treat
Option B as a separate later step gated on `TimestampUpdater` hardening.

#### Decision: **Option B** (read `collection.updated_at` directly).

Follow-up checks turned up that Option B needs **no `TimestampUpdater` hardening**:
- **No orphan comic-write paths** — every runtime `comic.updated_at` write goes
  through the importer → `TimestampUpdater` (the only non-importer hits are
  migrations + FTS5 DDL). This is also why OPDS/reader can already trust it.
- **0-comic collections are filtered out** of the browser by `force_inner_joins`
  ([filter.py:68](codex/views/browser/filters/filter.py:68)), so the
  last-comic-deleted `TimestampUpdater` gap is browser-moot.
- **Custom covers stay folded directly** in the page mtime (`Max(custom_cover…)`),
  and per-card covers bust via the `cover_custom_pk` URL path — so the Volume
  custom-cover gap doesn't matter to the browser.
- **Query shape preserved:** the page-mtime `.annotate(Greatest(Max(...))).first()`
  produces an identical GROUP BY whether the term is `Max("comic__updated_at")`
  or `Max("updated_at")` (verified via `str(qs.query)`), so the swap is structural,
  not semantic.

#### Implementation (Option B)  ✅ DONE
- [x] Page mtime (`collection_mtime.py`): `Max("comic__updated_at")` →
      `Max("updated_at")` (own column); kept bookmark + custom_cover terms.
- [x] Per-card mtime (`card.py`): `JsonGroupArray(comic__updated_at)` + Python-max
      loop → `Max("updated_at")` annotated as `updated_at_max`.
- [x] Serializer (`mixins.py:get_mtime`): folds the scalar `updated_at_max` with
      the per-user bookmark max; dropped the `itertools.chain` JSON-array reduce.
- [x] Refreshed the now-inverted comments (`card.py`, `collection_mtime.py`); fixed
      the stale `scope` comment in `timestamp_update.py` left from Stage 3.
- [x] Added `test_card_mtime_tracks_collection_updated_at` — bumping
      `Series.updated_at` moves the card mtime (would fail under the old path).
- [x] Verified: 154 tests green across browser/metadata/table/opds/reader/admin;
      ruff/format/ty clean. No `TimestampUpdater` change needed (see findings).

### Stage 3 — Remove the unused fine-grained `scope` plumbing  ✅ DONE
Decision: **delete it (de-complicate).** The `scope` was already vestigial —
all three `covers.changed` sites passed empty scope, and the frontend never read
`payload.scope`.
- [x] Removed `scope` field from `NotifierTask`; factories now only stamp `mtime`.
- [x] Deleted dead `bookmark_changed_task` (zero callers).
- [x] Dropped `scope` from the wire (`notifierd._send_task`, `consumers.send_text`,
      `payloads.typed_payload`) — payload is now `{type, mtime}`.
- [x] Cleaned all call sites (`admin/user.py`, `group.py`, `flag.py`,
      `custom_cover.py`), including the `group.py` `instance`/"Deleted"-shim ripple.
- [x] Verified: ruff/format/ty clean; runtime smoke confirms `{type, mtime}` and no
      `scope` key; `test_group` + `test_admin_custom_cover` + `test_admin_writes`
      pass (19 tests).

### Stage 4 — Honest refresh gate  ✅ DONE
Two parts:
- [x] **4a (frontend gate):** `browser.js`/`reader.js` `loadMtimes` now always
      probe the scoped `/api/v4/mtime` and reload only when the *viewed*
      collection's max mtime moved, instead of trusting the non-comparable
      `library.updated_at` hint (which never matched, so every broadcast forced a
      full reload). `socket.js` `libraryNotified` drops the hint. 99 vitest green.
- [x] **4b (drop dead wire mtime):** with the hint gone the frontend never reads
      `payload.mtime`, so the whole `{type, mtime}` enrichment is dead. Removed the
      `NotifierTask.mtime` field, `_ENRICHED_TYPES`, and the channel forwarding —
      the wire payload is now just **`{type}`**. The five mtime-only factories
      collapsed to their shared constants (callers enqueue the constant directly);
      `users_changed_task` stays for per-user targeting. Importer + admin suites green.

### Stage 5 — Precise cover busting  ✅ DONE
- [x] `annotate_cover` now also returns the representative comic's own
      `updated_at` as `cover_mtime` (Coalesce'd with a linked custom cover's), and
      the cover `?ts=` uses it (`card.vue`) instead of the group mtime — so a cover
      image re-downloads only when the image it shows changes, not when a sibling
      comic in the collection is re-imported.
- [x] Added `test_cover_mtime_tracks_representative_not_siblings`. The extra
      correlated subquery adds no Django round-trips (query-count test green).
      Cost note: one more correlated subquery per collection card per browse.

## Open decisions (forks)
1. **Scope plumbing:** delete as dead (Stage 3 default, de-complicate) **vs**
   wire it up for client-side fine-grained skip (Stage 3 alt). Deleting
   forecloses future fine-grained refresh.
2. **Timestamp consolidation (Stage 2):** trust `collection.updated_at` as the
   single source (delete per-card aggregation) — pending the prototype confirming
   the multijoin behavior and `TimestampUpdater` reliability.

## Verification
- Backend: `make fix` → `make lint` → `make ty` → pytest (browser + librarian +
  opds + reader suites).
- Frontend: vitest (`socket`, `browser` store specs).
- Manual: browser publisher/series view, add/remove a comic, confirm the
  affected cover updates; confirm OPDS `<updated>` + reader arc mtimes still move.

## Constraints
- Branch `codex-v2` is local-only: commit to the branch, no pushing, no PRs.
