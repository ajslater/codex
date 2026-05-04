# 04 — Auth + admin + small surfaces

This sub-plan covers everything outside the browser/OPDS/models
hot paths: top-level serializers (`auth.py`, `homepage.py`,
`reader.py`, `route.py`, `versions.py`, etc.) plus
`codex/serializers/admin/`.

## Surface

Top-level (`codex/serializers/`):

- `auth.py` — auth-related serializers
- `homepage.py` — `/homepage`
- `mixins.py` — `OKSerializer`, `JSONFieldSerializer` helpers
- `reader.py` — reader open response (148 LOC)
- `redirect.py` — 404 handler shapes
- `route.py` — frontend route shape
- `settings.py` — browser settings input
- `versions.py` — `/versions`

Admin (`codex/serializers/admin/`):

- `flags.py` — admin flag CRUD
- `groups.py` — admin group CRUD
- `libraries.py` — admin library CRUD (validate_path here)
- `stats.py` — admin stats response (already cached by PR #610)
- `tasks.py` — admin task input
- `users.py` — admin user CRUD

## Findings

### F1 — `codex/serializers/auth.py`: dead code **(cleanup)**

`UserSerializer`, `UserCreateSerializer`, `UserLoginSerializer`,
`TimezoneSerializerMixin`, `TimezoneSerializer` are declared but
**never imported anywhere**:

```bash
$ grep -rn 'codex.serializers.auth' codex/ | grep -v __pycache__
codex/views/timezone.py:8:from codex.serializers.auth import TimezoneSerializer
codex/views/public.py:12:from codex.serializers.auth import AuthAdminFlagsSerializer
```

Only `TimezoneSerializer` and `AuthAdminFlagsSerializer` are live.

The dead `UserSerializer` includes a `get_admin_flags` SMF that
fires `AdminFlag.objects.filter(...)` per call — but it's never
called. **Delete the dead serializers.**

The actual auth-flags endpoint is `AdminFlagsView` in
`codex/views/public.py`, which uses `AuthAdminFlagsSerializer`
(scalar fields only — verified clean).

**Fix:** Trim `auth.py` to:

```python
"""Codex Auth Serializers."""

from rest_framework.fields import BooleanField, CharField
from rest_framework.serializers import (
    Serializer,
    SerializerMetaclass,
)

from codex.serializers.fields.auth import TimezoneField


class TimezoneSerializerMixin(metaclass=SerializerMetaclass):
    """Serialize Timezone submission from front end."""

    timezone = TimezoneField(write_only=True)


class TimezoneSerializer(TimezoneSerializerMixin, Serializer):
    """Serialize Timezone submission from front end."""


class AuthAdminFlagsSerializer(Serializer):
    """Admin flags related to auth."""

    banner_text = CharField(read_only=True)
    lazy_import_metadata = BooleanField(read_only=True)
    non_users = BooleanField(read_only=True)
    registration = BooleanField(read_only=True)
```

Drop unused imports (`User`, `AdminFlag`, `AdminFlagChoices`,
`SanitizedCharField`, `BaseModelSerializer`,
`SerializerMethodField`).

### F2 — `LibrarySerializer.validate_path` O(N) overlap check
**(low impact, cosmetic)**

`codex/serializers/admin/libraries.py:48-63`.

```python
def validate_path(self, path):
    ppath = Path(path).resolve()
    if not ppath.is_dir():
        raise ValidationError("Not a valid folder on this server")
    existing_path_strs = Library.objects.values_list("path", flat=True)
    for existing_path_str in existing_path_strs:
        existing_path = Path(existing_path_str)
        if existing_path.is_relative_to(ppath):
            raise ValidationError("Parent of existing library path")
        if ppath.is_relative_to(existing_path):
            raise ValidationError("Child of existing library path")
    return path
```

Loops every Library row to check parent/child relationships. O(N)
where N is the library count.

**Status:** Library counts are typically < 50; not a perf hot
spot. Keep the loop but cache the queryset evaluation:

```python
def validate_path(self, path):
    ppath = Path(path).resolve()
    if not ppath.is_dir():
        raise ValidationError("Not a valid folder on this server")
    existing_paths = [
        Path(p) for p in Library.objects.values_list("path", flat=True)
    ]
    for existing in existing_paths:
        if existing.is_relative_to(ppath):
            raise ValidationError("Parent of existing library path")
        if ppath.is_relative_to(existing):
            raise ValidationError("Child of existing library path")
    return path
```

The simplification is cosmetic — no real perf gain on a small N.
**Recommend dropping this finding** unless library count
discovery surfaces it as a problem.

### F3 — `GroupSerializer.exclude` source chain assertion
**(test addition)**

`codex/serializers/admin/groups.py:17`.

```python
exclude = BooleanField(default=False, source="groupauth.exclude")
```

`AdminGroupViewSet.queryset` already calls
`.select_related("groupauth")`, but no test enforces it. A future
refactor that splits the queryset will silently regress to N+1.

**Fix:** add a regression test:

```python
def test_admin_group_list_query_count(admin_client, three_groups):
    with CaptureQueriesContext(connection) as ctx:
        admin_client.get("/api/v3/admin/group")
    # 1 group list + 1 prefetch + setup queries; no per-group fanout
    assert len(ctx.captured_queries) <= 4
```

The exact count depends on per-request setup; pick a ceiling that
catches "1 + N × 3" without false-flagging "1 + 3" baselines.

### F4 — `UserSerializer.last_active` / `age_rating_metron` source
chains **(test addition)**

`codex/serializers/admin/users.py:33-40`.

```python
last_active = DateTimeField(read_only=True, source="userauth.updated_at",
                            allow_null=True)
age_rating_metron = PrimaryKeyRelatedField(
    queryset=AgeRatingMetron.objects.all(),
    source="userauth.age_rating_metron",
    allow_null=True,
    required=False,
)
```

`AdminUserViewSet.queryset` calls
`.select_related("userauth__age_rating_metron")`. Same situation as
F3 — works today, no test enforces it. Add the same shape of test
for `/api/v3/admin/user`.

**Note:** `PrimaryKeyRelatedField(queryset=AgeRatingMetron.objects.all())`
also has a per-init cost — DRF evaluates the queryset to validate
incoming pks. This is unavoidable unless the validation model is
changed. Low impact; admin user writes are infrequent.

### F5 — `ReaderComicsSerializer` `ArcsIdsField.to_representation`
**(low impact)**

`codex/serializers/reader.py:119-132`.

```python
class ArcsIdsField(DictField):
    def to_representation(self, value):
        string_keyed_map = {}
        for ids, arc_info in value.items():
            string_key = ",".join(str(pk) for pk in ids)
            string_keyed_map[string_key] = arc_info
        return super().to_representation(string_keyed_map)
```

Rebuilds string keys for the arcs dict per reader-open. Each comic
in a story arc spans the dict; a complex arc graph could have 50+
entries.

**Status:** reader-open is a one-shot operation per book. Not a
hot path. Cosmetic refactor only — could move the string-key
construction upstream, but the cost is low microseconds.

**Recommend dropping unless reader open shows up in baseline.**

### F6 — `RouteSerializer.to_representation` tuple→string
**(verified clean)**

`codex/serializers/route.py:14-44`. Tuple sort + string join per
serialization. Used in 404 redirect handlers; low volume.

### F7 — Verify `homepage.py`, `versions.py`, `mixins.py`,
`settings.py`, `redirect.py` **(verified clean)**

All read-only scalar serializers, no SMFs, no DB. Single endpoint
calls each.

### F8 — `admin/flags.py:AdminFlagSerializer` **(verified clean)**

`codex/serializers/admin/flags.py:9-25`. CRUD for `AdminFlag` rows.
Includes `PrimaryKeyRelatedField(queryset=AgeRatingMetron.objects.all())` —
unavoidable for write validation. List/detail GETs are admin-tab
loads, low frequency. No fix.

### F9 — `admin/stats.py` **(out of scope — covered in PR #610)**

The `/admin/stats` endpoint is cached for 60s by PR #610. The
nested serializer structure is fine for a single response; no
per-row work. **Skip.**

### F10 — `admin/tasks.py:AdminLibrarianTaskSerializer`
**(verified clean)**

`codex/serializers/admin/tasks.py`. Module-level
`_ADMIN_JOB_CHOICES` tuple built once at import. Per-call cost
near zero.

## Suggested commit shape

One PR, two commits:

1. **F1: dead-code cleanup in `auth.py`.** Single-file diff,
   ~30 lines deleted. Lint passes.
2. **F3 + F4: regression tests for admin source chains.** New
   tests file `tests/serializers/test_admin_query_counts.py`
   covering `/admin/group` and `/admin/user` list endpoints.

F2 (validate_path), F5 (ArcsIdsField), F6 (RouteSerializer) are
optional discretionary follow-ups; flag in commit message and
defer.

## Verification

- `make lint-python` clean (the trim removes unused imports — Ruff
  catches them).
- `make test-python` clean.
- New `tests/serializers/test_admin_query_counts.py` passes.
- `grep -rn 'UserSerializer\|UserCreateSerializer\|UserLoginSerializer'
  codex/serializers/auth.py` returns nothing (deleted).
- Confirm
  `from codex.serializers.auth import AuthAdminFlagsSerializer,
  TimezoneSerializer` still resolve (live consumers).
