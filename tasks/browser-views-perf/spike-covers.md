# Stage 3 Spike — Cover fan-out

_Design doc. No code yet. Pick an option, then implement._

## 1. The problem

`/api/v3/<group>/<pks>/cover.webp` is called once per visible card. A typical
page shows 72 cards. Each call runs the full `BrowserAnnotateOrderView` pipeline
just to pick _which_ comic's cover to serve — ACL filter, search filter, group
filter, order aggregates, ORDER BY, `.first()`. Measured cost from
`99-summary.md`: **~7-14 s of wall time per first page load**, server bound, 72×
parallel from the browser but still dwarfing the 1-query main browse response.

Short-circuits already in place:

- `CoverView._get_comic_cover` — trivial for Comic model (returns `pks[0]`).
- `CoverView._get_custom_cover` — cheap
  `CustomCover.objects.filter(...).first()`.
- HTTP `cache-control: max-age=604800` (7 days) on the endpoint.

The expensive path is `_get_dynamic_cover` for non-Comic groups. This is where
all the saving is.

### What "first cover" means today

`CoverView.get_group_filter` (lines 56-76) is deliberately fuzzy: instead of
"first comic in _this_ group's children," it picks comics whose `sort_name`
matches any of the browser's current pks, optionally constrained to a
parent_route. This lets a volume's cover be picked from anywhere under the
current parent, not just from that volume's comic rows. Any option that
pre-computes cover pks must reproduce this semantic, or we change what users
see.

---

## 2. Options

### Option A — `for_cover=True` pipeline trim

Plan's option 1. Add a `for_cover=True` kwarg to `get_filtered_queryset` and
`annotate_order_aggregates` so CoverView skips the expensive annotations that
aren't needed for picking a single cover pk.

**What gets skipped**

Looking at `annotate_order_aggregates` (annotate/order.py:260-273):

| Step                            | Needed for cover?                           |
| ------------------------------- | ------------------------------------------- |
| `JsonGroupArray("id")`          | No — only used to list pks in the response  |
| `_annotate_search_scores`       | Yes if `order_key == "search_score"`        |
| `_alias_sort_names`             | Yes if `order_key == "sort_name"`           |
| `_alias_filename`               | Yes if `order_key == "filename"`            |
| `_alias_story_arc_number`       | Yes if `order_key == "story_arc_number"`    |
| `_annotate_page_count`          | No — just a sort/display sum                |
| `_annotate_bookmark_updated_at` | Yes if `order_key == "bookmark_updated_at"` |
| `_annotate_order_child_count`   | Yes if `order_key == "child_count"`         |

So we can unconditionally drop `JsonGroupArray("id")` and the `page_count` alias
for cover, but everything order-key-specific has to stay or the ORDER BY breaks.
Card annotations (`annotate_card_aggregates`) are already skipped — CoverView
never calls them.

**ACL:** unchanged. Same filter path.

**Invalidation:** unchanged. Same cache keys, same HTTP cache semantics.

**Rollback:** remove the kwarg; default behavior is what we have now.

**Estimated win:** modest. Drops 2 of ~8 annotation steps per request. Each
request stays at ~100-200ms × 72 requests. Realistic estimate: **15-25% per
request**, so 7-14s → 5-11s. The architecture of "72 pipeline runs per page" is
unchanged — we're just trimming each.

**Cost:** low. Small diff, easy to understand, easy to revert.

### Option B — Pre-compute cover pks in BrowserView, thin cover endpoint

Plan's option 2. The expensive work (picking which comic's cover to show for
each group card) happens **once per page**, not 72 times. The cover endpoint
becomes a near-trivial "look up comic, serve blob" path.

Two flavors, different ACL stories:

#### B.1 — Plain comic-pk URL + cheap ACL re-check

- BrowserView annotates each group card with `cover_pk` (subquery returning the
  representative Comic pk using the existing "first cover" semantics).
- New endpoint: `/api/v3/c/<int:comic_pk>/cover.webp`. Reuses the existing cover
  file lookup but skips the whole `_get_dynamic_cover` path.
- On the new endpoint: one cheap query,
  `get_filtered_queryset(Comic).filter(pk=comic_pk).exists()`, for ACL. No ORDER
  BY, no annotations, no grouping. If the user can't see this comic, 404.
- Frontend updated to use the new URL shape for non-custom, non-Comic covers.

**ACL:** still validated on every request, but the query is single-row and
indexed. ~1-5ms vs ~100-200ms for the current pipeline.

**Invalidation:** `cover_pk` lives on the browser page response, which is
already wrapped in `cache_page(BROWSER_TIMEOUT)`. When filters / search change
the URL changes → new response → new `cover_pk`. When bookmarks / comics change,
cachalot invalidates the browser response. No new invalidation surface.

**Rollback:** two coordinated reverts (backend cover annotation + endpoint;
frontend URL builder). Not a one-line toggle, but mechanical. Keep the old
`/<pks>/cover.webp` endpoint working in parallel during transition so a
pre-JS-updated client still renders covers.

**Estimated win:** large. The 72 full pipelines collapse into:

1. One extra aggregate on the main browse query (one subquery per group row
   returning ~one pk). Cost: probably +50-150ms on the browse query, though
   potentially cachalot-covered.
2. 72× a single-row ACL check = ~72-360ms total.

So 7-14s → ~0.5-1s of cover server time. **10-20× reduction.**

#### B.2 — Signed URLs (no ACL re-check)

- BrowserView signs `(comic_pk, user_id, exp)` into a token, serves
  `/api/v3/c/<token>/cover.webp`.
