# Bookmark daemon perf — plan

`codex/librarian/bookmark/` is small (5 files, ~400 LOC) — single
plan file, no meta split.

## Why this matters

The bookmark thread sits behind every page turn. `ReaderPageView`
fires `BookmarkUpdateTask` every time a reader advances a page (when
`?bookmark=true`); the bookmark PUT endpoint
(`/api/v3/c/<pk>/<page>/bookmark`) does the same. With even a single
user reading sequentially, the thread sees one task per page turn —
amplified across concurrent users. The aggregator collapses bursts,
but the per-task work still runs every `FLOOD_DELAY` (3 s) on a
non-empty cache.

The thread also handles three secondary task types
(`ClearLibrarianStatusTask`, `CodexLatestVersionTask`, `TelemeterTask`,
`UserActiveTask`). Some of these block the thread on network I/O,
which delays bookmark writes.

## Scope

```
codex/librarian/bookmark/
├── __init__.py
├── bookmarkd.py       BookmarkThread + BookmarkKey aggregation
├── tasks.py           BookmarkUpdateTask, UserActiveTask, etc.
├── update.py          BookmarkUpdateMixin (the actual SQL)
├── user_active.py     UserActiveMixin (UserAuth.updated_at touch)
└── latest_version.py  CodexLatestVersionUpdater (PyPI fetch)
```

Plus the live callers:

- `codex/views/reader/page.py` — fires `BookmarkUpdateTask` per
  page read (hottest source)
- `codex/views/bookmark.py` — fires `BookmarkUpdateTask` from
  `BookmarkPageView.put`
- `codex/views/browser/bookmark.py` — calls `update_bookmarks`
  directly (synchronous path, not via task queue)
- `codex/views/mixins.py` + `codex/views/frontend.py` — fires
  `UserActiveTask` per index page hit

## Hot path

`BookmarkUpdateTask` from the reader page view. The aggregator's
`BookmarkKey` partitions tasks by `(auth_filter, comic_pks)` — so
all updates from one user reading one comic collapse into one
cache entry, last-write-wins on `page` and `finished`. Per
`FLOOD_DELAY` window (3 s), `send_all_items` walks the cache and
calls `update_bookmarks` per key.

`update_bookmarks` today fires **two SELECTs and two writes per
key**:

1. SELECT existing bookmarks (with `page_count` annotation) →
   `_update_bookmarks` builds bookmark instances → `bulk_update`
2. SELECT comics missing bookmarks (`~Q(bookmark__user_id=...)`) →
   `_create_bookmarks` builds Bookmark rows → `bulk_create`

Then per call: enqueue one `NotifierTask` to broadcast the change
to the user's WebSocket group.

## Findings

### F1 — `BookmarkKey.__eq__` uses hash equality **(correctness)**

`codex/librarian/bookmark/bookmarkd.py:39-42`:

```python
@override
def __eq__(self, other) -> bool:
    """Equal uses hashes."""
    return self.__hash__() == other.__hash__()
```

This is **wrong**. Two distinct `BookmarkKey`s with a hash
collision would compare equal, so the second one's update gets
merged into the first one's cache entry. With small input spaces
collisions are rare, but the consequence is data loss — one user's
bookmark merged into another user's row.

`__eq__` should compare fields directly. `__hash__` is a digest;
`__eq__` is the authoritative identity check.

**Fix**:

```python
@override
def __eq__(self, other) -> bool:
    if not isinstance(other, BookmarkKey):
        return NotImplemented
    return (
        self.auth_filter == other.auth_filter
        and self.comic_pks == other.comic_pks
        and self.user_pk == other.user_pk
    )
```

`@dataclass(frozen=True)` would auto-generate both `__hash__` and
`__eq__` correctly — but the auth_filter Mapping isn't trivially
hashable. Easier: keep the manual `__hash__` (which is correct)
and replace `__eq__` only.

### F2 — `BookmarkKey.__hash__` rebuilds the auth_filter tuple per call **(low)**

Same file, lines 31-37:

```python
@override
def __hash__(self) -> int:
    auth_filters = (
        None if self.auth_filter is None else tuple(self.auth_filter.items())
    )
    return hash((auth_filters, self.comic_pks, self.user_pk))
```

`__hash__` is called per-cache-key lookup (`if key not in self.cache`,
`self.cache[key]`). Each call materializes `tuple(...items())` from
the auth_filter dict. Cheap but redundant.

**Fix**: cache the hash on the dataclass instance via
`__post_init__`. Requires the instance to be effectively immutable
after construction — which it already is, by convention.

