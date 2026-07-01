import { defineStore } from "pinia";

import { HTTP } from "@/api/v4/base";

export const useOnlineTagStore = defineStore("onlineTag", {
  state: () => ({
    activeSessionId: null,
    pendingPrompts: [],
    promptDialogOpen: false,
    // Fingerprints the admin just answered. The daemon removes answered
    // prompts from its cache only when it gets a chance (a busy scan defers
    // that to between comics), so a re-fetch can briefly resurrect one. We
    // suppress these until the backend stops returning them — see loadPrompts.
    recentlyResolved: [],
    // Live (or last-finished) status snapshot for the admin Tagging-tab
    // status table: batch progress, per-source rate state, and a capped
    // per-comic list. Null until a scan has run.
    snapshot: null,
    // Optimistic per-comic resolution overlay {pk: user_matched|user_skipped}
    // for the status table. The daemon can't record a resolution until it
    // drains the task queue (stalled during a rate-limit wait), so without
    // this the table lagged a full resolution behind. Pruned in loadSnapshot
    // once the server snapshot reflects the same outcome.
    locallyResolved: {},
  }),
  actions: {
    async startSession({
      collection,
      pks,
      sources,
      mode,
      promptsMode,
      deleteOriginal,
      mergeAllSources,
      rename,
    }) {
      const response = await HTTP.post("/admin/tag-sessions/start", {
        collection,
        pks: pks.map(String),
        sources,
        mode,
        promptsMode,
        deleteOriginal,
        mergeAllSources,
        rename,
      });
      this.activeSessionId = response.data.sessionId;
      return response.data;
    },
    async tagById({
      collection,
      pk,
      identifier,
      identifiers,
      source,
      mergeAllSources,
      rename,
    }) {
      // Tag one comic by a known Metron / Comic Vine issue id, skipping
      // search. Returns the resolved { source, id } the server queued.
      const response = await HTTP.post("/admin/tag-by-id", {
        collection,
        pk: String(pk),
        identifier,
        identifiers: identifiers || [identifier],
        source: source || "",
        mergeAllSources,
        rename,
      });
      return response.data;
    },
    async discoverSession() {
      const response = await HTTP.get("/admin/tag-sessions");
      const sid = response.data.sessionId;
      this.activeSessionId = sid || null;
      return sid;
    },
    async loadPrompts({ autoOpen = true } = {}) {
      /*
       * Pending prompts persist in the cache independently of any running
       * scan, so they're fetched globally — no active session required. They
       * survive daemon restarts and page reloads until answered or skipped.
       */
      const response = await HTTP.get("/admin/tag-prompts", {
        params: { ts: Date.now() },
      });
      const raw = response.data.prompts || [];
      // Reconcile against optimistic local resolutions. Drop any
      // recently-answered fingerprint the backend still echoes (it's lagging),
      // and forget the suppression once it's actually gone — a drifted
      // re-queue returns under a *new* fingerprint, so it surfaces normally.
      const rawFingerprints = new Set(raw.map((p) => p.fingerprint));
      this.recentlyResolved = this.recentlyResolved.filter((fp) =>
        rawFingerprints.has(fp),
      );
      this.pendingPrompts = raw.filter(
        (p) => !this.recentlyResolved.includes(p.fingerprint),
      );
      if (
        autoOpen &&
        this.pendingPrompts.length > 0 &&
        !this.promptDialogOpen
      ) {
        this.promptDialogOpen = true;
      }
    },
    rememberResolved(fingerprint) {
      if (fingerprint && !this.recentlyResolved.includes(fingerprint)) {
        this.recentlyResolved.push(fingerprint);
      }
    },
    rememberLocalOutcome(pk, status) {
      // Optimistic status-table overlay until the daemon records it.
      if (pk !== undefined && pk !== null) {
        this.locallyResolved = { ...this.locallyResolved, [pk]: status };
      }
    },
    async resolvePrompt(fingerprint, action, payload, chosenVolumeId) {
      // Answering a prompt is decoupled from any scan: the server applies the
      // chosen match in a fresh session and writes that one comic.
      const prompt = this.pendingPrompts.find(
        (p) => p.fingerprint === fingerprint,
      );
      await HTTP.post(`/admin/tag-prompts/${fingerprint}`, {
        action,
        payload: String(payload ?? ""),
        chosenVolumeId: String(chosenVolumeId ?? ""),
      });
      this.rememberResolved(fingerprint);
      this.rememberLocalOutcome(
        prompt?.pk,
        action === "skip" ? "user_skipped" : "user_matched",
      );
      this.pendingPrompts = this.pendingPrompts.filter(
        (p) => p.fingerprint !== fingerprint,
      );
      if (this.pendingPrompts.length === 0) {
        this.promptDialogOpen = false;
      }
    },
    async pauseSession() {
      // Stops the in-flight scan, keeping the unprocessed comics resumable;
      // lingering prompts are left intact. The status-table pause has no
      // activeSessionId in hand (that's only set on start/reconnect discovery),
      // so fall back to the snapshot's id.
      const sessionId = this.activeSessionId || this.snapshot?.sessionId;
      if (!sessionId) return;
      await HTTP.delete(`/admin/tag-sessions/${sessionId}`);
      this.activeSessionId = null;
    },
    async resumeSession() {
      // Re-run the comics a paused/interrupted scan never reached. The server
      // rebuilds the batch from its stored resume descriptor (remaining pks +
      // original params) and returns a fresh session id.
      const response = await HTTP.post("/admin/tag-sessions/resume");
      this.activeSessionId = response.data.sessionId || null;
      return response.data;
    },
    async dismissSession() {
      // Clear the status table for a paused/finished session. Optimistically
      // drop the local snapshot; the daemon clears the cache + resume state.
      await HTTP.post("/admin/tag-sessions/dismiss");
      this.snapshot = null;
      this.activeSessionId = null;
    },
    async skipAllPrompts() {
      await HTTP.post("/admin/tag-prompts/skip-all");
      for (const p of this.pendingPrompts) {
        this.rememberResolved(p.fingerprint);
        this.rememberLocalOutcome(p.pk, "user_skipped");
      }
      this.pendingPrompts = [];
      this.promptDialogOpen = false;
    },
    async loadSnapshot() {
      /*
       * The daemon publishes a JSON snapshot of the running (or last-finished)
       * scan to the tagging cache on each status update; this reads that single
       * key. Independent of any in-memory session, so it survives reloads and
       * keeps the final tally after a batch ends (snapshot.active === false).
       */
      const response = await HTTP.get("/admin/tag-sessions/snapshot", {
        params: { ts: Date.now() },
      });
      this.snapshot = response.data.snapshot || null;
      this.pruneLocallyResolved();
      return this.snapshot;
    },
    pruneLocallyResolved() {
      // Forget an optimistic overlay once the authoritative snapshot agrees
      // (or the comic is gone); keep it while the server is still catching up.
      const byPk = new Map(
        (this.snapshot?.comics || []).map((c) => [c.pk, c.status]),
      );
      const next = {};
      for (const [pk, status] of Object.entries(this.locallyResolved)) {
        const serverStatus = byPk.get(Number(pk));
        if (serverStatus !== undefined && serverStatus !== status) {
          next[pk] = status;
        }
      }
      this.locallyResolved = next;
    },
    async refresh() {
      // Sync transient tagging state after a (re)connect: which scan (if any)
      // is live, plus any prompts still awaiting an answer and the status
      // snapshot for the Tagging-tab table.
      await this.discoverSession();
      await this.loadPrompts({ autoOpen: false });
      await this.loadSnapshot();
    },
    onPromptNotification() {
      // A prompt change (new deferral, or a resolution the daemon just
      // processed) also moves the status table — refresh both. Skips produce
      // no write activity, so this notification is the only signal the table
      // gets that a skip landed.
      this.loadPrompts();
      this.loadSnapshot().catch(() => {});
    },
  },
});
