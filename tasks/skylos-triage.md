# Skylos triage report

Triage of the 147 findings from `skylos --confidence 61` on this branch.
Scope is dead-code only; noise/false-positive analysis is the bulk of this
report, followed by real cleanup candidates.

## TL;DR

- **~133 of 147 are false positives** — skylos misses three pervasive
  patterns: DRF metaclass field assignment, Django `getattr`-by-name
  framework hooks, and string-name dispatch tables.
- **~14 items are real**: 1 dead class, 6 dead/abandoned methods, 5
  abandoned model-field declarations, 1 abandoned choices alias, 1
  abandoned helper.
- A handful of the "real" items are leftovers from refactors and would
  shrink with a single targeted PR.

## Skylos configuration changes already applied

Applied on this branch:

- `bin/lint-python.sh` invocation is now
  `skylos --no-upload --confidence 61 --category dead_code --no-provenance .`
  - `--category dead_code` drops circular-dep / quality / provenance
    sections from the report (~37s → ~20s).
  - `--no-provenance` skips the AI-authorship git-log scan (~20s → ~16s).
**Pitfall to know about**: I tried extending `[tool.skylos.masking].bases`
to cover the full thread hierarchy (`NamedThread`, `QueuedThread`, …)
since skylos's mask matcher only inspects direct base names. The result
was *worse*: 143 findings → 208 findings. Masking replaces a class body
with `pass`, which deletes the *outgoing* reference edges from that
body — so symbols those bodies used to reference now look unreferenced.
Conclusion: keep the masking list narrow, and prefer the whitelist for
specific framework-method names.

## Configuration changes still recommended

Skylos has no built-in awareness of:
1. **DRF Serializer field assignment**: `name = CharField(...)` inside a
   `Serializer` body. The `Serializer` masking *does* mask the body but
   skylos still reports the *imported field types* as unused (it walks
   imports independently of the masked AST). This drives ~83 of the
   "unused import" findings.
2. **Django framework class attributes** read via `getattr`:
   `lookup_field`, `default_code`, `default_detail`, `view_is_async`,
   `sync_capable`, `async_capable`, `keyword`, `charset`, `render_style`,
   `content_negotiation_class`, `prepare_rhs`.
3. **String-name dispatch tables** like `_JANITOR_METHOD_MAP`,
   `_PUBLICATION_METHOD_KEYS`, `_PRE_PHASES`, etc. that resolve via
   `getattr(self, name)`.

The pragmatic fix is to extend `[tool.skylos.whitelist].names` and
`[tool.skylos.masking].bases`. Recommended additions (each represents one
of the categories above; pick the ones whose noise actually bothers you):

```toml
[tool.skylos.whitelist]
names = [
  # … existing
  # Django DB-router protocol
  "db_for_read", "db_for_write", "allow_relation", "allow_migrate",
  # Django URL-converter protocol
  "to_python", "to_url",
  # DRF serializer "validate_<field>" methods (skylos does not match this)
  "validate_*",
  # DRF/Django framework class attributes
  "lookup_field", "default_code", "default_detail",
  "view_is_async", "sync_capable", "async_capable",
  "keyword", "charset", "render_style", "content_negotiation_class",
  "prepare_rhs",
  # Janitor task dispatch (string-name table)
  "vacuum_db", "cleanup_fks", "cleanup_custom_covers",
  "cleanup_sessions", "cleanup_orphan_bookmarks", "cleanup_orphan_settings",
  "force_update_all_failed_imports", "foreign_key_check",
  "fts_integrity_check", "fts_rebuild", "queue_nightly_tasks",
  # Importer phase dispatch
  "init_apply", "move_and_modify_dirs", "fail_imports", "full_text_search",
  # OPDS2 _publication_* getattr dispatch
  "_publication_identifier", "_publication_belongs_to",
  # Thread public hooks (when masking misses them)
  "wake", "poll", "restart",
]
```

If we don't want to pollute the whitelist with this volume, the
alternative is a few targeted `# skylos: ignore` comments per file —
but the patterns above repeat across many files, so the central
whitelist is lower-cost.

## False positives, by pattern (~133 findings)

| Pattern | Count | Why skylos misses it |
|---|---:|---|
| DRF field-class imports used as serializer class attributes | ~75 | Skylos walks imports independently of masked class bodies |
| Django framework class attributes read via `getattr` | 10 | `lookup_field`, `default_code`, etc. — no AST reference |
| DRF Serializer field declarations (e.g. `series_volume_count = IntegerField(...)`) | 12 | `Serializer`-body masking suppresses the inner def, but the *attribute* is still tracked |
| Django DB-router protocol methods (`SilkRouter`) | 4 | Registered via `DATABASE_ROUTERS = ["codex.db_routers.SilkRouter"]` string |
| Django URL converter protocol methods (`IntListConverter.to_python/to_url`) | 2 | Registered via `register_converter(IntListConverter, "int_list")` |
| Janitor task dispatch via `_JANITOR_METHOD_MAP` (string-name table) | ~9 | `getattr(self, method_name)` |
| OPDS2 `_publication_*` dispatch via `_PUBLICATION_METHOD_KEYS` | 2 | `getattr(self, f"_publication_{key}")` |
| Importer phase dispatch via `_PRE_PHASES` / `_PER_COMIC_PHASES` / `_POST_PHASES` | 1 | `getattr(self, name)` |
| Django ORM `Func`/`Lookup` registration (`FTS5Match`, `Like`) | 2 | Registered via `@CharField.register_lookup` decorator |
| DRF `validate_<field>` protocol method (`validate_path`) | 1 | DRF resolves by name |
| DRF Serializer subclasses referenced compositionally | 5 | `IdentifierSourceSerializer`, `StoryArcSerializer`, etc. — used as nested fields by the framework |
| Django Settings model fields used by API serializers | 5 | `two_pages`, `read_rtl_in_reverse`, `finish_on_last_page`, `page_transition`, `cache_book` — declared on the model, serialized in `codex/serializers/reader.py`, defaults in `codex/choices/reader.py`, telemeter reads in `codex/librarian/telemeter/stats.py` |
| Underscore-prefixed unpacking discards (`_dirnames`, `_parent`, `_changes`) | 3 | Intentional throwaway — skylos treats `_`-prefix the same as any other |
| Type-checking-only imports (`Queue`, `Logger` in `codex/librarian/threads.py`) | 2 | Behind `if TYPE_CHECKING:` — skylos misses TYPE_CHECKING gates |

