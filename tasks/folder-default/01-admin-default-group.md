# 01 — `BROWSER_DEFAULT_GROUP` admin flag

The single change that resolves the meta plan. Adds an admin flag
that picks the fallback group when a request reaches `IndexView`
without a per-user / per-session `last_route` row. Existing users
who already navigate at all keep their persisted `last_route`
unchanged.

## Wire model

Reusable structure: codex's existing flags use the
`AdminFlag.value` CharField for free-form values
(`AdminFlag.banner_text`, `AdminFlag.age_rating_*`). We do the
same — store the group code as a string in `value`, with
serializer-level validation that it's a member of
`BROWSER_ROUTE_CHOICES`.

```python
# codex/choices/admin.py
class AdminFlagChoices(TextChoices):
    ...
    BROWSER_DEFAULT_GROUP = "BG"

ADMIN_FLAG_CHOICES = MappingProxyType({
    ...
    AdminFlagChoices.BROWSER_DEFAULT_GROUP.value: "Browser Default Group",
})
```

The label phrasing is the user-facing choice. Suggested:
**"Default View"** in the admin UI, with an explanation tooltip
"View shown to anonymous and new users when they have no saved
preference."

## Choice surface

`BROWSER_ROUTE_CHOICES` (`codex/choices/browser.py:50`) is the
source of truth — it's `BROWSER_TOP_GROUP_CHOICES` plus the `"r"`
root pseudo-group:

```
"p" Publishers
"i" Imprints
"s" Series
"v" Volumes
"f" Folders
"a" Story Arcs
"r" Root  (the existing default)
```

The user mentioned three: Story Arc / Groups / Folders. I'd
expose all seven — there's no harm in letting an admin default
to "Series" if that's what their library wants. The dropdown
labels come from the existing `BROWSER_ROUTE_CHOICES` dict so
they stay in sync with everything else.

## Default value

`"r"` — preserves the current hardcoded behavior on upgrade-day.
No existing install changes behavior unless the admin opts in.

## Code touchpoints

### 1. Choices + label

```python
# codex/choices/admin.py
class AdminFlagChoices(TextChoices):
    ANONYMOUS_USER_AGE_RATING = "AA"
    AGE_RATING_DEFAULT = "AR"
    AUTO_UPDATE = "AU"
    BANNER_TEXT = "BT"
    BROWSER_DEFAULT_GROUP = "BG"  # NEW
    FOLDER_VIEW = "FV"
    ...

ADMIN_FLAG_CHOICES = MappingProxyType({
    ...
    AdminFlagChoices.BROWSER_DEFAULT_GROUP.value: "Browser Default Group",
})
```

### 2. Migration

`0044_admin_flag_browser_default_group.py`:

- `AlterField(model_name="adminflag", name="key", choices=...)` —
  add `"BG"` to the choices list.
- `RunPython(_seed_browser_default_group_flag)` — insert the row
  with `value="r"` (preserves current behavior).

```python
def _seed_browser_default_group_flag(apps, _schema_editor):
    AdminFlag = apps.get_model("codex", "AdminFlag")
    AdminFlag.objects.get_or_create(
        key="BG",
        defaults={"on": True, "value": "r"},
    )
```

### 3. Startup seed parity

`codex/startup/__init__.py:init_admin_flags` currently seeds
`age_rating_defaults` separately. Extend the same pattern so
`BROWSER_DEFAULT_GROUP` rows recreated after an admin deletion
get `value="r"`:

```python
default_value_overrides = {
    AdminFlagChoices.BROWSER_DEFAULT_GROUP.value: "r",
}

for key, title in AdminFlagChoices.choices:
    defaults = {"on": key not in AdminFlag.FALSE_DEFAULTS}
    if key in age_rating_defaults:
        defaults["age_rating_metron_id"] = ...
    if key in default_value_overrides:
        defaults["value"] = default_value_overrides[key]
    flag, created = AdminFlag.objects.get_or_create(defaults=defaults, key=key)
```

### 4. Serializer validation

`codex/serializers/admin/flags.py`'s `AdminFlagSerializer`
currently accepts any string for `value`. Add a `validate`
method that rejects out-of-range group codes when
`key == "BG"`:

```python
def validate(self, attrs):
    if (
        self.instance
        and self.instance.key == AdminFlagChoices.BROWSER_DEFAULT_GROUP.value
        and (val := attrs.get("value", self.instance.value))
        not in BROWSER_ROUTE_CHOICES
    ):
        raise ValidationError({
            "value": f"Must be one of {tuple(BROWSER_ROUTE_CHOICES)}",
        })
    return attrs
```

### 5. `IndexView` fallback path

`codex/views/settings.py:277` — `get_last_route()` currently
falls back to `DEFAULT_BROWSER_ROUTE`. Change to:

```python
def get_last_route(self) -> Mapping:
    """Get the last route from the browser session."""
    if last_route := self.get_from_settings("last_route", browser=True):
        return last_route
    return self._get_admin_default_route()

@staticmethod
def _get_admin_default_route() -> Mapping:
    """Resolve the admin-configured default route.

    Falls back to the hardcoded ``DEFAULT_BROWSER_ROUTE`` if the
    flag row is missing or holds an invalid group code (defense
    against a hand-edited DB / pre-migration state).
    """
    try:
        flag = AdminFlag.objects.only("on", "value").get(
            key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value
        )
    except AdminFlag.DoesNotExist:
        return DEFAULT_BROWSER_ROUTE
    group = flag.value if flag.on and flag.value in BROWSER_ROUTE_CHOICES else "r"
    return {"group": group, "pks": (0,), "page": 1}
```

The `flag.on` check lets an admin disable the override without
deleting the row — `on=False` reverts to the hardcoded `"r"`.
Marginal feature but matches the boolean-flag idiom.

