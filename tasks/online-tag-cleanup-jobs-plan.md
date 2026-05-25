# Online Tag Cleanup Jobs — Plan

## Goal

Add admin-triggerable cleanup operations for the online tagging
subsystem, and wire them into the nightly janitor sweep. The online
tag pipeline persists session state to `ComicboxTaggingDefaults`
(`active_session_id`, `active_prompts`) to survive process restarts,
but there is currently no path — manual or scheduled — to clear
stale rows when a session dies uncleanly or a prompt batch times out.

## Background

Relevant files:

- DB row holding session state: `codex/models/admin.py:111-112`
  (`active_session_id`, `active_prompts` on `ComicboxTaggingDefaults`)
- Session manager that reads/writes those fields:
  `codex/librarian/onlinetag/session_manager.py`
  (`_persist_session`, `_persist_prompts`, `_clear_session_db`)
- Existing nightly tasks: `codex/librarian/scribe/janitor/janitor.py`
  (`_NIGHTLY_TASK_CLASSES`, `_JANITOR_METHOD_MAP`)
- Manual job registry: `codex/choices/jobs.py` (`ADMIN_JOBS`, "Cleanup"
  section)
- Closest analog cleanup: `cleanup_sessions` in
  `codex/librarian/scribe/janitor/cleanup.py` (Django session table)

There are zero online-tagging janitor entries today. Both candidate
jobs are DB-consistency cleanups against a single singleton row
(`ComicboxTaggingDefaults` pk=1), making them cheap and idempotent —
exactly the shape of work the janitor was built for.

## Approved shape

**Option C** — one combined cleanup job plus an `OnlineTagThread`
startup hook that unconditionally clears any persisted state. In-
memory session state cannot survive a restart, so any persisted row
at startup is by definition orphan. The janitor sweep covers the
rarer "daemon survived but in-memory state diverged from DB" case.

- Status code: **`JTG`** (Janitor TaGging).
- Admin UI title: **"Clear Stale Online Tagging State"** — "stale"
  signals safe / no-data-loss.
- Prompts have **no age-based expiry**. They persist indefinitely
  until resolved or the session is aborted (abort already clears
  both fields via `_cleanup` → `_clear_session_db`).

## Liveness check & wiring (investigated)

The janitor and `OnlineTagSessionManager` both live as threads in the
same `LibrarianDaemon` process, so the janitor can peek at
`_session_manager._sessions` directly via shared memory. But the
janitor currently has no handle to the OnlineTagThread — we need to
wire one through.

`Janitor` is constructed per-task by `ScribeThread.process_item`
([scribed.py:109-116](codex/librarian/scribe/scribed.py:109)). The
`LibrarianThreads` NamedTuple is immutable but the thread instances
inside are mutable, so we can set a back-reference attribute after
construction.

**Cleanup logic** (in `Janitor.cleanup_tagging_state`):

- If `active_session_id` is non-empty AND the OnlineTagThread reports
  no live session for that id → clear both fields under
  `db_write_lock`.
- If `active_session_id` is empty AND `active_prompts` is non-empty
  → inconsistent state, clear prompts under `db_write_lock`.
- Otherwise no-op.

### Re-examining how often the janitor will actually do work

`_cleanup` is in a `finally:` block
([session_manager.py:237-238](codex/librarian/onlinetag/session_manager.py:237)),
so DB state only becomes stale under:

- Process killed (not graceful) mid-session → **startup hook handles
  this**.
- DB manipulated externally → **manual button handles this**.
- Crash mid-`finally` block → vanishingly rare → janitor catches it.

The janitor entry is genuinely defensive and should be a no-op almost
every night. Still worth including for the nightly safety-net role
and the manual button, but this justifies keeping the cleanup method
small.

## Implementation outline

Files to touch:

### Cross-thread wiring (new — required for liveness check)

1. `codex/librarian/onlinetag/session_manager.py` — add public
   `has_session(session_id: str) -> bool` that acquires `self._lock`
   and returns `session_id in self._sessions`.
