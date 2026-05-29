# Critical Rating Normalization

## Context (corrected)

The previous draft of this plan got the source-format landscape wrong. The actual situation:

| Source | Rating field | Scale | Status |
|---|---|---|---|
| ComicInfo (CIX) | `CommunityRating` | 0.0–5.0, one decimal place (per spec) | Numeric, well-defined |
| ComicBookInfo (CBI) | `rating` | Unspecified integer | Numeric, **scale unknown** — apps wrote whatever they wanted |
| MetronInfo (MIX) | **none** | — | No rating field exists in the schema. Confirmed by reading [`metron_info/schema/__init__.py`](https://github.com/ajslater/comicbox/blob/main/comicbox/formats/metron_info/schema/__init__.py) — only `AgeRating` is present. |
| CoMet | `rating` | Age-rating string (e.g. "Teen") | **Not numeric.** Maps to `age_rating`, not a critical rating. |
| Metron API | `rating.name` | Age-rating string | Also age rating; maps to `age_rating`. |
| ComicTagger | `critical_rating` | Arbitrary float | Origin of the field name. ComicTagger blindly accepted any float and called it a critical rating. The field name in comicbox is inherited from ComicTagger; we'll keep it for continuity. |

So in practice there are exactly **two** numeric rating systems in the wild:

1. **ComicInfo `CommunityRating`** — 0–5, the only field with a spec-defined scale.
2. **ComicBookInfo `rating`** — an integer in an unspecified range (apps tended to use 0–10 or 0–100).

Today, comicbox routes both into a single `critical_rating` DecimalField (`places=2`) with **no scale conversion** — see [`comic_info/transform/__init__.py:183`](https://github.com/ajslater/comicbox/blob/main/comicbox/formats/comic_info/transform/__init__.py) and [`comic_book_info/transform/__init__.py:71`](https://github.com/ajslater/comicbox/blob/main/comicbox/formats/comic_book_info/transform/__init__.py). A CIX `CommunityRating=4.5` and a CBI `rating=90` land in the same field with no marker saying which scale they came from.

`COMMUNITY_RATING_KEY` is declared as a constant in `comicbox/formats/comicbox/schema/__init__.py:57` but is **not bound to any field** and **not used in any transform** — leftover from the v1.0 schema era. The current canonical comicbox key is `critical_rating` only.

Codex inherits this mess: `Comic.critical_rating` is `CoercingDecimalField(max_digits=5, decimal_places=2)` (range 0.00–999.99). The dev-DB values like 36.81 and 94.95 come from `mock_comics/mock_comics.py:77` generating `random.random() * 100 * 1.1` for `CommunityRating`, which the importer then stores raw.

## End state

- **Canonical scale is ComicInfo's 0.0–5.0**, stored at **one decimal place** of precision — matches the ComicInfo spec exactly and avoids fake precision in aggregates.
- **Comicbox does the source-aware normalization on read** — codex sees only canonical values, so no source-format detection is needed downstream.
- **Comicbox does the inverse conversion on write** — round-trips back to file formats use that format's native scale.
- **Codex migrates existing data** using the same algorithm the comicbox CBI normalizer uses, with one wrinkle: values ≤ 5 are assumed to already be legit CIX and left alone.
- **MetronInfo is left out entirely** — there's nothing to read or write. The previous plan invented a Metron rating transform that has no field to map to.
- **The "critical rating" name stays.** It's inherited from ComicTagger and matches the existing comicbox API. Renaming would churn fixtures, API consumers, and choices JSON for no functional gain.

## The normalization algorithm

CBI's `rating` is an integer with no declared upper bound. The bucketing heuristic the user specified:

| Input range | Divisor | Rationale |
|---|---|---|
| `value ≤ 10` | 2 | Assume CBI used a 0–10 scale |
| `11 ≤ value ≤ 100` | 20 | Assume CBI used a 0–100 scale |
| `101 ≤ value ≤ 1000` | 200 | 0–1000 scale |
| `1001 ≤ value ≤ 10000` | 2000 | etc. |

The general form for `value > 10`: divisor = `2 × 10^(ceil(log10(value)) − 1)`. Equivalently: round the value up to the next power of 10 to find the implied max scale, then divide so that the max maps to 5.

```python
from decimal import Decimal, ROUND_HALF_UP
from math import ceil, log10

def cbi_rating_to_canonical(value: Decimal) -> Decimal:
    """Convert a CBI integer rating to the canonical 0-5 scale (1 decimal place)."""
    if value is None or value <= 0:
        return Decimal("0.0")
    if value <= 10:
        divisor = Decimal(2)
    else:
        implied_max = Decimal(10) ** ceil(log10(float(value)))
        divisor = implied_max / 5
    result = (value / divisor).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return min(result, Decimal("5.0"))  # belt-and-suspenders clamp
```

Spot checks (1 decimal place): `10 → 5.0`, `11 → 0.6`, `90 → 4.5`, `100 → 5.0`, `500 → 2.5`, `1000 → 5.0`.

Comicbox's canonical schema also uses `places=1` — there's no precision to be had from a second decimal when the source-of-truth ComicInfo spec only carries one. Codex stores at 1 dp too — see CX-2.

**Write-back for CBI** (the user's "5.X → 10-point integer" rule): multiply the canonical 0–5 by 2, round to nearest integer, clamp to `[0, 10]`. This collapses the CBI side to a stable 0–10 integer scale on write regardless of what the file originally had. Lossy by design — the user has explicitly accepted this.

```python
def canonical_to_cbi_rating(value: Decimal) -> int:
    if value is None:
        return 0
    return int((value * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP).min(10).max(0))
```

## Plan

### Comicbox changes

All changes live in `comicbox/`. The codex side does **not** need any of this to land first — codex can carry its own normalizer for the migration and rely on the upstream comicbox change for ingest going forward.

#### CB-1 Normalize CBI rating on read

[`comicbox/formats/comic_book_info/transform/__init__.py:71`](https://github.com/ajslater/comicbox/blob/main/comicbox/formats/comic_book_info/transform/__init__.py) currently maps `"rating" → CRITICAL_RATING_KEY` via a `SIMPLE_KEYPATHS` bidict. That's a 1:1 passthrough.

Replace the simple mapping with a `MetaSpec` that runs the value through `cbi_rating_to_canonical`. Pattern to follow: look at how `cbi_credits_transform_to_cb` is wired in the same module — same shape, just substitute the rating converter.

Touch:
- `comicbox/formats/comic_book_info/transform/__init__.py` — remove `"rating"` from `SIMPLE_KEYPATHS`, add a dedicated `MetaSpec` for it on the to-comicbox side.
- New file `comicbox/formats/comic_book_info/transform/rating.py` (or inline a helper — module is small enough) housing `cbi_rating_to_canonical`.

#### CB-2 Serialize canonical → CBI integer on write

Same module's `SPECS_FROM` direction. Add a `MetaSpec` that calls `canonical_to_cbi_rating` when writing `rating` back into a CBI dict. Remove `"rating"` from the inverse `SIMPLE_KEYPATHS` use as well.

#### CB-3 Document the canonical scale

- `comicbox/formats/comicbox/schema/__init__.py:197` — `critical_rating = DecimalField(places=2)`. Switch to `places=1` and add `minimum=0, maximum=5` to the field constructor. Existing `DecimalField` already supports `minimum`/`maximum` per [`comicbox/formats/base/fields/number_fields.py:103`](https://github.com/ajslater/comicbox/blob/main/comicbox/formats/base/fields/number_fields.py). This causes marshmallow to validate-and-quantize inputs.
- `comicbox/schema_definitions/v2.0/comicbox.example.yaml:26-29` — current example has both `community_rating: 5.0` and `critical_rating: 10.0`. Drop the `community_rating` line entirely; change `critical_rating: 10.0` to `critical_rating: 5.0` so the example doesn't lie about the scale.
- `comicbox/schema_definitions/v2.0/comicbox-v2.0.schema.json` — add `"minimum": 0, "maximum": 5` to the `critical_rating` JSON schema entry.

#### CB-4 Drop dead `COMMUNITY_RATING_KEY`

`COMMUNITY_RATING_KEY = "community_rating"` at `comicbox/formats/comicbox/schema/__init__.py:57` is unreferenced. Search-and-delete in the same commit as CB-3.

#### CB-5 Verify CIX read is a no-op conversion

[`comicbox/formats/comic_info/transform/__init__.py:183`](https://github.com/ajslater/comicbox/blob/main/comicbox/formats/comic_info/transform/__init__.py) maps `"CommunityRating" → CRITICAL_RATING_KEY` 1:1. After CB-3 the schema validates `[0, 5]` so values outside the spec will be rejected — verify with a test that an in-range CIX value passes through unmodified, and that an out-of-range CIX value (e.g. `7.0`) either raises a validation error or clamps. Pick clamp + warn over raise so a single malformed file doesn't abort an import.

#### CB-6 Tests

- `tests/unit/test_cbi_rating_normalize.py` (new) — table-driven test for `cbi_rating_to_canonical` and `canonical_to_cbi_rating` covering each bucket boundary (0, 1, 10, 11, 100, 101, 1000, 5000) plus zero and negative inputs.
- `tests/test_import_export.py:112` — current fixture sets `"critical_rating": Decimal(5)` for a CBI source file. Under the new behavior, a CBI `rating=5` integer should normalize to `Decimal("2.50")`. Update the expected value (or change the input rating to `10` so the expected stays at `5`, whichever reads more clearly).
- Round-trip test: read a CBI file with `rating=8`, expect canonical `4.00`, write back, expect CBI `rating=8` again (modulo rounding).

#### CB-7 Out of scope (called out so the next reviewer doesn't expect it)

- **No** MetronInfo rating transform — the field doesn't exist in the spec.
- **No** CoMet rating transform — already correctly mapped to `age_rating`.
- **No** schema-version bump. The change is a scale normalization, not a structural break; v2.0 stays.

### Codex changes

Comicbox does the heavy lifting; codex just needs to migrate existing dirty data, tighten its own field, and clean up mocks.

#### CX-1 Data migration `0054_critical_rating_normalize.py`

Two-step migration:

1. **RunPython** — walks every `Comic` row where `critical_rating IS NOT NULL` and rescales any value above 5 using the same algorithm comicbox uses for CBI. Then quantizes every row (rescaled or not) to 1 decimal place so the subsequent `AlterField` is lossless.
2. **AlterField** — drops `decimal_places` from 2 to 1 and `max_digits` from 5 to 2 (see CX-2 for the field shape rationale).

```python
from decimal import Decimal, ROUND_HALF_UP
from math import ceil, log10

ONE_DP = Decimal("0.1")
MAX = Decimal("5.0")

def normalize(value):
    if value is None:
        return None
    if value <= MAX:
        # Already in (or below) canonical range — assume legit CIX, just requantize.
        return value.quantize(ONE_DP, rounding=ROUND_HALF_UP)
    # Above 5: apply the comicbox CBI bucketing.
    if value <= Decimal(10):
        divisor = Decimal(2)
    else:
        implied_max = Decimal(10) ** ceil(log10(float(value)))
        divisor = implied_max / 5
    result = (value / divisor).quantize(ONE_DP, rounding=ROUND_HALF_UP)
    return min(result, MAX)
```

Notes:
- Use `iterator(chunk_size=2000)` + `bulk_update` to avoid memory spikes on large libraries.
- Log every conversion at `info` (path + before/after) so admins have a record. Do **not** broadcast progress over the WebSocket — librarian status broadcasts are for librarian tasks, not migrations.
- Pattern to mimic: `codex/migrations/0011_library_groups_and_metadata_changes.py` already does a `critical_rating`-targeted RunPython migration, same shape. `codex/migrations/0034_comicbox2.py:35` shows the `AlterField` pattern for this exact field.
- Ordering: RunPython first, AlterField second. If we shrink the field before quantizing, Django/SQLite will silently truncate (or fail validation on Postgres if someone ever ports). Quantize first, then narrow.

The "≤ 5 means legit CIX" heuristic is the user's call. It will misclassify any historical CBI `rating=3` (which should have become canonical `1.5`) as already-canonical `3.0`, but there's no provenance left in the DB to tell them apart, and the user explicitly accepted this guess.

#### CX-2 Resize the field and clamp on write

[`codex/models/comic.py:160`](codex/models/comic.py:160) currently:

```python
critical_rating = CoercingDecimalField(
    db_index=True, decimal_places=2, max_digits=5, default=None, null=True
)
```

Change to:

```python
critical_rating = CoercingDecimalField(
    db_index=True, decimal_places=1, max_digits=2, default=None, null=True,
    coerce_max=Decimal("5.0"),
)
```

`max_digits=2, decimal_places=1` is exactly the range we want (0.0–9.9 representable, clamped to 5.0 by `coerce_max`). The migration in CX-1 handles the schema change.

The `CoercingDecimalField` at [`codex/models/fields.py:104`](codex/models/fields.py:104) currently hardcodes `_decimal_max = Decimal(10 ** (max_digits - 2) - 1)` — that `- 2` is implicitly assuming `decimal_places=2`. Two fixes needed in the same change:

1. **Fix the formula.** Replace with `Decimal(10 ** (self.max_digits - self.decimal_places) - 1)` so the field-ceiling clamp matches the actual field shape regardless of decimal_places.
2. **Add `coerce_max` kwarg.** Optional `Decimal | None` constructor kwarg; when set, `get_prep_value` takes the `min` of the prepped value and `coerce_max` (after the existing `_decimal_max` clamp). Catches every ORM write path — `bulk_create`, `bulk_update`, raw `save()` — because `get_prep_value` runs on all of them. This is load-bearing: importer bulk writes bypass validators entirely.

Additionally add `validators=[MinValueValidator(Decimal("0.0")), MaxValueValidator(Decimal("5.0"))]` to the field for DRF and form-layer validation. Cheap, and gives nicer error messages than a silent clamp at the API boundary.

#### CX-3 Fix mock_comics rating generator

[`mock_comics/mock_comics.py:77`](mock_comics/mock_comics.py:77): change `"DECIMALS": {"CommunityRating": 100.0}` to `"DECIMALS": {"CommunityRating": 5.0}`. Now-canonical scale, matches spec, prevents fresh seeds from polluting dev DBs with values like 94.95.

The `* 1.1` overshoot in `create_float` at `mock_comics/mock_comics.py:144` (`random.random() * limit * 1.1`) stays — its purpose is to occasionally generate slightly-over-max values to exercise validation/clamping paths. With limit=5 and the new comicbox `maximum=5` validation, that test is exactly what we want.

#### CX-4 Card-caption display

[`frontend/src/components/browser/card/order-by-caption.vue`](frontend/src/components/browser/card/order-by-caption.vue): the existing `★  ${formatStarRating(ov)}` renders correctly under the new scale (a value of `4.5` displays as `★ 4.5`). No template change needed for the card caption — it's the dense thumbnail label and `/ 5` would clutter it.

The metadata panel's read-only display is handled in CX-7 (lives in the same file the editor work touches).

#### CX-5 Aggregates

`codex/views/browser/annotate/order.py:52` uses `Avg("comic__critical_rating")`. Once stored values are all in the same 0–5 scale, this is finally meaningful. **No code change** — just a comment noting the assumption, or a test asserting the aggregate stays in `[0, 5]` for a synthetic library.

#### CX-7 Editable critical_rating in the metadata editor

Add `critical_rating` as a user-editable field in the edit panel, restricted to `0.0–5.0` with one decimal place. Only enabled when ComicInfo is selected as a write format (MetronInfo has no rating field; ComicBookInfo isn't exposed in the editor's format picker at [`edit-panel.vue:863-866`](frontend/src/components/metadata/edit-mode/edit-panel.vue:863), so it stays out).

**Frontend — `frontend/src/components/metadata/edit-mode/edit-panel.vue`:**

1. Add a cell to the `<section class="mdSection detailsGrid">` block (around line 312, alongside Reading Direction / Original Format / Language / Age Rating / Monochrome). Use `<v-text-field type="number">` with HTML5 bounds and an inline validator. Sample shape:

```vue
<div :title="isFieldDisabled('critical_rating') ? disabledTooltip : ''">
  <v-text-field
    v-model.number="patch.critical_rating"
    label="Critical Rating"
    type="number"
    min="0"
    max="5"
    step="0.1"
    :rules="criticalRatingRules"
    hide-details="auto"
    density="compact"
    :disabled="isFieldDisabled('critical_rating')"
    :class="{
      fieldCleared: isCleared('critical_rating'),
      fieldChanged:
        isFieldChanged('critical_rating') && !isCleared('critical_rating'),
    }"
    @update:model-value="onFieldInput('critical_rating')"
  >
    <template #append-inner>
      <ClearFieldIcon
        :cleared="isCleared('critical_rating')"
        @toggle="toggleClear('critical_rating')"
      />
    </template>
  </v-text-field>
</div>
```

2. Add `critical_rating: null` to the `patch` data object (around line 961-986).
3. Add a `criticalRatingRules` computed/data array:

```js
criticalRatingRules: Object.freeze([
  (v) => v === null || v === "" || (v >= 0 && v <= 5) || "Must be 0.0–5.0",
])
```

4. In `initFromMetadata()` (around line 1246), add:

```js
this.patch.critical_rating =
  this.md.criticalRating == null ? null : Number(this.md.criticalRating);
```

5. In `buildPatch()` (around line 1327), add a numeric-field branch that clamps and rounds to one decimal:

```js
if (changed.has("critical_rating")) {
  if (cleared.has("critical_rating") || this.patch.critical_rating === null || this.patch.critical_rating === "") {
    cbPatch.critical_rating = null;
  } else {
    const n = Number(this.patch.critical_rating);
    if (Number.isFinite(n)) {
      cbPatch.critical_rating = Math.round(Math.max(0, Math.min(5, n)) * 10) / 10;
    }
  }
}
```

The clamp + round mirrors the server-side `coerce_max=5.0` from CX-2 and the comicbox `maximum=5` schema validation from CB-3 — defence-in-depth, not redundant. A user typing `7.9` should see it snap to `5.0` on save, not bounce off the server with an error.

6. In `clearField()` (around line 1215), add an explicit case so `clearField('critical_rating')` sets it to `null` (current default-case `""` would also work for the patch builder above, but `null` matches the intent better — "no rating" rather than "empty string").

**Frontend — `frontend/src/choices/format-field-support.json`:**

Add `"critical_rating"` to the `COMIC_INFO` array. Do **not** add it to `METRON_INFO`. This drives the `isFieldDisabled('critical_rating')` check via `supportedFields`.

**Frontend — display (`frontend/src/components/metadata/metadata-ratings.vue:7`):**

Bonus while we're in the file: change the read-only display to include the scale, since the editor now makes the bound user-visible. `<MetadataText :value="md.criticalRating" />` → render as `${value} / 5.0` so the read-only and edit modes agree on the scale.

Also fix the typo at [`metadata-ratings.vue:40`](frontend/src/components/metadata/metadata-ratings.vue:40) — `md?.criticRating` should be `md?.criticalRating`. Pre-existing bug; the v-table `v-if` currently never short-circuits on rating alone.

**Backend — `codex/views/admin/tagwrite.py` / `codex/serializers/admin/tagging.py`:**

The `patch` field is currently a raw JSON string that passes through to `comicbox` ([`tagwrite.py:125`](codex/views/admin/tagwrite.py:125)). With CB-3 in place, comicbox will reject `critical_rating > 5` during the write. That's a fine final line of defense — but the user gets a librarian error in their UI rather than an inline form error, which is bad UX. Two options:

- **A.** Add a JSON-schema or DRF validator on the patch payload server-side. More work, but consistent error surfacing.
- **B.** Trust the frontend clamp + comicbox validation, and accept that the only way to send a bad value is via a hand-crafted API request. Smaller change.

Pick **B** for this pass — the frontend clamp covers the UI path. File a follow-up if API consumers complain.

**Choices — `codex/choices/browser.py:430`:**

Update the `critical_rating` row in the browser-table `column_map` to:

```python
"critical_rating": {
    "label": "Critical Rating",
    "sort_key": "critical_rating",
    "m2m": False,
    "editable": True,
    "edit_widget": "decimal",  # min=0, max=5, step=0.1
},
```

The `editable`/`edit_widget` fields are noted as reserved for "a later phase" at [`browser.py:231-232`](codex/choices/browser.py:231). This is that phase — set the values for critical_rating so the eventual inline-table edit knows to render a decimal stepper. Doesn't affect the dialog editor in this PR, but documents the contract.

#### CX-6 Tests

- `tests/importer/test_basic.py` — add a case for an imported CBI file with `rating=8`; assert resulting `Comic.critical_rating == Decimal("4.0")`. This proves comicbox's CB-1 conversion flows into codex (both layers now use 1 dp).
- New test for the migration: seed a `Comic` row with `critical_rating=Decimal("94.95")` against the pre-migration schema, run the migration, assert the result is `Decimal("0.5")` (94.95 / 200 = 0.47475, rounded half-up to 1 dp).
- New test that direct ORM writes of out-of-range values are clamped: `Comic.objects.create(critical_rating=Decimal(99))` then re-fetch and assert `critical_rating == Decimal("5.0")`.
- New test for the `CoercingDecimalField` formula fix: instantiate the field with `decimal_places=1, max_digits=2` and confirm `_decimal_max == Decimal(9)` (not `0` as today's broken formula would give).
- Frontend (vitest) — mount `EditPanel` with a fixture book whose `criticalRating === 4.5`, confirm the input renders `4.5`, type `7.3`, click Save, assert the emitted `cbPatch.critical_rating === 5.0` (clamp + round).
- Frontend (vitest) — mount with `METRON_INFO` selected only, assert the Critical Rating input is `disabled` and the `disabledTooltip` is shown.

## Ordering

The two repos can ship in either order:

- **Comicbox first** is the natural choice — once CB-1/CB-2 ship, codex picks it up on the next comicbox dependency bump, and the codex migration is then purely a one-shot cleanup of legacy data.
- **Codex first** also works — the migration is independent of comicbox behavior. Future imports will keep writing dirty values until comicbox updates, but the migration won't actively hurt.

Recommended: ship comicbox CB-1 through CB-6 first, then bump the comicbox dep in codex, then ship CX-1 through CX-6 in a single PR. The migration runs once during the comicbox-bump deploy and the new ingest path takes over from there.

## Risks

- **Lossy CBI write-back.** A canonical `4.37` round-trips to CBI as integer `9` then re-reads as canonical `4.50`. Acceptable — the user has called this out as a deliberate simplification ("convert the 5.X system to a ten point integer scale for simplicity"). Document in the comicbox PR description.
- **The "≤ 5 = legit CIX" heuristic in CX-1 has no escape valve.** A library that was 100% CBI-sourced and had ratings in [0, 5] (interpreted as 0–10 scale) will be misclassified. There's no metadata to detect this. The only mitigation would be a per-library override flag, which is out of scope.
- **Mock data overshoot.** With max=5 and `*1.1`, the mocks will sometimes write 5.5, which comicbox CB-3 validation may now reject. If that breaks the mock pipeline, either bypass validation in mock mode or change the multiplier to `*1.0`. Decide when the comicbox change lands.

## Out of scope

- Adding a separate `community_rating` field to preserve CIX/CBI provenance — explicitly rejected.
- Renaming `critical_rating` to something else — keeping ComicTagger's name for continuity.
- Inline-table editing of critical_rating (the `editable: True, edit_widget: "decimal"` flag in CX-7 is set so the eventual implementation has the contract, but the table-edit UI itself is a separate piece of work).
- Backfilling provenance from `original_format` — too brittle, and the migration's heuristic is good enough.
