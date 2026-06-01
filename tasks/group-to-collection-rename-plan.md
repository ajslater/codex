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
- ✅ Tier C DB: `Favorite.group` → `Favorite.collection` (migration 0047);
  `CustomCover.group` → `CustomCover.collection` (migration 0048, admin wire
  field kept as `group` via `source=` — see below).

**REMAINING (the entangled wire/engine + frontend pass — NOT bulk-sed-safe):**
1. `SettingsBrowserLastRoute.group` column → `collection`. Entangled with the
   `Route` dataclass (`views/util.py` `self.group`) and the route-dict `"group"`
   key (settings serialize/restore) — do it with the engine route-dict rename.
2. `SettingsBrowser.top_group` → `top_collection`: DB field + the
   `BROWSER_DEFAULT_GROUP` admin flag + serializers + ~29 frontend refs +
   `BROWSER_TOP_GROUP_COLLECTION_CHOICES`. Self-contained-ish but full-stack.
3. **The engine route-dict `{"group": …, "pks": …}` key** + `Route` dataclass —
   pervasive (~50 dict literals: route masks in validate/exceptions/
   page_in_bounds, OPDS `TopRoutes`/const, breadcrumbs `Route(...)`, mtime,
   redirect, reader). ⚠️ The literal `"group":` key is OVERLOADED — it also
   appears for websocket `{"group": ChannelGroups.ALL}` (notifierd/listener)
   and `task.group` routing. A `s/"group":/"collection":/` would corrupt those.
   Must be edited concept-aware, file-by-file. Pairs with `pks` → `parent_ids`.
4. **Item wire field `group`** (browser page serializer + ~15 frontend
   consumers: `item.group` in card/controls/download-button/subtitle/
   force-update/select-many, custom-cover upload buttons). The custom-cover
   `source=group` shim collapses once this lands.
5. mtime `groups` wire key, reader arc `group` wire field (`ArcCollectionField`).
6. Frontend: `routeForGroup`/`groupForRoute` → `*Collection`, `liveBrowseParams().group`,
   store internals, components.

Approach for the remainder: rename the **`Route` dataclass + engine route-dict
key** first (`group`/`pks` → `collection`/`parent_ids`) editing each dict
literal by hand (skip the ChannelGroups/task `"group"`), then the three wire
serializer fields (route input, item, reader arc) + their frontend consumers in
lockstep, then `top_group`, then `SettingsBrowserLastRoute.group`, then the
frontend helpers/vars. Test after each. Then the custom-cover `source=` shim and
the favorites-view `kwargs["group"]` engine kwarg fall away.

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
