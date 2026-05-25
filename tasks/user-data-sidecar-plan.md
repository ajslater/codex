# User Data Sidecar (Corruption-Survivable User Settings)

## Context

The main SQLite database (`db.sqlite3`) can be corrupted by power loss, mid-write
kills, network filesystem flakiness, and general user misbehavior. The current
recovery path is "delete the database and re-import," which is fast for comic
metadata (filesystem scan + comicbox parse) but destroys all user data:
accounts, bookmarks, favorites, browser settings, admin flags, library
definitions, custom-tagging defaults.

Users keep getting hurt by this. We need user data to survive a main-DB
rebuild.

Two architectures were considered:

1. **Split into two databases.** Django supports multi-DB routing, but does
   *not* support cross-DB foreign keys. `Bookmark.comic` (FK → Comic) and
   `Favorite.target_id` (polymorphic FK → BrowserGroupModel/Comic/StoryArc)
   and `SettingsBrowserFilters.*` (lists of tag PKs) would all need
   denormalization anyway. We'd pay denormalization cost *and* take on
   permanent router/query complexity.
2. **Sidecar write-through DB.** Mirror user-data writes to a separate
   SQLite file in `/config/` keyed by stable identifiers (username, comic
   path, group name-chain, tag names). Main DB stays a single, normalized,
   FK-rich Django ORM. Sidecar is denormalized and write-only from the
   app's perspective — read only on restore.

This plan implements option 2.

## Decisions

1. **Storage**: a SQLite file at `/config/user_data.sqlite`, schema owned by
   this feature (not a Django app — see Architecture). Codex 1.x users will
   get one auto-created on first user-data write after upgrade.
2. **Write path**: Django `post_save` / `post_delete` signals on the tracked
   models mirror the row into the sidecar, with FKs and tag PKs replaced by
   stable identifiers at write time. Signal handlers are best-effort —
   sidecar failure logs a warning but never raises into the main request /
   librarian path.
3. **Stable identifier for comics**: `Comic.path`. There is no content hash
   in the schema today, and adding one is a separate (larger) project. Path
   is what the librarian already uses for upsert.
4. **Stable identifier for browsable groups**: a `(group_char, name_chain)`
   tuple — e.g. Series is `("s", publisher_name, imprint_name, series_name)`,
   Volume is `("v", publisher_name, imprint_name, series_name, volume_name)`,
   Folder is `("f", path)`, StoryArc is `("a", name)`, Publisher is
   `("p", name)`, Imprint is `("i", publisher_name, name)`, Comic is
   `("c", path)`.
5. **Stable identifier for tag/filter PKs**: `(tag_table, tag_name)`. The
   filter JSONField columns get rewritten on sidecar write from `[pk, pk]`
   to `[name, name]`, and reverse-resolved on restore.
6. **Restore is opt-in and idempotent.** A `codex restore_user_data`
   management command + admin button. Detects sidecar at startup if main
   DB is empty/fresh and prompts. Logs every unmatched row (comic deleted,
   tag renamed) without aborting.
7. **No automatic restore on startup.** Too magical, too easy to clobber
   intentionally-blank installs. Always user-triggered.
8. **Sidecar is also the migration/backup file.** Same file users can
   download from admin and carry to a new host or stash offsite.
9. **Out of scope for this plan**: encrypting the sidecar (passwords are
   hashed already), versioning the sidecar schema across codex upgrades
   (will add a `schema_version` table from day one, but migration logic
   waits until we actually need to break the schema).

## Architecture

### Why not a second Django app / second DB router

A Django multi-DB setup forces the sidecar to know about every model. We'd
have to maintain shadow models, a router, and migrations against the
sidecar — and we'd still have to denormalize because cross-DB FKs aren't
supported. The sidecar is conceptually a *backup log*, not a peer
database. Treating it as a hand-rolled SQLite file with its own schema
(via `sqlite3` stdlib or a thin wrapper) keeps the boundary clean.

### Sidecar location and lifecycle

