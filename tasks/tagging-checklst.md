# Codex Tagging — Implementation Checklist

## Phase 1: Defaults Foundation
- [ ] Add `CODEX_FIELD_ENCRYPTION_KEY` to settings + `codex.toml` pattern
- [ ] Add `django-cryptography-django5` dependency
- [ ] Create `ComicboxTaggingDefaults` singleton model (codex/models/admin.py)
- [ ] Create migration with RunPython seeder
- [ ] Create `codex/integrations/comicbox.py` (config helpers, credential decrypt)
- [ ] Create `ComicboxTaggingDefaultsSerializer` (redacted GET / full PUT)
- [ ] Create `AdminComicboxTaggingDefaultsView` (GET/PUT)
- [ ] Register `/api/v3/admin/tagging-defaults` URL
- [ ] Frontend: add "Tagging" to admin TABS + route
- [ ] Frontend: create `tagging-tab.vue` (write defaults, online defaults, credentials, timeout)
- [ ] Verify: PUT/GET roundtrip, encrypted values not readable in DB

## Phase 2: Status Registry
- [ ] Add `TagWriteStatus(CODE="TWR")` to `SCRIBE_STATII`
- [ ] Create `codex/librarian/onlinetag/status.py` with `OnlineTagStatus(CODE="OTG")` and `OnlineTagPromptStatus(CODE="OTP")`
- [ ] Import `ONLINETAG_STATII` in `codex/choices/statii.py`
- [ ] Run `make build-choices`
- [ ] Verify: status titles appear in choices JSON

## Phase 3: Tag-Write in ScribeThread
- [ ] Add `BulkTagWriteTask(ScribeTask)` and `TagWriteAbortTask` to scribe/tasks.py
- [ ] Create `codex/librarian/scribe/tag_writer.py` (TagWriter: bulk_write + batch re-import)
  - Supports universal `patch` (manual edit) AND `per_comic_patches` (online tag)
  - `_on_event` → StatusController for sidebar progress
  - After bulk_write: batch re-import all written comics in-process
- [ ] Add `case BulkTagWriteTask()` / `case TagWriteAbortTask()` to scribed.py
- [ ] Verify: Django shell LIBRARIAN_QUEUE.put(BulkTagWriteTask(...)) against fixture comic

## Phase 4: Tag-Write Endpoint
- [ ] Create `AdminTagWriteView(AdminAuthMixin, GroupFilterView)` — POST resolves PKs, enqueues task
- [ ] Create `TagWriteRequestSerializer` (group, pks, filters, patch, mode, formats)
- [ ] Register `/api/v3/admin/tagwrite` URL
- [ ] Verify: curl POST

## Phase 5: Edit-Mode Frontend
- [ ] Add admin-only "Edit" button to `metadata-dialog.vue` (`v-if="isUserAdmin"`)
- [ ] Create `frontend/src/components/metadata/edit-mode/edit-panel.vue` (defineAsyncComponent lazy)
- [ ] Create sub-chunks: text-fields.vue, tag-chips.vue, credits-editor.vue (lazy per-section)
- [ ] Session-mode picker (v-select: Additive / Update / Replace) pre-filled from defaults
- [ ] Per-comic mode override (single-comic only, kebab menu)
- [ ] "Save" button → POST /api/v3/admin/tagwrite
- [ ] Verify: single comic edit → save → file + DB updated, sidebar progress
- [ ] Verify: group edit with active filters → only filtered comics rewritten
- [ ] Verify: bundle split (edit-mode not in initial admin chunk)

## Phase 6: Online-Tag Backend
- [ ] Create `codex/librarian/onlinetag/__init__.py`
- [ ] Create `codex/librarian/onlinetag/tasks.py` (BulkOnlineTagTask, OnlineTagAbortTask, OnlineTagPromptResponseTask)
- [ ] Create `codex/librarian/onlinetag/session_manager.py` (OnlineTagSessionManager)
  - run_session: pass 1 (defer) → deferred prompts → wait → preload → pass 2 → enqueue BulkTagWriteTask
  - resolve_prompt: preload_resolution → decrement pending → set event
  - get_pending_prompts, cancel_session
- [ ] Create `codex/librarian/onlinetag/handler.py` (CodexBatchedPromptHandler)
- [ ] Create `codex/librarian/onlinetag/onlinetagd.py` (OnlineTagThread)
- [ ] Register OnlineTagThread in librariand.py + route OnlineTagTask subtypes
- [ ] Verify: with monkeypatched OnlineSession end-to-end

## Phase 7: Online-Tag Endpoints
- [ ] Create `codex/views/admin/onlinetag.py` (Start, PromptsList, PromptResponse, Abort views)
- [ ] Create `OnlineTagStartSerializer`, `OnlineTagPromptSerializer`, `OnlineTagPromptResponseSerializer`
- [ ] Register four URLs: online-tag/start, <session_id>/prompts, <session_id>/prompts/<fingerprint>, <session_id>/abort
- [ ] Verify: curl

## Phase 8: Prompt WebSocket Fan-Out
- [ ] Add `ONLINE_TAG_PROMPT` to `codex/choices/notifications.py`
- [ ] Add dispatch case in `frontend/src/stores/socket.js` → lazy-import online-tag store

## Phase 9: Online-Tag Frontend
- [ ] Create `frontend/src/stores/online-tag.js` (pendingPrompts, loadPrompts, resolvePrompt)
- [ ] Create `frontend/src/components/online-tag/launcher-dialog.vue` (session options form)
- [ ] Create `frontend/src/components/metadata/online-tag-button.vue` (metadata dialog trigger)
- [ ] Create `frontend/src/components/browser/actions/online-tag-action.vue` (browser action)
- [ ] Create `frontend/src/components/online-tag/prompt-popup.vue` (v-expansion-panels per prompt)
- [ ] Mount prompt popup in `frontend/src/admin.vue`
- [ ] Verify: real Metron credentials against fixture comics

## Phase 10: Polish
- [ ] Run `make build-choices` (regenerate all frontend JSON)
- [ ] Bundle size check
- [ ] `make fix` + lint + test suites + `make build-frontend`
