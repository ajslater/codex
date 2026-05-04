# 05 — Manifest (v2 single-publication metadata + reading_order)

The v2 Webpub / DiViNa manifest endpoint returns extended metadata
for a single publication: identifiers, story arcs, credits, M2M
subjects, and (for DiViNa) a per-page reading_order list. Unlike the
feed view, the manifest is single-comic per request — but each
request fans out into many M2M / FK queries.

## Files in scope

| File                                       | LOC | Purpose                                              |
| ------------------------------------------ | --- | ---------------------------------------------------- |
| `codex/views/opds/v2/manifest.py`          | 304 | `OPDS2ManifestMetadataView` + `OPDS2ManifestView`    |

## Per-request cost shape

`OPDS2ManifestView.get_object()` (lines 299-304):

```python
@override
def get_object(self) -> MappingProxyType:
    book_qs, _, zero_pad = self.get_book_qs()
    obj = book_qs.first()
    return MappingProxyType(self._publication(obj, zero_pad))
```

`book_qs.first()` is a single `LIMIT 1` query against the full
browser-views ACL/filter pipeline. Then `_publication(obj, zero_pad)`
materializes the manifest dict, which calls `_publication_metadata`
which calls into the per-publication helpers below.

Estimated per-manifest query count (from manifest.py only, on top of
whatever the browser pipeline produced):

