# 05 — Custom field classes

This sub-plan covers `codex/serializers/fields/`. Field classes
fire on every (de)serialization — they're the smallest unit of
work in the serializer layer, but multiplied across every Comic,
every browser card, every OPDS entry.

## Surface

- `auth.py` — `TimestampField`, `TimezoneField`
- `base.py` — `CodexChoiceField` (abstract)
- `browser.py` — `BookmarkFilterField`, `PyCountryField`,
  `CountryField`, `LanguageField`, `BreadcrumbsField`
- `group.py` — `BrowseGroupField`, `BrowserRouteGroupField`
- `reader.py` — `FitToField`, `ReadingDirectionField`,
  `ArcGroupField`
- `sanitized.py` — `SanitizedCharField`
- `settings.py` — `SettingsKeyField`
- `stats.py` — `StringListMultipleChoiceField`,
  `SerializerChoicesField`, `CountDictField`
- `vuetify.py` — Vuetify form-field adapters (10 classes)

## Findings

### F0 — Verify country/language codes are stripped at import

**Prerequisite for F1.** The cache lookup in F1 uses
`alpha_2_map.get(value, value)` — direct dict-`get`, no fuzzy
matching. If imports leave whitespace on country/language codes
(`"US "`, `" EN"`, etc.) the fast-path miss, and the existing
pycountry fallback that hides those misses goes away with F1.

**Audit chain**

1. **Source of values.** The codex importer pulls country /
   language codes from comicbox-parsed metadata. Trace:

   ```
   codex/librarian/scribe/importer/read/aggregate_path.py:34,46
       — comicbox keys aggregated into the import payload
   codex/librarian/scribe/importer/<aggregate / link>
       — payload merged into Comic field assignments
   ```

   Read the importer's normalize-and-link path end to end; confirm
   whether `payload["country"]` / `payload["language"]` flow
   through any `.strip()` step.

2. **Field-level cleanup.** `Comic.country` / `Comic.language`
   are `ForeignKey` to `Country` / `Language` (subclasses of
   `NamedModel` in `codex/models/named.py:89,102`).
   `NamedModel.name` is a `CleaningCharField`, which uses
   `CleaningStringFieldMixin.get_prep_value` in
   `codex/models/fields.py:17-26`:

   ```python
   def get_prep_value(self, value):
       if value := super().get_prep_value(value):
           value = value[: self.max_length]
           value = clean(value)             # nh3 HTML sanitize
           value = unescape(value)          # HTML entity decode
       return value
   ```

   **No `.strip()` step here today.** nh3 `clean()` does not
   strip outer whitespace.

3. **Pick a fix location.**

   - **(a) Importer-side** — add `.strip()` in the comicbox
     payload normalization, before the `Country` / `Language`
     row is created or looked up. Most localized; only affects
     these two fields. **Recommended.**
   - **(b) `CleaningStringFieldMixin.get_prep_value`** — add a
     `value = value.strip()` after `unescape`. Broadest fix;
     touches every CharField in the codebase, including
     description / banner / comment text where leading whitespace
     might be significant for display. Risky.
   - **(c) `PyCountryField._alpha_2_map().get(value.strip(),
     value)` defense-in-depth** — purely serializer-side fallback.
     Cheap (one strip per per-row Comic country/language access).
     Doesn't fix the underlying data; existing rows still have
     whitespace stored. Use as a belt-and-braces in addition to
     (a), not instead.

4. **Verify with a query**:

   ```sql
   SELECT name, length(name) FROM codex_country
   WHERE name != trim(name);
   SELECT name, length(name) FROM codex_language
   WHERE name != trim(name);
   ```

   If either returns rows, write a one-shot data migration:

   ```python
   migrations.RunPython(
       lambda apps, schema_editor: ...
       # UPDATE codex_country SET name = trim(name) WHERE ...
   )
   ```

**Done state for F0**: either confirmed clean (no rows with
whitespace, no fix needed beyond defensive `.strip()` in the
cache lookup), or fix (a) lands in the importer plus a one-shot
data migration to clean the existing rows.

