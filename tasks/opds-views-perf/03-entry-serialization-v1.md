# 03 — Entry serialization (v1 Atom)

Per-entry serialization on the v1 feed. Each book / group on the page
becomes one `OPDS1Entry` instance and the template renders its
properties. The hot loop sits in `_get_entries_section` (`v1/feed.py`)
and the per-entry properties (links, authors, contributors,
category_groups) live under `v1/entry/`.

## Files in scope

| File                                       | LOC | Purpose                                              |
| ------------------------------------------ | --- | ---------------------------------------------------- |
| `codex/views/opds/v1/entry/entry.py`       | 152 | Entry properties: title, issued, language, summary, authors, contributors, category_groups |
| `codex/views/opds/v1/entry/links.py`       | 181 | Entry links: cover, nav, download, stream, lazy_metadata |
| `codex/views/opds/metadata.py`             | 60  | Shared M2M query helpers                             |

## Per-entry cost shape

Each call to `OPDS1Entry(obj, query_params, data, ...)` produces an
object whose properties are evaluated lazily by the template engine.
For a typical page of 50 books with `metadata=False` (non-acquisition
nav feed):

- **Always**: `id_tag`, `title`, `issued`, `published`, `updated`,
  `language`, `summary`, `links`. These read attributes already on
  the queryset row (no DB cost) plus a handful of `reverse()` calls
  for href construction.
- **Books only (`obj.group == "c"`)**: `_links_comic` runs which
  invokes `_stream_link` → `lazy_metadata()`. See #2 below.
- **`metadata=True` (single-comic acquisition feed)**: `authors`,
  `contributors`, `category_groups` fire. Each spawns a separate M2M
  queryset that the template materializes by iterating it. See #1.

## Hotspots

### #1 — `category_groups` / `authors` / `contributors` fire 9 M2M querysets per acquisition entry

`v1/entry/entry.py:131-152`:

```python
@property
def authors(self) -> list:
    if not self.metadata:
        return []
    people = get_credit_people(self.obj.ids, AUTHOR_ROLES, exclude=False)
    return self._add_url_to_obj(people, "credits")

@property
def contributors(self) -> list:
    if not self.metadata:
        return []
    people = get_credit_people(self.obj.ids, AUTHOR_ROLES, exclude=True)
    return self._add_url_to_obj(people, "credits")

@property
def category_groups(self) -> dict:
    if not self.metadata:
        return {}
    return get_m2m_objects(self.obj.ids)
```

Each of these is gated on `self.metadata` (set per-feed-section, not
per-entry). For a non-acquisition feed (`metadata=False`) the gates
are tight — zero cost. For a single-comic acquisition feed
(`metadata=True`):

- `get_credit_people` (`metadata.py:26-35`) fires 1 query per call;
  called twice (authors + contributors) = 2 queries per entry.
- `get_m2m_objects` (`metadata.py:50-60`) loops `OPDS_M2M_MODELS`
  and builds a queryset per model. Each queryset is materialized
  when the template iterates it. **7 queries per entry** for the
  M2M fan-out (assuming `OPDS_M2M_MODELS` has 7 entries — confirm).

Total acquisition-feed cost: **9 queries per entry × N entries**.

For the common case (single-comic acquisition feed), that's 9
queries for 1 entry = trivial. For a multi-comic acquisition feed
(rare — only some clients request `?opdsMetadata=1` on book lists),
it's 9 × page_size = 450 queries on a 50-book page.

Mitigation:

- **Batch into single querysets per type.** Replace the per-entry
  call with a per-page call:
  - Authors: one `CreditPerson.objects.filter(credit__comic__in=all_pks).filter(...)` call, distinct, post-grouped by comic_pk.
  - Contributors: same shape with `exclude` flipped.
  - Category groups: one prefetch per M2M model on the books queryset,
    or a single UNION grouped by comic_pk + model_name.
- **Gate `metadata=True` on actual usage.** The OPDS spec says
  acquisition feeds should include detailed metadata, but in
  practice the metadata=True feed is usually consumed for single
  comics (the per-book acquisition page). If the multi-comic path
  is rarely hit, the per-page batch is a low-priority refactor.

**Severity:** medium. High if multi-comic acquisition feeds are
common; low otherwise. Needs traffic data to rank.

### #2 — `lazy_metadata()` opens Comicbox per book that's missing page_count or file_type

`v1/entry/links.py:120-128`:

```python
def lazy_metadata(self) -> bool:
    """Get barebones metadata lazily to make pse work for chunky-like readers."""
    if self.obj.page_count and self.obj.file_type:
        return False
    with Comicbox(self.obj.path, config=COMICBOX_CONFIG, logger=logger) as cb:
        self.obj.page_count = cb.get_page_count()
        self.obj.file_type = cb.get_file_type()
    logger.debug(f"Got lazy opds pse metadata for {self.obj.path}")
    return True
```

Called from `_stream_link` (line 140) **unconditionally per Comic
entry** in the books section. Short-circuits on the first line if
metadata is already present, but if a comic was imported without
full metadata, this opens the comic file (CBZ/CBR/PDF) on the
serializer hot path.

