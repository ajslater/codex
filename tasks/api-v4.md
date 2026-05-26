# Codex API v4 — Design & Migration Plan

REST v4 of the Codex API. Cleans up accumulated v3 cruft, standardizes
the wire format, fixes concrete frontend pain points, and adopts
JSON:API-style conventions where they fit (admin CRUD) while keeping
RPC-flavored "view" endpoints for the browser and reader where they're
the honest shape.

v3 stays alive during the migration. v4 is built behind a feature flag
and migrated one Pinia store at a time.

## Goals

- **Drop magic values from URLs.** No more `pks=0` for "root"; no more
  single-char group codes (`p/i/s/v/c/f/a`).
- **One round trip for layered settings.** Eliminate the per-scope fan-out
  in [frontend/src/stores/reader.js](frontend/src/stores/reader.js)
  (`loadAllSettings` → N calls).
- **Stop pivoting metadata on the client.** Ship credits and identifiers
  in the shape [frontend/src/stores/metadata.js](frontend/src/stores/metadata.js)
  consumes (role-pivoted credits, parsed identifier sources).
- **Kill the mtime two-step.** WebSocket payloads carry the new mtime
  and affected scope; frontend invalidates locally without a probe
  request. Drop the `GET /mtime` endpoint.
- **Bulk admin ops + patch-returns-row.** Stop the
  full-table refetch after every admin mutation
  ([frontend/src/stores/admin.js](frontend/src/stores/admin.js) lines 79-157).
- **Standardize the envelope.** `{data, meta, errors}` everywhere. Flat
  root, raw list, composite — pick one.
- **camelCase on the wire.** Drop the ad-hoc `username` ↔ `login`,
  `fitTo=null` ↔ `""` rewrites.
- **Cursor pagination for admin lists.** Page-number stays for paginated
  browser views (matches the existing UX).

## Pain Points Explicitly NOT Addressed

- **Filter dropdown lazy loading is correct.** Typical UX is 1-2 menus
  opened, so per-field `/choices/{field}` stays. No batching.
- **Cover/page binary endpoints stay REST.** No re-imagining.
- **OPDS stays on its own router.** Public protocol, separate concerns.

## Decisions

- **Path scheme:** Option A — collection segment, optional comma-list of
  parent IDs. Omitted segment means root. Parent *type* is implicit
  (each child collection has exactly one valid parent type today).
  Example: `/api/v4/browse/series` (root) vs
  `/api/v4/browse/series/5,7` (under publishers 5 and 7).
- **JSON:API for admin resources only.** Use
  `django-rest-framework-json-api` for `/api/v4/admin/{users,groups,
  libraries,flags,...}`. The wire format is JSON:API
  (`{data: {type, id, attributes, relationships}}`) with sparse
  fieldsets and includes.
- **Hand-rolled envelope for view endpoints.** Browser and reader
  responses use `{data, meta, errors}` with JSON:API's error object
  shape. Not full JSON:API — the composite payloads don't fit.
