# Custom Cover Upload UI

## Context

Codex supports custom group covers (Publisher, Imprint, Series, StoryArc, Folder), but the only way to set them today is by dropping files on disk in two filesystem-watched locations:

- `config/custom-covers/{publishers,imprints,series,story-arcs}/{sort_name}.{ext}` — discovered by a filesystem watcher/poller against a singleton `Library(covers_only=True)` row. Name-based group resolution.
- `.codex-cover.{jpg,png,webp,...}` inside library folders — matched by `match_folder_cover()` and linked by parent path.

This requires shell or filesystem access and is opaque to non-admins. The `covers_only` flag has metastasized: it gates branches in the filesystem watcher, poller, snapshot, importer, janitor, telemeter, browser view, library admin view, library serializer, and frontend admin store. The entire custom-covers concept is currently a "fake library" hack.

End state:
- Admins click "Upload Cover" on any card's 3-dot menu, pick a file, the card updates.
- Originals live in `config/custom-covers/uploads/{pk}-{group-char}-{slug}.{ext}` — pk-keyed for uniqueness, with a human-readable group char and slug for browseability.
- Thumbnails continue to live in `cache/custom-covers/` (existing pipeline unchanged).
- The legacy `config/custom-covers/{group}/` watch is removed; existing files migrate once.
- `.codex-cover.{ext}` discovery inside library folders is removed; existing files migrate once.
- The `Library.covers_only` flag is removed entirely along with all its branches; `CustomCover` no longer references a Library.
- A new admin "Custom Covers" tab lists every `CustomCover` row with thumbnail, linked group, and delete action.

## Decisions