| Helper                              | Queries (typical) | Notes                                       |
| ----------------------------------- | ----------------- | ------------------------------------------- |
| `_publication_identifier`           | 1                 | Single Identifier filter + materialize      |
| `_publication_belongs_to_series`    | 0                 | Reads `obj.series`/`obj.series_name` from queryset |
| `_publication_belongs_to_folder`    | 1 (AdminFlag)     | Plus `obj.parent_folder.path` access        |
| `_publication_belongs_to_story_arcs`| 1                 | StoryArcNumber filter; then per-row FK access to `story_arc` (potential N+1 — see #2) |
| `_publication_subject` (M2M)        | 7                 | `get_m2m_objects` loops `OPDS_M2M_MODELS`   |
| `_publication_credits` (Credit fan-out) | up to 11      | Loops `_MD_CREDIT_MAP` (11 keys), one Credit query per role |

Total per manifest: **~20 queries** beyond what `get_book_qs()`
already fired. The browser pipeline itself produces more queries on
top of that.

## Hotspots

### #1 — `_publication_credits` fires up to 11 queries per manifest

`v2/manifest.py:194-199`:

```python
def _publication_credits(self, obj) -> Mapping[str, tuple[Credit, ...]]:
    credit_md = {}
    for key, roles in _MD_CREDIT_MAP.items():
        if credit_objs := self._add_credits(obj.ids, roles):
            credit_md[key] = credit_objs
    return credit_md
```

`_MD_CREDIT_MAP` (lines 24-39) has 11 keys: `author`, `translator`,
`editor`, `artist`, `illustrator`, `letterer`, `penciller`,
`colorist`, `inker`, `contributor`, `narrator`. Each key triggers
`_add_credits(obj.ids, roles)` → `get_credits(...)` (`metadata.py:38-47`)
which is a `Credit.objects.filter(comic__in=obj.ids).filter(role__name__in=roles)`.

Then `_add_credits` (manifest.py:186-192):

```python
def _add_credits(self, pks, roles) -> QuerySet[Credit] | None:
    if credit_objs := get_credits(pks, roles, exclude=False):
        for credit_obj in credit_objs:
            self._add_tag_link(credit_obj, "credits", "person")
        return credit_objs
    return None
```

The `for credit_obj in credit_objs:` materializes the queryset (1
query), and `_add_tag_link` calls `self.link(...)` per credit (URL
build, no DB).

**Total for credits alone: 11 queries per manifest** even when most
roles are empty (the truthiness check `if credit_objs := ...` still
materializes the queryset to determine emptiness).

Mitigation:

- **Single batched query.** One `Credit.objects.filter(comic__in=obj.ids)`
  with `.values("role__name", "person__name", "pk", ...)` then
  partition by role-name in Python. Drops 11 queries to 1.
- **`_MD_CREDIT_MAP` covers nearly all credit roles.** Any role not
  listed gets dropped. A single fetch + partition handles this
  correctly without a per-role filter.

**Severity:** **high** for the manifest endpoint specifically.
Manifest is hit per-comic when a reader opens the publication, so
every reader-open pays this cost.

### #2 — `_publication_belongs_to_story_arcs` does a per-row FK access on `story_arc`

`v2/manifest.py:122-144`:

```python
def _publication_belongs_to_story_arcs(self, obj) -> list:
    story_arcs = []
    rel = GroupACLMixin.get_rel_prefix(StoryArcNumber)
    comic_filter = {rel + "in": [obj.pk]}
    story_arc_numbers = (
        StoryArcNumber.objects.filter(**comic_filter)
        .only("story_arc", "number")
        .order_by("story_arc__name")
    )
    for story_arc_number in story_arc_numbers:
        story_arc = story_arc_number.story_arc  # ← FK access, potential N+1
        name = story_arc.name or BLANK_TITLE
        ...
```

`.only("story_arc", "number")` restricts the columns fetched, which
**defers** the `story_arc` FK to a per-row lookup. Each iteration
fires a `StoryArc.objects.get(pk=...)` query. For a comic with N
story arcs, that's N+1 queries.

Mitigation: replace `.only(...)` with `select_related("story_arc")`
or `.values("story_arc__pk", "story_arc__name", "number")`. Either
collapses to a single query.

**Severity:** medium. Most comics have 0-2 story arcs, so the
absolute cost is bounded. But this is a textbook N+1 pattern that
should be fixed regardless.

### #3 — `_publication_subject` triggers 7 M2M queries via `get_m2m_objects`

`v2/manifest.py:176-184`:

```python
def _publication_subject(self, obj) -> tuple[NamedModel, ...]:
    m2m_objs = get_m2m_objects(obj.ids)
    flat_subjs = []
    for key, subjs in m2m_objs.items():
        filter_key = key + "s"
        for subj in subjs:
            self._add_tag_link(subj, filter_key)
            flat_subjs.append(subj)
    return tuple(flat_subjs)
```

`get_m2m_objects` (`metadata.py:50-60`) loops `OPDS_M2M_MODELS` (7
models) and builds a queryset per model. Each queryset materializes
when iterated in the `for subj in subjs:` loop above. **7 queries
per manifest.**

Mitigation:

- **One UNION query.** SELECT pk, name, 'character' AS type FROM
  codex_character WHERE pk IN (...) UNION ALL ... etc. Django's
  `QuerySet.union()` supports this. Single query, partition in
  Python by `type` column.
- **Prefetch on the source comic.** Add a `prefetch_related(
  "characters", "genres", "locations", ...)` on the manifest's book
  queryset. Drops to one query per relation (7 queries total) but
  with the prefetch correctly populating the comic's M2M caches —
  reusable elsewhere.

**Severity:** medium. Same shape as #1 (per-manifest fan-out) but
fewer queries.

### #4 — `_publication_reading_order` builds a list of `range(obj.page_count)` dicts

`v2/manifest.py:231-259`:

```python
def _publication_reading_order(self, obj) -> list:
    reading_order = []
    if not obj:
        return reading_order
    ts = floor(datetime.timestamp(obj.updated_at))
    query_params = {"ts": ts}
    for page_num in range(obj.page_count):
        kwargs = {"pk": obj.pk, "page": page_num}
        href_data = HrefData(
            kwargs, query_params, url_name="opds:bin:page",
            min_page=0, max_page=obj.page_count,
        )
        href = self.href(href_data)
        page = {
            "href": href,
            "type": MimeType.JPEG,
        }
        reading_order.append(page)
    return reading_order
```

Iterates `range(obj.page_count)` — typically 20-100 pages, but PDFs
can have 500+. Each iteration calls `self.href(...)` which calls
`reverse()` for `opds:bin:page`. **N reverse() calls per manifest.**

Mitigation:

- **Resolve the page URL once, format per page.** The URL pattern is
  static — only `pk` and `page` change. Build the format string
  once outside the loop, do `f.format(pk=pk, page=i)` inside.
  Eliminates `reverse()` overhead in the loop.
- **Lazy / paginated reading_order.** The OPDS spec doesn't strictly
  require all pages in the manifest. Some clients only read the
  first few; gating on user-agent or producing a paginated reading
  order would reduce the per-manifest payload.

**Severity:** medium for high-page-count comics. A 500-page PDF
manifest runs `reverse()` 500 times — measurable wall time.

### #5 — `_publication_identifier` fetches identifiers but uses `.annotate(F(...))` instead of `select_related`

`v2/manifest.py:58-71`:

```python
def _publication_identifier(self, obj) -> str:
    rel = GroupACLMixin.get_rel_prefix(Identifier)
    comic_filter = {rel + "in": [obj.pk]}
    identifiers = (
        Identifier.objects.filter(**comic_filter)
        .annotate(source_name=F("source__name"))
        .only("id_type", "key")
        .order_by("source_name", "key")
    )
    urns = []
    for identifier in identifiers:
        urn = f"{identifier.source_name}:{identifier.id_type}:{identifier.key}"
        urns.append(urn)
    return ",".join(urns)
```

The `.annotate(source_name=F("source__name"))` plus `.only("id_type",
"key")` is the right pattern (single query, no FK fan-out). **No
change needed** — flagged as the template for how the story_arcs
helper (#2) should be rewritten.

### #6 — Five duplicate `floor(datetime.timestamp(obj.updated_at))` expressions

`v2/manifest.py:101, 117, 137, 240, 265` all compute the same
expression. Combined with the same expression in `publications.py:145`,
the timestamp helper proposed in sub-plan 04 (#4) absorbs all six
sites.

**Severity:** code health.

### #7 — `_publication_belongs_to_folder` calls the static `is_allowed`

`v2/manifest.py:110`:

```python
def _publication_belongs_to_folder(self, obj) -> list:
    if not self.is_allowed(obj):
        return []
    folder = obj.parent_folder
    name = folder.path
    ...
```

`self.is_allowed(...)` is the static method from
`v2/feed/publications.py:35-56` that fires `AdminFlag.objects.get`.
See sub-plan 04 #2 — same fix applies here.

### #8 — `_publication_belongs_to_folder` reads `obj.parent_folder` (FK)

The browser-views annotation pipeline doesn't generally `select_related`
`parent_folder` on Comic since it's not on the canonical browser
path. Verify whether this FK is fetched as part of `get_book_qs()`
or whether reading `obj.parent_folder` triggers a per-manifest FK
query. If the latter, add `.select_related("parent_folder")` to
the manifest book queryset.

**Severity:** unknown — needs verification.

## Interactions with `BrowserView`

- `OPDS2ManifestView.get_object()` calls `self.get_book_qs()` from
  `BrowserView` to produce the comic queryset, then `.first()` to
  pull the single comic.
- The browser-views ACL filter applies — manifest correctly
  refuses to leak comics outside the user's visible libraries.
- The manifest *does* run the full annotation pipeline even though
  it only returns 1 comic. That's because `get_book_qs` is the same
  method as the feed views. A manifest-specific `get_book_qs` (with
  fewer annotations) would let the manifest skip Card/Order/Bookmark
  annotations it doesn't actually need — but verify what fields the
  manifest reads first; many of them are annotated values.

## Open questions

- **What's `OPDS_M2M_MODELS` actually used for in clients?** If most
  clients ignore M2M subjects in the manifest, the entire
  `_publication_subject` cost (#3) could be gated off by user-agent.
- **Is the credit role list (11 entries in `_MD_CREDIT_MAP`)
  comprehensive?** The comment in source says "make this
  comprehensive by using comicbox role enums" — meaning some roles
  are silently dropped today. Either fix the comment or fix the map.
  Not a perf concern, but worth flagging.
- **What fraction of manifest hits are for high-page-count comics?**
  Determines whether #4 (reading_order URL fan-out) is worth
  scheduling. PDFs can have 1000+ pages; a 1000-page manifest is
  the absolute worst case.
