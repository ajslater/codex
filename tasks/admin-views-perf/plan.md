# Codex `codex/views/admin/` — Performance Plan

How to make the admin endpoints faster, ranked by impact. Mirrors
the format of the [`tasks/reader-views-perf/`](../reader-views-perf/)
and [`tasks/opds-views-perf/`](../opds-views-perf/) plans, but
condensed into one file because the surface is small (~755 LOC,
11 view modules).

## Scope

Everything under `codex/views/admin/` plus the URL configuration
in `codex/urls/api/admin.py` and the `CodexStats` collector at
`codex/librarian/telemeter/stats.py` (which the `/admin/stats`
endpoint delegates to).

Out of scope:

- Browser, reader, OPDS views — covered by their own perf plans.
- Librarian daemon internals (CoverThread, ScribeThread, etc.) —
  the admin task endpoint just enqueues; the work is elsewhere.
- Frontend admin Pinia store and Vue components except for usage
  patterns that drive backend load (poll cadence, batch shape).
- Schema migrations — index suggestions are surfaced but not
  written; treat them as discretionary follow-ups.

## Why this matters

The admin views aren't on the hot read path the way
`browser/group/<pks>` or `reader/c/<pk>/<page>/page.jpg` are, but
two endpoints stand out as worth attention:

1. **`/admin/stats`** — opened on every Stats tab load and called
   nightly by the telemeter. ~30 SQL round trips today plus a
   CPU-heavy session-decode loop and a Python aggregation pass over
   every `SettingsBrowser` / `SettingsReader` row in the database.
   Slowest single admin response.
2. **`/admin/library`** — opened on the Libraries tab and reloaded
   on every websocket library-changed broadcast. The current
   `comic_count` + `failed_count` annotations join `Comic` and
   `FailedImport` together with `DISTINCT` to compensate for the
   Cartesian product. On a library with many comics this is the
   slowest list-page response.

Everything else is small/constant-time and falls out of the
`AdminAuthMixin` plumbing.

## Surface map

| File | LOC | Class(es) | Role |
| ---- | --- | --------- | ---- |
| `auth.py` | 28 | `AdminAuthMixin`, `Admin{API,GenericAPI,Model,ReadOnlyModel}View(Set)` | `IsAdminUser` permission. Trivial. |
| `permissions.py` | 22 | `HasAPIKeyOrIsAdminUser` | API-key bypass for `/admin/stats`. One DB hit per request. |
| `flag.py` | 48 | `AdminFlagViewSet` | CRUD on `AdminFlag`. Tiny table. Fine. |
| `group.py` | 56 | `AdminGroupViewSet` | CRUD on auth `Group` + `GroupAuth`. Already prefetches `user_set`/`library_set` and selects `groupauth`. |
| `user.py` | 135 | `AdminUserViewSet`, `AdminUserChangePasswordView` | CRUD on `User` + `UserAuth`. Already prefetches `groups` and selects `userauth__age_rating_metron`. |
| `library.py` | 172 | `AdminLibraryViewSet`, `AdminFailedImportViewSet`, `AdminFolderListView` | CRUD on `Library` + `FailedImport`, server-side dir picker. Hot. |
| `tasks.py` | 177 | `AdminLibrarianStatus{Active,All}ViewSet`, `AdminLibrarianTaskView` | Job status read + librarian queue dispatch. |
| `stats.py` | 74 | `AdminStatsView` | Wraps `CodexStats`. Hot. |
| `api_key.py` | 23 | `AdminAPIKey` | One PUT to rotate the API key. Fine. |
| `age_rating_metron.py` | 19 | `AdminAgeRatingMetronViewSet` | Read-only seeded lookup table. Trivial. |
| `__init__.py` | 1 | — | — |

Supporting code:

- `codex/librarian/telemeter/stats.py` — `CodexStats` aggregator
  (190 LOC). The actual work behind `/admin/stats`.
- `codex/serializers/admin/*.py` — DRF serializers; mostly thin.
- `codex/urls/api/admin.py` — URL config; one `path` per endpoint.

## Methodology

The same recipe used by the browser/reader/OPDS plans:

