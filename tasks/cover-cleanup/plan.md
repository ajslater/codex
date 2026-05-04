# Cover cleanup — plan (revised)

Three related cover-asset follow-ups, scoped from the actual code:

1. **Rename** `missing-cover-165.webp` → `comic-165.webp` and
   `missing-cover.svg` → `comic.svg`. Keep the `-165` suffix on the
   webp so the existing `f"{name}-{width}"` naming in
   `bin/icons_transform.py` continues to apply with no special-case.
2. **Per-type placeholders**: web cards should show the type-specific
   SVG (`publisher.svg`, `series.svg`, …) while the real cover loads,
   instead of a blank placeholder.
3. **Web + OPDS missing-cover behavior** — Option A with status-code
   split: the cover endpoint returns **404** for missing covers
   instead of serving the comic webp body. Web client falls back to
   its `lazy-src` SVG; OPDS clients use whatever default rendering
   they have for a missing image. Same response shape for both.

Plus a small visual fix on the new `comic.svg` (orange → grey logo).

Bundling into one PR is fine — the asks are tightly coupled and a
partial landing would be confusing.

## Surface map

The cover pipeline (read top-to-bottom):

| Layer | Path | Role |
| ----- | ---- | ---- |
| Master sources | `img/*.svg` | Hand-edited SVGs (uncompressed). |
| Build script | `bin/icons_transform.py` | Copies SVGs to `static_src/img/`, rasterizes `missing-cover` to `missing-cover-165.webp` via Inkscape, then runs picopt. |
| Optimized assets | `codex/static_src/img/*.svg` + `*.webp` + `*.png` | Picopt'd SVGs + the rasterized webp/png Django serves. Tracked in git. |
| Static-URL injection | `codex/templates/headers-script-globals.html` | Exposes `globalThis.CODEX.STATIC` (e.g. `/static/`) to the frontend. |
| Backend missing-cover constant | `codex/views/const.py:58` | `MISSING_COVER_FN = "missing-cover-165.webp"` plus `MISSING_COVER_PATH`. |
| Cover endpoint | `codex/views/browser/cover.py` | Reads `MISSING_COVER_PATH` bytes and returns them with `image/webp` for 200 (no cover) and 202 (pending). Group-agnostic. Used by both `/api/v3/c/<pk>/cover.webp` and `/opds/bin/c/<pk>/cover.webp`. |
| Web cover URL builder | `frontend/src/api/v3/browser.js:23` | `getCoverSrc({coverPk, coverCustomPk}, ts)` — points at the cover endpoint. |
| Web card | `frontend/src/components/book-cover.vue` | Renders `<v-img :src="coverSrc">`. No `placeholder` / `lazy-src` today, so v-img shows blank while loading. |
| Web metadata cover | `frontend/src/components/metadata/metadata-cover.vue:55` | Hardcodes `volume.svg` for the `forceGenericCover` branch — drive-by bug we fix in the same pass. |
| OPDS v1 / v2 cover links | `codex/views/opds/v1/entry/links.py:59`, `codex/views/opds/v2/feed/publications.py:166` | Build `<link rel="thumbnail" type="image/webp" href="…/opds/bin/c/<pk>/cover.webp"/>`. OPDS clients fetch via the same endpoint as the web. |

Existing per-type SVGs (already in `codex/static_src/img/`):
`publisher.svg`, `imprint.svg`, `series.svg`, `volume.svg`,
`folder.svg`, `story-arc.svg`. The constant
`MISSING_COVER_NAME_MAP` in `codex/views/const.py:51` already maps
group letters to these names — we'll mirror it on the JS side.

## Task 1 — Rename `missing-cover` → `comic` (keep `-165` suffix)

### File renames

| From | To |
| ---- | -- |
| `img/missing-cover.svg` | `img/comic.svg` |
| `codex/static_src/img/missing-cover.svg` | `codex/static_src/img/comic.svg` |
| `codex/static_src/img/missing-cover-165.webp` | `codex/static_src/img/comic-165.webp` |
| `codex/static_src/img/missing-cover-165.png` | `codex/static_src/img/comic-165.png` |

The webp keeps the `-165` width suffix so the existing
`output_png_name = f"{name}-{width}"` template in
`bin/icons_transform.py` works without modification — only the
icon name in the dict + two special-case branches change.

### `bin/icons_transform.py` updates

Three single-line edits:

1. Rename the dict key:

   ```python
   # Before:
   "missing-cover": (165, round(165 * _COVER_RATIO)),

   # After:
   "comic": (165, round(165 * _COVER_RATIO)),
   ```

