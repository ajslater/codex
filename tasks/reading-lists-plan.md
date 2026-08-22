# Reading Lists for Codex + comicbox (issue #309)

Status: PLAN — for revision and implementation later.

## Context

[Issue #309](https://github.com/ajslater/codex/issues/309) asks for Reading Lists:
create them in codex and import ComicRack `.cbl` files with file matching. The
plan extends that with downloading lists from the internet
(comicbookreadingorders.com /
[DieselTech/CBL-ReadingLists](https://github.com/DieselTech/CBL-ReadingLists) /
[json-cbl-standard](https://github.com/ComicReadingLists/json-cbl-standard)),
viewing lists in codex, ordering and filtering comics by list, plus a universal
parse/transform layer with CLI viewing and a codex-facing API — in comicbox.

**Decisions (fixed):**

1. Universal layer = new **comicbox subpackage** (`comicbox.readinglists`),
   shipped as comicbox 4.9.0; codex bumps its pin.
2. Codex lists are **per-user from day one** (`user` FK, NULL = global/promoted).
3. **Both** in v1: new `ReadingList`/`ReadingListEntry` models (source of truth)
   **and** an optional "write to file tags as Story Arc" action reusing existing
   tagwrite machinery.
4. Downloads v1: in-app **DieselTech GitHub catalog** + import-from-URL + file
   upload. **No CBRO scraping** (site has no API; orders are prose WordPress
   `<p>` text; DieselTech "(WEB-CBRO)" lists mirror it with ComicVine-verified
   IDs — 1,704 CBLs / 336k entries).

## Key research facts (verified)

- **CBL XML**: `<ReadingList><Name/><NumIssues/><Books><Book Series Number
  Volume Year [Format]><Database Name="cv|metron" Series Issue/>…`. `Volume` =
  series start year. Native ComicRack exports add `Id`/`FileName` (ignore);
  smart lists have `<Matchers>` → reject (static lists only, like Kavita).
- **json-cbl 1.0**: `fileDetails{version,UUID}`, `listDetails{name,description,
  publisher,imprint,startYear,endYear,type,tags,coverImageURLs,
  relationships(prev/next by UUID),source}`, `notes`,
  `issueList[{seriesName,seriesStartYear,issueNumber,issueCoverDate,issueType,
  id[{comicvine|metron|grandComicsDatabase,series,issue}]}]`.
- **codex**: `StoryArc`/`StoryArcNumber` are import-owned (M2M-link prune on
  re-import, nightly `cleanup_fks` orphan deletion) → imported lists must NOT be
  DB-grafted arcs. The arc browse machinery (`Collection.ARC`,
  `_alias_story_arc_number` FilteredRelation ordering, reader arcs, OPDS arc
  defaults) is the template to clone. Precedents: `Favorite` (per-user,
  `IsAuthenticated`), `AdminCustomCoverUploadView` (MultiPartParser upload),
  onlinetag sessions (`codex/librarian/onlinetag/`),
  `BulkTagWriteTask.per_comic_patches` (verified,
  `codex/librarian/scribe/tasks.py:45`), user_data sidecar (`codex/user_data/`).
  Hard rule: every new `ScribeTask` registers in `_SCRIBE_TASK_PRIORITY`;
  janitor jobs also in `_JANITOR_METHOD_MAP` + `_NIGHTLY_TASKS`.
- **comicbox 4.8.2**: everything is per-single-archive → lists are a standalone
  subpackage (precedent: `process.py`, `write.py`, `online_session.py`). Config
  key `"cbl"` is TAKEN by ComicBookLover — reading-list format names get their
  own namespace. Available infra: xmltodict + xmlschema, marshmallow 4,
  `IdSources`/identifier machinery (incl. `arc` type), httpx, rapidfuzz, rich.
  Codex declares neither rapidfuzz nor xmltodict → fuzzy/XML helpers must be
  exported from comicbox.

---

## Part A — comicbox 4.9.0: `comicbox.readinglists`

New subpackage (all new files):

```text
comicbox/readinglists/
  __init__.py    # public API re-exports
  model.py       # frozen slotted dataclasses (OnlineSession house style):
                 #   ReadingList{name, entries, uuid, description, publisher, imprint,
                 #     start_year, end_year, list_type, tags, cover_image_urls,
                 #     relationships, sources, notes}
                 #   ReadingListEntry{series, issue(raw str), volume(=start year), year,
                 #     cover_date, format, ids: tuple[EntryId]}
                 #   EntryId{source (IdSources value), series_key, issue_key}
  normalize.py   # normalize_series_name(), parse_issue() — public wrapper around the
                 #   box/computed/issue.py issue-number/suffix split rule (parity with
                 #   codex Comic.issue_number/issue_suffix) — series_similarity() (rapidfuzz)
  formats/       # ReadingListFormats enum + detect_format(name, data); per-format
    cbl.py       #   read AND write: CBL via xmltodict ("cv"/"metron" → IdSources names;
    jsoncbl.py   #   <Matchers> → SmartListUnsupportedError), json-cbl validated against
    csv.py       #   vendored schema (comicbox/schemas/reading-list/v1.0/), CSV (stdlib)
  sources.py     # fetch_url() (httpx, size-capped); DieselTechCatalog: one recursive
                 #   git-tree API call → cached JSON (ETag, 24h TTL); per-list downloads
                 #   via raw.githubusercontent.com (avoids the 60/hr API limit);
                 #   search via rapidfuzz over cached names
  match.py       # standalone CLI matcher: list vs a directory of archives
                 #   (iter_process_files metadata), have/missing report
  session.py     # ReadingListSession — codex-facing sync façade (no event stream;
                 #   ops are single parse/fetch): load/loads/dumps, catalog_entries/
                 #   catalog_search/fetch_catalog_list, fetch_url
  runner.py      # CLI action dispatch
```

Existing files to modify: `comicbox/cli/parser.py` (new "Reading Lists"
argparse group: `--rl-print` (rich table), `--rl-validate`,
`--rl-convert {cbl,json,csv}`, `--rl-download URL`, `--rl-catalog-search` /
`--rl-catalog-download`, `--rl-match DIR`), `comicbox/cli/__init__.py` +
`comicbox/config/` (new `readinglists` config node), `comicbox/run.py` (Runner
branches to `readinglists.runner` for list actions — positionals are list
files, not archives), `pyproject.toml` → 4.9.0, `NEWS.md`.

Conversion loss rule: CBL→json-cbl lacks required `issueCoverDate` — synthesize
`{year}-01-01` when year known, else omit + warn. Exceptions subclass
`ComicboxError`.

Tests (`tests/readinglists/`): per-format round-trips, detection matrix,
smart-list rejection, schema validation, catalog via `httpx.MockTransport`, CLI
smoke, matcher against tiny generated cbz fixtures.

## Part B — codex (5 releasable phases)

### Phase 1 — core: models + import + matching + browse

**Models** — new `codex/models/readinglist.py` (export in
`models/__init__.py`; migration `codex/migrations/0053_reading_lists.py`
modeled on `0049_reprints.py`, no FTS rebuild):

- `ReadingList(BrowserCollectionModel)` — inherits name/sort_name/custom_cover.
  Fields: `user` FK (null = global), `uuid`, `description`, `notes`,
  `publisher_name`/`imprint_name` (raw strings, NOT FKs to import-owned rows),
  `start_year`/`end_year`, `list_type`,
  `tags`/`cover_image_urls`/`relationships`/`source_urls` (JSONFields).
  Constraints: unique `(user, name)` + partial unique `name` where
  `user IS NULL`.
- `ReadingListEntry(BaseModel)` — `reading_list` FK (CASCADE,
  related_name="entries"), `position` (dense 0-based int, indexed, **no unique
  constraint** — SQLite can't defer uniques across a bulk reorder; browse
  orders by `(position, pk)`), `comic` FK (**SET_NULL** — entries outlive file
  deletions), raw match keys (`series`, `issue` raw string, `volume`, `year`,
  `cover_date`, `format`), `ids` JSONField
  (`[{source, series_key, issue_key}]` — NOT `Identifier` rows: those are
  import-owned and janitor-GC'd), `match_status`
  (`UNMATCHED|MATCHED|AMBIGUOUS|MANUAL`; MANUAL is never auto-rematched).
- Keep `ReadingList` **out of** janitor `_FK_MODELS` (empty user lists must
  survive).

**Librarian** — new `codex/librarian/scribe/readinglists/` (`tasks.py`,
`importer.py`, `match.py`, `status.py`):

- `ReadingListImportTask(ScribeTask)`
  `{user_id, source: path|url|catalog_path, fmt_hint}` — parse via
  `ReadingListSession`, upsert list (same-owner UUID → update; name collision →
  " (2)"), bulk-create entries, run matcher.
- `ReadingListMatchTask(ScribeTask)` + nightly
  `JanitorRematchReadingListsTask` (resets null-comic rows, rematches
  UNMATCHED+AMBIGUOUS).
- Register all in `_SCRIBE_TASK_PRIORITY`
  (`codex/librarian/scribe/priority.py`); janitor task in
  `_JANITOR_METHOD_MAP` + `_NIGHTLY_TASKS` (`janitor/janitor.py`). Statuses
  `RLI`/`RLM` in `codex/choices/statii.py`; "Rematch Reading Lists" in
  `ADMIN_JOBS` (`codex/choices/jobs.py`) + `_TASK_MAP`
  (`codex/views/admin/tasks.py`). `READING_LISTS_CHANGED` notification
  (`codex/choices/notifications.py`) → `user_<uid>` for private, `ALL` for
  global. `make build-choices`.

**Matching engine** (`readinglists/match.py`, batched queries then per-entry
resolution; ACL-unfiltered — visibility enforced at browse): tier 1 issue IDs
via `Identifier(source, id_type="comic", key)` in `IdSources` priority order;
tier 2 series ID + parsed `(issue_number, issue_suffix)` (use
`comicbox.readinglists.normalize.parse_issue` for parity); tier 3 exact
`Series.sort_name` nocase + `Volume.name == entry.volume` + exact issue; tier 4
normalized name (`normalize_series_name`, fallback `series_similarity ≥ 0.95`)
+ numeric issue. Multi-candidate: deterministic score
`(volume match, |year Δ|, suffix match, min pk)` → best pick with `AMBIGUOUS`.
No candidate → `UNMATCHED`.

**Browse collection** — token `reading-lists` / singular `reading-list` / label
"Reading Lists", cloned from `ARC` at every site:

- `codex/collection.py` (`Collection.READING_LIST`), `codex/views/const.py`
  maps (`COLLECTION_MODEL_MAP`,
  `COLLECTION_RELATION → "reading_list_entries__reading_list"`, etc.),
  `codex/urls/converters.py` regex, frontend `frontend/src/plugins/router.js`
  regex, `stores/browser.js`
  `NON_BROWSE_COLLECTIONS`/`ALWAYS_ENABLED_TOP_COLLECTIONS`,
  `codex/choices/browser.py` (`BROWSER_TOP_COLLECTION_CHOICES`, order key
  `reading_list_position` in
  `BROWSER_ORDER_BY_CHOICES`/`BROWSER_COVER_ORDER_BY_KEYS`/
  `BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS`), breadcrumbs beside arcs.
- Listing shows own + global lists
  (`Q(user=request.user) | Q(user__isnull=True)`; anonymous = global only);
  with pks → comics, ownership-guarded (`codex/views/browser/browser.py`).
- Ordering: `_alias_reading_list_position` in
  `codex/views/browser/annotate/order.py` cloning `_alias_story_arc_number`
  (FilteredRelation on `reading_list_entries`, `Min/Max("…__position")`);
  default order for the collection in `codex/views/browser/settings.py` +
  `codex/views/settings.py`; copy the arc `force_inner_joins` demotion in
  `filters/filter.py` (documented 150s→36ms precedent) + `.distinct()`.
- Metadata panel: description/notes/type + counts
  `{total, matched, unmatched, needs_review}` computed on the
  viewer-ACL-filtered comic queryset. Favorites:
  `FAVORITE_MODEL_COLLECTIONS[ReadingList] = Collection.READING_LIST`.
- **Deliberately skipped in v1**: FTS + comic-filter dimension (per-user names
  would leak into the shared index/filter cache; list search is `icontains` on
  the listing), `coverImageURLs` remote fetch (cover falls out of first-entry
  ordering; `custom_cover` FK exists for later).

**API** — `/api/v4/reading-lists/` (new `codex/urls/api/v4/readinglists.py`,
`codex/views/readinglists/`; auth like `Favorite` — `IsAuthenticated` for
writes, anonymous reads global lists only):

- CRUD on own lists; global lists writable by admin; `PATCH <pk>/promote`
  (admin).
- `POST <pk>/entries` (`{comic: pk}` or raw keys),
  `DELETE <pk>/entries/<entry_pk>`, `PATCH <pk>/reorder` `{entry_pks: [...]}`
  (transactional full rewrite).
- Match review: `GET <pk>/entries/<entry_pk>/candidates`, `PATCH …/match`
  `{comic: pk|null}` → MANUAL/UNMATCHED, `POST <pk>/rematch`.
- Import: `POST /import` (MultiPartParser upload cloning
  `AdminCustomCoverUploadView` — suffix + size validation, store under new
  `READING_LIST_UPLOADS_DIR`, enqueue task, 202), `POST /import-url`.
- Export: `GET <pk>/export?format=cbl|json|csv` (sync FileResponse via the
  comicbox façade; matched entries refresh keys from live comic metadata).

**user_data sidecar + telemetry**: new `reading_lists` /
`reading_list_entries` tables in `codex/user_data/schema.sql` (list key =
`(username|NULL, name)`; matched comic stored as rebuild-stable `comic_path`;
restore misses land UNMATCHED and nightly rematch heals). Telemetry: **counts
only, never list names** (hard rule).

**Frontend (minimal)**: router regex + store sets + regenerated choices;
`frontend/src/api/v4/reading-lists.js` + `stores/readingLists.js`; import
dialog (upload + URL); `stores/socket.js` handles `reading-lists.changed`.
Browse cards come free from MainBrowser.

### Phase 2 — editing UI

Create/rename dialog; entry panel on the list view (add-from-browser action
beside favorite, remove, reorder — up/down buttons unless a drag lib already
exists); unmatched/needs-review panel driving the candidates→resolve picker;
export buttons. DRF tests for reorder transactionality + permission edges.

### Phase 3 — catalog browser

`GET /api/v4/reading-lists/catalog?query=&publisher=` +
`POST /import-catalog {path}` proxying the comicbox catalog (server-side
shared cache; gate behind a new `AdminFlag` like other online features).
Frontend: catalog tab in the import dialog with publisher facets + fuzzy
search.

### Phase 4 — tagwrite-back

`POST <pk>/tagwrite` (admin-only, destructive-confirm UI): build
`per_comic_patches = {comic_pk: {"arcs": {list.name: {"number":
entry.position + 1}}}}` and enqueue the **existing** `BulkTagWriteTask` —
re-import then materializes real StoryArc/StoryArcNumber rows from file tags
via the legitimate import-owned path. No new scribe machinery.

### Phase 5 — reader + OPDS

Reader: list as a reader arc — extend `codex/views/reader/arcs.py`
(ReadingList query beside StoryArc, visibility-filtered) and
`codex/views/reader/books.py` ordering
(`F("reading_list_entries__position")` scoped to the list); add
`reading_list` FK to `SettingsReader` + extend `settingsreader_scope_xor` +
partial uniques (second migration). OPDS v1/v2: `TopRoutes` entry +
`orderBy=reading_list_position` defaults mirroring arc special cases;
`opds_acquisition_collections` += reading lists. Optional: render json-cbl
previous/following relationships as links.

## Verification

- **comicbox**: `pytest tests/readinglists/`; CLI smoke:
  `comicbox --rl-print sample.cbl`, `--rl-convert json`, `--rl-match <dir>`
  against fixtures; lint per repo rules.
- **codex backend**: importer-style integration test
  (`tests/readinglists/test_import.py`): seed tmp library from existing
  comicbox fixtures, run `ReadingListImportTask` for three fixture CBLs
  (CV-id match, name-only match, unmatched), assert rows/statuses/positions.
  Matcher tier + ranking-determinism + MANUAL-immunity unit tests.
  `tests/test_scribe_priority.py` (existing guard) must pass. Upload endpoint
  test cloning `tests/test_admin_custom_cover.py`. Browse tests: ownership
  filtering, position ordering, foreign-pk empty. user_data dump/restore round
  trip. A wiring test asserting every `Collection` member appears in each
  views/const map + both URL regexes.
- **frontend**: vitest for store/router token + reorder payloads;
  `make build-choices && make build-frontend`.
- **end-to-end**: run codex against a scratch library, upload a DieselTech
  CBL, watch import progress in the admin drawer, browse `/reading-lists/`,
  open a list, confirm order + reader flow, export back to `.cbl` and diff.

## Risks

1. ~15-site collection wiring fan-out — mitigated by the wiring test.
2. Match quality on untagged libraries (tier 1 needs embedded CV/Metron ids) —
   surface needs-review prominently; document.
3. Browse perf — must copy the arc inner-join demotion.
4. GitHub rate limits — one recursive tree call + ETag cache + raw-host
   downloads.
5. Release lockstep: comicbox 4.9.0 on PyPI before codex pin bump
   (`comicbox[pdf]~=4.9.0`). The comicbox work happens in the
   `ajslater/comicbox` repo; the codex work in this repo.
6. ACL edges: counts/unmatched listings computed on viewer-filtered querysets;
   foreign private list pks → empty/404.