2. `codex/librarian/onlinetag/onlinetagd.py` — add public
   `has_active_session(session_id: str) -> bool` that returns False
   when `self._session_manager is None`, else delegates to the
   manager's `has_session`. Also add the startup hook:
   override `run_start` (from `NamedThread`) to call
   `ComicboxTaggingDefaults.objects.filter(pk=1).update(
   active_session_id="", active_prompts=[])` before entering the
   queue loop. Keep the DB call defensive (suppress
   `OperationalError` etc. — startup must not crash on a brand-new
   install where the row hasn't been seeded).
3. `codex/librarian/librariand.py` — in `_create_threads`, after the
   for-loop builds every thread, add:
   ```python
   threads["scribe_thread"].online_tag_thread = threads["online_tag_thread"]
   ```
   before `self._threads = LibrarianThreads(**threads)`. Type-hint
   the attribute on `ScribeThread`.
4. `codex/librarian/scribe/scribed.py` — declare
   `online_tag_thread: OnlineTagThread | None = None` as a class-
   level attribute on `ScribeThread`. In the `JanitorTask` branch,
   pass `online_tag_thread=self.online_tag_thread` into `Janitor()`.

### Janitor task

5. `codex/librarian/scribe/janitor/tasks.py` — add
   `JanitorCleanupTaggingStateTask`.
6. `codex/librarian/scribe/janitor/status.py` — add
   `JanitorCleanupTaggingStateStatus` with code `JTG` (confirmed
   free; existing J-codes: JAF, JAS, JCT, JCU, JDB, JDO, JID, JIF,
   JIS, JLV, JRB, JRF, JRS, JRV, JSR).
7. `codex/librarian/scribe/janitor/janitor.py` (the `Janitor` class
   in `update.py`'s base chain actually — verify) — accept
   `online_tag_thread` kwarg in `__init__`, store on self.
8. `codex/librarian/scribe/janitor/cleanup.py` — add
   `cleanup_tagging_state` method on `JanitorCleanup`. Logic per the
   "Cleanup logic" section above. Log INFO on any clear, DEBUG
   otherwise — matches existing cleanup style.
9. `codex/librarian/scribe/janitor/janitor.py` (the wiring module):
   - Import the new task + status.
   - Add `JanitorCleanupTaggingStateStatus` to `_JANITOR_STATII`.
   - Add `JanitorCleanupTaggingStateTask` to `_NIGHTLY_TASK_CLASSES`.
   - Add `JanitorCleanupTaggingStateTask: "cleanup_tagging_state"`
     to `_JANITOR_METHOD_MAP`.

### Admin UI exposure

10. `codex/choices/jobs.py`:
    - Add `"JTG"` to `_JANITOR_NIGHTLY_STATUSES` (line 39) so the
      nightly job's status set includes it.
    - Add entry under "Cleanup" section mirroring `cleanup_sessions`:
      ```python
      {
          "value": "cleanup_tagging_state",
          "title": "Clear Stale Online Tagging State",
          "desc": (
              "Reset orphan online tagging session and prompt"
              " state. Runs nightly."
          ),
          "statuses": ("JTG",),
      },
      ```
11. `codex/views/admin/tasks.py` — wire the new task value into the
    manual-trigger dispatch. Inspect how existing janitor cleanups
    (e.g. `cleanup_sessions`) are routed and follow the same pattern.

Touchpoint count: 11 files, but several are one-liners. No new
models, no migrations.

## Verification plan

- Unit: add a janitor cleanup test in
  `tests/codex/librarian/scribe/janitor/` (mirroring existing
  `cleanup_sessions` tests) that seeds a stale row and asserts both
  fields are cleared.
- Unit: assert no-op when the session manager reports the session is
  live.
- Manual: start a tagging session, kill the server mid-flight,
  restart, confirm the startup hook clears the row; trigger the
  manual job and confirm it logs a no-op against a clean DB.
- Lint/test: `make fix && make lint && make ty && make test`.

## Remaining work before implementation

- (Resolved) Wiring: janitor needs a back-reference to OnlineTagThread.
  Pattern: set `scribe_thread.online_tag_thread = online_tag_thread`
  after both threads are constructed in
  `LibrarianDaemon._create_threads`; pass through to `Janitor()` per
  task.
- (Resolved) Status code `JTG` is free.
- Verify the exact dispatch shape in `codex/views/admin/tasks.py`
  before writing step 11 — there's likely an enum/map that pairs
  task `value` strings with `LibrarianTask` classes; need to mirror
  the existing `cleanup_sessions` entry.

## Out of scope (per prior conversation)

- Retry-failed-tagging job — admin can re-run from browser.
- Validate-tagging-credentials health check — belongs in the admin
  tagging settings page next to the credential fields.
- Rate-limit state reset — separate concern.
- Age-based prompt expiry — prompts persist indefinitely; abort
  clears them when the operator decides to give up.
- "Dismiss all prompts" button on the prompt dialog — distinct from
  abort (would skip-resolve all prompts so the session can commit
  auto-matched tags). Worth a follow-up if operators ask for it.
