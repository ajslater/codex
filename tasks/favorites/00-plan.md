# Favorites — Implementation Plan

Per-user favorites for every browseable group (Publisher, Imprint, Series, Volume, Folder, StoryArc) and Comic. Filterable in browser, surfaced as a table column, exposed via OPDS.

## Locked design

- Single `Favorite(user, group, target_id, created_at)` model. Group is a single-letter code matching codex's existing URL group enum (`p|i|s|v|f|a|c`).
- Authenticated users only — no session fallback. (Bookmark needs anonymous; favorites are persistent intent and don't.)
- Unique on `(user, group, target_id)`; composite index on the same.
- Boolean filter — "favorites only" toggle, not tri-state.
- Re-imported targets lose their favorite (Comic/Folder gain new pks on re-import; this is intentional per spec).
- Cleanup via Django `post_delete` signals on the 7 target models, with a librarian cron sweep as a backstop for any non-ORM deletes.
- ACL respected end-to-end: a user cannot favorite a target they cannot see, and the filter/feed only surface favorites of accessible targets.

## Phase 1 — Model + migration

- [x] `codex/models/favorite.py`: `Favorite(BaseModel)` with `user` FK (CASCADE), `group` CharField(max_length=1, choices=FAVORITE_GROUP_CHOICES), `target_id` PositiveIntegerField. BaseModel supplies `created_at`/`updated_at`. `unique_together = ("user", "group", "target_id")` doubles as the lookup index.
- [x] Wired wildcard import into `codex/models/__init__.py`.
- [x] `codex/migrations/0043_favorite.py` — generated via `bin/manage.py makemigrations`.
- [x] Tests added to `tests/test_models.py::FavoriteTestCase` — create, unique violation, distinct users, distinct groups, user-delete cascade.

Verify: ruff + basedpyright clean; pytest passes (5/5 in `tests/test_models.py`).

## Phase 2 — Cleanup signals + cron backstop

- [x] `codex/signals/django_signals.py` — single `_on_favorite_target_deleted` dispatcher driven by a module-level model→group-code map populated in `connect_signals()`. Connected `post_delete` for all 7 target models.
- [x] Cron backstop: `JanitorCleanupFavoritesTask` / `Status` / `cleanup_orphan_favorites()` wired into `JANITOR_STATII`, `_NIGHTLY_TASK_CLASSES`, and `_JANITOR_METHOD_MAP` (mirrors `cleanup_orphan_bookmarks`). Uses `target_id NOT IN (SELECT pk FROM <model>)` per group code under `db_write_lock`.
- [x] Tests: `test_target_delete_cascades_via_signal` confirms ORM-deletion fires the signal and only the matched (group, target_id) is dropped (distractors survive). Cron sweep follows the codebase's existing untested-cleanup pattern; trusted via integration.

Verify: ruff + basedpyright + vulture + complexipy clean; pytest 6/6 in `tests/test_models.py`.

## Phase 3 — API ViewSet

- [ ] `codex/serializers/favorite.py` — minimal serializer for list response (`group`, `target_id`).
- [ ] `codex/views/favorites.py` — `FavoriteViewSet`:
  - `PUT /api/v3/favorites/<group>/<pk>/` — idempotent create (200 if existed, 201 if new). Validate target exists and request user has ACL access to it before creating.
  - `DELETE /api/v3/favorites/<group>/<pk>/` — idempotent delete (204).
  - `GET /api/v3/favorites/?group=<g>` — list ids the user has favorited (group filter optional).
- [ ] Register routes in `codex/urls/api_v3.py`.
- [ ] Tests: 401 for unauthenticated, 404 for nonexistent target, 403 for inaccessible target (ACL), idempotency on repeated PUT/DELETE, list filtering by group.

Verify: `make fix && make test-backend`.

## Phase 4 — Browser filter wiring

- [ ] `codex/views/browser/filters/favorite.py`, mirroring [bookmark.py](codex/views/browser/filters/bookmark.py). `get_favorite_filter(model, group_code)` returns `Q()` when filter unset, else `Q(pk__in=Favorite.objects.filter(user=request.user, group=group_code).values("target_id"))`. Anonymous users → always `Q()` (no-op).
- [ ] Add `"favorite": BooleanField(required=False)` to filter serializer in `codex/serializers/browser/filters.py`.
- [ ] Wire `get_favorite_filter()` into `BrowserFilterView.get_filtered_queryset()` next to the bookmark filter chain.
- [ ] Tests: filter on/off, anonymous no-op, composes with bookmark filter, ACL still respected.

Verify: `make fix && make test-backend`.

## Phase 5 — Table column

- [ ] Add `"favorite"` entry to `BROWSER_TABLE_COLUMNS` in [codex/choices/browser.py](codex/choices/browser.py): user-facing `label="Favorite"` (match the i18n wrapper convention used by neighboring entries — `_()`/`gettext_lazy` if present, bare string otherwise), `sort_key="is_favorite"`, `m2m=False`, `editable=True`, `edit_widget="checkbox"` for now (custom star widget deferred to Phase 8 if needed).
- [ ] `make build-choices` to regenerate `frontend/src/choices/browser-table-columns.json`.
- [ ] In [codex/views/browser/columns.py](codex/views/browser/columns.py): add `is_favorite` annotation builder using `Exists(Favorite.objects.filter(user=request.user, group=group_code, target_id=OuterRef("pk")))`. Confirm it composes with existing default-column logic and `is_sortable()`/`sort_key_for()`.
- [ ] Tests: column appears in default choices, annotation present, sort by `is_favorite` works, anonymous users get `False` for all rows.

Verify: `make fix && make test-backend`.

## Phase 6 — OPDS favorites filter + start-page nav link

- [ ] Add `"favorite"` to the OPDS feed's filter list (mirrors the browser filter wired in Phase 4 — same `Q()` shape, just plumbed through the OPDS filter dispatch).
- [ ] On the OPDS start page, conditionally render a "Favorites" nav link that points at the favorites-filtered feed. Show only when `Favorite.objects.filter(user=request.user).exists()`; cache the existence check per request.
- [ ] Tests: filtered feed contents respect ACL, nav link hidden when no favorites, link present when at least one favorite exists, requires auth.

Verify: `make fix && make test-backend`.

## Phase 7 — Frontend store + API client

- [ ] `frontend/src/api/v3/favorites.js` — xior client: `toggleFavorite(group, pk, on)` (PUT or DELETE), `listFavorites(group?)`.
- [ ] `frontend/src/stores/favorites.js` — Pinia store:
  - state: `favoriteIds: { p: Set, i: Set, s: Set, v: Set, f: Set, a: Set, c: Set }`
  - actions: `hydrate()`, `toggle(group, pk)` with optimistic update + rollback on error, getter `isFavorite(group, pk)`.
- [ ] Hydrate on login (wire into auth store flow).
- [ ] Vitest unit tests: toggle path, optimistic rollback, hydration, getters.

Verify: `make fix && make test-frontend`.

## Phase 8 — Frontend UI

- [ ] `frontend/src/components/common/FavoriteToggle.vue` — star icon button. Props: `group`, `pk`. Reads from `favorites` store, calls `toggle`.
- [ ] Mount in browser cards (`components/browser/`).
- [ ] Mount in reader header (`components/reader/`).
- [ ] Mount in table-cell renderer for the new "favorite" column.
- [ ] Browser toolbar settings panel: add a "favorites only" toggle that writes `filters.favorite` into the `browser` Pinia store.
- [ ] Manual UI verification: `make dev`, then favorite items at each group level, confirm filter, table column, and OPDS feed all reflect state.

Verify: `make fix && make test-frontend && make build-frontend`. Manual UI walkthrough.

## Phase 9 — Integration + docs

- [ ] End-to-end smoke: favorite items at every group level → confirm browser filter, table column, OPDS feed; delete a favorited target → confirm signal cleanup; run cron sweep manually → confirm orphan cleanup.
- [ ] Update README features list (sibling commit `26235aa6` added table view there — favorites belongs in the same section).
- [ ] Single commit per phase, sequenced. PR titled e.g. "add per-user favorites".

Verify: full `make fix && make test`.

## Out of scope

- Bulk favorite/unfavorite UI.
- Favorite-follows-rename for re-imported Folders/Comics (spec: re-imports lose favorites).
- Per-library or curator/staff favorites (different feature).
- Websocket sync of favorite toggles across a user's open tabs (favorites change rarely; an extra fetch on focus is enough if needed later).

## Resolved verification points

1. Signals live in `codex/signals/django_signals.py`.
2. OPDS already has filtered feeds — favorites is just a new filter entry plus a conditional start-page nav link, not a new feed endpoint.
3. `BROWSER_TABLE_COLUMNS` `label` is the user-facing string — match the existing i18n convention in neighboring entries.
