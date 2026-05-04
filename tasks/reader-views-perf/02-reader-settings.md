# 02 — Reader settings (`c/settings`, `c/<pk>/settings`)

Per-scope settings CRUD. Settings can live at five scope levels:

- **`g`** (global) — one row per user, no FK.
- **`c`** (comic) — one row per (user, comic).
- **`s`** / `p` / `i` / `v` (series, all canonicalized to `s`) —
  one row per (user, series).
- **`f`** (folder) — one row per (user, folder).
- **`a`** (story_arc) — one row per (user, story_arc).

Three HTTP methods:

- `GET ?scopes=g,s,c` — return settings for the requested scopes.
- `PATCH` — update a single scope (with optional `scope_pk`).
- `DELETE` — reset / drop the scope.

## Files in scope

| File | LOC | Purpose |
| ---- | --- | ------- |
| `codex/views/reader/settings.py` | 309 | `ReaderSettingsBaseView` + `ReaderSettingsView`. Two classes; the base is also inherited by the reader view chain (sub-plan 01). |

## Per-request cost shape

### GET — `?scopes=g,s,c` (typical multi-scope read)

```python
# Pre-fetch comic if any non-g/c scope needs it
if needed_comic_fks and comic_pk:
    comic = Comic.objects.only(*needed_comic_fks).get(pk=comic_pk)
# Per scope
for scope in requested:
    self._get_scope(scope, scopes_out, comic, scope_info)
```

Per-scope work:

- **`g` (global):** `_get_global_settings` does `filter().first()`
  → if hit, return; if miss, `objects.create(...)` → 1 or 2
  queries.
- **`c` (comic):** `_get_scoped_settings("comic_id", comic.pk)` →
  1 query.
- **`s` (series), `f` (folder), `a` (story_arc):**
  `_get_scoped_settings(fk_field, scope_pk)` → 1 query, plus a
  follow-up `Model.objects.filter(pk=scope_pk).values_list("name").first()`
  → 1 query for the scope's display name. **2 queries per
  intermediate scope.**

For `?scopes=g,s,c` typical: 1 (comic prefetch) + 1 (global) + 2
(series settings + name) + 1 (comic settings) = **5 queries per GET**.

For `?scopes=g,s,f,a,c` (all five): 1 + 1 + 2 + 2 + 2 + 1 = **9
queries**.

### PATCH

- Validate input via serializer.
- For non-global: `_get_or_create_scoped_settings(fk_field,
  scope_pk)` → 1 (filter().first()) + 0–1 (create if missing) → 1–2
  queries.
- For global: `_get_global_settings()` → 1–2 queries.
- `instance.save()` → 1 query.
- Total: **2–3 queries per PATCH**.

### DELETE

- For global: `_get_global_settings()` + `instance.save()` → 2–3
  queries.
- For non-global: `SettingsReader.objects.filter(...).delete()` →
  1 query.

## Hotspots

### #1 — Per-scope name lookup fires its own query

`codex/views/reader/settings.py:198-207`:

```python
name = (
    (
        model.objects.filter(pk=scope_pk)
        .values_list("name", flat=True)
        .first()
        or ""
    )
    if model
    else ""
)
```

For each non-global, non-comic scope (`s`, `f`, `a`) the GET
handler fires a separate query just to fetch the name string for
the scope display. With `?scopes=g,s,c` that's one extra query;
with `?scopes=g,s,f,a,c` it's three.

Mitigations:

- **Fold into the comic prefetch.** When the comic is prefetched
  for FK resolution (line 227), pull the scope display names from
  the same comic row via `.select_related("series__name",
  "parent_folder__path")`. Story-arcs aren't on the comic FK
  pyramid; one extra query for them stays.
- **Batch into a single query.** Collect all the `(model, pk)`
  pairs, fire one query per model with `pk__in=[...]`, partition
  by pk in Python. With at most 3 scope types this is 0–3 queries
  vs. the current 0–3.
