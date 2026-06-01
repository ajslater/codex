# Handoff: finish the `group`→`collection` rename — the engine `kwargs` nav key

**Start state:** clean + green at commit `e75e3929` (backend 405 / vitest 99 /
ty unchanged). Everything user-visible is already renamed — the entire **wire
surface, all 4 DB columns, and the whole code vocabulary** say `collection`
(`Group`→`Collection` enum, `COLLECTION_*` constants, `BrowserCollectionModel`,
`top_collection`, the browse-item field, reader-arc, the shared mixin field,
`model_collection`). See `tasks/group-to-collection-rename-plan.md` for the done
list. This handoff covers the **one remaining piece**: the engine's internal
`group` nav key.

## What's left (and why it's the last piece)

The browse/reader/OPDS engine threads the current nav level as `group` in three
coupled forms:

1. **`kwargs["group"]`** — the per-request nav key. Set by `AuthMixin`, read by
   ~50 sites (`self.kwargs["group"]` / `.get("group")`).
2. **Route-mask dicts** `{"group": …, "pks": …, "page": …}` (~32 literals) —
   redirect targets, OPDS link kwargs, breadcrumb inputs.
3. **`Route` dataclass** (`codex/views/util.py`, fields `group`/`pks`) +
   `RouteSerializer` INPUT field + the `mtime`/`cover` consumers that read the
   validated `{group, pks}`.

It is **invisible**: the route *output* wire is already `{collection, parentIds}`
(from the dual-dialect collapse), so renaming the internal key changes no
contract. That's why it was deferred — pure internal consistency.

## ⚠️ Why the bulk attempt failed (do not repeat)

A `perl s/kwargs\["group"\]/kwargs["collection"]/` pass broke OPDS + favorites.
**Root cause:** these three forms are ONE coupled unit, and the reverse helper
hard-codes the old name:

- `codex/views/opds/route.py:56-57` `opds_feed_reverse` does
  `if … and "group" in out_kwargs: group = out_kwargs.pop("group")`. The route
  masks feed this. If you rename the masks' key (or the kwargs that build them)
  without updating `opds_feed_reverse`, the `"group" in out_kwargs` test goes
  False → the collection-segment mapping is skipped → `reverse()` fails.
- The masks are built FROM the kwargs (e.g. `params.py:42
  {"group": self.kwargs.get("group", "r")}`), so renaming kwargs but not the
  mask key leaves a half-state.

**Lesson:** rename the kwargs nav key + the mask key + `opds_feed_reverse` + the
`Route` dataclass **as one atomic change**, then run the full suite and debug.
Incremental "one read at a time" does NOT work here because the coupling means
any partial state is broken.

## The coupled unit — exact inventory

**SET sites (5)** — these write the nav key:
- `codex/views/auth.py:134,136` — `AuthMixin._translate_browser_kwargs`
  (`kwargs["group"] = Collection.ROOT` / `= collection`). The keystone setter.
- `codex/views/favorites.py:55` — `self.kwargs["group"] = collection`
- `codex/views/admin/tagwrite.py:54` — `self.kwargs["group"] = group`
- `codex/views/browser/bookmark.py:92` — `self.kwargs["group"] = Collection.COMIC`

**READ sites (~50)** — `self.kwargs["group"]` / `self.kwargs.get("group")` across
`views/browser/*`, `views/reader/*`, `views/opds/*`. Bulk-renameable once the
setters + masks + reverse move with them.

**Route masks (~32)** — `{"group": …, "pks": …}` literals. Producers incl.
`page_in_bounds.py:22,29`, `validate.py:112`, `breadcrumbs.py:89`,
`opds/v2/feed/{groups,feed_links,publications}.py`, `opds/v1/entry/links.py:76`,
`opds/const.py` `TopRoutes`/`Facets`, `choices/browser.py` `DEFAULT_BROWSER_ROUTE`
+ `admin_default_route_for`, `urls/opds/*.py` defaults, `params.py:42`,
`reader/reader.py`, `settings.py` last-route, `user_data/restore.py:671`-area.