2. Update line 74's special-case touch:

   ```python
   # Before:
   (SRC_IMG_PATH / "missing-cover.svg").touch()
   # After:
   (SRC_IMG_PATH / "comic.svg").touch()
   ```

3. Update line 89's Inkscape branch:

   ```python
   # Before:
   if name == "missing-cover":
       inkscape(input_svg_path, output_png_path, width, height)
   # After:
   if name == "comic":
       inkscape(input_svg_path, output_png_path, width, height)
   ```

No filename-helper / suffix-skip logic needed — the `-165` suffix
stays universal for sized icons.

### Backend constant

`codex/views/const.py:58`:

```python
# Before:
MISSING_COVER_FN = "missing-cover-165.webp"
# After:
MISSING_COVER_FN = "comic-165.webp"
```

`MISSING_COVER_PATH` follows automatically. After Task 3 lands, the
backend reads of `MISSING_COVER_PATH` go away entirely, but the
constant + the file stay (per the user's "keep the comic cover webp
generation code anyway until I test this solution with OPDS clients").

### Picopt treestamp

`codex/static_src/img/.picopt_treestamps.yaml` will have stale
entries for `missing-cover.svg` / `missing-cover-165.webp`. Picopt
re-processes on next run; orphaned entries are harmless. Recommend
leaving as-is.

### Search-and-replace audit

Confirmed runtime references to the old filenames:

- `codex/views/const.py:58` — covered above.
- `codex/migrations/0027_import_order_and_covers.py:58` — historical
  migration log message ("Removed N missing-cover symlinks"). **Don't
  edit** — the migration's audit log should reflect what it actually
  did at the time.
- `codex/views/opds/v1/entry/links.py:52` — comment-only reference;
  optional cosmetic update.
- `codex/views/browser/annotate/cover.py:32` — comment-only
  reference; optional cosmetic update.
- `img/missing-cover.svg:11,14` — Inkscape `sodipodi:docname` /
  `inkscape:export-filename` metadata inside the SVG. Gets rewritten
  on next Inkscape save anyway; the rename + the visual edit (Extra,
  below) will produce a clean version.

### Wheel install pipeline

User confirmed: the wheel install pipeline doesn't reference the
webp directly; it copies all files from `static/`. The renamed
files ship under the new name with no install-side change.

## Extra — orange → grey logo on `comic.svg`

The current `missing-cover.svg` embeds `logo.svg` via an
`<image xlink:href="logo.svg">` element. The logo's own SVG
(`img/logo.svg`) uses an orange linear gradient
(`#d97700` → `#a85c00`). When `<image>` references an external SVG
by xlink, the parent's `style="fill:..."` does **not** cascade into
the embedded SVG's own fills — that's why the existing
`style="fill:#808080;stroke:#808080"` on the `<image>` element in
`missing-cover.svg` doesn't actually grey the logo.

### Goal

Match the rest of the line art: book outlines + pages are
`fill:#808080` (grey). The circular logo element should match
`#808080` so it visually aligns with the book line art.

### Implementation choices (implementer's pick)

1. **Inline the logo paths.** Open `comic.svg` in Inkscape, replace
   the `<image xlink:href="logo.svg">` element with the actual paths
   from `logo.svg`, then change all orange fills to `#808080`.
   Cleanest but largest SVG change. Picopt will re-optimize.

2. **Switch logo.svg to `currentColor`.** Edit `img/logo.svg` to use
   `fill="currentColor"` (or `fill:currentColor` in style), then
   `<image>` references that pick up the parent's `color`
   attribute. Risky: every other consumer of `logo.svg` (favicon,
   PWA logo, etc.) inherits the colorless variant unless they
   explicitly set `color`. Likely a no-go without auditing logo
   usage everywhere.

3. **Re-export comic.svg with the logo flattened in greyscale.**
   Open in Inkscape, set the embedded logo's color to `#808080`,
   "Object → Flatten" to bake it. Saves a clean SVG with no
   external `<image>` reference.

**Recommendation**: Option 1 (inline + recolor). Confined to
`comic.svg`; doesn't touch `logo.svg`'s other consumers.

## Task 2 — Per-type placeholders on the web client

### `frontend/src/components/book-cover.vue`

Add a `placeholderSrc` computed prop and pass it to `<v-img>` via
`lazy-src`:

```vue
<template>
  <div class="bookCover">
    <v-img
      :src="coverSrc"
      :lazy-src="placeholderSrc"
      class="coverImg"
      :class="multiPkClasses"
      position="top"
    />
    <span v-if="group !== 'c'" class="childCount">{{ childCount }}</span>
  </div>
</template>
```

```js
const PLACEHOLDER_BY_GROUP = Object.freeze({
  p: "publisher",
  i: "imprint",
  s: "series",
  v: "volume",
  f: "folder",
  a: "story-arc",
  c: "comic",
});

// computed:
placeholderSrc() {
  const name = PLACEHOLDER_BY_GROUP[this.group] ?? "comic";
  return `${globalThis.CODEX.STATIC}img/${name}.svg`;
},
```

The map mirrors the backend's `MISSING_COVER_NAME_MAP` (root group
`r` is intentionally absent — root never appears as a card group).
The fallback to `comic` covers any unexpected group letter.