1. **Storage scheme**: `config/custom-covers/uploads/{pk}-{group-char}-{slug}.{ext}` — pk guarantees uniqueness; `{group-char}` and `{slug}` are informational for filesystem readability.
2. **Legacy mechanism**: one-time migration of `config/custom-covers/{group}/` and `.codex-cover.{ext}` into the uploads dir, then **remove** both filesystem-watch branches.
3. **Library.covers_only**: remove the field and every consumer; the synthetic covers-only library row is deleted; `CustomCover.library` FK is dropped (nullable then dropped, since uploads don't belong to any library).
4. **Upload surfaces**: card action menu (upload + remove). Plus a new top-level admin tab for browse/delete (view-only of existing covers, no upload from there in this pass).
5. **Size limit**: 10 MB default, configurable as `custom_covers.max_upload_mb` in `codex.toml`.
6. **Volume custom covers**: now supported. Originally skipped because legacy filename matching required a `sort_name` and Volume's `name` is numeric — that blocker is gone with direct-FK linking.

## Architecture

### Storage layout

| Kind | Location | Naming |
|---|---|---|
| Upload originals | `config/custom-covers/uploads/` | `{pk}-{group_char}-{slug}.{ext}` |
| Cache thumbnails | `cache/custom-covers/` | hex-sharded by pk, `.webp`, 165×254 (existing) |

- `group_char` is `p|i|s|v|a|f` matching `CustomCover.GroupChoices` (`v` added — see Volume section).
- `slug` is the linked group's `sort_name` slugified (lowercase, ascii, hyphens, truncated to ~60 chars). For folders use the folder name. For volumes, use `Volume.to_str(name, number_to)` stripped of parentheses (e.g., `v3`, `2024`). If empty, omit the trailing `-{slug}`.
- `ext` preserved from upload, restricted to image types (`jpg`, `jpeg`, `png`, `webp`, `gif`, `bmp`).
- File is named after the row is created (need the pk). On rename of the linked group later, leave the filesystem name stale; the DB is authoritative.

### `CustomCover` model evolution

[`codex/models/paths.py:84`](codex/models/paths.py):

- Drop the `library` FK (or null it first, then drop in a follow-up migration).
- Keep `group`, `sort_name`, `path`, `stat`.
- Add `V = "v"` to `GroupChoices`; remove the `# no V` comment.
- `_set_group_and_sort_name()` currently derives `group`/`sort_name` from parent dir name. Replace with: no-op when `path` is under the uploads dir (set in the upload view explicitly). Drop the `DIR_GROUP_CHOICE_MAP` constant after migration runs.
- `FOLDER_COVER_STEM` constant can be removed once `.codex-cover.{ext}` discovery is gone.

### Volume custom-cover support

Volume was the only browser group with `custom_cover = None` overriding the inherited FK ([`models/groups.py:161`](codex/models/groups.py)). Re-enable:

- Delete the `custom_cover = None` line on `Volume`. The FK inherited from `BrowserGroupModel` ([`models/groups.py:39-41`](codex/models/groups.py)) now takes effect.
- Add `Volume: CustomCover.GroupChoices.V.value` to `CLASS_CUSTOM_COVER_GROUP_MAP` ([`codex/librarian/scribe/importer/const.py:395-403`](codex/librarian/scribe/importer/const.py)).
- Remove the `if group_model is Volume: return None` short-circuit in [`codex/views/browser/annotate/cover.py:88`](codex/views/browser/annotate/cover.py). `CUSTOM_COVER_GROUP_RELATION` already maps `v → volume` via `GROUP_NAME_MAP` ([`codex/views/const.py:47-48,83`](codex/views/const.py)), so the subquery works without further changes.
- Django migration: add `custom_cover_id` column on `codex_volume`. Generate via `makemigrations`.
- Frontend: include `v` in the set of group chars that surface upload/remove items on cards.

### `Library` model + downstream cleanup

Drop `covers_only` field ([`library.py:42`](codex/models/library.py)) and `CUSTOM_COVERS_DIR_DEFAULTS` ([`library.py:35-41`](codex/models/library.py)).

Every consumer becomes simpler. Replace each `Library.objects.filter(covers_only=False)` with `Library.objects.all()` (or just drop the filter clause):

- [`codex/serializers/admin/libraries.py:18-46`](codex/serializers/admin/libraries.py) — drop `covers_only` from `fields` and `read_only_fields`.
- [`codex/views/admin/library.py:77,115-116,130-131,145-146,206-207`](codex/views/admin/library.py) — drop the annotation `When(covers_only=True, ...)`, the create/update/destroy guards, the `_default_root_path` filter.
- [`codex/startup/__init__.py:197-260`](codex/startup/__init__.py) — delete `init_custom_cover_dir` and `update_custom_covers_for_config_dir`. Replace with a single one-shot `migrate_filesystem_custom_covers` step (described below).
- [`codex/startup/custom_cover_libraries.py`](codex/startup/custom_cover_libraries.py) — delete entire file. Its caller in `startup/__init__.py` goes away.
- [`codex/librarian/fs/filters.py`](codex/librarian/fs/filters.py) — drop `match_group_cover_image` and `match_folder_cover`.
- [`codex/librarian/fs/poller/poller.py:24-31,120-132`](codex/librarian/fs/poller/poller.py) — drop `covers_only` from `_LIBRARY_ONLY`, drop `covers_only=` arg passing.
- [`codex/librarian/fs/poller/snapshot.py:24-31,76-78,98-128`](codex/librarian/fs/poller/snapshot.py) — drop `_covers_only` field, `is_cover()` becomes always-false, `_should_include` drops the `_covers_only` branch. `match_folder_cover` use is also removed (no more in-library folder covers).
- [`codex/librarian/fs/watcher/watcher.py:30-36,63-66,94-118,144`](codex/librarian/fs/watcher/watcher.py) — drop `_covers_only_paths`, related branches and DB query columns.
- [`codex/librarian/fs/watcher/events.py:22-29,73-79,83-102`](codex/librarian/fs/watcher/events.py) — drop `covers_only=` plumbing through `_process_change`, `_find_library`, `process_changes`. `is_cover` always becomes `False`.
- [`codex/librarian/fs/watcher/dirs.py:21-40`](codex/librarian/fs/watcher/dirs.py) — drop `covers_only` param from `_classify_added_file` / `expand_dir_added`.
- [`codex/librarian/scribe/importer/link/covers.py`](codex/librarian/scribe/importer/link/covers.py) — delete the file's logic; the sort_name-vs-path branching disappears entirely (no more importer-driven linking — linking is direct in the upload view).
- Adjacent importer files for query/create/move/delete of `CustomCover` rows: delete the orchestration entry points (no more watcher events trigger them). Keep any helper that's still referenced by something else; otherwise prune.
- [`codex/librarian/scribe/timestamp_update.py:124`](codex/librarian/scribe/timestamp_update.py) — drop `.filter(covers_only=False)`.
- [`codex/librarian/scribe/janitor/adopt_folders.py:102`](codex/librarian/scribe/janitor/adopt_folders.py) and [`failed_imports.py`](codex/librarian/scribe/janitor/failed_imports.py) — drop filters.
- [`codex/librarian/telemeter/stats.py`](codex/librarian/telemeter/stats.py) — drop the `if model == Library: qs = qs.filter(covers_only=False)` special case.
- [`codex/views/browser/browser.py`](codex/views/browser/browser.py) — `libraries_exist()` becomes a plain `Library.objects.exists()`.

Tests that exercise these branches ([`tests/test_fs_filters_ignore.py:90,101,109-112,158`](tests/test_fs_filters_ignore.py), [`tests/test_snapshot_diff.py:28`](tests/test_snapshot_diff.py)) get their `covers_only` args removed.

### Migrations

Three Django migrations in `codex/migrations/`:

1. **Schema**: `AlterField CustomCover.library` to `null=True, blank=True`. Allows the data migration to detach rows.
2. **Data** (`RunPython`):
   - For each `CustomCover` row whose `path` is not already under `config/custom-covers/uploads/`:
     - Resolve `group_char` from `group`; resolve `slug` from the linked group's `sort_name` (lookup via `CLASS_CUSTOM_COVER_GROUP_MAP`), or from folder basename, or empty.
     - Compute `new_path = CUSTOM_COVERS_UPLOADS_DIR / f"{pk}-{group_char}-{slug}{ext}"` (or without `-{slug}` if empty).
     - Move file with `shutil.move()` (handles cross-device); skip rows whose source file is missing and log.
     - `cover.path = str(new_path); cover.library = None; cover.save()`.
   - Walk the legacy `config/custom-covers/{publishers,imprints,series,story-arcs}/` dirs, `.codex-cover.{ext}` files in library trees referenced by any remaining-pre-migration rows, and unlink any orphan files. Best-effort; non-fatal.
   - Delete the singleton `Library(covers_only=True)` row.
3. **Schema**: `RemoveField Library.covers_only`; `RemoveField CustomCover.library` (or keep nullable forever — slight preference to remove entirely since no consumer remains).

The data migration is idempotent: rows already under `uploads/` are skipped.

### Backend endpoints

All under `/api/v3/admin/`. Reuse `AdminAPIView` / `AdminModelViewSet` base from [`codex/views/admin/auth.py`](codex/views/admin/auth.py).

**`POST /api/v3/admin/custom-cover`** — multipart upload.
- Form fields: `group` (`p|i|s|a|f`), `pks` (comma-separated ints — typically one, support multi for bulk-link to multiple groups sharing the same artwork), file as `image`.
- Validate: auth (superuser/staff), image type (extension + Pillow open), size ≤ `CUSTOM_COVERS_MAX_UPLOAD_BYTES`, all target group rows exist and match `group`.
- Transaction:
  1. `cover = CustomCover.objects.create(library=None, path="", group=group_char, sort_name=first_group.sort_name)`.
  2. Compute `final_path` from `cover.pk`, `group_char`, slug, extension.
  3. Write upload bytes to `{final_path}.tmp` then `os.replace` into place.
  4. `cover.path = str(final_path); cover.save(update_fields=["path", "stat"])`.
  5. For each target group: if its current `custom_cover_id` references a row that no other group references, schedule that old row for deletion (file + thumb + row).
  6. `GroupModel.objects.filter(pk__in=pks).update(custom_cover=cover)`.
  7. Enqueue `CoverCreateTask(pks=(cover.pk,), custom=True)`.
- Response: `{"customCoverPk": cover.pk}`.

**`DELETE /api/v3/admin/custom-cover/{pk}`** — delete a CustomCover by pk.
- Unset `custom_cover` FK on every linked group row (search across Publisher/Imprint/Series/StoryArc/Folder using `CLASS_CUSTOM_COVER_GROUP_MAP[cover.group]` to pick the model).
- Delete the original file in uploads.
- Enqueue `CoverRemoveTask` to clear the cached thumb.
- Delete the row.

**`POST /api/v3/admin/custom-cover/remove`** — remove the custom cover from one or more groups without deleting the row (only delete the row if no group still references it). Body: `group`, `pks`. Useful for "Remove Cover" from a single card.

**`GET /api/v3/admin/custom-cover/`** — list all CustomCover rows for the new admin tab.
- DRF `ListAPIView` with serializer returning: `pk`, `group`, `groupCharLabel`, `linkedGroupPk`, `linkedGroupName`, `path`, `mtime`, `sizeBytes`.
- `linkedGroup*` are resolved by querying the group model for the first row with `custom_cover_id == cover.pk` (typical case is one).
- Thumbnail URL is `/api/v3/custom_cover/{pk}/cover.webp` (existing).

Wire all four to a new sub-router in [`codex/urls/api/admin.py`](codex/urls/api/admin.py).

### Settings

[`codex/settings/__init__.py`](codex/settings/__init__.py):

- Add `CUSTOM_COVERS_UPLOADS_DIR = CUSTOM_COVERS_DIR / "uploads"`. Auto-create at startup.
- Add `CUSTOM_COVERS_MAX_UPLOAD_MB` from `codex.toml` `custom_covers.max_upload_mb` (default 10). Derive `CUSTOM_COVERS_MAX_UPLOAD_BYTES`.
- Delete `CUSTOM_COVERS_GROUP_DIRS` and `create_custom_cover_group_dirs()` once migration code stops referencing them.

### Frontend

**Card menu** ([`browser-card-menu.vue:14-18`](frontend/src/components/browser/card/browser-card-menu.vue)):

- Two new admin-only items beneath the existing three:
  - `UploadCoverButton` (new) — opens a hidden `<input type="file" accept="image/*">`; on file select, POST as multipart to `/admin/custom-cover` with `group` and `pks` from the card's item.
  - `RemoveCoverButton` (new) — only rendered when `item.coverCustomPk` is set; small confirm dialog; POST to `/admin/custom-cover/remove`.
- Gate the whole admin block with `useAuthStore().isUserAdmin`.
- Suppress for cards whose group is `c` (Comic) or `r` (Root) — `{p, i, s, v, a, f}` get the option.

**Cover cache bust**: when upload succeeds, mutate the matching `book` in `useBrowserStore().page.books`: set `coverCustomPk = response.customCoverPk` and bump a per-card cache key (or the existing `mtime`) so `getCoverSrc()` produces a fresh URL. The 202-polling loop in `BookCover` then picks up the new thumbnail.

**New API client**: `frontend/src/api/v3/admin-custom-cover.js`:
- `uploadCustomCover({ group, pks, file })` — builds `FormData`, POSTs. xior + CSRF middleware already work for `FormData` ([`api/v3/base.js:31-54`](frontend/src/api/v3/base.js)).
- `removeCustomCover({ group, pks })` and `deleteCustomCover(pk)`.
- `listCustomCovers()` for the admin tab.

**New admin tab "Custom Covers"**:

- Add `"Custom Covers"` to the `TABS` constant in [`frontend/src/stores/admin.js:28-36`](frontend/src/stores/admin.js). Order: between Libraries and Flags.
- Add route to [`frontend/src/plugins/router.js:43-60`](frontend/src/plugins/router.js): `/admin/custom-covers`.
- Create `frontend/src/components/admin/tabs/custom-covers-tab.vue` — wraps `AdminTable` with columns:
  - Thumbnail (v-img, 80×120, src = `/api/v3/custom_cover/{pk}/cover.webp`)
  - Group (chip with character label P/I/S/A/F mapped to full name)
  - Linked To (name of the linked Publisher/Imprint/Series/StoryArc/Folder)
  - Modified
  - Actions (delete via existing `AdminDeleteRowDialog` pointed at `CustomCover` table)
- Add `customCovers: []` to admin store state; add CustomCover descriptor in [`codex/urls/api/admin.py:25-55`](codex/urls/api/admin.py) so `loadTable("CustomCover")` works through the existing store machinery.
- Delete `frontend/src/components/admin/tabs/custom-covers-panel.vue` and its embed in [`library-tab.vue:19,35,46`](frontend/src/components/admin/tabs/library-tab.vue).
- Delete the `normalLibraries` / `customCoverLibraries` getters and the `coversDir` plumbing in [`library-table.vue:112-259`](frontend/src/components/admin/tabs/library-table.vue) — there are no covers libraries anymore, so the libraries table just shows `this.libraries`.

### Tests

Backend:
- `tests/views/admin/test_custom_cover_upload.py` (new): happy path, non-admin 403, oversize 400, non-image 400, group/pk mismatch 400. Mock the librarian queue.
- `tests/views/admin/test_custom_cover_remove.py` (new): unset FK, delete file + thumb + row when last reference drops.
- `tests/views/admin/test_custom_cover_list.py` (new): listing returns linked group name.
- `tests/migrations/test_migrate_filesystem_custom_covers.py` (new): tmp config dir with pre-existing `CustomCover` rows in legacy locations; run data migration; assert files moved, paths updated, library row deleted.
- Update or delete `tests/test_fs_filters_ignore.py` and `tests/test_snapshot_diff.py` to drop `covers_only` arguments.

Frontend:
- vitest spec for card menu admin gate and the upload/remove handlers (xior mocked).
- vitest spec for the new admin tab listing.

## Files to modify

**Backend (modify):**
- `codex/models/paths.py` — add `V` to `GroupChoices`; `_set_group_and_sort_name` no-op for uploads; remove `FOLDER_COVER_STEM`, `DIR_GROUP_CHOICE_MAP` post-migration.
- `codex/models/groups.py` — drop `Volume.custom_cover = None` override.
- `codex/models/library.py` — remove `covers_only`, `CUSTOM_COVERS_DIR_DEFAULTS`.
- `codex/librarian/scribe/importer/const.py` — add Volume to `CLASS_CUSTOM_COVER_GROUP_MAP`.
- `codex/views/browser/annotate/cover.py` — drop the Volume short-circuit in `_cover_custom_subquery`.
- `codex/serializers/admin/libraries.py` — drop `covers_only` from fields.
- `codex/settings/__init__.py` — add uploads dir & max-upload setting; drop group-dir auto-create.
- `codex/views/admin/library.py` — remove covers_only annotation/guards/filter.
- `codex/views/admin/custom_cover.py` — **new**.
- `codex/views/browser/browser.py` — drop covers_only filter in `libraries_exist`.
- `codex/urls/api/admin.py` — wire CustomCover ViewSet + endpoints.
- `codex/startup/__init__.py` — remove `init_custom_cover_dir`, `update_custom_covers_for_config_dir`; add `migrate_filesystem_custom_covers` step.
- `codex/librarian/fs/filters.py` — delete `match_group_cover_image`, `match_folder_cover`.
- `codex/librarian/fs/poller/poller.py`, `poller/snapshot.py` — drop covers_only.
- `codex/librarian/fs/watcher/watcher.py`, `watcher/events.py`, `watcher/dirs.py` — drop covers_only.
- `codex/librarian/scribe/importer/link/covers.py` and adjacent query/create/move/delete for CustomCover — delete the watcher-driven path; keep `CoverCreateTask`/`CoverRemoveTask` orchestration unchanged.
- `codex/librarian/scribe/timestamp_update.py` — drop covers_only filter.
- `codex/librarian/scribe/janitor/adopt_folders.py`, `janitor/failed_imports.py` — drop covers_only filter.
- `codex/librarian/telemeter/stats.py` — drop covers_only special-case.

**Backend (delete):**
- `codex/startup/custom_cover_libraries.py`.

**Backend (new):**
- `codex/migrations/00XX_customcover_library_nullable.py` (AlterField), plus `AddField` `Volume.custom_cover` and `AddField` `CustomCover.GroupChoices V`.
- `codex/migrations/00XY_migrate_custom_covers.py` (data migration).
- `codex/migrations/00XZ_drop_covers_only.py` (RemoveField).

**Frontend (modify):**
- `frontend/src/components/browser/card/browser-card-menu.vue` — admin-only upload/remove items.
- `frontend/src/stores/admin.js` — add "Custom Covers" to TABS, add `customCovers` state, drop `normalLibraries`/`customCoverLibraries` getters.
- `frontend/src/stores/browser.js` — small helper to bust a card's cover URL.
- `frontend/src/plugins/router.js` — add `/admin/custom-covers` route.
- `frontend/src/components/admin/tabs/library-tab.vue` — drop embedded custom-covers panel.
- `frontend/src/components/admin/tabs/library-table.vue` — drop `coversDir` prop and branching.

**Frontend (new):**
- `frontend/src/components/browser/card/upload-cover-button.vue`.
- `frontend/src/components/browser/card/remove-cover-button.vue`.
- `frontend/src/components/admin/tabs/custom-covers-tab.vue`.
- `frontend/src/api/v3/admin-custom-cover.js`.

**Frontend (delete):**
- `frontend/src/components/admin/tabs/custom-covers-panel.vue`.

## Verification

1. **`make fix && make lint && make ty`** clean.
2. **`make test`** — new backend tests for upload/remove/list/migration pass; updated `test_fs_filters_ignore.py` and `test_snapshot_diff.py` pass without `covers_only` args; new frontend vitests pass.
3. **Manual end-to-end**:
   - Pre-seed: drop a `config/custom-covers/publishers/Marvel.jpg`, a `config/custom-covers/series/Watchmen.jpg`, and a `.codex-cover.jpg` inside a library folder. Boot once with the *current* code so the legacy rows exist.
   - Switch to the new branch and boot. Confirm the data migration moved all three files to `config/custom-covers/uploads/{pk}-p-marvel.jpg` etc., paths in the DB updated, group FKs still resolve, cards render the correct covers, the singleton library row is gone.
   - As a non-admin user: confirm no Upload/Remove items on card menus.
   - As admin: on a Series card without a custom cover, click ⋮ → Upload Cover, pick a JPEG. Card thumbnail updates within a few seconds.
   - Confirm on disk: `uploads/{pk}-s-{slug}.jpg` exists; `cache/custom-covers/...` has a fresh `.webp`; `Series.custom_cover_id` points to the new row.
   - Click ⋮ → Remove Cover → confirm. Card reverts to derived cover; files and row are gone; FK is null.
   - Repeat for Publisher, Imprint, Volume, StoryArc, Folder.
   - Oversize upload → clean error toast, no partial file in `uploads/`.
   - Navigate to `/admin/custom-covers` → table shows every cover with thumbnail + linked group + delete button. Delete one → row + file + thumb gone; corresponding card reverts.
4. **Regression**: confirm normal libraries still poll/watch and import comics correctly with no `covers_only` plumbing. Run `make test` covering filesystem watcher tests.

## Out of scope

- Comic-level cover overrides (group `c`). The Comic model also has `custom_cover = None` overriding the inherited FK; supporting it would require additionally annotating `cover_custom_pk` in the Comic branch of [`annotate/cover.py:99-102`](codex/views/browser/annotate/cover.py) and a separate UX decision about overriding the archive-extracted cover. Doable later if desired.
- Bulk upload from the admin tab (delete-only there in this pass).
- Cover cropping, positioning, priority ordering.
