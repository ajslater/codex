# 03 — OPDS serializers (v1 + v2)

OPDS endpoints feed external clients (KyBook, Chunky, Panels,
Aldiko, etc.). They poll feed URLs; one client opening a folder
triggers a feed fetch. Per-feed-entry cost dominates wall time.

## Surface

- `codex/serializers/opds/v1.py` — `OPDS1*Serializer` family (73
  LOC). `OPDS1FeedView` renders via Django template
  (`templates/opds/v1/index.xml`); these serializers structure the
  template context.
- `codex/serializers/opds/v2/`:
  - `feed.py` — `OPDS2FeedSerializer`
  - `publication.py` — `OPDS2PublicationSerializer` (159 LOC, hot)
  - `links.py` — `OPDS2LinkSerializer` + `OPDS2LinkListField`
  - `metadata.py` — base metadata wrapper
  - `facet.py` — facet entries
  - `progression.py` — bookmark position
  - `unused.py` — explicitly unused (101 LOC, dead)
- `codex/serializers/opds/authentication.py`,
  `codex/serializers/opds/urls.py` — wiring helpers; lightweight.

## Hot endpoints

1. `/opds/v1.2/<group>/<pks>` — XML feed, 50–100 entries.
2. `/opds/v2.0/<group>/<pks>` — JSON feed, 50–100 publications.

Both render through the per-entry serializer N times per feed.

## Findings

### F1 — OPDS v1 default-mode batching gap

`codex/views/opds/v1/feed.py:123-143`. The view batches `credits`
and `m2m subjects` per-comic **only when `?opdsMetadata=1` is set**
on the request. Default v1 fetches don't request metadata; the
template-level fallbacks (`get_credit_people`,
`get_m2m_objects`) fire per-entry, multiplying queries by N.

**Status:** the per-entry properties on `OPDS1Entry` already short-
circuit on `self._authors_by_pk is not None` — the batched path is
correct. The gap is whether default-mode fetches actually trigger
the per-entry properties at all (they may not — the v1 XML
template likely guards on whether the data is present in the
context).

**Audit step:** silk-trace
`tests/perf/run_opds_baseline.py::flow_v1_default` (no
`opdsMetadata=1`). If the queries match the expected baseline (no
per-entry credit/subject queries), this is **verified clean**. If
queries multiply by N, either:

- Wire the v1 view to always batch (cheap upgrade — already
  written, just remove the `if metadata:` guard around lines
  131–139 and remove the per-entry fallback).
- Or document that callers must pass `opdsMetadata=1` for batched
  responses.

Likely outcome: verified-clean. The XML template emits per-entry
data only when the relevant tags are populated, and the populating
code paths are gated by the metadata flag.

### F2 — OPDS v2: wire batching helpers + populate contributor fields

`codex/views/opds/v2/feed/publications.py:114-151`. The v2
publication metadata is currently thin — only `title`, `subtitle`,
`published`, `modified`, `number_of_pages`. No contributor or
subject data is populated, even though
`OPDS2PublicationMetadataSerializer:89-99` declares 10 contributor
fields (author, translator, editor, artist, illustrator, letterer,
penciller, colorist, inker, narrator) plus subject groups.

**Per user direction:** preemptively wire the v2 batching helpers
parallel to v1 and populate the declared contributor fields. The
batching collapses what would be N×K credit/subject queries
(for K roles × N publications) into a fixed handful of UNION
queries per feed.

**Reference — the v1 pattern**
(`codex/views/opds/v1/feed.py:117-147`):

```python
def _get_entries_section(self, key, metadata) -> list:
    entries = []
    if objs := self.obj.get(key):
        ...
        authors_by_pk = contributors_by_pk = category_groups_by_pk = None
        if metadata and key == "books":
            all_pks = [obj.pk for obj in objs]
            authors_by_pk = get_credit_people_by_comic(
                all_pks, AUTHOR_ROLES, exclude=False
            )
            contributors_by_pk = get_credit_people_by_comic(
                all_pks, AUTHOR_ROLES, exclude=True
            )
            category_groups_by_pk = get_m2m_objects_by_comic(all_pks)
        data = OPDS1EntryData(
            ...,
            authors_by_pk=authors_by_pk,
            contributors_by_pk=contributors_by_pk,
            category_groups_by_pk=category_groups_by_pk,
        )
        for obj in objs:
            entry = OPDS1Entry(obj, ..., data)
            entries.append(entry)
    return entries
```

**Implementation steps for v2**

The v2 view is in
`codex/views/opds/v2/feed/publications.py`. The hot loop is
`OPDS2PublicationsView.get_publications` calling `_publication`
per `obj` in `book_qs`.

1. **Reuse the v1 helpers verbatim** — `get_credit_people_by_comic`
   and `get_m2m_objects_by_comic` are not v1-specific; they're
   M2M union utilities that take comic pks and return
   `dict[pk, list[obj]]`. Same import location:
   `codex.views.opds.v1.batch` (or wherever the helpers live —
   confirm during implementation by reading the v1 import path).