1. **Baseline.** Add an admin-specific perf-baseline runner under
   `tests/perf/run_admin_baseline.py` modeled on
   `run_baseline.py`. Capture silk traces for: Stats tab load
   (`GET /admin/stats`), Libraries tab load (`GET /admin/library`),
   Users tab load (`GET /admin/user`), Groups tab load
   (`GET /admin/group`), Jobs tab load (`GET /admin/librarian/status/all`),
   Folders picker (`GET /admin/folders`), and a worst-case `/admin/stats`
   call with all five `params` keys set.
2. **Per-finding patch.** Apply one fix per commit. Re-run baseline,
   compare cold/warm timings, capture deltas in this directory.
3. **No schema migrations** unless the perf gain is large enough to
   justify a separate review.

## Findings (ranked by impact)

### 1. `CodexStats._get_session_stats` — full Python decode loop **(high)**

`codex/librarian/telemeter/stats.py:104-120`.

```python
sessions = Session.objects.all()
anon_session_count = 0
for encoded_session in sessions:
    session = encoded_session.get_decoded()
    if not session.get("_auth_user_id"):
        anon_session_count += 1

user_stats = {}
for info in _USER_STATS.values():
    model = info["model"]
    subkeys = info["keys"]
    for instance in model.objects.all():
        cls._aggregate_settings_instance(instance, subkeys, user_stats)
```

Two compounding issues:

- **Session decode O(N).** `get_decoded()` runs HMAC + JSON parse
  per row, on every `Session` (active and idle). On installations
  with many returning users this is the single most expensive
  operation in `/admin/stats`.
- **Settings iteration O(M).** `SettingsBrowser` and `SettingsReader`
  are loaded as full ORM instances and aggregated in Python. A
  `SettingsReader` table can be huge — there's a row per
  `(user, comic|series|folder|story_arc, client)` scope tuple.
  Heavy readers easily hit tens of thousands of rows. Loading them
  all into memory just to bucket three fields is wasteful.

**Fix**

- Drop the per-session decode entirely. The frontend stat
  ("`user_anonymous_count`") doesn't need to be exact — replace with
  a heuristic using the public Session API:

  ```python
  total = Session.objects.count()
  # Authenticated sessions store `_auth_user_id` in session_data.
  # Use a server-side filter on the encoded blob — Django stores
  # session_data as `<sig>:<base64-json>`; the auth user id appears
  # as a JSON key inside the base64. We can avoid decode by filtering
  # for the literal `_auth_user_id` substring before the b64 boundary
  # — but that's fragile. Simpler: count authenticated sessions via
  # `User.last_login` recency + `SESSION_COOKIE_AGE` and subtract.
  ```

  Even simpler: drop `user_anonymous_count` from the response when
  decode-cost is unjustified. The flag exists to satisfy the
  `StatsConfigSerializer` field; a hardcoded `None` (or omitted via
  `required=False`) is acceptable telemetry.

  *Recommended path:* keep the field but use a sampled estimate.
  Iterate at most `MAX_DECODE` (e.g. 100) sessions chosen via
  `.order_by("?")[:MAX_DECODE]`, and scale up to the total count.
  Telemetry is approximate by nature; an O(1) sample is enough.

- Replace the settings-instance loops with SQL aggregation:

  ```python
  user_stats: dict[str, dict[str, int]] = {}
  for info in _USER_STATS.values():
      model = info["model"]
      for key in info["keys"]:
          rows = (
              model.objects
              .values(key)
              .exclude(**{f"{key}__isnull": True})
              .annotate(count=Count("pk"))
          )
          bucket = user_stats.setdefault(key, {})
          for row in rows:
              bucket[row[key]] = row["count"]
  ```

  3 columns × 2 models = 6 GROUP-BY queries instead of `O(N+M)`
  Python rows. Each query indexes the column being grouped; no
  JOINs.

**Estimated win**: order-of-magnitude on installations with non-trivial
session/settings volume. On the slimlib dev DB the session loop is
fast; the settings loop is the dominant cost.

### 2. `CodexStats._get_model_counts` — serial `COUNT(*)` round trips **(high)**

`codex/librarian/telemeter/stats.py:79-89`.

```python
for model in models:
    name = snakecase(model.__name__) + "_count"
    qs = model.objects
    if model == Library:
        qs = qs.filter(covers_only=False)
    obj[name] = qs.count()
```