```python
@dataclass
class BookmarkKey:
    auth_filter: Mapping[str, int | str | None] | None = None
    comic_pks: tuple = ()
    user_pk: int = 0
    _hash: int = field(default=0, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        af = (
            None if self.auth_filter is None
            else tuple(sorted(self.auth_filter.items()))
        )
        object.__setattr__(self, "_hash",
                           hash((af, self.comic_pks, self.user_pk)))

    @override
    def __hash__(self) -> int:
        return self._hash
```

Bonus: `sorted()` on the tuple makes the hash stable regardless of
the dict's insertion order — defensive against `{"user_id": 1}`
vs `{"session_id": "abc", "user_id": 1}` shape drift.

### F3 — `update_bookmarks` does 2× SELECT + 2× write per key **(high impact)**

`codex/librarian/bookmark/update.py:139-146`:

```python
@classmethod
def update_bookmarks(cls, auth_filter, comic_pks, updates) -> int:
    count = cls._update_bookmarks(auth_filter, comic_pks, updates)
    count += cls._create_bookmarks(auth_filter, comic_pks, updates)
    if count:
        uid = next(iter(auth_filter.values()))
        cls._notify_library_changed(uid)
    return count
```

`_update_bookmarks`:
- SELECT existing bookmarks with annotated `page_count`
- Python loop validating page bounds + setting fields
- `bulk_update`

`_create_bookmarks`:
- SELECT comics that don't have a matching bookmark
  (`~Q(bookmark__user_id=...)`)
- Python loop building Bookmark instances
- `bulk_create`

The whole pattern collapses to one UPSERT via
`bulk_create(update_conflicts=True, ...)`. Django ≥ 4.1 supports
`ON CONFLICT … DO UPDATE` natively. The unique-together
`(user, session, comic)` is exactly the conflict key.

**Fix sketch**:

```python
@classmethod
def update_bookmarks(cls, auth_filter, comic_pks, updates) -> int:
    if not updates:
        return 0

    # Fetch page_count once for the page-clamp pass — only field
    # we need from Comic.
    page_counts = (
        {} if updates.get("page") is None
        else dict(
            Comic.objects.filter(pk__in=comic_pks)
            .values_list("pk", "page_count")
        )
    )

    now = django_timezone.now()
    upserts = []
    for comic_pk in comic_pks:
        row_updates = dict(updates)
        cls._clamp_page(row_updates, page_counts.get(comic_pk, 0))
        upserts.append(Bookmark(
            comic_id=comic_pk,
            updated_at=now,
            **auth_filter,
            **row_updates,
        ))

    Bookmark.objects.bulk_create(
        upserts,
        update_conflicts=True,
        update_fields=tuple(set(updates.keys())
                            & _BOOKMARK_UPDATE_FIELDS | {"updated_at"}),
        unique_fields=Bookmark._meta.unique_together[0],
    )

    cls._notify_library_changed(next(iter(auth_filter.values())))
    return len(upserts)
```

**Query count**: 2 SELECTs + 2 writes → 1 SELECT (only when `page`
is in updates) + 1 INSERT-OR-UPDATE.

**Bonus correctness fix**: the existing `_create_bookmarks` passes
`update_fields` and `unique_fields` to `bulk_create` without
`update_conflicts=True`. Django ignores both args silently in that
mode (verified by reading `_check_bulk_create_options` in the
Django source — `update_fields` only takes effect when
`update_conflicts=True`). The current code only works because
`_get_comics_without_bookmarks` already pre-filters to avoid
conflicts. Worth fixing.

**Caveat — auto-`finished` on last page**: today
`_update_bookmarks_validate_page` sets `bm.finished = True` when
the page hits `max_page`. The UPSERT path needs the same
auto-flip — keep the clamp-and-flag logic in `_clamp_page`.

### F4 — `Now()` per-instance vs single timestamp **(low)**

`codex/librarian/bookmark/update.py:52`:

```python
bm.updated_at = Now()
```

`Now()` is a SQL expression evaluated server-side — every Bookmark
row in the bulk_update gets its own `NOW()` call in the generated
SQL. Most DBs short-circuit `NOW()` to the same transaction-start
timestamp anyway, but the SQL is uglier than necessary.

**Fix**: capture `now = django_timezone.now()` once at the top of
`update_bookmarks` and reuse. Already part of the F3 sketch above.

### F5 — `urlopen` blocks the bookmark thread **(high impact for latest-version path)**

