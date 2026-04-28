# 01 — `BROWSER_DEFAULT_GROUP` admin flag

The single change that resolves the meta plan. Adds an admin flag
that picks the fallback view when a request reaches `IndexView`
without a per-user / per-session `last_route` row, AND drives the
`top_group` default for newly-created `SettingsBrowser` rows.
Existing users who already navigate keep their persisted
`last_route` and `top_group` unchanged.

## Wire model

Reusable structure: codex's existing flags use the
`AdminFlag.value` CharField for free-form values
(`AdminFlag.banner_text`, `AdminFlag.age_rating_*`). We do the
same — store the group code as a string in `value`, with
serializer-level validation that it's a member of
`BROWSER_TOP_GROUP_CHOICES`.

```python
# codex/choices/admin.py
class AdminFlagChoices(TextChoices):
    ...
    BROWSER_DEFAULT_GROUP = "BG"

ADMIN_FLAG_CHOICES = MappingProxyType({
    ...
    AdminFlagChoices.BROWSER_DEFAULT_GROUP.value: "Default View",
})
```

UI label: **"Default View"**, tooltip "View shown to anonymous
and new users when they have no saved preference."

## Choice surface

The seven values already in `BROWSER_TOP_GROUP_CHOICES`
(`codex/choices/browser.py:42-49`):

| Label | Flag value | URL `group` | New-user `top_group` |
| --- | --- | --- | --- |
| Folders | `f` | `f` | `f` |
| Story Arcs | `a` | `a` | `a` |
| Publishers | `p` | `r` | `p` |
| Imprints | `i` | `r` | `i` |
| Series | `s` | `r` | `s` |
| Volumes | `v` | `r` | `v` |
| Issues | `c` | `r` | `c` |

Two distinct things the flag drives:

1. **`IndexView.get_last_route()`** — the bare-`/` redirect
   target. For `f` and `a` the URL `group` matches the flag;
   for the rest it's `r` (the canonical groups-view URL).
2. **New-user `SettingsBrowser.top_group`** — the existing model
   default is the hardcoded `"p"`. For Publishers/Imprints/
   Series/Volumes/Issues to actually display the right view, a
   freshly-created row needs `top_group = flag_value`. For `f`
   and `a` the URL itself selects the view, but we set
   `top_group` to match anyway so the per-user state is
   consistent if the admin later flips back.

Mapping helper:

```python
# codex/choices/browser.py
_FLAG_GROUP_HAS_OWN_ROUTE = frozenset({"f", "a"})

def admin_default_route_for(flag_value: str) -> dict:
    """Translate a BROWSER_DEFAULT_GROUP flag value into a route dict."""
    group = flag_value if flag_value in _FLAG_GROUP_HAS_OWN_ROUTE else "r"
    return {"group": group, "pks": (0,), "page": 1}
```

## Default value

`"p"` — matches the existing `SettingsBrowser.top_group` default
and preserves the existing hardcoded route fallback (`"r"` group,
which is what Publishers maps to in the table above). Upgrade-day
no-op for both reads.

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
  with `value="p"` (matches the existing
  `SettingsBrowser.top_group` default).

```python
def _seed_browser_default_group_flag(apps, _schema_editor):
    AdminFlag = apps.get_model("codex", "AdminFlag")
    AdminFlag.objects.get_or_create(
        key="BG",
        defaults={"on": True, "value": "p"},
    )
```

### 3. Startup seed parity

`codex/startup/__init__.py:init_admin_flags` currently seeds
`age_rating_defaults` separately. Extend the same pattern so
`BROWSER_DEFAULT_GROUP` rows recreated after an admin deletion
get `value="p"`:

```python
default_value_overrides = {
    AdminFlagChoices.BROWSER_DEFAULT_GROUP.value: "p",
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
method that rejects out-of-range top-group codes when
`key == "BG"`:

```python
def validate(self, attrs):
    if (
        self.instance
        and self.instance.key == AdminFlagChoices.BROWSER_DEFAULT_GROUP.value
        and (val := attrs.get("value", self.instance.value))
        not in BROWSER_TOP_GROUP_CHOICES
    ):
        raise ValidationError({
            "value": f"Must be one of {tuple(BROWSER_TOP_GROUP_CHOICES)}",
        })
    return attrs