Called for each of `config` (4 models), `groups` (7 models), and
`metadata` (19 models) when their respective param keys are set.
Worst case: **30 separate `SELECT COUNT(*)` queries** per `/admin/stats`
call, one round trip each.

**Fix**

Two layers, in priority order:

a. **Cache the entire stats response** at the view layer with a
   short TTL (e.g. 60s). The data changes only as the librarian
   imports — a brief staleness window is fine for a stats tab.
   Invalidate the cache on `LIBRARY_CHANGED_TASK` /
   `USERS_CHANGED_TASK` / `GROUPS_CHANGED_TASK`. Implementation:
   `django.core.cache` with a deterministic key derived from
   sorted `params`.

   This is the highest-leverage fix because it covers both the
   COUNT(*) cost *and* the session/settings cost from finding 1.

b. **Parallelize the counts** with `ThreadPoolExecutor` if (a) isn't
   accepted. SQLite + django-cachalot tolerate concurrent reads;
   the per-table COUNT(*)s are independent. Caveat: this adds
   thread complexity for a one-shot endpoint and the cache approach
   gives a bigger win.

c. **Single-query union (last resort)**. SQLite supports
   `SELECT 'comic' AS t, COUNT(*) FROM comic UNION ALL ...`.
   Cuts round trips to one but loses Django ORM clarity. Only
   pursue if (a) and (b) are both rejected.

**Estimated win**: ~30× reduction in round-trip count when cached;
cold path stays at current speed (acceptable, runs nightly).

### 3. `AdminLibraryViewSet` — JOIN+DISTINCT count annotations **(medium)**

`codex/views/admin/library.py:47-60`.

```python
queryset = (
    Library.objects.prefetch_related("groups")
    .annotate(
        comic_count=Case(
            When(covers_only=True, then=_CUSTOM_COVER_COUNT),
            default=Count("comic", distinct=True),
        ),
        failed_count=Count("failedimport", distinct=True),
    )
    .defer("update_in_progress", "created_at", "updated_at")
)
```

The `Count("comic", distinct=True)` and `Count("failedimport", distinct=True)`
both join their respective related tables in the same query. Django
adds `DISTINCT` to suppress the Cartesian product, but the database
still has to materialize and de-duplicate the join's output. On a
library with millions of comics and a non-trivial failed-imports
table, this is slow even with `(library_id, *)` indexes.

The pattern `_CUSTOM_COVER_COUNT` (`library.py:30-38`) already shows
the cure: a correlated `Subquery` with `OuterRef`. Apply it
uniformly:

```python
_COMIC_COUNT = Coalesce(
    Subquery(
        Comic.objects
        .filter(library=OuterRef("pk"))
        .values("library")
        .annotate(c=Count("pk"))
        .values("c")[:1]
    ),
    Value(0),
)

_FAILED_COUNT = Coalesce(
    Subquery(
        FailedImport.objects
        .filter(library=OuterRef("pk"))
        .values("library")
        .annotate(c=Count("pk"))
        .values("c")[:1]
    ),
    Value(0),
)

queryset = (
    Library.objects.prefetch_related("groups")
    .annotate(
        comic_count=Case(
            When(covers_only=True, then=_CUSTOM_COVER_COUNT),
            default=_COMIC_COUNT,
        ),
        failed_count=_FAILED_COUNT,
    )
    .defer("update_in_progress", "created_at", "updated_at")
)
```

Both subqueries hit `(library_id, …)` indexes on `Comic` and
`FailedImport` — index-only counts, no DISTINCT, no Cartesian
materialization.

**Estimated win**: significant on large libraries (millions of comics);
neutral on small. Verify with the baseline runner.

### 4. `AdminFolderListView._get_dirs` — double syscall per entry **(medium-low)**

`codex/views/admin/library.py:137-150`.

```python
for subpath in root_path.iterdir():
    if subpath.name.startswith(".") and not show_hidden:
        continue
    if subpath.resolve().is_dir():
        subdirs.append(subpath.name)
```

`iterdir()` returns `Path` objects without inode metadata, so
`subpath.resolve()` does a full readlink chain *and* `is_dir()`
runs a final `stat()`. That's two-or-more syscalls per directory
entry. On a directory with thousands of entries (or a large library
root with deep symlink chains) this is noticeably slow.