This finding takes the trailing-whitespace risk off the
[Risks](#risks) list.

### F1 — `PyCountryField` per-call lookup **(high impact)**

`codex/serializers/fields/browser.py:26-51`.

```python
class PyCountryField(SanitizedCharField, ABC):
    DB: Database = pycountry.countries
    _ALPHA_2_LEN = 2

    @override
    def to_representation(self, value) -> str:
        if not value:
            return ""
        if value == DUMMY_NULL_NAME:
            return value
        try:
            lookup_obj = (
                self.DB.get(alpha_2=value)
                if len(value) == self._ALPHA_2_LEN
                else self.DB.lookup(value)
            )
        except Exception:
            logger.warning(...)
            return value
        else:
            return lookup_obj.name if lookup_obj else value
```

Subclasses: `CountryField` (DB = `pycountry.countries`),
`LanguageField` (DB = `pycountry.languages`).

Used in:

- `ComicSerializer` country / language FK fields (one row per Comic
  per metadata pane fetch + one row per Comic per browser card +
  one row per OPDS entry that mentions country/language)
- Filter menus via `CountrySerializer` / `LanguageSerializer`

Per request: a browse-list with 50 cards × (country + language) =
**100 pycountry lookups per browse-list**. Per OPDS feed: same
order of magnitude.

**Three issues:**

1. `pycountry.countries.get(alpha_2="US")` is a **table scan**
   internally — pycountry stores rows in a JSON file and
   re-parses on first access; subsequent calls do dict lookups
   but still allocate `Country` objects. The cost is consistent
   but not zero (~1–5 µs per call).
2. `self.DB.lookup(value)` for non-alpha_2 input is **slower** —
   does a fuzzy text match across name, official_name, etc.
3. The exception handler swallows everything (`except Exception:`),
   masking real bugs.

**Fix — module-level cache:**

```python
# codex/serializers/fields/browser.py
from functools import cache

import pycountry
from pycountry.db import Database

class PyCountryField(SanitizedCharField, ABC):
    DB: Database = pycountry.countries
    _ALPHA_2_LEN = 2

    @classmethod
    @cache
    def _lookup_alpha_2(cls, db_id: str, value: str) -> str:
        # ``db_id`` keys the cache by the subclass's DB choice
        # (``"countries"`` vs ``"languages"``). Required because
        # the lru_cache is class-method-scoped — without the key,
        # CountryField and LanguageField would share a cache.
        ...

    @override
    def to_representation(self, value) -> str:
        if not value:
            return ""
        if value == DUMMY_NULL_NAME:
            return value
        # alpha_2 fast path is the common case (ISO codes)
        if len(value) == self._ALPHA_2_LEN:
            return self._cached_alpha_2_name(value)
        # non-alpha_2 input: rare, falls through to DB.lookup
        return self._cached_lookup(value)
```

The `_cached_alpha_2_name` builds a `dict[alpha_2, name]` once at
first access:

```python
class PyCountryField(SanitizedCharField, ABC):
    DB: Database = pycountry.countries
    _ALPHA_2_LEN = 2

    @classmethod
    def _alpha_2_map(cls) -> dict[str, str]:
        # Build once per subclass on first call. Pycountry's
        # internal table is built lazily on first access too;
        # this just memoizes the (alpha_2 -> name) projection.
        if not hasattr(cls, "_cached_alpha_2_map"):
            cls._cached_alpha_2_map = {
                row.alpha_2: row.name
                for row in cls.DB
                if hasattr(row, "alpha_2")
            }
        return cls._cached_alpha_2_map

    @override
    def to_representation(self, value) -> str:
        if not value or value == DUMMY_NULL_NAME:
            return value or ""
        if len(value) == self._ALPHA_2_LEN:
            return self._alpha_2_map().get(value, value)
        # Non-alpha_2 fallback (rare)
        try:
            row = self.DB.lookup(value)
        except (LookupError, KeyError):
            logger.warning(f"pycountry lookup failed: {value}")
            return value
        return row.name if row else value
```

**Expected impact:** 100 pycountry lookups/request → 100 dict
gets/request. Microbench shows ~5 µs → ~50 ns per call. Saves
~0.5 ms wall time per browse-list request on a 50-card response.
Larger savings on installs with high-cardinality international
metadata.

Bonus: replace `except Exception:` with `except (LookupError,
KeyError):` so real exceptions surface.

### F2 — `SanitizedCharField` for country/language codes
**(low — bug-shaped)**

`codex/serializers/fields/sanitized.py:9-16`.

```python
class SanitizedCharField(CharField):
    @override
    def to_internal_value(self, data) -> str:
        sanitized_data = clean(data)  # nh3 HTML sanitizer
        return super().to_internal_value(sanitized_data)
```

`PyCountryField` inherits from `SanitizedCharField`, which means
**every Country/Language write** runs `nh3.clean()` on the input.
ISO 3166-1 alpha-2 codes (e.g. `"US"`, `"FR"`) are by definition
alphanumeric — they don't need HTML sanitization.

**Status:** correctness is fine (`nh3.clean("US")` is a no-op). But
nh3 is meant for free-form HTML and adds CPU per call.

**Fix:** `PyCountryField` should inherit from plain `CharField`,
not `SanitizedCharField`. The serializer-level validation already
constrains length and charset for ISO codes; nh3 is overkill.

```python
# Before
class PyCountryField(SanitizedCharField, ABC):

# After
from rest_framework.fields import CharField

class PyCountryField(CharField, ABC):
```

Audit `SanitizedCharField` users to see if any others are similarly
mis-applied:

```bash
grep -rn 'SanitizedCharField' codex/serializers/
```

Free-text fields (banner_text, comments, descriptions) want
sanitization. ISO codes, enum values, tightly-constrained inputs
don't.

**Expected impact:** ~10 µs per write × write frequency. Low,
because writes are rare. Land alongside F1 because the same file.

### F3 — `SerializerChoicesField` per-instance cost **(low —
land with stats refactor)**