```

Note: `BROWSER_TOP_GROUP_CHOICES` (not `BROWSER_ROUTE_CHOICES`)
— `"r"` is not a valid flag value because it's not a
`top_group`; the route URL `r` is *derived* from the flag value
via `admin_default_route_for`.

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
def _get_admin_default_top_group() -> str:
    """Read the admin-configured default top group.

    Returns the validated flag value, falling back to ``"p"`` if
    the row is missing, the flag is off, or the value is invalid
    (defense against a hand-edited DB / pre-migration state).
    """
    try:
        flag = AdminFlag.objects.only("on", "value").get(
            key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value
        )
    except AdminFlag.DoesNotExist:
        return "p"
    if flag.on and flag.value in BROWSER_TOP_GROUP_CHOICES:
        return flag.value
    return "p"

@classmethod
def _get_admin_default_route(cls) -> Mapping:
    """Translate the admin default top group into a bare-URL redirect target."""
    return admin_default_route_for(cls._get_admin_default_top_group())
```

The `flag.on` check lets an admin disable the override without
deleting the row — `on=False` reverts to the hardcoded `"p"`/`"r"`.

### 6. New-user `top_group` propagation

`codex/views/settings.py:_create_browser_settings` currently
creates `SettingsBrowser` rows with the model-level default
`top_group="p"`. To make Series / Volumes / Issues admin-default
choices actually display the right view for a new user, set
`top_group` from the admin flag at row-creation time:

```python
@classmethod
def _create_browser_settings(cls, user, session_key, client, create_args):
    """Create a SettingsBrowser with its related show/filters/last_route."""
    show, _ = SettingsBrowserShow.objects.get_or_create(...)
    # Admin-controlled default applies only to NEW rows. Returning
    # users with a persisted ``top_group`` keep theirs because
    # ``_get_or_create_settings`` returns the existing row before
    # reaching this branch.
    create_kwargs = dict(create_args)
    create_kwargs.setdefault("top_group", cls._get_admin_default_top_group())
    instance = SettingsBrowser.objects.create(
        user=user,
        session_id=session_key,
        client=client,
        show=show,
        **create_kwargs,
    )
    ...
```

The `setdefault` lets explicit callers (admin tools, tests) pass
their own `top_group` and only fills from the flag when the
caller didn't specify.

Hot-path concern: `_get_admin_default_top_group` runs once at
the moment a new `SettingsBrowser` row is created (rare, only
on first navigation per session/user). The bare-URL path also
hits it for the route resolution. The `AdminFlag` row is one
indexed `key` lookup; ~1 ms. If profiling shows it on the path,
cache for the request lifetime via the same pattern the
`_on_change` hook already uses (broadcasts
`ADMIN_FLAGS_CHANGED_TASK`).

### 7. Frontend admin tab

`frontend/src/components/admin/tabs/flag-tab.vue` renders the
existing flags. Looking at how `BANNER_TEXT` (a `value`-string
flag) is rendered already — same pattern with a `<v-select>`
instead of `<v-text-field>` for the choice list:

```vue
<v-select
  v-if="flag.key === 'BG'"
  v-model="flag.value"
  :items="topGroupChoices"
  label="Default View"
/>
```

Where `topGroupChoices` comes from the existing choices JSON
already generated from `BROWSER_TOP_GROUP_CHOICES`
(`frontend/src/choices/browser.json` includes `TOP_GROUP`).

### 8. Surface the choice on the build-choices export

`make build-choices` regenerates `frontend/src/choices/*.json`
from the Django enums. `BROWSER_TOP_GROUP_CHOICES` is already
exported as `TOP_GROUP` in `BROWSER_CHOICES` so the seven
labels are already available to the frontend; no build-choices
change required.

## Tests

### Unit: route fallback resolution

```python
def test_index_view_uses_folder_default_when_no_user_route(self):
    """Flag value 'f' yields a /f/0/1 redirect."""
    AdminFlag.objects.update_or_create(
        key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value,
        defaults={"on": True, "value": "f"},
    )
    response = self.client.get("/")
    self.assertContains(response, '"group": "f"')

def test_index_view_uses_root_for_top_group_choices(self):
    """Flag value 's' (Series) yields /r/0/1; the per-user
    SettingsBrowser row carries top_group=s for the actual view."""
    AdminFlag.objects.update_or_create(
        key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value,
        defaults={"on": True, "value": "s"},
    )
    response = self.client.get("/")
    self.assertContains(response, '"group": "r"')

def test_index_view_falls_back_when_admin_value_invalid(self):
    AdminFlag.objects.update_or_create(
        key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value,
        defaults={"on": True, "value": "z"},  # not a top-group
    )
    response = self.client.get("/")
    # Falls back to "p" -> /r/0/1 (Publishers in groups view).
    self.assertContains(response, '"group": "r"')

def test_index_view_falls_back_when_admin_flag_off(self):
    AdminFlag.objects.update_or_create(
        key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value,
        defaults={"on": False, "value": "f"},
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
    # Simulate the user having navigated to /a/0/1.
    self.client.get("/a/0/1")
    response = self.client.get("/")
    self.assertContains(response, '"group": "a"')
```

