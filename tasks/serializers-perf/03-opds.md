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

### F2 — OPDS v2 has no batching helpers

`codex/views/opds/v2/feed/publications.py:114-151`. The v2
publication metadata is currently thin — only `title`, `subtitle`,
`published`, `modified`, `number_of_pages`. No contributor or
subject data is populated.

**Status:** **No N+1 risk in the current code path** because the
contributor fields are declared in the serializer
(`OPDS2PublicationMetadataSerializer:89-99`) but never set by the
view. They're aspirational.

**Footgun:** any future contributor for v2 metadata that adds
`author`, `translator`, etc. fields will trigger an N+1 unless
they pre-batch via the v1-style helpers
(`get_credit_people_by_comic`, `get_m2m_objects_by_comic`).

**Two ways to address:**

**Option A — Delete unused contributor fields from the serializer.**
Smallest diff. Re-add when the view actually populates them.

```python
# OPDS2PublicationMetadataSerializer — drop these:
author = OPDS2ContributorSerializer(many=True, required=False)
translator = OPDS2ContributorSerializer(many=True, required=False)
editor = OPDS2ContributorSerializer(many=True, required=False)
artist = OPDS2ContributorSerializer(many=True, required=False)
illustrator = OPDS2ContributorSerializer(many=True, required=False)
letterer = OPDS2ContributorSerializer(many=True, required=False)
penciller = OPDS2ContributorSerializer(many=True, required=False)
colorist = OPDS2ContributorSerializer(many=True, required=False)
inker = OPDS2ContributorSerializer(many=True, required=False)
narrator = OPDS2ContributorSerializer(many=True, required=False)
```

**Option B — Pre-emptively wire the v2 batching helpers.**
Larger diff. Replicates the v1 batching pattern in the v2
publications view so populating contributor fields is cheap when
that day comes.

**Recommendation:** Option A. The drf-spectacular OpenAPI schema
will lose those fields, but no client reads them today.

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

### F5 — `opds/v2/unused.py` is dead code

`codex/serializers/opds/v2/unused.py` — 101 lines of serializers
that are explicitly named "unused". Imports / references zero.

**Fix:** delete or move into a docstring example block. If the
intent is to leave them as a starting point for future work, file
under `tasks/serializers-perf/opds-v2-unused-stash.py.bak`.

### F6 — OPDS1 / v2 duplicated link logic

OPDS1 builds links via Django template helpers; v2 builds via
`LinkData.to_dict()` + `OPDS2LinkSerializer`. The shapes are
similar but the code paths are independent. Cross-cutting refactor
candidate, but **out of scope for a perf project** — flag and
defer.

## Suggested commit shape

One PR, three commits:

1. **F2 unused-field cleanup.** Drop the 10 contributor fields from
   `OPDS2PublicationMetadataSerializer`. Update OpenAPI schema
   tests if any pin them.
2. **F3 `get_rel` SMF removal.** Replace with `JSONField`. Move the
   isinstance guard into `LinkData.to_dict()`. Add a test that a
   list-typed rel passes through unchanged.
3. **F5 unused.py deletion.** Single-file removal, no import sites.

F1 verified-clean lands as a documentation update in this plan
file (not a code commit).

## Verification

- `tests/perf/run_opds_baseline.py::flow_v1_default` and
  `::flow_v1_metadata` — query counts before/after F1 audit
  (F1 likely no-op).
- `::flow_v2_default` — query counts before/after F2/F3.
- New unit test: `LinkData.to_dict()` produces a dict with `rel`
  as either str or list, never something else.
- OPDS2 feed sample request returns identical bytes before/after
  (bit-for-bit match), confirming F3 didn't change wire shape.

## Notes for OPDS-client testing

OPDS feeds are read by external clients with various tolerance for
schema drift. F2's deletion of contributor fields removes
declared-but-empty fields from the JSON output (they would have
been `null` or absent). Likely no client cares; verify with a real
client (e.g. KyBook, Chunky) before merging.