## Likely real dead code (remove)

| File:line | Symbol | Notes |
|---|---|---|
| [codex/models/fields.py:58](codex/models/fields.py:58) | `CoercingSmallIntegerField` | Sibling `CoercingPositiveSmallIntegerField` is the only one used (in `comic.py`, `groups.py`, `named.py`). The non-Positive form has zero refs. |
| [codex/librarian/scribe/importer/init.py:89](codex/librarian/scribe/importer/init.py:89) | `Counts.search_changed` | No callers. Sibling `.changed()` is used in `finish.py:63`. Looks like an early API surface that never got wired up. |
| [codex/librarian/scribe/importer/query/links_fk.py:17](codex/librarian/scribe/importer/query/links_fk.py:17) | `QueryPruneLinksFKs.pop_links_to_fts` | No callers. |
| [codex/librarian/scribe/importer/query/update_fks.py:70](codex/librarian/scribe/importer/query/update_fks.py:70) | `_query_normalize_existing_values` | No callers (private helper). |
| [codex/librarian/scribe/importer/search/sync_m2m.py:29](codex/librarian/scribe/importer/search/sync_m2m.py:29) | `_to_fts_str` | No callers (private static helper). |
| [codex/librarian/scribe/search/remove.py:50](codex/librarian/scribe/search/remove.py:50) | `SearchIndexerRemove.remove_duplicate_records` | No callers. Sibling `remove_stale_records` is used. |
| [codex/views/reader/settings.py:85](codex/views/reader/settings.py:85) | `ReaderSettingsBaseView._get_bookmark_auth_filter` | The class also calls `self.get_bookmark_auth_filter()` (no leading underscore) inherited from `BookmarkAuthMixin`. The underscore variant is a refactor leftover. |
| [codex/views/opds/v1/facets.py:120](codex/views/opds/v1/facets.py:120) | `OPDS1FacetsView._is_facet_active` | The neighboring `_facet_or_facet_entry` carries the comment `"This logic preempts facet:activeFacet but no one uses it."` — entire facet:activeFacet feature is abandoned. |
| [codex/models/age_rating.py:127](codex/models/age_rating.py:127) | `allowed_ratings_for` | No callers. |
| [codex/models/choices.py:47](codex/models/choices.py:47) | `text_choices_from_string` | No callers. (Sibling `text_choices_from_enum` is used.) |

Total: **10 functions/classes that look genuinely removable.** None are
public API of the wheel — all are internal.

## Abandoned but possibly worth restoring

| File:line | Symbol | Why I think it's abandoned, not dead |
|---|---|---|
| [codex/models/choices.py:63](codex/models/choices.py:63) | `MetronAgeRatingChoices` | Sibling pattern: `FileTypeChoices` is wired to `Comic.file_type`'s `choices=`, `ReadingDirectionChoices` to `Comic.reading_direction`'s `choices=`. `MetronAgeRatingChoices` is built from `MetronAgeRatingEnum` but never assigned to any field. Probably meant for `Comic.age_rating` — `MetronAgeRatingEnum` itself is referenced in [codex/migrations/0039_metron_age_rating_default_view_and_performance.py](codex/migrations/0039_metron_age_rating_default_view_and_performance.py), suggesting the migration landed but the `choices=` wiring was dropped. **Worth restoring** if Metron ratings should be enforced as choices on the `age_rating` field. |
| [codex/librarian/fs/poller/poller.py:50](codex/librarian/fs/poller/poller.py:50) | `LibraryPollerThread.wake()` | Comment block above it reads `# Public interface - called from librariand`. `librariand.py` imports `LibraryPollerThread` but never calls `.wake()`. Either the call site got refactored away, or the wake-on-config-change path was never finished. **Worth checking** whether library config changes currently trigger a re-poll — if not, this method should be wired up to the admin-flag write path. |

## Settings-model fields skylos flags (false positives — context for future maintainers)

These five fields on `SettingsReader` are flagged as unused vars but are
in active use through Django's metaclass + DRF + frontend defaults:

- `two_pages`, `read_rtl_in_reverse`, `finish_on_last_page`,
  `page_transition`, `cache_book`
- Declared in [codex/models/settings.py:429-439](codex/models/settings.py:429)
- Serialized in [codex/serializers/reader.py:33](codex/serializers/reader.py:33)
- Defaults in [codex/choices/reader.py:27-32](codex/choices/reader.py:27)
- One (`finish_on_last_page`) is read by the telemeter
  ([codex/librarian/telemeter/stats.py:38](codex/librarian/telemeter/stats.py:38))

If you ever DO suppress them, prefer the `Model` masking approach (mask
`Model` base class) rather than naming them in the whitelist —
otherwise unrelated future fields could regress unnoticed.

## Suggested next step

Before tightening the skylos config further, drop the obvious dead code
in one PR (the 10 items in §4), since most of the remaining noise after
that will be the framework-pattern false positives — and those are best
addressed via the central whitelist additions in §2 rather than
investigating each one again.