### Unit: new-user `top_group` propagation

```python
def test_new_session_top_group_uses_admin_default(self):
    """A first-navigation request creates a SettingsBrowser row
    whose top_group reflects the admin's chosen view."""
    AdminFlag.objects.update_or_create(
        key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value,
        defaults={"on": True, "value": "v"},  # Volumes
    )
    self.client.get("/api/v3/r/0/1/...")  # browser endpoint
    row = SettingsBrowser.objects.get(...)  # newly created
    self.assertEqual(row.top_group, "v")

def test_existing_user_top_group_unchanged_by_admin_default(self):
    """Returning user keeps their pinned top_group regardless of
    a later admin-flag change."""
    user = User.objects.create_user(...)
    self.client.force_login(user)
    self.client.get("/api/v3/r/0/1/...")  # creates row
    SettingsBrowser.objects.filter(user=user).update(top_group="i")
    AdminFlag.objects.update_or_create(
        key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value,
        defaults={"on": True, "value": "v"},
    )
    self.client.get("/api/v3/r/0/1/...")
    row = SettingsBrowser.objects.get(user=user)
    self.assertEqual(row.top_group, "i")  # not "v"
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
def test_migration_seeds_browser_default_group_with_p(self):
    # Already-existing install: the migration should insert the
    # row with value="p" so the URL-derivation rule still maps
    # to the existing /r/0/1 redirect.
    flag = AdminFlag.objects.get(key="BG")
    self.assertEqual(flag.value, "p")
    self.assertTrue(flag.on)
```

## Correctness invariants

- **Per-user route still wins**: the new code sits in the
  `if last_route := self.get_from_settings("last_route", browser=True)`
  fallback branch. Users with persisted state hit the early
  return on line 280 of `views/settings.py:277-281` and never
  see the admin default.
- **Returning users' `top_group` unchanged**: the
  `_create_browser_settings` change only fires on row *creation*
  (no existing row). `_get_or_create_settings` returns the
  existing row before reaching the create branch, so a returning
  user's pinned `top_group` is never overwritten.
- **Upgrade-day no-op**: the migration inserts `value="p"`. With
  the URL-derivation rule, `"p"` maps to URL `"r"` — exactly the
  pre-fix hardcoded default. New `SettingsBrowser` rows also get
  `top_group="p"`, matching the model default. So existing
  installs see no behavior change. Admins must opt into a
  different default explicitly.
- **Disabled flag = old default**: setting `on=False` reverts
  to `"p"` (and thus URL `"r"`) without requiring the admin to
  re-enter the value.
- **Invalid persisted value falls back**: if the DB somehow
  holds a non-top-group string in `value` (downgrade edge case,
  manual SQL edit), the fallback returns `"p"` rather than
  crashing the SPA bootloader or storing an invalid `top_group`.

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
   choices enum + label, migration (seed `value="p"`), startup
   seed parity, serializer validation against
   `BROWSER_TOP_GROUP_CHOICES`, `admin_default_route_for` helper
   in `codex/choices/browser.py`.
2. **`views: honor BROWSER_DEFAULT_GROUP in IndexView fallback`** —
   `_get_admin_default_top_group` + `_get_admin_default_route`
   helpers, `get_last_route` change, `_create_browser_settings`
   `top_group` propagation, `_REFRESH_LIBRARY_FLAGS` membership.
3. **`frontend: admin tab control for default view`** — Vue
   `<v-select>` rendering on `flag.key === "BG"`, populated from
   the existing `TOP_GROUP` choices JSON.

Total ~150 LOC across the three commits.

## Out of scope

The "browser select box for defaults" the user mentioned as a
worst-case fallback — already exists. `top_group` on
`SettingsBrowser` is a per-user preference, surfaced in the UI
at `frontend/src/components/browser/toolbars/top/top-group-select.vue`.
A user who wants their personal default to be Folders pins
`top_group = "f"` today; the admin flag covers the
no-preference-yet case orthogonally.