- Cover endpoint verifies HMAC + expiry. No DB query at all. Serves blob.

**ACL:** enforced at sign time. Token is user-scoped, so a copied URL can't be
replayed cross-user (if the signing key isn't leaked).

**Invalidation:** token has `exp`. To rotate ACL (e.g., library made private,
user demoted), we must expire tokens. Either short `exp` (e.g., 15 min) with
rolling re-signing on each browse load, or bump a signing-key version on ACL
change events.

**Rollback:** backend revert + token code removal + frontend revert. More moving
parts than B.1.

**Estimated win:** slightly larger than B.1 (saves the single-row ACL query).
7-14s → ~0.1-0.3s. But complexity is meaningfully higher for the incremental
savings over B.1.

**Security caveat:** we now have a signing key to manage. If any worker uses a
stale key, clients see broken covers. If the key leaks, attackers can forge
tokens until rotation.

### Option C — Static placeholder hybrid

Plan's option 3. BrowserView returns a static group-placeholder URL for dynamic
covers unless a real cover is already cached. Real covers load in a
lazy/background flow.

**ACL:** placeholder is the same SVG for everyone → no ACL needed. Real cover
still runs the full pipeline when requested.

**Invalidation:** placeholder is immutable; real cover uses today's path.

**Rollback:** revert the placeholder branch, frontend falls back to dynamic URL.

**Estimated win:** none in the steady state. First-paint is faster because the
user sees placeholders immediately, but every subsequent cover fetch still pays
the ~100-200ms pipeline cost. We'd be trading perceived latency for real
throughput, and users on slow connections would end up with many ugly
placeholder-to-real transitions.

This is a UX band-aid, not a perf fix.

---

## 3. Cross-option concerns

### OPDS parity

`codex/urls/opds/binary.py` routes `/api/v3/o/<group>/<pks>/cover.webp` to
`OPDSCoverView`. Whatever Option we pick needs to apply there too, or OPDS
clients keep the slow path. For Option A, `OPDSCoverView` presumably extends the
same base and inherits the flag. For Option B, OPDS URLs need the same rewrite —
OPDS feeds generated by BrowserView can carry `cover_pk` the same way the browse
cards can. Worth verifying before commit.

### Test coverage

Regardless of option, tests must cover:

1. Private-library ACL — user A can't see user B's library covers.
2. Age-rating ACL — a restricted user can't get a cover for a restricted comic
   even if they know the URL.
3. Cover path traversal guard — `CoverPathMixin.get_cover_path` sanitation
   unchanged.
4. HTTP cache behavior — 304s where applicable, correct `cache-control`.
5. Semantic parity — the same comic pk is picked as cover across a set of
   representative browse states. This is the subtle one; the sort_name fuzzy
   match in `CoverView.get_group_filter` has to be reproduced exactly.

### Measurement

New perf flow needs adding: "Flow D: full 72-card browse with cover requests."
Without it we can't credit the cover win in the stage diff.

---

## 4. Recommendation

**Go with Option B.1 (plain comic-pk URL + cheap ACL re-check).** Reasons:

- **Biggest real win.** Collapses the 72× pipeline to 1×+72 cheap lookups.
  Order-of-magnitude reduction in server time, which is what the 99-summary
  ranks as "very high impact."
- **Security story is straightforward.** Same ACL path as everything else in the
  codebase. No signing-key ops burden, no token rotation.
- **Rollback is mechanical, not scary.** Backend + frontend revert; no data
  migration, no persistent state introduced.
- **B.2 is overkill.** The incremental savings over B.1 (~100ms total per page)
  don't justify the signing-key management surface.
- **Option A is worth doing anyway** and we can land it as a secondary
  improvement inside this stage (or defer to Stage 5). It's cheap and composes —
  even with B.1, the first page still runs the pipeline once to compute cover
  pks, so A's trim helps that one query. But A alone doesn't solve the fan-out.
- **Option C is rejected.** It's a UX change disguised as a perf fix.

### Scope for the implementation PR

1. BrowserView annotates each group card with `cover_pk` using a subquery that
   reproduces `CoverView.get_group_filter`'s sort_name fuzzy matching.
   Serializer field `cover_pk` on `BrowserCardSerializer`.
2. New endpoint `/api/v3/c/<int:comic_pk>/cover.webp` — thin wrapper, validates
   ACL with one query, delegates to existing cover file pipeline.
3. Frontend `getCoverSrc` returns the new URL shape when `cover_pk` is present
   on the card; falls back to the old URL shape during transition.
4. OPDS parity: same treatment for `OPDSCoverView`, cover pks carried in the
   feed entries.
5. Keep the old `/<pks>/cover.webp` endpoint working so partially-updated
   clients don't break.
6. Test matrix covering ACL, traversal, HTTP cache, and semantic parity.
7. Add Flow D to `run_baseline.py`; include before/after in the PR description.

### Open questions for check-in

- **Do we keep `dynamic_covers=False` / `custom_covers=True` as knobs?** They
  alter `CoverView.get_group_filter` and `_get_custom_cover`. The pre-compute
  must respect them or we lose a user setting. Confirm they're per-request
  params (they are: from `BrowserCoverInputSerializer`).
- **Scope of old endpoint deprecation:** cleanly remove in a follow-up once all
  clients are known to send the new URL, or leave it indefinitely?
- **Flow D details:** hit `/browser` once, then fire 72 parallel cover requests,
  measure both phases. Capture in one silk trace? Multiple?