### Behavior

- **First paint**: v-img shows the per-type SVG immediately (no
  network roundtrip — the SVGs are tiny, ~400 B – 12 KB, cached
  forever via Django's static serving).
- **Cover loads**: v-img swaps to the real cover bytes when the
  cover endpoint returns 200.
- **Cover pending (202)**: the polling loop re-fetches; the
  placeholder stays visible because `<v-img>` keeps showing
  `lazy-src` until `src` resolves.
- **Cover never resolves** (404 after Task 3, repeated 202, or
  fetch aborted): the placeholder stays as the final visual.

### `frontend/src/components/metadata/metadata-cover.vue` fix

Line 55 hard-codes `volume.svg` regardless of group. Replace with
the same `PLACEHOLDER_BY_GROUP` lookup so a comic / publisher /
folder etc. shows the right SVG when `forceGenericCover` is set.
Tiny drive-by.

## Task 3 — Status-code split (Option A)

The cover endpoint stops returning the comic webp body for missing
covers. It returns **404 Not Found** instead. Same response shape
for both web (`/api/v3/c/<pk>/cover.webp`) and OPDS
(`/opds/bin/c/<pk>/cover.webp`) — no route split needed.

### Edits to `codex/views/browser/cover.py`

`_missing_cover_response` becomes a 404-empty response:

```python
@staticmethod
def _missing_cover_response(
    status_code: int = status.HTTP_404_NOT_FOUND,
) -> HttpResponse:
    return HttpResponse(b"", content_type=_WEBP_CONTENT_TYPE,
                        status=status_code)
```

`_get_cover_response` shape becomes:

| Case | Old | New |
| ---- | --- | --- |
| Real cover hit | 200 + cover bytes | unchanged |
| 0-byte marker (cover thread tried & failed) | 200 + comic webp body | **404 + empty** |
| Cover queued, not yet generated | 202 + comic webp body + `Retry-After: 2` + `Cache-Control: no-store` | **202 + empty** + same headers |

The 202-pending case keeps its `Retry-After` + `Cache-Control:
no-store` so the web polling loop continues to work. Empty body
(zero-length) means the web client's `<v-img>` shows the lazy-src
SVG during polling instead of a flicker through the webp
placeholder.

### Web polling loop

`frontend/src/components/book-cover.vue`'s `pollCover` already
returns when `resp.status !== 202`. With 404, the early return
fires; the `<v-img>` falls back to `lazy-src` because no body
loaded. No frontend change needed beyond Task 2.

### OPDS clients

OPDS clients see 404 for missing covers and use whatever default
rendering they implement. Per the user: "let the OPDS client use
its own default."

### Keep the webp generation code dormant

Per the user: "If it's totally deprecated, keep the comic cover
webp generation code anyway until I test this solution with OPDS
clients."

Concretely:

- `bin/icons_transform.py` keeps generating `comic-165.webp` (and
  `.png`) on each invocation.
- `codex/static_src/img/comic-165.webp` stays committed in git.
- `MISSING_COVER_FN` + `MISSING_COVER_PATH` constants in
  `codex/views/const.py` stay.
- The runtime no longer reads `MISSING_COVER_PATH` after the
  `_missing_cover_response` rewrite — but the import + the file
  remain, ready for a quick revert if OPDS-client testing surfaces
  problems.

A future PR can drop the webp asset + constants once OPDS testing
confirms the 404 path is fine across the OPDS client ecosystem.

### Acceptance + cache headers

- 404 responses use Django's default headers (no special
  `Cache-Control`); reverse proxies may cache 404 short-term —
  usually fine.
- 202 responses keep `Cache-Control: no-store` so the polling loop
  always reaches the backend (avoids stale 202 caching).

## Cross-cutting concerns

### OPDS namespace + URL stability