- **camelCase via DRF renderer (djangorestframework-camel-case or the
  JSON:API renderer's inflection).** Applied uniformly.
- **mtime invalidation:** push-based via WebSocket payloads.
  `GET /mtime` endpoint is removed. `HEAD` requests on view endpoints
  return an `ETag` for clients that want explicit validation.
- **Bookmark split:** `PATCH /comics/{id}/bookmark` for reader progress
  (single comic, `{page, finished}`); `PATCH /browse/{collection}/{ids}/bookmark`
  for bulk mark-as-read/unread from the browser.

## Open Questions

- Folder hierarchy: confirm that `/api/v4/browse/folders/{parentIds}`
  works for arbitrarily deep folder trees, or if folder browsing needs
  a different shape.
- Saved browser settings: per-collection or global? Today they live
  under `/<group>/settings/saved`. Keeping per-collection unless a
  reason surfaces.
- Whether to keep the `/reader/comics/{id}` composite view endpoint or
  encode it via `?include=prev,next,arc` on `/comics/{id}`. Leaning
  toward the explicit view endpoint — cleaner, matches `/browse/...`.
- Bootstrap call: should `GET /session` also return `opds-urls` and
  `version` so the SPA boots with one request?

---

## Conventions

| Aspect | Decision |
|---|---|
| Base path | `/api/v4/` |
| JSON casing | camelCase |
| Envelope (view endpoints) | `{data, meta: {mtime, pagination, searchError}, errors}` |
| Envelope (admin resources) | JSON:API: `{data: {type, id, attributes, relationships}, included, meta, errors}` |
| Errors | JSON:API error object shape (`status/code/title/detail/source`) |
| Pagination | Cursor (`?cursor=&limit=`) for admin lists; page number (`?page=N`) for paginated browser views |
| Sparse fields | `?fields=a,b,c` (top-level) — admin only initially |
| Includes | `?include=publisher,characters` — admin only initially |
| Cache validation | HTTP `ETag` / `If-None-Match`; `HEAD` returns just the validator |
| WebSocket | `/ws/v4/` with typed JSON messages, mtime + scope in payloads |
| Date/time fields | ISO-8601 strings; clients still use `Date.parse` |
| IDs in URLs | Integer or comma-separated integers. No magic `0` |

---

## URL Map

### Auth & session

```
POST   /api/v4/auth/register
POST   /api/v4/auth/login
POST   /api/v4/auth/logout
POST   /api/v4/auth/token
GET    /api/v4/auth/csrf                          # bootstrap cookie
GET    /api/v4/session                            # user + adminFlags + perms
GET    /api/v4/auth/profile
PATCH  /api/v4/auth/profile                       # name, timezone, email
POST   /api/v4/auth/password/reset                # request link
POST   /api/v4/auth/password/reset/confirm
POST   /api/v4/auth/password/change
```

### Browser (Option A — omit segment for root)

```
GET    /api/v4/browse/publishers
GET    /api/v4/browse/imprints[/{publisherIds}]
GET    /api/v4/browse/series[/{parentIds}]
GET    /api/v4/browse/volumes[/{seriesIds}]
GET    /api/v4/browse/comics[/{parentIds}]
GET    /api/v4/browse/folders[/{parentFolderIds}]
GET    /api/v4/browse/arcs[/{parentIds}]
```

Query params on all listing endpoints:
`?page=N&filters={…}&search=…&orderBy=…&orderReverse=true&columns=a,b,c`

Per-scope ops (share the same `[{parentIds}]` shape):

```
GET    /api/v4/browse/{collection}[/{parentIds}]/choices                # which fields have ≥1 result
GET    /api/v4/browse/{collection}[/{parentIds}]/choices/{field}        # values for one field (lazy)
GET    /api/v4/browse/{collection}[/{parentIds}]/metadata               # aggregated metadata panel
GET    /api/v4/browse/{collection}[/{parentIds}]/download/{filename}    # archive download
POST   /api/v4/browse/{collection}/{ids}/import                         # lazy import metadata
POST   /api/v4/browse/{collection}/{ids}/refresh                        # force tag update
PATCH  /api/v4/browse/{collection}/{ids}/bookmark                       # bulk mark read/unread
```

Browser settings (per top-level collection):

```
GET    /api/v4/browse/{collection}/settings
PATCH  /api/v4/browse/{collection}/settings
GET    /api/v4/browse/{collection}/saved-settings
POST   /api/v4/browse/{collection}/saved-settings
GET    /api/v4/browse/{collection}/saved-settings/{id}
PATCH  /api/v4/browse/{collection}/saved-settings/{id}
DELETE /api/v4/browse/{collection}/saved-settings/{id}
```

### Reader & comics

```
GET    /api/v4/reader/comics/{id}                 # comic + nav (prev/next/arc) — view endpoint
GET    /api/v4/comics/{id}                        # raw comic resource
GET    /api/v4/comics/{id}/pages/{n}              # page image
GET    /api/v4/comics/{id}/cover                  # cover image
GET    /api/v4/comics/{id}/download/{filename}
PATCH  /api/v4/comics/{id}/bookmark               # {page, finished}
```

Reader settings — layered in one call:

```
GET    /api/v4/reader/settings                    # global only
PATCH  /api/v4/reader/settings
GET    /api/v4/comics/{id}/reader-settings?scopes=global,comic,arc
PATCH  /api/v4/comics/{id}/reader-settings        # writes to comic scope
```

### Favorites

```
GET    /api/v4/favorites                          # all favorites by collection
PUT    /api/v4/favorites/{collection}/{id}        # idempotent add
DELETE /api/v4/favorites/{collection}/{id}
```

### Admin (JSON:API resources)

Standard CRUD per resource:

```
GET|POST                          /api/v4/admin/users
GET|PATCH|DELETE                  /api/v4/admin/users/{id}
POST                              /api/v4/admin/users/{id}/password
POST                              /api/v4/admin/users/bulk

GET|POST                          /api/v4/admin/groups
GET|PATCH|DELETE                  /api/v4/admin/groups/{id}

GET|POST                          /api/v4/admin/libraries
GET|PATCH|DELETE                  /api/v4/admin/libraries/{id}

GET                               /api/v4/admin/flags
GET|PATCH                         /api/v4/admin/flags/{key}

GET                               /api/v4/admin/failed-imports
GET                               /api/v4/admin/age-ratings
```

Custom covers:

```
GET|POST                          /api/v4/admin/custom-covers
DELETE                            /api/v4/admin/custom-covers/{id}
POST                              /api/v4/admin/custom-covers/bulk-delete
```

Singletons / config:

```
GET|PATCH                         /api/v4/admin/email-settings
POST                              /api/v4/admin/email-settings/test
GET|PATCH                         /api/v4/admin/tagging-defaults
POST                              /api/v4/admin/tagging-defaults/validate
GET|POST                          /api/v4/admin/api-key                  # POST = regenerate
GET                               /api/v4/admin/stats
```

Librarian tasks:

```
GET                               /api/v4/admin/tasks                    # ?include=history
POST                              /api/v4/admin/tasks
DELETE                            /api/v4/admin/tasks/{id}
```

Online tagging:

```
GET|POST                          /api/v4/admin/tag-sessions
GET|DELETE                        /api/v4/admin/tag-sessions/{id}        # DELETE = abort
POST                              /api/v4/admin/tag-sessions/{id}/skip-all
GET                               /api/v4/admin/tag-sessions/{id}/prompts
POST                              /api/v4/admin/tag-sessions/{id}/prompts/{fingerprint}
```

Misc admin actions:

```
POST                              /api/v4/admin/identifier-url           # parse
POST                              /api/v4/admin/tag-write/preflight
POST                              /api/v4/admin/tag-write
GET                               /api/v4/admin/folders?path=&showHidden=
POST                              /api/v4/admin/user-data/export
POST                              /api/v4/admin/user-data/import
```

### Utility

```
GET    /api/v4/version
GET    /api/v4/schema                  # OpenAPI 3
GET    /api/v4/opds-urls
GET    /api/v4/covers/{source}/{id}    # source = comic | series | publisher | custom
```

(`/mtime` is intentionally removed.)

---

## WebSocket (`/ws/v4/`) — typed messages

v3 sends bare strings (`"LIBRARY"`, `"COVERS"`, etc.) and the frontend
infers what to refetch. v4 carries enough payload that the frontend
can act without a probe round trip.

```ts
{ type: "library.changed", mtime: number, scope: { collection: string, parentIds: number[] } }
{ type: "task.progress",   taskId: string, status: string, progress?: number, libraryId?: number }
{ type: "admin.flags.changed", flags: AdminFlags }
{ type: "bookmark.changed", comicId: number, page: number, finished: boolean }
{ type: "session.ended" }                                 // forces logout
{ type: "tag-session.prompt", sessionId: string, prompt: TagPrompt }
{ type: "covers.changed", scope: { collection: string, ids: number[] } }
{ type: "failed-imports.changed" }
```

ACL still applies at the channel-group level (`ALL` / `ADMIN` /
`user_{uid}`). No client-side filtering of scope.

---

## Migration Phases

### Phase 1: Scaffolding

- [ ] Install `django-rest-framework-json-api`. Pin to a known-good
      version compatible with the project's DRF 3.16+.
- [ ] Add `codex/urls/api/v4/__init__.py` mounting `/api/v4/`.
- [ ] Add a feature flag (`ADMIN_FLAGS.api_v4` or env var) gating
      whether v4 routes are exposed. Default off.
- [ ] Add `codex/views/v4/` directory with empty `auth.py`, `browse.py`,
      `reader.py`, `admin.py`, `common.py`.
- [ ] Add `codex/serializers/v4/` mirroring the same structure.
- [ ] Configure DRF renderer chain: JSON:API renderer for admin
      endpoints, hand-rolled `{data, meta, errors}` renderer for view
      endpoints, camelCase inflection everywhere.
- [ ] Wire `/api/v4/version` as the first endpoint to validate the
      scaffold end-to-end.

### Phase 2: Session bootstrap & auth

- [ ] `GET /api/v4/session` — return `{user, adminFlags, permissions}`
      in one response. Replaces three v3 calls (`/auth/profile`,
      `/auth/flags`, plus any per-feature permission probes).
- [ ] Port the remaining `/api/v4/auth/*` endpoints. These can largely
      be thin wrappers around the v3 implementations with new envelope.
- [ ] Frontend: add `frontend/src/api/v4/` alongside v3. Start with an
      `auth.js` module that uses `/api/v4/session` and document the
      coexistence pattern.

### Phase 3: Browser view endpoints

- [ ] Implement Option A path routing for `/api/v4/browse/{collection}[/{parentIds}]`.
      Confirm the `<int:>` + comma-list converter works in Django URL
      patterns (probably a custom converter).
- [ ] Port `BrowserView` to v4 with the new envelope. Drop the dual
      `groups`/`books`/`rows` serialization — pick card or table based
      on the request, not both at once.
- [ ] Port `/choices`, `/choices/{field}`, `/metadata`,
      `/download/{filename}`, `/import`, `/refresh`.
- [ ] Port browser settings + saved-settings endpoints.
- [ ] Migrate `frontend/src/stores/browser.js` to v4. Verify breadcrumb
      navigation, filter dropdowns, table/card switching, search.

### Phase 4: Reader endpoints

- [ ] Implement `/api/v4/reader/comics/{id}` composite view.
- [ ] Implement `/api/v4/comics/{id}/reader-settings?scopes=…` returning
      all requested scopes in one response.
- [ ] Port `/comics/{id}/bookmark` (PATCH).
- [ ] Migrate `frontend/src/stores/reader.js`. Verify page navigation,
      prev/next book, settings layering, bookmark debouncing.

### Phase 5: Metadata pivot on the backend

- [ ] Update aggregated metadata serializer to ship credits as
      `{ role: [{person}] }` instead of `[{role, person}]`. Sort by
      HEAD_ROLES precedence then alphabetically on the backend.
- [ ] Parse `identifier.name` (`"type:code"`) on the backend; ship
      `{type, code, displayName}` with the source display name resolved.
- [ ] Remove the corresponding getters from
      `frontend/src/stores/metadata.js`.

### Phase 6: WebSocket payload redesign

- [ ] Define typed message shapes in
      `codex/websockets/messages.py` (or similar).
- [ ] Update all librarian-side broadcasters to emit typed messages
      with mtime + scope.
- [ ] Mount a v4 WebSocket consumer at `/ws/v4/` (v3 consumer stays for
      transition).
- [ ] Migrate `frontend/src/stores/socket.js` to typed dispatch.
- [ ] Remove the `loadMtimes()` two-step in browser and reader stores
      once typed messages carry mtime directly.

### Phase 7: Admin resources (JSON:API)

- [ ] Convert AdminUserViewSet, AdminGroupViewSet, AdminLibraryViewSet,
      AdminFlagViewSet, AdminFailedImportViewSet, AdminCustomCover\* to
      JSON:API renderers + serializers.
- [ ] Update PATCH responses to return the updated row.
- [ ] Add `/api/v4/admin/users/bulk` and equivalents.
- [ ] Add cursor pagination class.
- [ ] Port the non-resource admin endpoints (stats, email-settings,
      tagging-defaults, librarian/tasks, tag-sessions, identifier-url,
      tag-write, folders, user-data import/export, api-key).
- [ ] Migrate `frontend/src/stores/admin.js` table by table. Replace
      full-refetch-on-mutate with splice-from-PATCH-response.

### Phase 8: Favorites + utility

- [ ] Port `/api/v4/favorites/*`. Should be straightforward.
- [ ] Port `/api/v4/opds-urls`, `/api/v4/covers/{source}/{id}`.
- [ ] Add `/api/v4/schema` (OpenAPI). Confirm
      `drf-spectacular` plays nicely with the JSON:API renderer.

### Phase 9: Cutover & cleanup

- [ ] Toggle the v4 feature flag to default-on in a release.
- [ ] One release cycle of v3+v4 coexistence to validate no regressions
      (especially around OPDS clients and external API token users).
- [ ] Mark v3 deprecated in docs. Add a `Deprecation` HTTP header to v3
      responses pointing at v4.
- [ ] Two release cycles later: remove v3 routes, views, serializers,
      and tests.
- [ ] Delete `frontend/src/api/v3/`, `frontend/src/stores/*` v3
      branches, and any compat shims.

## Migration Risks

- **OPDS coexistence.** OPDS endpoints are public and consumed by
  third-party readers. Verify they aren't accidentally affected by the
  renderer/inflection changes (they live in `/api/v3/opds/` not
  `/api/v4/`, so should be isolated, but worth a test pass).
- **API token consumers.** External scripts may hit `/api/v3/` directly.
  Deprecation warnings need to land in release notes, not just headers.
- **`django-rest-framework-json-api` quirks.** Sparse fieldsets,
  includes, and nested writes can surface bugs in edge cases. Budget
  extra time for Phase 7.
- **camelCase migration.** Some serializer field aliases (e.g.,
  `username` → `login` in auth) are externally-facing contracts.
  Double-check rest_registration's expected wire shape before
  blindly camelCasing.
- **Custom URL converters.** Django supports custom path converters
  (single-char `<group:group>` today). The new comma-list converter
  needs the same plumbing.
- **WebSocket compatibility.** Frontend may briefly run v3 stores
  against v4 socket (or vice versa) during partial rollouts. Either
  run both consumers in parallel, or gate the socket version by the
  same flag.
