# "Dismiss All Prompts" Button — Plan

## Goal

Add a button to the online-tagging prompt dialog that skip-resolves
every prompt currently in the queue in one shot. The session keeps
running, the wait loop unblocks (or stays open if more prompts are
still streaming in), and any auto-matched tags collected so far get
committed by the deferred-pass write that already runs at the tail
of `run_session`.

Distinct from existing controls:

- **Per-prompt "Skip"** — resolves a single prompt with `action="skip"`
  ([prompt-popup.vue:66-68](frontend/src/components/online-tag/prompt-popup.vue:66),
  [session_manager.py:240-269](codex/librarian/onlinetag/session_manager.py:240)).
- **"Abort Session"** — tears down the entire session, clears
  `active_session_id` and `active_prompts`, no tags written
  ([session_manager.py:288-304](codex/librarian/onlinetag/session_manager.py:288)).
- **"Dismiss All Prompts" (new)** — bulk skip every queued prompt, no
  session teardown, tags get written by the existing
  `enqueue_write` path
  ([session_manager.py:235-236](codex/librarian/onlinetag/session_manager.py:235)).

## Background

The session lifecycle ([session_manager.py:189-238](codex/librarian/onlinetag/session_manager.py:189)):

1. `collect_results` runs the initial tag pass; ambiguous files emit
   `PromptDeferred` events which `_sync_deferred_prompts`
   ([session_manager.py:104-113](codex/librarian/onlinetag/session_manager.py:104))
   snapshots into `state.deferred_prompts` and persists to
   `ComicboxTaggingDefaults.active_prompts`.
2. `_wait_for_prompts` blocks until `resolved_count >= total_prompts`
   or the per-session timeout fires.
3. If not cancelled, `run_deferred_pass` re-runs the prompted files
   with preloaded resolutions
   ([tag_pass_runner.py:152-156](codex/librarian/onlinetag/tag_pass_runner.py:152))
   and `enqueue_write` queues a `BulkTagWriteTask` for everything
   collected.

`resolve_prompt` ([session_manager.py:240-269](codex/librarian/onlinetag/session_manager.py:240))
takes a `(session_id, fingerprint, action, payload, chosen_volume_id)`
tuple, calls `state.session.preload_resolution`, increments
`state.resolved_count`, filters the resolved entry out of
`state.deferred_prompts`, persists, broadcasts
`ONLINE_TAG_PROMPT_TASK`, and signals the event when the queue is
empty.

The frontend posts one HTTP call per resolution
([online-tag.js:53-69](frontend/src/stores/online-tag.js:53)) which
enqueues one `OnlineTagPromptResponseTask`
([tasks.py:35-43](codex/librarian/onlinetag/tasks.py:35)) per prompt.
Doing 50 prompts that way would be 50 HTTP calls and 50 librarian
tasks.

## Approved shape

- **One bulk task** (`OnlineTagSkipAllPromptsTask(session_id)`) routed
  through one new endpoint, handled by one new session-manager method
  that snapshots `state.deferred_prompts` under `self._lock`, preloads
  `action="skip"` for each fingerprint, clears the list, persists
  once, and signals the event if the queue is now empty.
- **Label decision** (please confirm — see "Open questions" below):
  rename current UI-only "Dismiss" button → "Close", use "Dismiss
  All Prompts" for the new bulk-skip button. Backend keeps `skip` as
  the canonical action name; only the operator-facing label says
  "dismiss."
- **No session teardown.** Operator can keep watching the dialog spin
  on the existing "Waiting for prompts..." empty state
  ([prompt-popup.vue:73-76](frontend/src/components/online-tag/prompt-popup.vue:73))
  while later batches stream in.

## Implementation outline

### Backend

1. `codex/librarian/onlinetag/tasks.py` — add
   `@dataclass OnlineTagSkipAllPromptsTask(LibrarianTask)` with
   `session_id: str`. Mirror the shape of
   `OnlineTagPromptResponseTask`.
2. `codex/librarian/onlinetag/session_manager.py` — add
   `skip_all_prompts(self, session_id: str) -> int`:
   - Acquire `self._lock`, look up `state`, snapshot
     `list(state.deferred_prompts)`, drop the list to `[]` on the
     state object, release the lock.
   - For each snapshotted prompt: call
     `state.session.preload_resolution(fp, action="skip",
     payload=None, chosen_volume_id=None)` and increment
     `state.resolved_count`.
   - Re-acquire lock briefly to call `self._persist_prompts(session_id)`
     once and broadcast `ONLINE_TAG_PROMPT_TASK`.
   - If `state.resolved_count >= state.total_prompts`, `state.event.set()`.
   - Return the count for logging.
   - **Verify before writing:** confirm `_sync_deferred_prompts`
     ([session_manager.py:104-113](codex/librarian/onlinetag/session_manager.py:104))
     acquires `self._lock` when mutating `state.deferred_prompts` —
     if it doesn't, the snapshot/clear pattern races with new
     prompts arriving mid-call. Existing per-prompt `resolve_prompt`
     also touches the list without a lock at
     [session_manager.py:262-264](codex/librarian/onlinetag/session_manager.py:262),
     so this may be a latent issue worth a small follow-up rather
     than blocking this PR.