OPDS feeds emit `<link rel="thumbnail" type="image/webp"
href="…/opds/bin/c/<pk>/cover.webp"/>`. The URL doesn't change.
After Task 3 the response is now 404 instead of webp body when no
cover exists. Mime stays `image/webp` for real covers and the
empty 404 / 202 responses (Django defaults the body type even when
empty).

### Static-asset CDN / proxies

Some deployments serve `/static/img/` through nginx/Caddy. After
the rename, those caches need to expire `missing-cover-165.webp`.
Filename change forces a fresh fetch on the next request — old URLs
404. The wheel ships under the new name; users who upgrade get the
new asset.

### Test fixtures

If any tests load `missing-cover-165.webp` or `missing-cover.svg`
directly, update to the new names. Quick `grep` should catch them
during the PR.

## Verification

For each task, the verification steps:

1. **Task 1 (rename)**:
   - `bin/icons_transform.py` runs cleanly and produces
     `codex/static_src/img/comic.svg` + `comic-165.webp` +
     `comic-165.png`.
   - `make collectstatic` writes the renamed files to
     `codex/static/img/`.
   - `MISSING_COVER_PATH` resolves to a readable file at server
     start.

2. **Extra (logo recolor)**:
   - Open `comic.svg` in a browser or Inkscape — the circular logo
     element shows `#808080` grey, matching the book line art.

3. **Task 2 (per-type placeholders)**:
   - Hard-refresh a browser page with mixed cards (publisher /
     series / volume / comic / folder / story-arc). Each card
     should briefly show the correct SVG (`time.sleep(2)` in the
     cover endpoint makes this visible during dev).
   - `metadata-cover.vue`'s `forceGenericCover` mode shows the
     right SVG for the metadata's group.
   - Comic cards specifically use `comic.svg`.

4. **Task 3 (status-code split)**:
   - Web: stop the cover thread (or point at a comic with no cover
     file). The card holds the SVG placeholder indefinitely instead
     of showing the webp placeholder body. Network panel shows 404
     on the cover endpoint.
   - OPDS: `curl /opds/bin/c/<pk>/cover.webp` for a comic with no
     cover returns 404. Verify with at least one OPDS reader app —
     this is the "test this solution with OPDS clients" step the
     user called out.
   - Pending case: hit the cover endpoint for a comic whose cover
     was just enqueued. First response is 202 + empty body +
     `Retry-After`. Subsequent polls return 200 once the cover
     thread writes the file.

## Suggested PR shape

One PR, four reviewable commits:

1. **Rename + build script** — `img/missing-cover.svg` →
   `img/comic.svg`, picopt outputs, `bin/icons_transform.py` ICONS
   dict + two special-case branches, `MISSING_COVER_FN` in
   `views/const.py`. Drive-by: optional comment-only updates
   (cover.py + opds links.py).

2. **comic.svg color fix** — orange logo → `#808080` grey.
   Standalone commit so the visual diff is reviewable in isolation.

3. **Per-type placeholders on web** — `book-cover.vue` adds
   `placeholderSrc` + `lazy-src`, `metadata-cover.vue` swaps its
   hardcoded `volume.svg` for the same dispatch.

4. **Status-code split** — `cover.py`'s `_missing_cover_response`
   returns 404 / 202 with empty bodies. Verify polling loop in
   `book-cover.vue` still handles the new shape.

Each commit is small enough to skim; the bundle is one PR for ease
of review.

## Risks / open questions

- **OPDS client behavior on 404.** This is the user's explicit
  test-before-deprecating gate. If any common OPDS client renders
  poorly on 404 (e.g. shows a broken-image icon prominently), we
  can revert Task 3's OPDS half by re-introducing the route split
  recommended in the previous draft of this plan.
- **Reverse-proxy 404 caching.** nginx / Caddy may cache 404s for
  short periods. If a comic's cover is generated shortly after a
  client first requested it (and got 404), a cached 404 could
  delay the cover from appearing. Mitigation: add
  `Cache-Control: no-store` to the 404 response too. Cheap and
  defensive; recommend including in Task 3.
- **Missing-cover deprecation timing.** The webp generation +
  asset + constants stay until the user finishes OPDS-client
  testing. A follow-up PR can drop them. No deadline; flag in
  `tasks/cover-cleanup/plan.md` (this file) so it's not forgotten.

## Out of scope (not in this PR)

- Backend type-aware cover responses (returning per-type SVGs from
  the cover endpoint). The frontend handles this naturally via
  `lazy-src`; backend doesn't need to know group.
- Dropping the `comic-165.webp` asset + constants. Deferred until
  OPDS-client testing confirms the 404 path is acceptable.
- Cover-thread / cover-cache work — separate concern, see
  `codex/librarian/covers/`.
