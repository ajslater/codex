# Plan: Rename `group` → `collection` (internal identifiers, all tiers)

## Progress (as of the rename execution)

**DONE (committed, all green — backend 405 / vitest 99 / ty unchanged):**
- ✅ Tier B core: `Group` enum → `Collection`; `codex/group.py` → `codex/collection.py`;
  the `COLLECTION_NAMES`/`COLLECTION_BY_NAME`/`COLLECTION_SINGULAR_NAMES`/
  `COLLECTION_LABELS` maps; all 28 importers + every `Collection.<member>`.
- ✅ Tier B: the `views/const.py` registry constants (`COLLECTION_RELATION`,
  `COLLECTION_ORDER`, `COLLECTION_MODEL_MAP`, the named `*_COLLECTION`
  constants, the relation maps), the `FAVORITE_*` family, and the
  `BrowserCollectionModel` class hierarchy.
- ✅ Tier B tail: the private/importer browse `GROUP_*` constants.
- ✅ Tier C DB — **all four browse-group columns renamed** (migrations 0047-0050,
  plain `RenameField`, unreleased):
  - `Favorite.group` → `Favorite.collection`
  - `CustomCover.group` → `CustomCover.collection` (admin-list wire field kept
    as `group` via serializer `source="collection"` — its FE readers are the
    *browse item* `group`, so it flips with that, not here)
  - `SettingsBrowserLastRoute.group` → `.collection` (the `get_last_route`
    default builder decouples: engine route-dict key stays `"group"`, the field
    lookup uses `"collection"`)
  - `SettingsBrowser.top_group` → `top_collection` — **full-stack** (~143 BE +
    ~62 FE, the `topCollection` wire field, `TOP_COLLECTION` choices, OPDS
    `topGroup` query-param emitters, choices JSON regen).

- ✅ **Item wire field** `group` → `collection`: the browse page serializer's
  `_row_repr` OUTPUT key + ~12 frontend `item.group` readers (card/controls/
  subtitle/order-by/download/mark-read/force-update/browser-table/main/
  select-many/upload+remove-cover buttons) + the `metadataBook`/metadata-dialog
  `book.group` ripple. Avoided the OPDS-entry reverse breakage by keeping the
  internal `card.py` annotation named `group` (read by OPDS v1 entry rendering)
  and flipping only the serializer output key.
- ✅ **Reader arc wire field** `group` → `collection`: serializer
  `collection = ArcGroupField`, reader.py/params.py/arcs.py arc dicts, the
  frontend `this.arc.collection` reads + arc-select send + DEFAULT_ARC.

- ✅ **Shared mixin wire field** `BrowserAggregateSerializerMixin.group` →
  `collection` (via `source="group"`). This is the card/cover-view row field +
  the metadata field. Fixed a latent break (cover view emitted `group` while
  table rows emitted `collection`). Frontend metadata reads `md.collection`.
- ✅ **`model_group`** → `model_collection` (page-level field): the view
  property + every reader, the serializer field + payload key, frontend
  `page.modelCollection`.

1. ✅ **DONE** (commit `737ef18d`, backend 405 / vitest 99 / ty unchanged):
   **The engine `kwargs["group"]` nav key** → `kwargs["collection"]`. The prior
   bulk attempt failed because the coupling was misread as one unit; it is
   actually **two independent clusters**:
   - **Cluster A (renamed):** the nav key itself — AuthMixin's setter + ~50
     reads, the favorites/tagwrite/bookmark setters, the OPDS url-pattern
     start/manifest defaults, and the OPDS masks that feed `opds_feed_reverse`.
   - **Cluster B (kept as `group`):** the `Route` dataclass, browser redirect
     masks, `DEFAULT_BROWSER_ROUTE`, the persisted `last_route`, and
     `RouteSerializer` — these double as **frontend wire payloads** (the
     RouteSerializer INPUT field is still `group`/`pks`; `last_route`
     serializes `group`). Renaming them needs a coordinated FE flip; out of
     scope for an internal-only pass.
   Mechanics: AuthMixin now translates only when `"collection" in kwargs and
   "pks" not in kwargs` (OPDS direct-kwarg routes carry `pks`); `opds_feed_reverse`
   is the one choke point that accepts **both** dialects (engine `collection`,
   wire-payload `group`); the manifest marker moved to `collection` (its view
   inherits the browse machinery) while `position` stays `group` (progression
   reads it directly, never hits the browse machinery).

