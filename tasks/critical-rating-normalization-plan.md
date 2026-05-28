# Critical Rating Normalization

## Context

`Comic.critical_rating` is a `CoercingDecimalField(max_digits=5, decimal_places=2)` that accepts anything 0.00–999.99 today. The values that actually land there have no defined scale because the ingest path does no normalization:

- `comicbox.transforms.comicinfo` maps `ComicInfo.CommunityRating` → `critical_rating` 1:1. Per the ComicInfo 2.1 spec `CommunityRating` is **0–5**, but comicbox has both a `community_rating` key (0–5 per its example yaml) and a `critical_rating` key (0–10 per its example yaml) and it routes ComicInfo's `CommunityRating` into the 0–10 bucket regardless. Whatever the publisher wrote, that's what we get.
- Metron does **not** participate in `critical_rating` at all (no transform; the key is absent from `metroninfo/SIMPLE_KEY_MAP`). Anything the Metron tagger writes lands by some other path or not at all.
- `CoercingDecimalField` just quantizes to 2 decimals and clamps at 999.99 — no scale conversion.
- Order-by aggregates use `Avg("comic__critical_rating")` over descendants. Mixed-scale inputs produce meaningless averages.
- `tests/mock_comics` generates `CommunityRating` values **0–110** (`random.random() * 100 * 1.1`), which is how 36.81 / 94.95 ended up in dev DBs.

Mock data aside, the real problem is that two upstream sources use different scales for the same concept and the storage layer treats them as one. Aggregates and display can't be right until ingest is consistent.

## End state

- A single canonical scale lives in `Comic.critical_rating`.
- Every ingest path converts to that scale; out-of-range values are clamped (with a warning), not silently stored.
- Aggregates (folder / series / publisher card display) operate on the canonical scale and produce values inside it.
- Write-back converts canonical → source-format on the way out (`ComicInfo.CommunityRating` gets the scale the spec asks for; Metron gets its own scale once a transform exists).
- The frontend renders the canonical scale with a fixed max so users always know the upper bound.

## Open question: which canonical scale?

This is the only decision I need locked in before the rest follows mechanically. Three options:

### Option A — Metron 0–10 (what the user said)

- Multiply ComicInfo `CommunityRating` (spec 0–5) by **2** on read.
- Divide canonical by 2 when writing ComicInfo.
- Aggregate range: 0.00–10.00. Two decimal places of resolution.
- Display: `★ 8.5` style; max-star UI fits 10.

The user's "multiplied by 100" line is ambiguous (multiplying 0–5 by 100 doesn't land in any standard scale). I'm reading the intent as "standardize on Metron" → which means 0–10 → which means **×2 for ComicInfo**, not ×100. Worth confirming.

### Option B — Integer 0–1000 (Metron 0–10 × 100, store as int)

- Multiply ComicInfo by 200 on read; multiply Metron 0–10 by 100 on read.
- Divide by 200 / 100 on write-back.
- Switch the field from `DecimalField(5,2)` to `PositiveSmallIntegerField` (max value 32k, plenty of room).
- Aggregate range: 0–1000. Integer math, no rounding mismatch.
- Display: divide by 100 in the frontend → `★ 8.5`.

This is what the user's "×100" phrasing actually fits. It avoids `DECIMAL`'s SQLite quirks for `Avg`. Cost is a migration and a field-type change.

### Option C — ComicInfo 0–5

- The ComicInfo spec's actual canonical; multiplying things by 2 fits a Metron value into 0–10 naturally, but going the other way (Metron → ComicInfo) means dividing by 2 with rounding loss for half-points.
- Probably wrong for a library that talks to Metron more than it talks to ComicInfo.

**Recommendation:** Option A unless you actually want the integer-storage refactor in B. A is a one-day change; B is a multi-day refactor with a real migration.

## Plan (assumes Option A — 0–10 Metron scale)

### Phase 1 — Lock the ingest scale