`codex/librarian/bookmark/latest_version.py:24-30`:

```python
@staticmethod
def _fetch_latest_version():
    response = urlopen(_REPO_URL, timeout=_REPO_TIMEOUT)  # noqa: S310
    source = response.read()
    decoded_source = source.decode("utf-8")
    return json.loads(decoded_source)["info"]["version"]
```

`_REPO_TIMEOUT = 5` seconds. `urlopen` is synchronous; it blocks
the bookmark thread for up to 5 s on a slow PyPI response or
network outage.

`bookmarkd.py`:

```python
case CodexLatestVersionTask():
    worker = CodexLatestVersionUpdater(...)
    worker.update_latest_version(force=task.force)
```

This runs inside `_process_task_immediately`, which is called from
`aggregate_items` → `process_item`. **The aggregator's main loop
stalls for the full network roundtrip.** Every queued
`BookmarkUpdateTask` waits behind the PyPI fetch.

`TelemeterTask` (also in `_process_task_immediately`) likely has
the same shape — `send_telemetry` is network I/O.

**Three fix options, ranked by scope**:

a. **Move long-running I/O off the bookmark thread.**
   Spawn a one-shot `threading.Thread` to do the network call,
   then enqueue a follow-up task on the librarian queue when it
   completes. The bookmark thread returns immediately. Best for
   correctness — bookmarks don't stall.

b. **Use `concurrent.futures.ThreadPoolExecutor`** on the
   `CodexLatestVersionUpdater` so the fetch runs concurrently
   with the next aggregator iteration. Same idea as (a), more
   structured.

c. **Tighten the timeout** (e.g. 2 s) and accept that the thread
   is occasionally blocked. Lowest-impact fix; doesn't address
   the design issue.

Recommended: (a) for both `CodexLatestVersionTask` and
`TelemeterTask`. The bookmark thread becomes purely DB work; the
"low priority background things" framing in the existing
docstring is wrong if those things include 5 s network timeouts.

### F6 — `update_or_create` in user_active.py **(low impact)**

`codex/librarian/bookmark/user_active.py:32-39`:

```python
if now - last_recorded > self.USER_ACTIVE_RESOLUTION:
    user = User.objects.get(pk=pk)
    UserAuth.objects.update_or_create(user=user)
    self._user_active_recorded[pk] = now
```