1b. ✅ **DONE** (commit `5675bf58`): the `group` browse-row annotation →
   `nav_collection` (couldn't be `collection` — `WatchedPath.collection`
   collision; see below).
1c. ✅ **DONE** (commit `817f86da`): the **route INPUT wire** `group` →
   `collection` (`pks` kept). `SimpleRouteSerializer` declared field (drives
   `mtime.groups[]` + `cover.parent_route`), the whole `last_route` family
   (`BrowserSettingsLastRouteSerializer`, settings dict + save mapping,
   `DEFAULT_BROWSER_ROUTE`, `admin_default_route_for`, `params._update_last_route`),
   the `Route` dataclass + browser redirect masks, and the FE producers (mtime
   items + cover `parentRoute`). `opds_feed_reverse` simplified back to a single
   `collection` dialect. The whole route contract now speaks `collection`.

**REMAINING (purely cosmetic FE-internal naming — no wire/behavior change; nav
is manual-QA'd, so vitest doesn't fully guard it):**
2. **The `group` browse-row annotation** (`card.py` `_annotate_group`) — ✅ DONE
   as `nav_collection` (1b). Original note retained for the collision rationale:
   `OPDS1EntryObject.group` mirror + the ~14 `self.obj.group` readers in
   `opds/v1/entry/*`. ⚠️ **BLOCKED from becoming `collection`:** `WatchedPath`
   (Folder/CustomCover base) already declares a real `collection` CharField
   (`models/paths.py:117`), and `_annotate_group` runs on Folder rows, so
   `annotate(collection=...)` raises `FieldError`. The annotation is therefore
   a *forced alias* — the wire already exposes it as `collection` (via
   `source="group"` / `getattr(instance,"group")`). To unify the name it would
   have to become a non-colliding third name (e.g. `nav_collection`), not
   `collection`. Cosmetic; no behavior or wire change either way.
3. ✅ **DONE** (commit `5d3f17f1`): the **FE-internal route engine shape**.
   `routeForGroup`/`groupForRoute` → `routeForCollection`/`collectionForRoute`,
   `liveBrowseParams()` → `{collection, pks, page}`, `toBrowseRoute` disambiguates
   v4-vs-engine on `pks` presence, the `api/v4/browser.js` segment param `group`
   → `collection` (+ two `"r"`→`"root"` vestiges), every api caller, and the
   coupled `BrowserSettingsInputSerializer.group` → `collection` query field.
   Surfaced + fixed two latent bugs from the earlier item-flip (`browser-table`
   row-click → reader instead of drill-in; `download-panel` item shape).

4. ✅ **DONE** (commit `0e6ac347`): the **shared `group` prop convention** →
   `collection` (favorite-toggle, book-cover, metadata-text/cover/header/controls
   + all `:group=`/`group=` bindings + the loadMetadata/lazyImport store actions).
   Also fixed a char-vestige bug (`GROUP_MAP` keyed by chars, looked up by
   collection → `markReadItem` name fallback) → `COLLECTION_PREFIX_MAP`.
   And a prior latent-bug sweep (commits `75ce24b0`, `1715347b`) fixed
   `book.group`/item-shape `group` reads that broke table-row drill-in,
   lazy-import, tag-write, and metadata mark-read.

**STILL `group` — genuinely different meaning or out-of-scope wire (NOT rename
targets):**
- The **admin custom-cover** (`uploadCustomCover`/`removeCustomCover`/replace) and
  **tag-write** (`onlinetag`, edit-panel) `group` API fields — a *different wire
  surface*; the backend still expects `group` there (pinned by
  `test_admin_custom_cover` / `test_tag_write_filters`).