- **Drop the name on the response.** If the frontend already
  knows the display name (it has the scope_pk to PATCH against —
  it presumably knows what it's editing), `scope_info` may be
  unnecessary. Audit frontend usage first.

**Severity: low.** 1–3 extra queries per GET; only fires on
multi-scope GETs.

### #2 — Two-query get-or-create pattern

`codex/views/reader/settings.py:114-117` (global):

```python
instance = SettingsReader.objects.filter(**filter_kwargs).first()
if instance is not None:
    return instance
return SettingsReader.objects.create(**base_lookup, **self.CREATE_ARGS)
```

Same shape at `_get_or_create_scoped_settings` (lines 124-132).
Two queries on the create path, one on the hit path.

Mitigations:

- **`get_or_create`.** The Django ORM's
  `Model.objects.get_or_create(defaults={}, **lookup)` does the
  same logic in a single query (or two, with a race-condition
  fallback). Mechanically equivalent.
- **`update_or_create`.** Useful if the caller follows the get
  with a save; not the case here for GET.

The trade-off is that `get_or_create` doesn't accept the
`FILTER_ARGS` / `CREATE_ARGS` dict separation the current code
uses (the lookup keys are the same for filter and create). For the
`_get_global_settings` path, `FILTER_ARGS` adds
`comic__isnull=True` / `series__isnull=True` / etc. on top of
`base_lookup`, while `CREATE_ARGS` sets those FKs explicitly to
None at creation. Django's `get_or_create` would do the right
thing if `defaults` are supplied — but the asymmetry is worth
preserving review attention during the conversion.

**Severity: low.** Saves 1 query per cold GET on global. Rare.

### #3 — `_resolve_scope_pk` calls `getattr(comic, comic_fk, None)` per scope

`codex/views/reader/settings.py:156-168`:

```python
def _resolve_scope_pk(
    self,
    scope: str,
    comic_fk: str | None,
    comic: Comic | None,
) -> int | None:
    if scope == "a":
        raw = self.request.GET.get("story_arc_pk")
        return int(raw) if raw else None
    if comic and comic_fk:
        return getattr(comic, comic_fk, None)
    return None
```

Pure attribute access; fine.

The pre-fetch on line 227:

```python
needed_comic_fks = set()
for scope in requested:
    config = _SCOPE_MAP.get(scope)
    if config and config[1]:
        needed_comic_fks.add(config[1])
if needed_comic_fks and comic_pk:
    comic = Comic.objects.only(*needed_comic_fks).get(pk=comic_pk)
```

Already correctly batches the FK lookup into one query. No change
needed.

**Severity: none.** Already optimal.

### #4 — `get_reader_default_params` rebuilds the defaults dict per call

`codex/views/reader/settings.py:63-69`:

```python
@classmethod
def get_reader_default_params(cls) -> dict:
    return {
        key: cls._get_field_default(SettingsReader, key)
        for key in SettingsReader.DIRECT_KEYS
    }
```

Called from `reset_reader_settings` (DELETE on global). Each call
walks the model field list. The values are pure model metadata —
they don't change at runtime.

Mitigation: cache the dict at class load via a `Final` /
`cached_classproperty` / lazy module-level cache. Trivial.

**Severity: trivial.** Code health.

### #5 — `_get_bookmark_auth_filter` is duplicated from `BookmarkAuthMixin`

`codex/views/reader/settings.py:83-92`:

```python
def _get_bookmark_auth_filter(self) -> dict[str, int | str | None]:
    """Filter only the current user's settings rows."""
    if TYPE_CHECKING:
        self.request: Request
    if self.request.user.is_authenticated:
        return {"user_id": self.request.user.pk}
    if not self.request.session or not self.request.session.session_key:
        logger.debug("no session, make one")
        self.request.session.save()
    return {"session_id": self.request.session.session_key}
```

The class docstring references "_ReaderSettingsAuthMixin /
BookmarkAuthMixin" inlining; the duplicated copy here ensures the
settings view doesn't depend on `BookmarkAuthMixin`. Functionally
correct; mostly refactor opportunity.

`books.py:43` (`ReaderBooksView`) uses
`self.get_bookmark_auth_filter()` (from `BookmarkAuthMixin`), which
returns a dict with `user_id` / `session_id` — same shape as this
inline copy.

Mitigations:

- **De-dupe.** Have `ReaderSettingsBaseView` inherit
  `BookmarkAuthMixin` and drop the local copy. Or move the helper
  into a shared module.

**Severity: code health.** Not perf.

## Out of plan

- **PATCH `instance.save()` cachalot churn.** Settings writes
  invalidate `SettingsReader` rows in cachalot. Settings volume is
  low (a few writes per session at most), so the churn doesn't
  matter.
- **`SettingsReader.DIRECT_KEYS` introspection.** Reflects the
  model schema; not a perf concern.
- **The `_canonical_scope` aliasing.** Pure dispatch, no DB.

## Open questions

- **What's the actual scope-GET volume?** If the frontend reads
  multi-scope settings on every settings panel open and writes
  per-field changes, the GET path is read-heavy and worth tuning;
  the PATCH path isn't.
- **Does the frontend already know scope display names?** If so,
  `scope_info` is redundant and #1 closes by deletion.
- **Could settings be cached per-user with a short TTL?** They're
  user-state and rarely change; a 60 s cache with `vary_on_cookie`
  would zero out the read path.
