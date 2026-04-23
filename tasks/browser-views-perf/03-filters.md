# Filters Subsystem — Performance Analysis

## Inventory

| File                         | LOC | Purpose                                                                     |
| ---------------------------- | --- | --------------------------------------------------------------------------- |
| `filter.py`                  | 65  | Main filter aggregator; calls all sub-filters and applies `.distinct()`     |
| `bookmark.py`                | 39  | Bookmark filter logic (READ / UNREAD / IN_PROGRESS)                         |
| `field.py`                   | 67  | Comic field / facet filters (credits, tags, genres, etc.)                   |
| `group.py`                   | 52  | Group filter (folder / series / story-arc selection)                        |
| `search/parse.py`            | 266 | Main search query parser; tokenizes search string into FTS and field tokens |
| `search/fts.py`              | 23  | FTS5 MATCH filter builder                                                   |
| `search/field/parse.py`      | 143 | Lark grammar parser for field expression boolean logic                      |
| `search/field/expression.py` | 189 | Parse RHS of field expressions (operators, ranges, globs)                   |
| `search/field/filter.py`     | 113 | Combine field tokens into Django Q objects; handle m2m hoisting             |
| `search/field/column.py`     | 59  | Map field names to DB relations (role, credits, identifiers, etc.)          |
| `search/field/optimize.py`   | 71  | UNUSED regex optimization for LIKE queries                                  |

---

## Hotspots

### 1. Unconditional `.distinct()` on every filtered queryset — HIGH

**Path:** `filter.py:65`

`return model.objects.filter(query_filters).distinct()`

DISTINCT is expensive, especially with many-to-many joins. Executes even when
search and m2m filters are inactive. For a browse with no field filters or
search, still forces DB deduplication of the entire result set. Comment says
"Distinct necessary for folder view with search" but applies globally.

**Proposed change:** Make `.distinct()` conditional. Track whether active
filters include search or m2m relations (credits, tags, genres, teams,
story_arcs, characters, locations, universes, identifiers, sources). Add a flag
`self._uses_m2m_join` during filter construction.

**Impact:** High — DISTINCT causes full result-set scan; cost scales with result
size. **Risk:** Medium — must verify folder+search view doesn't regress.

---

### 2. ACL filter invokes DB queries on every request without cross-request cache — HIGH

**Path:** `filter.py:34` → `self.get_acl_filter(model, self.request.user)`

Returns `library_id__in=<visible_pks>` & age_rating filter. Has per-request
cache in `GroupACLMixin.init_group_acl()` (auth.py:354-368), but these are still
computed fresh on every request.

Called 7+ times per browser request (Comic, Folder, Series, StoryArc, Publisher,
Imprint, Characters, StoryArcs). Per-request cache helps, but 3 DB queries still
execute.

**Proposed change:** Add cross-request cache (Redis / memcache / django cache
framework) with key like
`f"codex:acl:lib:{user_id}:{library_last_modified_ts}"`. Invalidate on Library /
GroupAuth / AgeRating create / delete.

**Impact:** Medium — 3 queries/request → 1-2 cache hits for repeat visitors.
**Risk:** Low — new cache; invalidation hooks are localized.

---

### 3. Search query parsing runs on every request without memoization — HIGH

**Path:** `search/parse.py:182-198` (`_preparse_search_query()`), called on hot
path from line 240

Regex tokenization with `_TOKEN_RE.finditer(text)` at line 190, field-to-ORM
classification via `_parse_column_match()`, FTS token rebuilding. All CPU-bound.

**Perfect cache key:** `(user_id, search_string, model_name)` — search string is
deterministic and in `self.params["search"]`. Pagination on a filtered view
re-parses the same string every page.

**Proposed change:** Decorate `_preparse_search_query()` or create a cached
wrapper with `functools.lru_cache(maxsize=256)`. Key:
`(text, user.is_admin, admin_flags["folder_view"])`.

**Impact:** Medium (5-10ms per complex search request). **Risk:** Low — pure
function, no side effects.

---

### 4. Field expression parsing invokes Lark multiple times for identical expressions — MEDIUM

**Path:** `search/field/filter.py:96-113` (`get_search_field_filters()`),
specifically line 61-64

For each `(col, exp)` token pair, calls
`get_field_query(rel, rel_class, exp, model, many_to_many=...)` which invokes
`PARSER.parse(exp)` at `search/field/parse.py:138` and
`FieldQueryTransformer.transform(tree)`.

For compound queries like `protagonists:"Spider-Man" authors:"Stan Lee"`, Lark
parses the same string twice if expressions coincide. No deduplication.

**Proposed change:** Add `functools.lru_cache()` to `get_field_query()` with key
`(rel, exp, model.__name__, many_to_many)`. Lark tree is immutable;
transformation is deterministic.

**Impact:** Medium (2-10× Lark parses reduced to 1 per complex search).
**Risk:** Medium — verify Lark tree and transformer results are truly
deterministic and immutable. Test with complex boolean expressions.

---

### 5. Join demotion applied unconditionally; FTS semantics fragile — MEDIUM

**Path:** `filter.py:13-21` (`force_inner_joins()`)