2. **Map the 10 contributor roles to v1's `AUTHOR_ROLES` set.**
   The v1 batching splits credits into "authors" (matching
   `AUTHOR_ROLES`) and "contributors" (everything else). v2's
   declared fields are more granular (author / translator /
   editor / artist / …). The cleanest split:

   - Run `get_credit_people_by_comic(all_pks, role_set, exclude=False)`
     once per role-bucket (e.g. one call for AUTHOR_ROLES, one
     for translator-roles, etc.), **or**
   - Run a single broad call that returns all credits, then
     partition in Python by role name. Single query is preferable
     even though the post-processing is Python-side.

   Recommended: a new helper `get_credits_by_comic(all_pks)` that
   returns `dict[pk, list[Credit]]` with role + person preloaded;
   v2 partitions by role name into the 10 declared fields.

3. **Thread the batched dicts through `_publication_metadata`**:

   ```python
   def get_publications(self, book_qs, ...):
       all_pks = [obj.pk for obj in book_qs]
       credits_by_pk = get_credits_by_comic(all_pks)
       subjects_by_pk = get_m2m_objects_by_comic(all_pks)
       publications = []
       for obj in book_qs:
           pub = self._publication(
               obj,
               zero_pad,
               credits=credits_by_pk.get(obj.pk, ()),
               subjects=subjects_by_pk.get(obj.pk, ()),
           )
           publications.append(pub)
       return publications

   def _publication(self, obj, zero_pad, *, credits=(), subjects=()):
       pub = super()._publication(obj, zero_pad)
       pub["metadata"] = self._publication_metadata(
           obj, zero_pad, credits=credits, subjects=subjects,
       )
       return pub
   ```

4. **Populate the 10 contributor fields** by partitioning
   `credits` per role inside `_publication_metadata`. Use the
   `OPDS2ContributorSerializer` shape already declared:

   ```python
   def _publication_metadata(self, obj, zero_pad, *, credits=(), subjects=()):
       md = {...existing fields...}
       md.update(self._partition_credits(credits))
       if subjects:
           md["subject"] = [s.name for s in subjects]
       return md

   @staticmethod
   def _partition_credits(credits) -> dict:
       buckets = defaultdict(list)
       for credit in credits:
           role_key = credit.role.name.lower()  # or a role-name → field-key map
           buckets[role_key].append({"name": credit.person.name})
       return dict(buckets)
   ```

   The role-name → field-key map should be a module-level
   `MappingProxyType` so the partitioning is O(N) lookup-only.

5. **Add a unit test** that captures query count for a v2 feed
   request:

   ```python
   def test_opds_v2_feed_query_count(client, ten_books_with_credits):
       with CaptureQueriesContext(connection) as ctx:
           client.get("/opds/v2.0/p/0/0/0")
       # Per-request setup + 1 publications page query + 1 credits
       # union + 1 subjects union + N cover pks (fixed). Pin a
       # ceiling that catches N+1 regressions.
       assert len(ctx.captured_queries) <= 12
   ```

**OpenAPI schema impact:** the contributor fields were already
declared, so drf-spectacular's schema doesn't change shape — only
the response body becomes non-empty. Existing v2 clients see the
new keys; clients that ignored unknown keys are unaffected.

**Risk:** OPDS v2 client interop. Some clients may emit warnings
on previously-empty fields suddenly populating with arrays.
Mitigation: roll out behind the existing OPDS-client testing
gate from PR #606 (cover cleanup) once the v2 implementation
ships.

### F3 — `OPDS2LinkSerializer.get_rel` SMF in tight loop

`codex/serializers/opds/v2/links.py:19-28`.

```python
class OPDS2LinkBaseSerializer(Serializer):
    rel = SerializerMethodField()
    ...

    def get_rel(self, obj) -> str | list[str]:
        rel: str | list[str] = obj.get("rel", "")
        if rel and not isinstance(rel, list | str):
            reason = "OPDS2LinkSerializer.rel is not a list or a string."
            raise TypeError(reason)
        return rel
```

Every link in every publication runs this. Per feed: ~5 links per
publication × 100 publications = 500 SMF invocations.

The SMF only does a `.get()` + `isinstance` guard. The dict already
has `"rel"`; the upstream view sets it as a string or list. No
type coercion is needed at serialize-time.

**Fix:**

```python
class OPDS2LinkBaseSerializer(Serializer):
    rel = CharField(allow_blank=True, required=False)
    # ...drop get_rel
```

DRF's `CharField` will accept either a string or a list (a list
gets `str()`-coerced — **bug risk**). Better:

```python
class OPDS2LinkBaseSerializer(Serializer):
    # rel is set upstream by LinkData.to_dict() — accept either
    # the string or list shape and pass through.
    rel = JSONField(required=False)
```

`JSONField` passes through Python primitives without modification.
The defensive `isinstance` guard moves into the upstream
`LinkData.to_dict()` (one place, not per-link).