The `_get_entries_section` driver (`v1/feed.py:130-135`) catches the
return value and queues an async re-import:

```python
if key == "books" and entry.lazy_metadata():
    import_pks.add(obj.pk)
...
if import_pks:
    task = LazyImportComicsTask(group="c", pks=frozenset(import_pks))
    LIBRARIAN_QUEUE.put(task)
```

So a missing-metadata book triggers (a) one `Comicbox` open in the
request-thread, (b) one async librarian task to fully re-import.
The async re-import is correct; the synchronous open is the part
that could be deferred.

Mitigation options:

- **Stop opening Comicbox in the request thread.** Use
  `obj.page_count = 0` (sentinel) for the v1 PSE link and let the
  async re-import populate the real value next time. PSE clients
  already handle missing/zero page counts gracefully (the Atom feed
  doesn't promise an accurate page count for unimported books).
- **Skip the link entirely.** If `not (obj.page_count and obj.file_type)`,
  omit the stream link rather than fabricating one. The next refresh
  after async re-import will render correctly.

**Severity:** medium. Disk I/O on the request path is rare in steady
state but will dominate latency on a fresh import. Low priority once
a baseline confirms how often it actually fires in production.

### #3 — Multiple `reverse()` calls per entry property

Each `OPDS1Entry` exercises `reverse()` for cover, nav, download,
stream, and metadata-nav links:

- `_cover_href` — 1 call (`v1/entry/links.py:42` or `:56`)
- `_nav_href` — 1 call (`:88`)
- `_download_link` — 1 call (`:116`)
- `_stream_link` — 1 call (`:136`)
- `id_tag` (calls `_nav_href`) — 1 more call

For a books-only entry with metadata, that's ~5 `reverse()` calls per
entry. Django's `reverse()` is regex-resolved against the URL
patterns; not free. With 50 entries × 5 = 250 `reverse()` calls per
v1 feed page.

Mitigation: cache resolved URL templates per `url_name`. The OPDS
URL set is small and static; once resolved, the patterns are stable
for the process lifetime. A module-level dict `{"opds:bin:cover":
"/o/bin/c/{pk}/cover.webp"}` plus an f-string format would cut this
to a single dict lookup + format per call.

**Severity:** low. Each `reverse()` is fast; the pattern is just
visibility for "all those small calls add up." A measurement that
shows it as a cumulative >5 ms per request would justify scheduling.

### #4 — `_add_url_to_obj` mutates queryset row objects

`v1/entry/entry.py:118-129`:

```python
@staticmethod
def _add_url_to_obj(objs, filter_key) -> list:
    """Add filter urls to objects."""
    result = []
    for obj in objs:
        filters = json.dumps({filter_key: [obj.pk]})
        query = {"filters": filters}
        obj.url = reverse(
            "opds:v1:feed", kwargs=dict(TopRoutes.SERIES), query=query
        )
        result.append(obj)
    return result
```

Mutates the model instance to attach a `url` attribute. Works fine
for the template engine but means cached querysets carry attributes
they shouldn't (cachalot reuses model instances, in principle). The
materialized list avoids leaking back into the cache, but the
pattern is fragile — flagged for cleanup, not perf.

**Severity:** code health, not perf. Mention in cross-cutting
guidance.

### #5 — `_did_special_group_change` and other utility methods are loop-internals

`v1/facets.py:129-137` walks through facet entries. The OPDS facet
machinery has multiple small helper methods that each do a constant
amount of work but are called per-facet in nested loops. No real
hotspot, but the cumulative method-call overhead in CPython is
non-trivial — a single `_facet_or_facet_entry` flat helper would
collapse three or four method indirections.

**Severity:** trivial.

## Interactions with `BrowserView`

`OPDS1Entry` is a plain class, not a Django view — no inheritance
concerns. It reads attributes from rows produced by
`OPDSBrowserView`. The annotations the entry depends on
(`publisher_name`, `series_name`, `volume_name`, `language`,
`bookmark_updated_at`, `child_count`, `cover_pk`, `cover_custom_pk`,
`page`, `page_count`, `file_type`, `path`, `size`, `name`,
`updated_at`, `created_at`, `date`, `summary`) all flow from the
browser-views annotation pipeline.

If a future browser-views refactor gates an annotation by `TARGET`,
make sure `TARGET in {"opds1", "opds2"}` keeps the OPDS-required
fields. The browser plan's item #14 (target-aware annotations) was
implemented in Stage 5b — verify the OPDS targets still receive
everything listed above.

## Open questions

- **How big is `OPDS_M2M_MODELS`?** Quick read of
  `codex/views/opds/const.py` will confirm — assumed 7 above.
- **What fraction of OPDS clients actually hit acquisition feeds with
  `?opdsMetadata=1` on multi-book pages?** Determines whether #1 is
  worth scheduling.
- **Does the existing browser-views search-parse cache (Stage 1)
  cover the v1 feed?** v1 inherits from `OPDSBrowserView` which
  inherits from `BrowserView`, so yes — but verify the cache key
  composition still wins on OPDS-shaped requests (different
  user-agent, different default params).