Always demotes `{"codex_library", "codex_comicfts"}` to INNER JOINs. If model is
not Comic, also demotes `codex_comic`.

Correctness concern: `group_mtime.py:87` warns "Can't run demote_joins on
aggregate." Implies demote_joins breaks GROUP BY semantics.

Query plan impact: INNER JOIN can use different indexes than LEFT JOIN.

**Proposed change:** Conditional demote:

- Only demote `codex_comicfts` if `self.fts_mode` is True.
- Always demote `codex_library` (ACL joins are inherently INNER; no semantics
  lost).
- Conditionally demote `codex_comic` only if model is not Comic and
  search/filter is active.

**Impact:** Low (1-2 fewer JOIN condition filters in most queries). **Risk:**
High — FTS5 behavior may depend on INNER JOIN; removing demote could break
search correctness. **Requires FTS5 testing before merging.**

---

### 6. Field filter iterates all 27 BROWSER_FILTER_KEYS unconditionally — LOW

**Path:** `field.py:53-61` (`get_all_comic_field_filters()`)

Loops through all 27 keys (const.py:3-27) and calls
`_filter_by_comic_field(field, rel_prefix, filter_list)` for each. If
`filter_list` is empty, returns empty `Q()`.

**Proposed change:** Pre-filter the loop:
`for field in _FILTER_ATTRIBUTES if filters.get(field)`.

**Impact:** Low (~1-2ms CPU, negligible). **Risk:** Low — identical Q result.

---

### 7. FTS expression LIKE glob-to-lookup instantiates `BaseDatabaseOperations` unnecessarily — LOW

**Path:** `search/field/expression.py:99-120` (`_glob_to_lookup()`), line 106

Calls `BaseDatabaseOperations(None).prep_for_like_query(value)` for each glob
expression. Instantiates with `None` connection.

**Proposed change:** Cache at module level:
`_DB_OPS = BaseDatabaseOperations(None)` at top of file, reuse in
`_glob_to_lookup()`.

**Impact:** Low (~0.1ms savings per search). **Risk:** Low —
`BaseDatabaseOperations` is stateless for this method.

---

## Cross-cutting Observations

### Parsing on every request (search + field)

Both `search/parse.py:_preparse_search_query()` and
`search/field/parse.py:get_field_query()` run on every request without caching.
The search string is a **perfect cache key** — semantically deterministic.

Two-tier caching recommended:

1. **Request-level** — cache parsed results per request to avoid re-parsing when
   the same query is applied to multiple models (Comic, Folder, StoryArc, etc.).
2. **Global LRU** — cache pre-parsed tokens / trees with
   `functools.lru_cache(maxsize=256)` keyed on (search_text, user_admin_level,
   model_name).

This is especially high-value for pagination (page 2, 3, …) where the search
string is identical.

### `.distinct()` policy inconsistency

Applied at line 65 unconditionally, but comment justifies it for "folder view
with search." Reality:

- **M2M joins need it:** credits, tags, genres, teams, story_arcs, characters,
  locations, universes, identifiers, sources.
- **Non-M2M filters don't:** year, page_count, critical_rating, monochrome,
  file_type, etc.
- **Bookmark is LEFT JOIN:** needs distinct only if multiple bookmarks per comic
  (unlikely).

Root cause: field filter doesn't distinguish m2m paths. Build a
`_filter_has_m2m` flag during `_get_query_filters()` by checking which fields
are active.

### Join demotion fragility

Three separate concerns:

1. **FTS5 semantics** — lines 18-20 comment suggests FTS5 MATCH behaves
   differently with LEFT vs INNER JOIN. Unverified; needs test.
2. **Aggregate semantics** — `group_mtime.py:87` warns demote breaks GROUP BY.
   Demoting the same table in different contexts could conflict.
3. **ACL semantics** — Library ACL joins are always INNER; no harm in demoting.

Document why FTS requires INNER JOIN. Test FTS with LEFT JOIN to validate
assumption. If FTS truly needs INNER, only demote `codex_comicfts` when
`fts_mode=True`.

### Admin flag access pattern

`search/parse.py:90-104` caches admin flags per-request in a property. First
access triggers `AdminFlag.objects.filter(...)` query. **This is correct and
efficient.** No optimization needed.

### Bookmark filter activation

Bookmark filter at `bookmark.py:17-39` only activates when
`params.get("filters", {}).get("bookmark")` is truthy. **Correctly conditional;
no hotspot.**

### Dead code

`search/field/optimize.py` (71 lines) appears unused ("UNUSED regex optimization
for LIKE queries"). Delete if confirmed unused — it's dead weight in the import
graph and confusing for future maintainers.

---

## Out of Scope / Deferred

1. **Bookmark pagination and prefetch** — depends on serializer select_related /
   prefetch_related strategy.
2. **FTS5 index tuning** — codex.models.comic indexes; separate subsystem.
3. **Serializer performance** — filter returns QuerySet; serializer does heavy
   lifting.
4. **Search result ranking** — FTS5 provides rank; display layer consumes it.
5. **Browser annotate subsystem** — separate slice covers order / group_by /
   annotations.
6. **Query compiler caching** — Django's SQL compiler caching is per- QuerySet,
   not per search string. Separate optimization.