**Fix**

Use `os.scandir()` to get a `DirEntry` with cached stat info, and
prefer `entry.is_dir(follow_symlinks=True)` (one stat per entry):

```python
@staticmethod
def _get_dirs(root_path, show_hidden) -> tuple[str, ...]:
    dirs: list[str] = []
    if root_path.parent != root_path:
        dirs.append("..")
    subdirs: list[str] = []
    with os.scandir(root_path) as it:
        for entry in it:
            if entry.name.startswith(".") and not show_hidden:
                continue
            try:
                if entry.is_dir(follow_symlinks=True):
                    subdirs.append(entry.name)
            except OSError:
                # Broken symlink or permission denied — skip silently
                continue
    dirs.extend(sorted(subdirs))
    return tuple(dirs)
```

Behavior change: the current `.resolve()` would canonicalize before
checking `is_dir`. `entry.is_dir(follow_symlinks=True)` follows the
link but doesn't canonicalize the path string we return — that
matches the user-visible behavior (the picker returns names, not
resolved paths).

**Estimated win**: 2× faster on directories with many entries; less
on small dirs. Real wins come on slow filesystems (NFS, deep symlink
chains) and on Windows where `stat()` is more expensive.

### 5. `HasAPIKeyOrIsAdminUser` — verify cachalot covers it **(low)**

`codex/views/admin/permissions.py:13-22`.

```python
return Timestamp.objects.filter(
    key=Timestamp.Choices.API_KEY.value, version=api_key
).exists()
```

Runs on every `/admin/stats` request that supplies `apiKey`. The
`Timestamp` table is small (4 rows max) and cachalot should cache
this; verify with a silk trace and either:

- confirm cachalot serves it (no work needed), or
- if it doesn't (e.g. due to `.filter().exists()` bypass), wrap with
  `django.core.cache` keyed by the api key with a 60s TTL.

This is a hygiene check, not a known-broken hot spot.

### 6. `AdminLibrarianStatusActiveViewSet` — `Q(...)` filter ordering **(low)**

`codex/views/admin/tasks.py:120-126`.

```python
queryset = LibrarianStatus.objects.filter(
    Q(preactive__isnull=False) | Q(active__isnull=False)
).order_by("preactive", "active", "pk")
```

Two un-indexed nullable timestamp columns under an `OR` filter +
ORDER BY. The table is small (one row per active/preactive task,
typically < 50 rows), so this isn't expensive in practice.

**Fix** — at user direction, add the index without baseline-tracing
the cost. A partial index on `(preactive, active)` with the matching
condition `preactive IS NOT NULL OR active IS NOT NULL` serves both
the filter and the ORDER BY without scanning historical (both-NULL)
rows. SQLite walks the index in `(preactive, active)` order and
appends rowid (= pk) as the natural tiebreak, satisfying the full
`ORDER BY preactive, active, pk` clause from the index alone.

```python
# codex/models/admin.py
class Meta(BaseModel.Meta):
    indexes = (
        Index(
            fields=("preactive", "active"),
            condition=Q(preactive__isnull=False) | Q(active__isnull=False),
            name="codex_libstat_active_idx",
        ),
    )
```

Migration: `0040_librarianstatus_codex_libstat_active_idx.py`
(autogenerated, then docstring-fixed for Ruff D100/D101).

### 7. `_TASK_MAP` shared mutable state **(correctness, not perf)**

`codex/views/admin/tasks.py:142-152`.

```python
def _get_task(self, name, pk) -> LibrarianTask | None:
    ...
    task = _TASK_MAP.get(name)
    if pk and isinstance(task, FSPollLibrariesTask):
        task.library_ids = frozenset({pk})
    return task
```

`_TASK_MAP` is a `MappingProxyType` of pre-instantiated task
objects shared across requests. The `poll`/`poll_force` entries are
`FSPollLibrariesTask` instances; `_get_task` mutates their
`library_ids` in place. Two concurrent admin POSTs that both call
`poll` with different library ids race: the second write wins, the
first might enqueue with the second's ids.

**Fix**

Build a fresh task instance for the mutable case:

```python
if isinstance(task, FSPollLibrariesTask):
    task = FSPollLibrariesTask(frozenset({pk}) if pk else frozenset(),
                               force=task.force)
```

Or store a *factory* in `_TASK_MAP` for the mutable kinds.

**Surface as a separate fix.** Not perf, but worth flagging since
the read of this code revealed it.

### 8. Frontend: `loadTables` fan-out **(observation, not a fix)**

`frontend/src/stores/admin.js:107-112`.

```js
loadTables(tables) {
  if (this._requireAdmin()) return false;
  for (const table of tables) {
    this.loadTable(table);
  }
}
```

Already concurrent (no `await`). Each call hits one endpoint; HTTP/2
multiplexes them onto a single connection. No change needed —
mention only because a casual reader might assume it's sequential.

### 9. `AdminLibrarianStatus` viewset consolidation **(code quality)**

`codex/views/admin/tasks.py:120-133`.

```python
class AdminLibrarianStatusActiveViewSet(AdminReadOnlyModelViewSet):
    queryset = LibrarianStatus.objects.filter(
        Q(preactive__isnull=False) | Q(active__isnull=False)
    ).order_by("preactive", "active", "pk")
    serializer_class = LibrarianStatusSerializer


class AdminLibrarianStatusAllViewSet(AdminReadOnlyModelViewSet):
    queryset = LibrarianStatus.objects.all().order_by("pk")
    serializer_class = LibrarianStatusSerializer
```

Two near-identical viewsets that differ only in filter and ordering.
Same model, same serializer, same permissions, same `never_cache`
wrapper at the URL layer.

**Fix** — collapse into a single viewset that picks its queryset off
a URL kwarg or an attribute set at `as_view()` time:

```python
class AdminLibrarianStatusViewSet(AdminReadOnlyModelViewSet):
    """Librarian Task Statuses, optionally filtered to active/preactive."""

    serializer_class = LibrarianStatusSerializer
    active_only: ClassVar[bool] = False

    @override
    def get_queryset(self):
        if self.active_only:
            return LibrarianStatus.objects.filter(
                Q(preactive__isnull=False) | Q(active__isnull=False)
            ).order_by("preactive", "active", "pk")
        return LibrarianStatus.objects.order_by("pk")
```

Wire `active_only=True` at the URL layer:

```python
# codex/urls/api/admin.py
path(
    "librarian/status",
    never_cache(AdminLibrarianStatusViewSet.as_view(
        {**READ}, active_only=True,
    )),
    name="librarian_status",
),
path(
    "librarian/status/all",
    never_cache(AdminLibrarianStatusViewSet.as_view({**READ})),
    name="librarian_status_all",
),
```

Not a perf win, but kills duplication and shrinks the imports in
`urls/api/admin.py`.

### 10. `UserAuth` / `GroupAuth` write-path always-update **(low)**

`codex/serializers/admin/users.py:62-75`,
`codex/serializers/admin/groups.py:32-40`.

`AdminUserViewSet.perform_create` always creates a `UserAuth` row
alongside the User; `GroupSerializer.create` always creates a
`GroupAuth` alongside the Group. So at update time the auth row is
guaranteed to exist — yet `_apply_userauth` calls `get_or_create`
(which always emits a `SELECT` and may emit an `INSERT`), and
`_apply_groupauth` does a `.get()` followed by an instance `.save()`.

**Fix** — swap to a single `UPDATE` on the queryset, no instance
hydration:

```python
@staticmethod
def _apply_userauth(instance, userauth_data) -> None:
    """Apply nested UserAuth fields with a single UPDATE."""
    if not userauth_data or "age_rating_metron" not in userauth_data:
        return
    UserAuth.objects.filter(user=instance).update(
        age_rating_metron=userauth_data["age_rating_metron"],
    )

@staticmethod
def _apply_groupauth(instance, groupauth_data) -> None:
    """Apply nested GroupAuth fields with a single UPDATE."""
    if not groupauth_data or "exclude" not in groupauth_data:
        return
    GroupAuth.objects.filter(group=instance).update(
        exclude=groupauth_data["exclude"],
    )
```

One round trip instead of two (or three, in the get-or-create
miss path). If the auth row is somehow absent the `UPDATE` is a
silent no-op rather than re-creating a row with a default — that's
the right semantic; a missing auth row is a data-integrity issue
the create path has already established invariants for.