- The **reader-arc** internal select shape (`reader-arc-select.vue`) and the mtime
  `groups` array *field name* (its items are `collection` now).
- **metadata-chip**'s internal `linkGroup` computed (self-contained chip vocab).
- The store **hierarchy vocabulary** (`topGroup`/`lowestShownGroup`/`GROUPS`/
  `getTopGroup`) — "group" as a browse *level*, a legitimately distinct meaning.

**Net result: every collection-valued `group` identifier across engine, DB,
wire, and frontend is now `collection`.** What remains named `group` is either a
genuinely different concept (browse *level*) or an external API contract
(admin custom-cover / tag-write) the backend still keys on `group`.

**Manual nav QA recommended** (vitest doesn't drive live routing): drill
publishers→series→volumes via cards AND table rows, breadcrumb back, "/" → last
route, open→close a comic returns to the right route, cover parent-route renders,
mark-read / force-update / download / select-many actions, no `/api/v4/mtime` or
`/settings` 400s.

## Goal

The browse-group vocabulary's *values* are already the plural collection
names (`publishers`, `imprints`, `series`, `volumes`, `comics`, `folders`,
`arcs`, plus synthetic `root`). The char codes and their compat machinery are
gone. What remains is the *naming*: the `Group` enum, `group` kwargs/params/
fields, `GROUP_*` constants, DB columns, wire keys, and frontend identifiers
all still say "group" while carrying collection values. This plan renames the
**browse-group concept** to **collection** everywhere it's safe.

This is a pure naming refactor — no behavior change. The values don't move;
only identifiers do.

## Why now is cheap

Nothing is released: the v4 API, the user_data sidecar, and the collection
transition are all unshipped. That collapses the usual Tier-C cost:

- **DB columns** can be renamed with plain `RenameField` migrations (or by
  editing the introducing migration in place) — no data migration, no
  backward-compat window.
- **Wire keys** (serializer fields, URL params, request bodies) can be flipped
  in one coordinated frontend+backend change — no versioning, no compat shim.
- **OPDS** URLs/feeds already speak the collection scheme; only internal Python
  identifiers change there.

The remaining real cost is *blast radius* (≈150 files, ≈950 identifier
occurrences) and the **overload hazard** below.

## ⚠️ DO NOT RENAME — unrelated "group" meanings (~270 hits)

A naive global `group`→`collection` would corrupt all of these. They must be
explicitly excluded:

| Meaning | Where | ~count |
|---|---|---|
| Django **auth `Group`** (permissions) | `views/const.py` (`import Group as AuthGroup`), `models/auth.py` `GroupAuth`, the `groups` M2M, many tests | 34 |
| Frontend **auth-group CRUD UI** | `admin/tabs/group-tab.vue`, `group-create-update-inputs.vue`, `group-chip.vue`, `api/v4/admin.js` `makeAdminCRUD("groups")` | 11 |
| **`SeriesGroup`** tag model + `series_groups` | `models/named.py`, `models/comic.py`, choices, importer, settings | 86 |
| SQL **`group_by`** / `regroup` / `JsonGroupArray` | `models/query.py`, `annotate/order.py`, `annotate/card.py` | 23 |
| Websocket **`GROUPS_CHANGED`** notification | `choices/notifications.py`, `websockets/payloads.py`, `notifier/tasks.py` | 14 |
| Channels `group_send` / `group_add` | `librarian/notifier/`, `websockets/listener.py` | ~5 |
| Frontend job-tab **UI grouping** (`isSelectGroup`, `groupSelectValues`) | `admin/tabs/job-tab.vue` | 28 |

**Bonus:** renaming browse `Group` → `Collection` *removes* the existing
`AuthGroup` aliasing collision in `views/const.py` rather than creating one.

## Naming decisions (decide before starting)

| Current | Proposed | Notes |
|---|---|---|
| `Group` (StrEnum, `codex/group.py`) | `Collection` | Module `group.py` → `collection.py`. `ROOT` member stays (synthetic top; value `"root"`). |
| `GROUP_MODEL_MAP`, `GROUP_RELATION`, `GROUP_ORDER`, `GROUP_NAME_MAP`, `GROUP_COLLECTIONS`, `GROUP_LABELS`, `GROUP_SINGULAR_NAMES`, … | `COLLECTION_*` | `GROUP_COLLECTIONS` becomes redundant → fold into the enum. |
| `FOLDER_GROUP`, `STORY_ARC_GROUP`, `COMIC_GROUP`, `ROOT_GROUP` | `FOLDER_COLLECTION`, … | |
| `FAVORITE_MODEL_GROUP_CODES`, `FAVORITE_GROUP_CODE_MODELS`, `FAVORITE_GROUP_CHOICES` | `FAVORITE_MODEL_COLLECTIONS`, … | |
| `BrowserGroupModel`, `IdentifiedBrowserGroupModel`, `WatchedPathBrowserGroup` | `BrowserCollectionModel`, … | Largest class-rename (76 refs / 21 files). |
| `group` kwarg/param/local var | `collection` | |
| `top_group` (DB col + flag + serializer + ~29 FE refs) | `top_collection` | Same concept ("which collection is the top/root level"). Full-stack rename. |
| Browser item wire field `group` | `collection` | Serializer + ~15 FE consumers (`item.group`). |
| `routeForGroup` / `groupForRoute` (FE) | `routeForCollection` / `collectionForRoute` | |
| DB cols `Favorite.group`, `CustomCover.group`, `SettingsBrowserLastRoute.group` | `.collection` | `RenameField` migrations. |
| `GROUPS_CHANGED` notification | **keep** (or separately decide) — it's a wire/notification string, borderline | |

Open question to settle: do `SettingsBrowserShow` flag fields stay
`publishers/imprints/series/volumes` (collection values, already correct) —
yes, those are values not the word "group", leave them.

## Tiers

### Tier A — internal-only, cheap (~400–500 occurrences, 0 migrations)
Local `group` vars, loop variables, private module constants
(`_GROUP_BY`, `_GROUP_PARENT_CHAIN`, `_GROUP_REL_TARGETS`, …), Python helper
names not on the wire, frontend internal vars in stores/components downstream
of `route.js`. Pure mechanical, low risk.

### Tier B — cross-module public symbols (~250–300 occ, ~40 files, 0 migrations)
- The `Group`→`Collection` enum + its **29 import sites**.
- The `views/const.py` registry (`GROUP_MODEL_MAP`, `GROUP_RELATION`,
  `GROUP_ORDER`, named-group constants) — everything imports it.
- The `FAVORITE_*` constant family across 8 files.
- The `BrowserGroupModel` class hierarchy (76 refs / 21 files).
- `make build-choices` regen if any enum member *name* feeds generated JSON
  (it doesn't today — values do).

### Tier C — DB columns + wire keys (~60–80 occ; cheap *because unreleased*)
**DB column renames** (`RenameField`, no data migration):
- `Favorite.group` → `Favorite.collection` (+ `unique_together`).
- `CustomCover.group` → `CustomCover.collection`.
- `SettingsBrowserLastRoute.group` → `.collection`.
- `SettingsBrowser.top_group` → `.top_collection`.

**Wire-key renames** (coordinated FE+BE, no compat needed):
- `RouteSerializer` input `group`/`pks` → `collection`/`parent_ids` (output is
  already `collection`/`parentIds`). Updates mtime/parentRoute producers in
  `stores/browser.js` + the input readers in `mtime.py` / `cover.py`.
- mtime request key `groups` → `collections`.
- Browser **item** field `group` → `collection`: `serializers/browser/*` +
  every `item.group` reader (`book-cover.vue`, `controls.vue`,
  `download-button.vue`, `card.vue`, `subtitle.vue`, `force-update-button.vue`,
  `browser-select-many.js`, …).
- Reader arc field `group` → `collection` (`serializers/reader.py`
  `ArcGroupField`, `reader.js` arc objects).
- Favorites URL path `/favorites/{group}/{pk}` — already `{collection}` (no-op).
- Custom-cover upload form key `group` → `collection` (`api/v4/admin.js`,
  `views/admin/custom_cover.py`).
- `serializers/fields/group.py` field classes (`BrowseGroupField`,
  `BrowserRouteGroupField`, `ArcGroupField`) → `*CollectionField`.

## Execution order (suggested)

1. **Enum core first** (Tier B): rename `codex/group.py` → `collection.py`,
   `Group` → `Collection`, update 29 import sites. Run suite.
2. **const.py registry + named constants** (Tier B): `GROUP_*` → `COLLECTION_*`.
   Run suite.
3. **FAVORITE_* family + BrowserGroupModel hierarchy** (Tier B). Run suite.
4. **Tier A sweep**: local vars/params `group` → `collection` per module, plus
   the frontend `route.js` boundary helpers + downstream store/component vars.
   Run vitest + suite.
5. **Tier C DB**: one `RenameField` migration per column (or a single migration
   with four operations) + `unique_together` + all ORM `.filter(group=…)` →
   `.filter(collection=…)`. Run suite.
6. **Tier C wire**: flip serializer field names + the matching FE producers/
   consumers in lockstep (item field, route input, mtime, reader arc,
   custom-cover form). Run suite + vitest. Manual QA.

Each step is independently green-able; commit per step. Use the test suite
(currently 405 backend / 99 vitest) as the guard — it caught every silent
char-vs-collection bug during the value flip, so it will catch a missed rename
(a `Collection`-keyed map looked up by a stale `group` var fails loudly only if
typed; many won't, so rely on grep discipline + `ruff`/`ty` for unused names).

## Risks & mitigations

- **Overload corruption** — the single biggest risk. Never `sed -i
  s/group/collection/g`. Use word-boundary, symbol-aware renames (IDE rename or
  `rg -w` + targeted edits), and explicitly skip the DO-NOT-RENAME list. Grep
  for `AuthGroup`, `SeriesGroup`, `series_groups`, `group_by`, `JsonGroupArray`,
  `GROUPS_CHANGED`, `group_send`, `group-tab`, `groupSelectValues` after each
  pass and confirm they're untouched.
- **Silent misses** — a renamed `Collection` map looked up by a leftover
  `group` string still works at runtime (StrEnum equality), so a partial rename
  won't necessarily fail tests. Mitigate by renaming whole symbols (not values)
  and letting `ruff`/`ty` flag unused/undefined names.
- **`top_group`** is the one genuinely ambiguous call — it IS the browse
  concept, so `top_collection` is correct, but it's full-stack (DB + flag +
  serializer + 29 FE refs). Bundle it with Tier C or defer it explicitly.

## Order-of-magnitude

| Scope | Files | Occurrences | Migrations |
|---|---|---|---|
| Tier A + B only | ~120 | ~700 | 0 |
| + Tier C (full) | ~150 | ~950 | 1 (4 RenameField ops) |

## Recommendation

The values are already collection; the names are the last inconsistency. Given
nothing is released, **doing all tiers is now cheap** (one rename migration, no
wire-compat). Recommended path:

- **Do Tier A + B + the Tier-C DB columns** as a sequence of mechanical,
  per-step-green commits. This makes the entire backend speak one word.
- **Do the Tier-C wire renames** (item field, route input, reader arc,
  custom-cover form, `top_group`) as a final coordinated FE+BE commit, since
  they're the only ones touching both sides at once.

If appetite is limited, stop after Tier A+B+DB (≈90% of the win, all backend,
one migration) and leave the wire keys named `group` — they're invisible to
users and carry collection values regardless. The frontend-visible `item.group`
is the most worthwhile wire rename if you do just one.