`update_or_create` is SELECT-then-UPDATE (or INSERT). The
`AdminUserViewSet.perform_create` always provisions a `UserAuth`
row at user creation, so the row is guaranteed to exist on this
hot path — same shape as
[PR #610 finding 10](../admin-views-perf/plan.md).

The in-process cache (`_user_active_recorded`) gates this to once
per user per hour, so the cost is bounded. But each first-call-
per-user-per-restart pays the SELECT + UPDATE round trip, plus a
separate `User.objects.get(pk=pk)` SELECT just to acquire a row
to pass into `update_or_create(user=user)`.

**Fix**:

```python
def update_user_active(self, pk: int, log) -> None:
    last_recorded = self._user_active_recorded.get(pk, EPOCH_START)
    now = django_timezone.now()
    if now - last_recorded <= self.USER_ACTIVE_RESOLUTION:
        return
    # ``auto_now=True`` on UserAuth.updated_at fires only on save();
    # ``.update()`` skips it. Pass the timestamp explicitly so the
    # row's mtime advances.
    updated = UserAuth.objects.filter(user_id=pk).update(updated_at=now)
    if not updated:
        log.warning(f"No UserAuth row for user pk={pk}; skipping.")
    self._user_active_recorded[pk] = now
```

**Query count**: 2 → 1. Drops the `User.objects.get` and the
`update_or_create` SELECT.

### F7 — `Bookmark` index for the `_get_comics_without_bookmarks` predicate **(deferred)**

The `~Q(bookmark__user_id=...)` subquery walks the
`bookmark.user_id` index. Today it's a single-column index
(declared via `db_index=True`). For very heavy users with many
bookmarks, a composite `(user, comic)` index would let the planner
satisfy the NOT EXISTS without a heap probe.

**Defer** — the F3 UPSERT eliminates this code path entirely
(`_get_comics_without_bookmarks` goes away). Only re-evaluate if
F3 lands and benchmarks reveal a different bottleneck.

### F8 — `_notify_library_changed` per-task vs cross-user batching **(low)**

Today `update_bookmarks` enqueues one `NotifierTask` per call. Per
`send_all_items`, that's one task per cache entry → one task per
unique `(user, comic_pks)` pair. With N concurrent readers, the
notifier queue grows by N per `FLOOD_DELAY` cycle.

`NotifierTask` is broadcast over Channels — each is cheap, but
batching multiple users' changes into one fan-out task could
amortize the WebSocket plumbing. Speculative; **defer until
benchmarks show notifier queue depth as a problem**.

## Suggested ordering

1. **F1** — correctness fix. Land first, alone. Pure refactor of
   `__eq__`. No behavior change beyond eliminating the collision
   data-loss path.
2. **F2** — hash caching, defensive sort. Bundle with F1 (same
   file, same dataclass).
3. **F6** — `user_active.py` `filter().update()`. Single-file
   diff, mirrors PR #610's pattern. Land independently.
4. **F3 + F4** — the big win. UPSERT collapse + single-timestamp.
   Touches `update.py` substantially; the unit of risk is one PR.
   Requires verifying the auto-`finished`-on-last-page invariant
   ports cleanly.
5. **F5** — move long-running tasks off the bookmark thread.
   Touches `bookmarkd.py`'s task dispatch. Land last so failures
   don't stall the perf-critical bookmark path while debugging.

## Methodology

For each finding:

1. **Capture baseline.** No existing perf harness for the bookmark
   thread. Cheap microbench shape:

   ```python
   # tests/perf/bookmark_microbench.py
   from time import perf_counter
   from codex.librarian.bookmark.update import BookmarkUpdateMixin
   from django.test.utils import CaptureQueriesContext
   from django.db import connection

   def bench(updates, comic_pks, auth_filter):
       with CaptureQueriesContext(connection) as ctx:
           t0 = perf_counter()
           BookmarkUpdateMixin.update_bookmarks(auth_filter, comic_pks, updates)
           wall = perf_counter() - t0
       return len(ctx.captured_queries), wall * 1000
   ```

   Run with N comic_pks ∈ {1, 10, 50} for each fix.

2. **Apply the fix**.

3. **Re-run microbench**. Capture cold/warm wall + query count
   diffs in the commit message.

4. **Add a regression test** where applicable
   (`tests/test_bookmark_*.py`).

## Verification

- `make test-python` clean across all five fixes.
- New microbench shows expected query-count drops.
- Reader page-flip flow on a populated install: open the reader,
  flip 50 pages, watch the bookmark thread log. Should see one
  bookmark write per `FLOOD_DELAY` window, never two.
- F5: hit the `CodexLatestVersionTask` path with PyPI mocked to
  block. Bookmark thread should keep flushing the cache without
  delay.

## Risks

- **F3 — UPSERT semantics across DB backends.** Codex ships with
  SQLite; it has supported `ON CONFLICT DO UPDATE` since 3.24
  (released 2018). Safe.
- **F3 — `Bookmark.unique_together = ("user", "session", "comic")`
  with nullable user/session.** UPSERT on a unique constraint
  containing nullable columns: SQLite treats NULLs as distinct
  (so two `(NULL, NULL, comic_pk)` rows could co-exist). The
  current code's `auth_filter` is always one-of `{user_id: X}`
  or `{session_id: Y}` — mutually exclusive, never both NULL.
  The unique constraint behaves correctly. Worth a regression
  test that two anonymous sessions for the same comic stay
  separate.
- **F5 — task ordering**. Moving network I/O to a side thread
  changes when `Timestamp.CODEX_VERSION` is updated relative to
  subsequent tasks. Today an immediate `CodexLatestVersionTask`
  blocks subsequent BookmarkUpdateTasks; with F5 they interleave.
  Side effect: a `JanitorCodexUpdateTask` enqueued from the
  fetch's `if update:` branch may fire concurrently with bookmark
  updates instead of after. Acceptable — those tasks run on
  separate threads anyway via `LIBRARIAN_QUEUE`.

## Out of scope

- **Bookmark response caching.** Distinct concern — affects the
  read path (`/api/v3/.../bookmark` GET), not the write thread.
- **Reader prefetch coordinating with bookmark-update tasks.**
  Frontend choice; backend just consumes events.
- **Rewriting the aggregator base class.**
  `AggregateMessageQueuedThread` is shared with other librarian
  threads; refactors there belong in their own project.

## References

- `codex/librarian/bookmark/` — the surface
- `codex/librarian/threads.py:110-160` —
  `AggregateMessageQueuedThread` base class
- PR #610 finding 10 — same `filter().update()` pattern as F6
- Django `bulk_create` source — `_check_bulk_create_options` for
  the `update_conflicts` semantics F3 leans on