3. `codex/librarian/onlinetag/onlinetagd.py` — route the new task to
   `self._session_manager.skip_all_prompts(task.session_id)`. Look at
   how `OnlineTagPromptResponseTask` is dispatched there and follow
   the same shape.
4. `codex/views/admin/onlinetag.py` — add a view that POSTs to
   `/admin/online-tag/{session_id}/prompts/skip-all`, validates the
   session id matches `active_session_id`, enqueues
   `OnlineTagSkipAllPromptsTask`, returns 202. Mirror the existing
   abort view ([onlinetag.py:127-133](codex/views/admin/onlinetag.py:127)).
5. `codex/urls/api/admin.py` — register the new route alongside the
   existing prompt routes ([admin.py:131-155](codex/urls/api/admin.py:131)).

### Frontend

6. `frontend/src/stores/online-tag.js` — add `dismissAllPrompts()`
   action: POST to the new endpoint; on success, set
   `pendingPrompts = []` (the next `loadPrompts()` triggered by an
   incoming `ONLINE_TAG_PROMPT_TASK` notification will refill it if
   more arrive). Do **not** close the dialog — let the existing empty
   state handle the spinner. Mirror the API client style used by
   `abortSession` ([online-tag.js:70-76](frontend/src/stores/online-tag.js:70)).
7. `frontend/src/components/online-tag/prompt-popup.vue` — in the
   header row at [prompt-popup.vue:6-13](frontend/src/components/online-tag/prompt-popup.vue:6):
   - Rename the existing "Dismiss" button (line 7-9) to "Close" so
     "Dismiss All Prompts" reads unambiguously.
   - Add a third button between "Close" and "Abort Session":
     `<v-btn variant="text" size="small" :disabled="!pendingPrompts.length" @click="dismissAll">Dismiss All Prompts</v-btn>`.
   - Add `dismissAll()` to `methods` calling `this.dismissAllPrompts()`
     and add `"dismissAllPrompts"` to the `mapActions` list at
     [prompt-popup.vue:94](frontend/src/components/online-tag/prompt-popup.vue:94).

### Choices

8. No choices file changes — the action stays as the existing `"skip"`
   string on the backend; only the operator-facing button text is new.

## Verification plan

- Unit: new test in `tests/codex/librarian/onlinetag/` that seeds a
  session with N deferred prompts, calls `skip_all_prompts`, and
  asserts: `state.deferred_prompts == []`,
  `state.resolved_count == N`, `state.event.is_set()` when
  `N == total_prompts`, `active_prompts` row cleared.
- Unit: assert `skip_all_prompts` against an unknown `session_id`
  logs a warning and is a no-op (mirror the guard in
  [session_manager.py:251-253](codex/librarian/onlinetag/session_manager.py:251)).
- View: assert the new endpoint rejects when `session_id` mismatches
  the active session, and returns 202 + enqueues the task on the
  happy path.
- Manual: trigger an online-tag run that produces ≥2 prompts, open
  the dialog, click "Dismiss All Prompts", confirm the dialog goes
  to the waiting-spinner state and the resulting `BulkTagWriteTask`
  commits auto-matched tags for files that didn't need prompts.
- Lint/test: `make fix && make lint && make ty && make test`. JS
  side: `cd frontend && pnpm lint && pnpm test`.

## Open questions

1. **Button label.** Plan assumes operator-facing label "Dismiss All
   Prompts" with the current "Dismiss" → "Close" rename. Alternative:
   call it "Skip All" to match the per-prompt "Skip" button's verb
   and leave "Dismiss" alone. Confirm preference before implementing.
2. **Race in `state.deferred_prompts` mutation.** Both existing
   `resolve_prompt` and `_sync_deferred_prompts` mutate the list
   without holding `self._lock` across the read-modify-write. The
   plan locks for the snapshot/clear in step 2. If the existing
   races bite in practice, worth a small separate fix; otherwise
   this PR can ignore the broader issue.

## Out of scope

- Per-prompt timeout / age-based auto-skip — different feature,
  already declined in the parent plan.
- Dismiss-with-prejudice (skip all + prevent future prompts from
  this session) — would require new session-level state and a
  different UX; revisit only if operators ask.
- Bulk "Pick best candidate for all" — different from skip; would
  need scoring rules and is a much larger feature.