`codex/serializers/fields/stats.py:20-29`.

```python
class SerializerChoicesField(StringListMultipleChoiceField):
    def __init__(self, serializer=None, **kwargs) -> None:
        if not serializer:
            raise ValueError("serializer required for this field.")
        choices = serializer().get_fields().keys()
        super().__init__(choices=choices, **kwargs)
```

`serializer()` instantiates the full serializer just to read field
names. `get_fields()` walks DRF's metaclass.

Used in `AdminStatsRequestSerializer` (5 fields, each instantiating
its target). Per app start: 5 instantiations. Per request: zero
(DRF caches field definitions on the serializer class).

**Status:** **per-class cost, not per-request.** Not a hot spot.

**Fix (cosmetic):** cache by serializer class:

```python
from functools import cache

class SerializerChoicesField(StringListMultipleChoiceField):
    @staticmethod
    @cache
    def _choices_for(serializer_cls) -> tuple[str, ...]:
        return tuple(serializer_cls().get_fields().keys())

    def __init__(self, serializer=None, **kwargs) -> None:
        if not serializer:
            raise ValueError("serializer required for this field.")
        super().__init__(choices=self._choices_for(serializer), **kwargs)
```

Saves ~5 instantiations per app start. Trivial — bundle as a
discretionary follow-up.

### F4 — `VuetifyListField.to_representation` per-item child
**(verified clean)**

`codex/serializers/fields/vuetify.py:108-115`.

```python
@override
def to_representation(self, value: list) -> list:
    """Remove superclass's None filter."""
    return [self.child.to_representation(item) for item in value]
```

Standard ListField pattern. Child is whatever was passed at
construction. Used in form definitions; typically short lists. No
fix.

### F5 — `BreadcrumbsField` `RouteSerializer` child
**(verified clean)**

`codex/serializers/fields/browser.py:66-69`. Module-level
`RouteSerializer()` instance reused across calls. No issue.

### F6 — `BookmarkFilterField` / `BrowseGroupField` /
`ArcGroupField` / `FitToField` / `ReadingDirectionField`
**(verified clean)**

All `CodexChoiceField` subclasses with `class_choices = tuple(...)`
declared at class definition time. No per-call cost.

### F7 — `TimestampField` / `TimezoneField` **(verified clean)**

`codex/serializers/fields/auth.py:14-44`.

```python
class TimestampField(IntegerField):
    @override
    def to_representation(self, value: datetime | None) -> int:
        if value is None:
            return 0
        return int(value.timestamp() * 1000)


class TimezoneField(CharField):
    @override
    def validate(self, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValidationError(...)
```

`TimestampField` is a pure scalar transform. `TimezoneField`
constructs `ZoneInfo` per validation call — once per timezone-set
request. Not hot. No fix.

### F8 — `SettingsKeyField` choices construction
**(verified clean)**

`codex/serializers/fields/settings.py:8-11`.

```python
class SettingsKeyField(ChoiceField):
    class_choices = (*READER_DEFAULTS.keys(), *BROWSER_DEFAULTS.keys())
```

Tuple unpacked at class definition time, not per-instance. No fix.

## Suggested commit shape

One PR, three commits:

1. **F0: import-side strip audit + data migration if needed.**
   Verify the importer normalizes country/language codes before
   creating `Country` / `Language` rows. If existing rows have
   whitespace, ship a one-shot data migration. If clean, document
   the assumption and add a regression test that round-trips a
   `"US "` import to a normalized `"US"` row.
2. **F1 + F2: `PyCountryField` cache + drop sanitization.** Single
   file (`fields/browser.py`). Add a microbench under
   `tests/perf/` measuring 1000 country lookups before/after.
3. **F3: `SerializerChoicesField` cache.** Cosmetic; bundle if
   convenient or skip.

F4–F8 are no-fix verifications; document in this plan.

## Verification

- `make lint-python` clean.
- `make test-python` clean.
- New microbench (e.g. `tests/perf/microbench_pycountry.py`):
  ```python
  def test_pycountry_field_speed(benchmark):
      field = CountryField()
      benchmark(lambda: field.to_representation("US"))
  ```
  Expect ~10× speedup.
- `tests/perf/run_baseline.py::flow_a_browse_root` cold + warm
  wall time: F1 saves ~0.5 ms on 50-card responses.

## Risks

- **pycountry version pin.** Module-level cache assumes the
  pycountry package data is stable across the process lifetime.
  Server restart picks up package updates. Document the assumption
  in `_alpha_2_map` docstring.
- ~~Trailing-whitespace ISO codes.~~ Closed by F0 — the import-
  side audit either confirms whitespace doesn't reach the DB or
  ships a data migration to clean up existing rows.