- Path: `${CODEX_CONFIG_DIR}/user_data.sqlite`. Sits alongside `codex.toml`.
- Created lazily on first write. PRAGMAs at open: `journal_mode=WAL`,
  `synchronous=NORMAL` (matches main DB), `foreign_keys=OFF` (sidecar has
  no FKs — that's the point).
- Single writer: a dedicated thread or queue inside the existing librarian
  process. Web request signals enqueue; the writer drains. This isolates
  sidecar I/O from request latency and avoids cross-process SQLite
  contention.
- A `schema_version` table with a single row. Bumped manually when we
  break the schema; no auto-migration yet.

### Signal wiring

For each tracked model, a `post_save` and `post_delete` signal handler
serializes the row into a sidecar-shaped dict and enqueues a write. Signal
handlers live in a new `codex/user_data/signals.py` module loaded from
`AppConfig.ready()`.

Tracked models (definitive list — see Denormalization Mapping below for
the per-model shape):

- `User` (and any custom user model under `settings.AUTH_USER_MODEL`)
- `Group` (Django auth Group, for permissions)
- `Bookmark`
- `Favorite`
- `SettingsBrowser` + `SettingsBrowserFilters` + `SettingsBrowserLastRoute`
  + `SettingsBrowserShow` (only the user-bound rows; the shared
  `SettingsBrowserShow` flag combos are derivable)
- `AdminFlag`
- `ComicboxTaggingDefaults`
- `Timestamp` (so post-rebuild we don't re-run one-shot migrations)
- `Library` (path + admin-set fields; the rebuild needs these to know
  where to scan)
- `UserAuth` / `GroupAuth` (per-library access grants)
- `CustomCover` (if present post the custom-covers PR — pk-keyed, but
  the file lives on disk; sidecar stores the metadata + linked group
  identifier)

Explicitly *not* tracked (derivable from filesystem + comicbox parse):
all of `Comic`, `Publisher`, `Imprint`, `Series`, `Volume`, `Folder`,
`StoryArc`, `Identifier`, `Credit`, `Character`, `Genre`, `Language`,
`Country`, `Location`, `OriginalFormat`, `ScanInfo`, `SeriesGroup`,
`Story`, `Tag`, `Tagger`, `Team`, `Universe`, `AgeRating`,
`AgeRatingMetron`, `ComicFTS`, `LibrarianStatus`.

### Denormalization Mapping

| Main model | Sidecar table | Key columns | Denormalized refs |
|---|---|---|---|
| `User` | `users` | `username` | password hash, is_staff, is_superuser, email, date_joined, last_login |
| `Group` | `groups` | `name` | permissions list (as `(app_label, codename)` pairs) |
| `User.groups` | `user_groups` | `(username, group_name)` | — |
| `Library` | `libraries` | `path` | poll, watch, events, last_poll, groups (group names) |
| `UserAuth` | `user_auth` | `(username, library_path)` | — |
| `GroupAuth` | `group_auth` | `(group_name, library_path)` | — |
| `Bookmark` (user-bound rows only; session-only rows skipped) | `bookmarks` | `(username, comic_path)` | page, finished |
| `Favorite` | `favorites` | `(username, group_char, identifier_json)` | — |
| `SettingsBrowser` | `settings_browser` | `(username, client)` | most scalar columns inline; show flags as `(p,i,s,v)` tuple |
| `SettingsBrowserFilters` | `settings_filters` | FK to `settings_browser.id` | scalar filters inline; list-of-PK JSONFields rewritten to list-of-names per tag table |
| `SettingsBrowserLastRoute` | `settings_last_route` | FK to `settings_browser.id` | `group`, `pks` (rewritten to identifier tuples per group char), `page` |
| `AdminFlag` | `admin_flags` | `key` | `on` |
| `ComicboxTaggingDefaults` | `tagging_defaults` | singleton | all scalar columns inline |
| `Timestamp` | `timestamps` | `key` | value |
| `CustomCover` | `custom_covers` | `(group_char, identifier_json)` | file path under `/config/custom-covers/uploads/` |

`identifier_json` is the JSON-serialized name-chain tuple from Decision 4.

### Restore path

`codex restore_user_data [--from PATH] [--dry-run]`:

1. Open the sidecar read-only.
2. For each table in dependency order (groups → users → user_groups →
   libraries → user_auth/group_auth → admin_flags/timestamps/tagging
   defaults → bookmarks → favorites → settings → custom_covers):
   a. Resolve each denormalized reference against the current main DB.
   b. Upsert into the main DB.
   c. Log unmatched rows to `restore_user_data.log` in the config dir.
3. Report counts: restored, updated, unmatched.

`--dry-run` produces the same log without writing.

Admin UI button surfaces the same command and tails the log.

### Backwards compatibility

- Codex installs with existing main DBs but no sidecar: the first
  user-data write after upgrade creates the sidecar and backfills with
  the current main-DB state in a single pass. A single startup task
  added to the librarian.
- Codex upgrades that change a tracked model's schema: the sidecar
  schema bumps `schema_version`; the next backfill rewrites affected
  tables. (For this plan: no breaking schema changes assumed; backfill
  on first write only.)

## Phases

### Phase 1 — Sidecar plumbing (no behavior change)

- `codex/user_data/store.py`: open/close, PRAGMAs, schema creation,
  write queue, drain thread (or reuse `BookmarkThread` infrastructure).
- `codex/user_data/schema.sql`: table definitions per the mapping above.
- Wire `AppConfig.ready()` to open the store on startup.

### Phase 2 — Signal mirroring

- `codex/user_data/signals.py`: `post_save`/`post_delete` handlers per
  tracked model. Serializers per model that resolve FKs to stable
  identifiers at write time.
- `codex/user_data/backfill.py`: one-shot full dump from main DB. Runs
  automatically the first time the store opens against an empty
  sidecar.
- Tests: signal-fires-once, FK-resolution, idempotent backfill, malformed
  row tolerance.

### Phase 3 — Restore command + admin surface

- `codex/management/commands/restore_user_data.py`.
- Resolver per stable identifier: comic path → Comic, name-chain →
  group, tag name → tag PK.
- Admin endpoint + Vue button under the existing admin "Tasks" or
  "Libraries" pane (TBD with design).
- Tests: round-trip (export → wipe main DB → restore → diff), missing
  comic, renamed tag, missing user.

### Phase 4 — Documentation & polish

- README + admin UI copy explaining the file, where it lives, and how
  to use it for host migration.
- Optional: surface "last sidecar write" timestamp in the admin status.

## Open Questions

1. **Sidecar write thread vs. signal-synchronous write.** Synchronous is
   simpler but couples user-data write latency to sidecar I/O. Queue +
   drain thread is more robust under load. Lean queue, but worth
   confirming we want the extra thread.
2. **CustomCover sidecar coverage** depends on whether
   `tasks/custom-covers-plan.md` lands first. If it does, sidecar
   tracks the new pk-keyed uploads table; if not, the legacy
   filesystem-watched scheme means user covers are already on disk and
   already survive rebuild — sidecar can skip CustomCover entirely
   in v1.
3. **Tag-PK denormalization in `SettingsBrowserFilters`** is the
   trickiest piece. Each filter JSONField has a different tag table
   behind it (characters → Character, credits → Credit, genres →
   Genre, etc.). A single dispatch map keyed on filter column → tag
   model resolves this; needs care to stay aligned with the existing
   `FILTER_KEYS` set in `codex/models/settings.py:245`.
4. **Session-only bookmarks** (anonymous users) — proposal is to
   *not* mirror these. They're ephemeral by design. Confirm.
5. **Library `groups` field** — `Library` has a many-to-many to
   `auth.Group`? Need to confirm the exact shape before finalizing
   the `libraries` sidecar schema.

## Non-Goals

- Real-time replication or HA. The sidecar is a recovery aid, not a
  hot standby.
- Two-way sync. The sidecar is write-through one-way (main → sidecar)
  during normal operation, and read-only during restore. No
  conflict-resolution logic.
- Encryption. Passwords are already hashed in the source rows.
- Schema migration across codex versions. Deferred until we actually
  break a sidecar table.