**The reverse + serializer:**
- `codex/views/opds/route.py` `opds_feed_reverse` — update the `"group"`/`"pks"`
  pop to `"collection"`/`"parent_ids"` (and `_collection_for` becomes near-identity
  since masks already hold collection values). Callers: `exceptions.py:95`
  (passes `self.route_kwargs`), `opds/metadata.py`, `opds/v1/links.py:41`,
  `opds/v1/entry/links.py:92`, `opds/v1/facets.py:85`, `opds/v1/entry/entry.py`,
  `opds/v2/href.py:55`.
- `codex/serializers/route.py` — the INPUT declared field is `group`/`pks`
  (the frontend mtime/parentRoute producers send those). `to_representation`
  already emits `collection`/`parent_ids`. `to_internal_value` produces
  `{group, pks}` read by `mtime.py` (`item["group"]`) + `cover.py`
  (`parent_route["group"]`).
- `codex/views/util.py` `Route` dataclass: fields `group`→`collection`,
  `pks`→`parent_ids`; `__hash__` reads them. Constructions in `breadcrumbs.py`
  are POSITIONAL (`Route(Collection.ROOT, (), 1, "")`), so the field rename
  doesn't break them — but `asdict(Route)` feeds `RouteSerializer.to_representation`,
  which must then read `instance["collection"]`/`["parent_ids"]`.

## 🚫 DO NOT rename (overloaded `"group"`)

- `codex/websockets/listener.py:22` `{"group": ChannelGroups.ALL}` — Channels group.
- `codex/librarian/notifier/notifierd.py:33` `{"group": task.group}` and
  `tasks.py:111,148` `group=f"user_{…}"` — task/channel routing.
- `task.group` everywhere (LazyImportComicsTask etc. — flipped to collection
  *values* already, but the attribute name is task-internal).
- Anything outside the browse/reader/OPDS engine.

## Bonus char vestiges to fix while here

- `codex/views/browser/params.py:42` `self.kwargs.get("group", "r")` — the `"r"`
  default is a leftover char; should be `Collection.ROOT` / `"root"`.
- Grep `"r"`/`"p"` near the mask defaults you touch.

## Recommended approach (atomic, guarded)

1. Decide whether to also do `pks`→`parent_ids` in the same pass. Recommended
   YES (they travel together in masks + `Route`), but it widens the diff.
2. In ONE branch, rename together: the 5 setters, the ~50 reads, the ~32 mask
   keys, `opds_feed_reverse` (+ simplify `_collection_for`), the `Route`
   dataclass, and `RouteSerializer.to_representation`'s instance reads. Keep the
   `RouteSerializer` INPUT field `group`/`pks` (frontend sends those) UNLESS you
   also flip the FE mtime/parentRoute producers + verify the GET-query-param
   camelization for `parent_ids` (a known wrinkle — query params aren't
   decamelized the way bodies are).
3. Use **perl** (`-pi -e`), macOS `sed` lacks `\b`. Scope by `kwargs\["group"\]`
   / `kwargs.get("group")` / `"group":` and EXCLUDE the protect list above.
4. Guard suite (run after the atomic change, then debug to green):
   `uv run pytest tests/test_opds_feed.py tests/test_favorites_api.py
   tests/test_breadcrumbs.py tests/test_reader.py tests/test_route_serializer.py
   tests/test_app_urls.py tests/test_lazy_import.py -q` then the full suite +
   `cd frontend && npx vitest run`.
5. The first failures will be `opds_feed_reverse` reverse mismatches and any
   mask producer/consumer you missed — chase each `NoReverseMatch` /
   `KeyError 'group'` to its set/read pair.

## Also remaining (smaller, independent)

- Frontend: `routeForGroup`/`groupForRoute` → `*Collection`,
  `liveBrowseParams().group`, the internal `{group, pks}` engine shape in
  `stores/browser.js` + `route.js`. Frontend-only; if you flip the
  `RouteSerializer` INPUT in step 2, the mtime/parentRoute producers move here.
- mtime endpoint field `groups` (and the admin-CustomCover list field kept via
  `source="collection"`; collapses once you flip the FE custom-cover form).
- The metadata `group` PROP name (carries a collection value; cosmetic).

If you only do ONE thing: the atomic engine-kwargs pass (step 2) is the
conceptually meaningful finish; everything else is cosmetic.