**Expected impact:** ~500 fewer SMF dispatches per OPDS v2 feed.
Wall-clock saving is measurable but small (low microseconds per
SMF).

### F4 — `OPDS2PublicationSerializer` inheritance chain

`codex/serializers/opds/v2/publication.py:111-124`.
`OPDS2PublicationSerializer` extends `OPDS2FacetSerializer` —
strange, since publications and facets aren't conceptually the
same. Likely a typo or copy/paste — both have a `metadata` field
but otherwise unrelated.

**Audit step:** is the inheritance there for the `metadata` field
or for something else? If only for `metadata`, factor a small
`MetadataMixin` and have both extend that. Cosmetic; not perf.

### F5 — `opds/v2/unused.py` is dead code → docstring scaffolds

`codex/serializers/opds/v2/unused.py` — 101 lines of serializers
that are explicitly named "unused". Imports / references zero.

**Per user direction:** preserve the scaffolds as documentation
rather than deleting them, but in a form that doesn't ship code
to the import system. Convert the file into a single module-level
docstring whose body is a `::` code block holding the (now
non-executable) class definitions.

**Concrete shape**

```python
# codex/serializers/opds/v2/unused.py
"""Reference scaffolds for future OPDS v2 endpoints.

These serializer shapes are NOT registered or imported anywhere;
they exist as starting points for endpoints like the navigation
feed, group feed, and library feed, which the OPDS v2 spec
allows but Codex does not yet expose. When wiring one of these
endpoints, copy the relevant class out of the example block,
move it into the appropriate module
(``feed.py`` / ``publication.py`` / etc.), and import it from
the view.

Example::

    from rest_framework.serializers import (
        BooleanField,
        CharField,
        ListField,
        Serializer,
    )

    from codex.serializers.opds.v2.links import OPDS2LinkSerializer
    from codex.serializers.opds.v2.metadata import OPDS2MetadataSerializer


    class OPDS2NavigationSerializer(Serializer):
        '''Navigation feed entry — example scaffold.'''

        title = CharField(...)
        # ... rest of the class body goes here ...


    class OPDS2GroupSerializer(Serializer):
        '''Group feed wrapper — example scaffold.'''

        # ... etc ...
"""
```

The actual existing class bodies move *inside* the
`Example::` block as indented prose-mode Python. Ruff / pyright
skip module docstrings, so no lint error. Imports referenced in
the docstring are listed near the top of the example so a future
contributor can copy a self-contained block.

**Caveat:** any third-party tool that imports `unused.py` and
introspects its module dict (Sphinx autodoc, etc.) will get an
empty namespace. None do today; verify with
`grep -rn 'opds.v2.unused' .` before merging.

### F6 — OPDS1 / v2 duplicated link logic

OPDS1 builds links via Django template helpers; v2 builds via
`LinkData.to_dict()` + `OPDS2LinkSerializer`. The shapes are
similar but the code paths are independent. Cross-cutting refactor
candidate, but **out of scope for a perf project** — flag and
defer.

## Suggested commit shape

One PR, three commits:

1. **F2 v2 batching + contributor field population.** Adds
   `get_credits_by_comic` (or reuses v1's
   `get_credit_people_by_comic` per role bucket) plus
   `get_m2m_objects_by_comic` to the v2 publications view, threads
   the batched dicts through `_publication_metadata`, populates
   the 10 declared contributor fields and the subject array.
   Lock in the query-count ceiling with a regression test.
2. **F3 `get_rel` SMF removal.** Replace with `JSONField`. Move the
   isinstance guard into `LinkData.to_dict()`. Add a test that a
   list-typed rel passes through unchanged.
3. **F5 unused.py → docstring scaffolds.** Convert the file to a
   module-level docstring containing the example class bodies in
   a `::` code block. No imports break (file path remains).

F1 verified-clean lands as a documentation update in this plan
file (not a code commit).

## Verification

- `tests/perf/run_opds_baseline.py::flow_v1_default` and
  `::flow_v1_metadata` — query counts before/after F1 audit
  (F1 likely no-op).
- `::flow_v2_default` — query count regression test from F2:
  pin a ceiling that catches N+1 (e.g. ≤ 12 queries for a 10-book
  page with full credits/subjects). Cold + warm wall time before
  and after.
- New unit test: `LinkData.to_dict()` produces a dict with `rel`
  as either str or list, never something else (F3).
- OPDS2 feed sample request: F2 changes the response body shape
  (previously-empty contributor fields now contain arrays). F3
  changes wire bytes only if a list-rel was previously coerced
  to a string by the SMF — confirm with a snapshot test.
- Confirm `unused.py` still imports as a no-op after F5 (parses
  but exports nothing).

## Notes for OPDS-client testing

OPDS feeds are read by external clients with various tolerance for
schema drift. F2 populates fields that were previously
declared-but-empty — clients that ignored them are unaffected;
clients that coded against an empty array may see real data for
the first time. Verify with a real client (e.g. KyBook, Chunky)
before merging, alongside the cover-cleanup OPDS testing gate
from PR #606.