Low impact: admin user/group writes are infrequent. Worth doing
because the fix is essentially free and removes a SELECT-then-write
race window.

## Discretionary follow-ups (not in this plan's first cut)

- **Stats cache**. If finding 2 lands as a TTL cache, document the
  invalidation contract in `CodexStats` so future callers don't
  bypass it.
- **`/admin/library/<pk>` retrieve**. The same `comic_count` /
  `failed_count` annotations apply on detail GETs; the fix from
  finding 3 covers it automatically (annotation lives on the
  queryset).
- **`AdminFlag.value` text vs typed fields**. `AdminFlag` overloads
  `value` as a string, plus `on` boolean, plus `age_rating_metron` FK.
  Each flag knows which one to read. Not perf, but the union shape
  hurts type checking and forces serializer branching.

## Out of scope

- Backend-paginated admin list views. The current viewsets return
  full lists; for installations with thousands of users / hundreds
  of libraries / large `LibrarianStatus` history this would matter,
  but pagination changes the wire contract and the frontend's table
  rendering. Separate project.
- Replacing the WebSocket-driven admin refresh with a more
  targeted invalidation mechanism. Cross-cuts the librarian
  notifier; out of scope.
- Schema changes — partial indexes, new composite indexes — surfaced
  as ideas in finding 6, but not landed without dedicated review.

## Verification

Per finding, the same shape:

1. Run the new `tests/perf/run_admin_baseline.py` against the dev
   slimlib DB (`CODEX_CONFIG_DIR=… DEBUG=1`). Capture silk traces.
2. Apply the fix.
3. Re-run; diff cold and warm timings. Aim for a measurable
   improvement on the targeted endpoint (median wall-clock + query
   count).
4. Land as one commit with the before/after silk JSON committed
   under `tasks/admin-views-perf/<finding>-{before,after}.json`.

Suggested ordering for the actual work:

1. **Stats cache (finding 2a).** Biggest single win, simplest patch.
2. **Stats settings aggregation (finding 1, settings half).** Removes
   the worst Python-side hot loop. Defer the session-decode question
   until the cache covers normal use.
3. **Library annotations (finding 3).** Replace the JOIN+DISTINCT
   pattern with correlated subqueries.
4. **Folder picker (finding 4).** `os.scandir` rewrite. Small but
   self-contained.
5. **LibrarianStatus index (finding 6).** Partial composite index;
   migration auto-generated.
6. **`_TASK_MAP` race (finding 7).** Build a fresh task instance for
   the mutable `FSPollLibrariesTask` case.
7. **Viewset consolidation (finding 9).** Collapse the two
   `LibrarianStatus` viewsets into one with an `active_only`
   class attribute set at `as_view()` time.
8. **UserAuth/GroupAuth update (finding 10).** Swap `get_or_create`
   /`get`+`save` to `filter().update()` on both auth helpers.
9. **Hygiene check (finding 5).** Verify cachalot covers
   `HasAPIKeyOrIsAdminUser` (deferred until baseline silk traces).

Each is a small reviewable commit. Bundle into one PR like the
cover cleanup, or land separately if the diff for any one fix is
non-trivial.

## Risks

- **Stats cache invalidation.** The TTL approach is simple but
  short-windows of staleness will be visible if a user clicks
  Stats immediately after an import. The 60s window is the right
  trade. Document the staleness in the response (e.g. include
  `cached_at` so the UI can render a freshness hint if desired).
- **Session-decode removal / sampling.** Telemetry consumers may
  rely on exact `user_anonymous_count`. Coordinate with the
  telemeter format owner before changing wire shape.
- **`Count` → `Subquery` migration.** Ensure the result type stays
  `IntegerField` (Coalesce(Subquery, Value(0)) does this); the
  serializer's `IntegerField(read_only=True)` won't notice the
  change.
- **`os.scandir` change.** Behavior on broken symlinks and recursive
  links must match the current `.resolve()` semantics enough that the
  picker doesn't surface dangling entries. Add a unit test against a
  fixture directory with: a normal subdir, a symlinked subdir, a
  broken symlink, and a hidden subdir.
