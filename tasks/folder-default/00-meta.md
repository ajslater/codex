# Folder mode default — meta plan

## The asks

1. **Per-user "remember last view" for the bare URL.** A user who
   prefers folder mode, browses in `/f/0/1`, then closes their tab
   and re-visits `/` should land back in `/f/0/1`. The user notes
   this already works "when codex remembers their session
   preferences" — so the per-user mechanism exists; the gap is the
   fallback case when there's no saved row.

2. **Admin-controlled fallback for new and anonymous users.** When
   no per-user setting exists, a new admin flag chooses between
   `Story Arc` (`/a/0/1`), `Groups` (`/r/0/1` — current default),
   or `Folders` (`/f/0/1`).

## What already works

The per-user / per-session "remember last route" plumbing is
complete:

- **Model**: `SettingsBrowserLastRoute` (`codex/models/settings.py:279`)
  is a one-to-one extension of `SettingsBrowser` storing `group`,
  `pks`, `page`. Created with the parent settings row.
- **Save path**: every browser API request flows through
  `BrowserParamsView.params` (`codex/views/browser/params.py:53-64`),
  which calls `_update_last_route(params)` then
  `save_params_to_settings(params)`. So every navigation persists
  the new route.
- **Read path**: `IndexView.get` (`codex/views/frontend.py:28-34`)
  serves the SPA bootloader template; calls
  `self.get_last_route()` (`codex/views/settings.py:277`), which
  reads the user's `SettingsBrowserLastRoute` row via
  `get_from_settings("last_route", browser=True)`. Falls back to
  `DEFAULT_BROWSER_ROUTE` if absent.
- **Frontend handoff**: `headers-script-globals.html:6` injects
  the route as `globalThis.CODEX.LAST_ROUTE`;
  `frontend/src/plugins/router.js:16-25` redirects the bare `/`
  route to it.

The fallback default lives in `codex/choices/browser.py:66`:

```python
DEFAULT_BROWSER_ROUTE = MappingProxyType(
    {"group": "r", "pks": (0,), "page": 1}
)
```

That hardcoded `"r"` is the only place change is needed for the
admin-default ask.

## What's missing / suspect

- **Admin-controlled fallback default**: the hardcoded `"r"`
  means a new install or anonymous-pre-navigation user always
  starts at the groups view. No way to express "default to
  folders" or "default to story arc" without editing source.
- **Per-user mechanism may have edge cases worth verifying**:
  the user's complaint "the bare codex start url defaults to
  going to /r/0/1" hints that even users with saved preferences
  sometimes land on `/r/0/1`. Possible causes:
  - Anonymous user clears cookies → new session → no saved row →
    falls through to default. Same cause as the new-user case;
    the admin-default flag fixes this.
  - User auth-promotion flow (`_get_or_create_settings_session`
    promotes anonymous row to user row on first login) might
    have a window where the row isn't found by either lookup.
    Worth a regression test.
  - The route stored in `last_route` could become unreachable
    (e.g., user was on `/f/...` but admin disabled `FOLDER_VIEW`
    flag in the meantime), causing the frontend or browser API
    to redirect somewhere safe — currently this would silently
    bounce to root, not surface the misconfiguration.

## Proposed approach

One sub-plan covers it cleanly. The per-user mechanism stays
intact; we add an admin-controlled fallback that sits behind it.

- **[01-admin-default-group.md](./01-admin-default-group.md)** —
  Add `BROWSER_DEFAULT_GROUP` admin flag with choices
  `Folders` / `Groups` / `Story Arcs` (mapping to `f` / `r` / `a`
  on the wire). `IndexView.get_last_route()` reads the flag when
  no per-user row exists. Includes:
  - New `AdminFlagChoices.BROWSER_DEFAULT_GROUP` enum value
  - Schema validation: must be one of the supported choices,
    defaults to `"r"` (preserves current behavior)
  - Migration: insert the flag row with default value
  - Frontend admin tab entry so users can change it from the UI
  - Regression test for the per-user fallback path

## Out of scope

- **The "browser select box for defaults" the user mentioned as
  a worst-case fallback**: not needed. The per-user `top_group`
  field on `SettingsBrowser` already serves this role and is
  already surfaced in the UI (`top-group-select.vue`). Users who
  want a personal default can pin `top_group = "f"` today.
- **Visual indicator when the admin-default route is unreachable
  (e.g., admin set default to Folders but FOLDER_VIEW=False)**.
  The flag-validation should refuse the inconsistent
  configuration at save time; pure UX concern, not architectural.
- **Migrating existing users**: the new flag is a fallback for
  users with no `last_route` row. Existing users keep theirs.
  The admin flag's default value preserves the current `r` for
  upgrade-day no-op.

## Decisions (resolved)

1. **Label**: "Default View".
2. **Override returning users' `top_group`?** No — admin sets the
   floor for "no expressed preference"; users who pin `top_group`
   keep their pin.
3. **Choice surface**: the seven entries already in
   `BROWSER_TOP_GROUP_CHOICES`, with two-tier mapping:

   | Label | Flag value | URL `group` | New-user `top_group` |
   | --- | --- | --- | --- |
   | Folders | `f` | `f` | `f` |
   | Story Arcs | `a` | `a` | `a` |
   | Publishers | `p` | `r` | `p` |
   | Imprints | `i` | `r` | `i` |
   | Series | `s` | `r` | `s` |
   | Volumes | `v` | `r` | `v` |
   | Issues | `c` | `r` | `c` |

   For `f` and `a` the URL `group` matches the flag — they have
   their own dedicated routes. For the other five the URL stays
   at `/r/0/1` and the per-user `top_group` setting controls
   what gets shown. So the flag has to drive **both** the
   `last_route.group` returned by `IndexView` **and** the
   `top_group` default for newly-created `SettingsBrowser` rows.
   The `top_group` default propagation is the part my original
   sketch missed; sub-plan 01 now covers it.