1. **Codex-side normalizer.** Add `codex/librarian/scribe/importer/normalize/critical_rating.py` (or wherever ingest normalization belongs — see Phase 0). On every comicbox metadata dict that reaches `aggregate_path.py`:
   - If `critical_rating` was sourced from ComicInfo (i.e. the comic's original_format is CIX), multiply by 2.
   - If sourced from Metron, leave as-is.
   - If we can't tell the source format reliably, leave as-is and warn once per import — see Phase 0.
   - After conversion, clamp to `[0.0, 10.0]`. Out-of-range gets clamped + a `warning` log with the original value and file path.
2. **Validator.** `Comic.critical_rating` keeps the field type for now (Option A) but a `presave` on `Comic` clamps any direct writes to `[0, 10]` as a belt-and-suspenders check for code that bypasses the importer (REST writes, migrations, fixtures).
3. **One-shot data migration.** Walk existing `Comic` rows where `critical_rating > 10`. Two buckets:
   - `10 < critical_rating <= 100`: probably a Metron-style 0–100 percentage (the mock data case). Divide by 10. Log each one.
   - `critical_rating > 100`: probably bad / test data. Null it out and log.
   - Migrate filename: `codex/migrations/00NN_critical_rating_normalize.py`.

### Phase 0 — Source-format detection at ingest

The Phase 1 step "if sourced from ComicInfo, multiply by 2" requires knowing which transformer produced the value. Comicbox merges transformers and the final dict doesn't carry provenance. Options:

- **A1.** Comicbox already records the formats it parsed per-file (`metadata_sources` or similar). Verify and use it. If a single source produced the dict, use that source's scale. If multiple, prefer Metron's value when both are present, else assume the dict reflects whatever single source it has.
- **A2.** Codex re-asks comicbox per source individually (one call per format we care about) and merges deliberately. More expensive at import time.
- **A3.** Trust comicbox to do the conversion. Means filing a comicbox PR. Adds an upstream dependency we can't ship without.

Recommendation: **A1**. Confirm comicbox exposes source provenance; if it does, this is a 5-line lookup. If it doesn't, fall back to A2 only for ratings — the import overhead is negligible compared to FTS5 indexing.

### Phase 2 — Aggregates and display

Once the stored value is canonical:

- The existing `Avg("comic__critical_rating")` aggregate becomes meaningful — values are all in the same scale.
- The card caption is already trimmed of trailing zeros (commit `93ac7132`). Add a max-bound formatter so anything > 10 (shouldn't happen post-migration, but defensive) clips at `10.0` and logs a warning client-side.
- Browser table column for `critical_rating`: confirm it formats the same way (no current bug, just a check).
- Metadata panel: display as `8.5 / 10` so the scale is unambiguous.

### Phase 3 — Write-back

When `codex/librarian/scribe/tag_writer.py` emits a patch back to a file:

- **ComicInfo writes:** divide canonical by 2, round to 1 decimal place (ComicInfo's typical precision), and emit as `CommunityRating`. Clamp to `[0, 5]` so out-of-range never round-trips back to a file.
- **Metron writes:** add a `CRITICAL_RATING_KEY → "Rating"` (or whatever Metron calls it) entry to comicbox's MetronInfo transform's `SIMPLE_KEY_MAP`. This is an upstream PR — without it, Metron tag writes silently drop the rating. As a stopgap, Codex can carry a local override in its tag-writer until the comicbox PR ships.

### Phase 4 — Cleanup

- Delete or fix `tests/mock_comics`' `CommunityRating` range so it generates values in `[0, 5]` (matching the ComicInfo spec the mock claims to produce). The mock is what put 94.95 in the dev DB; fixing it prevents the same noise on every fresh seed.
- Add a test seeding mixed-source comics (one with `critical_rating=4.5` from CIX, one with `critical_rating=8.5` from Metron) and asserting both land at 9.0 / 8.5 in the DB.
- Add a serializer round-trip test (read → write back → re-parse) confirming `CommunityRating` survives the ÷2 on write-back.

## Risk

- **Comicbox provenance reliability.** If A1 doesn't work and A2 is too slow, we're stuck either filing a comicbox PR or guessing on read. Mitigation: do the comicbox provenance audit (Phase 0) BEFORE committing to Option A's migration — if it turns out comicbox can't tell us, switch to Option B which avoids the per-source detection (treat everything as needing ×N scale based on a heuristic + clamp).
- **Migrations on large libraries.** Walking every `Comic` row is fine for normal libraries but I should `iterator(chunk_size=2000)` it and gate the migration behind a status broadcast so admins know what's happening.
- **Round-trip precision loss.** Canonical 0–10 with 2 decimals → ComicInfo 0–5 (÷2, 1 decimal) → back to canonical (×2) loses the second decimal. Acceptable for a rating display; document it.

## Out of scope

- Adding a `community_rating` field to `Comic` to keep ComicInfo and Metron values separate. Tempting (lossless round-trip) but doubles the schema, doubles the aggregate logic, and the user explicitly wants ONE canonical value.
- Letting users edit `critical_rating` in the metadata editor. This plan is read/write through comicbox only.