Hot-path concern: this runs on every bare-URL hit. The
`AdminFlag` row is one indexed `key` lookup; ~1 ms. If profiling
shows it on the path, cache it for the request lifetime via
`functools.cache` on a method decorated to invalidate when the
flag changes (the `_on_change` hook in `views/admin/flag.py`
already broadcasts `ADMIN_FLAGS_CHANGED_TASK`).

### 6. Frontend admin tab

`frontend/src/components/admin/tabs/flag-tab.vue` renders the
existing flags. Looking at how `BANNER_TEXT` (a `value`-string
flag) is rendered already — same pattern with a `<v-select>`
instead of `<v-text-field>` for the choice list:

```vue
<v-select
  v-if="flag.key === 'BG'"
  v-model="flag.value"
  :items="browserRouteChoices"
  label="Default View"
/>
```

Where `browserRouteChoices` comes from the existing choices
JSON (codex generates `frontend/src/choices/browser.json` from
`BROWSER_TOP_GROUP_CHOICES` via `make build-choices`).

### 7. Surface the choice on the build-choices export

`make build-choices` regenerates `frontend/src/choices/*.json`
from the Django enums. Confirm `BROWSER_ROUTE_CHOICES` (or its
dict form) is already exported; if not, add to the build
manifest. This is plumbing the frontend already does for
existing choices.

## Tests

### Unit: fallback resolution

```python
def test_index_view_uses_admin_default_when_no_user_route(self):
    AdminFlag.objects.update_or_create(
        key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value,
        defaults={"on": True, "value": "f"},
    )
    response = self.client.get("/")
    # SPA template injects last_route into globalThis.CODEX
    self.assertContains(response, '"group": "f"')

def test_index_view_falls_back_when_admin_value_invalid(self):
    AdminFlag.objects.update_or_create(
        key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value,
        defaults={"on": True, "value": "z"},  # not a valid group
    )
    response = self.client.get("/")
    self.assertContains(response, '"group": "r"')

def test_index_view_uses_user_route_over_admin_default(self):
    user = User.objects.create_user(...)
    self.client.force_login(user)
    AdminFlag.objects.update_or_create(
        key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value,
        defaults={"on": True, "value": "f"},
    )
    # Simulate the user having navigated to /a/0/1
    self.client.get("/a/0/1")
    response = self.client.get("/")
    # User's last_route wins over admin default
    self.assertContains(response, '"group": "a"')
```

### Validation

```python
def test_admin_flag_serializer_rejects_invalid_group(self):
    flag = AdminFlag.objects.get(key="BG")
    serializer = AdminFlagSerializer(flag, data={"value": "z"}, partial=True)
    self.assertFalse(serializer.is_valid())
    self.assertIn("value", serializer.errors)
```

### Migration safety

```python
def test_migration_seeds_browser_default_group_with_r(self):
    # Already-existing install: the migration should insert the
    # row with value="r" so behavior is unchanged on upgrade.
    flag = AdminFlag.objects.get(key="BG")
    self.assertEqual(flag.value, "r")
    self.assertTrue(flag.on)
```

## Correctness invariants

- **Per-user route still wins**: the new code sits in the
  `if last_route := self.get_from_settings("last_route", browser=True)`
  fallback branch. Users with persisted state hit the early
  return on line 280 of `views/settings.py:277-281` and never
  see the admin default.
- **Upgrade-day no-op**: the migration inserts `value="r"` so
  existing installs see no behavior change. Admins must opt
  into the new default explicitly.
- **Disabled flag = old default**: setting `on=False` reverts
  to `"r"` without requiring the admin to re-enter the value.
- **Invalid persisted value falls back**: if the DB somehow
  holds a non-route-choice string in `value` (downgrade edge
  case, manual SQL edit), the fallback returns `"r"` rather
  than crashing the SPA bootloader.

## Risks

- **Choice cardinality**: if codex later adds a new top-group
  choice, the migration choices list needs the same update;
  routine pattern. The serializer validation reads
  `BROWSER_ROUTE_CHOICES` at call time so it picks up new
  entries automatically.
- **Cache invalidation on flag change**: the existing
  `AdminFlagViewSet._on_change()` broadcasts an
  `ADMIN_FLAGS_CHANGED_TASK` for `_REFRESH_LIBRARY_FLAGS`. The
  new flag should join that set so an admin's change is
  reflected immediately rather than waiting for the next page
  load. The actual UI refresh is the frontend's job; backend
  just notifies.
- **OPDS clients**: `OPDSV1Feed` / `OPDSV2Feed` have their own
  default-route logic gated on `folder_view`. They don't go
  through `IndexView`, so the new flag doesn't touch them.
  Worth a sentence in the admin tooltip clarifying "browser
  only — OPDS feeds use the OPDS spec's discovery flow."

## Suggested commit shape

One PR, three commits:

1. **`models / startup: add BROWSER_DEFAULT_GROUP admin flag`** —
   choices enum, migration, startup seed parity, serializer
   validation.
2. **`views: honor BROWSER_DEFAULT_GROUP in IndexView fallback`** —
   the `_get_admin_default_route` helper + `get_last_route`
   change + `_REFRESH_LIBRARY_FLAGS` membership.
3. **`frontend: admin tab control for default view`** — Vue
   select using the existing choices JSON; `make build-choices`
   regen if needed.

Total ~150 LOC across the three commits.

## Out of scope

The "browser select box for defaults" the user mentioned as a
worst-case fallback — already exists. `top_group` on
`SettingsBrowser` is a per-user preference, surfaced in the UI
at `frontend/src/components/browser/toolbars/top/top-group-select.vue`.
A user who wants their personal default to be Folders pins
`top_group = "f"` today; the admin flag covers the
no-preference-yet case orthogonally.
