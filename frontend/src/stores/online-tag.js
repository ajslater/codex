import { defineStore } from "pinia";

import { HTTP } from "@/api/v4/base";

export const useOnlineTagStore = defineStore("onlineTag", {
  state: () => ({
    activeSessionId: null,
    pendingPrompts: [],
    promptDialogOpen: false,
  }),
  actions: {
    async startSession({
      collection,
      pks,
      sources,
      mode,
      promptsMode,
      deleteOriginal,
    }) {
      const response = await HTTP.post("/admin/tag-sessions/start", {
        collection,
        pks: pks.map(String),
        sources,
        mode,
        promptsMode,
        deleteOriginal,
      });
      this.activeSessionId = response.data.sessionId;
      return response.data;
    },
    async tagById({ collection, pk, identifier, source }) {
      // Tag one comic by a known Metron / Comic Vine issue id, skipping
      // search. Returns the resolved { source, id } the server queued.
      const response = await HTTP.post("/admin/tag-by-id", {
        collection,
        pk: String(pk),
        identifier,
        source: source || "",
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
      this.pendingPrompts = response.data.prompts || [];
      if (
        autoOpen &&
        this.pendingPrompts.length > 0 &&
        !this.promptDialogOpen
      ) {
        this.promptDialogOpen = true;
      }
    },
    async resolvePrompt(fingerprint, action, payload, chosenVolumeId) {
      // Answering a prompt is decoupled from any scan: the server applies the
      // chosen match in a fresh session and writes that one comic.
      await HTTP.post(`/admin/tag-prompts/${fingerprint}`, {
        action,
        payload: String(payload ?? ""),
        chosenVolumeId: String(chosenVolumeId ?? ""),
      });
      this.pendingPrompts = this.pendingPrompts.filter(
        (p) => p.fingerprint !== fingerprint,
      );
      if (this.pendingPrompts.length === 0) {
        this.promptDialogOpen = false;
      }
    },
    async abortSession() {
      // Stops the in-flight scan only; lingering prompts are left intact.
      if (!this.activeSessionId) return;
      await HTTP.delete(`/admin/tag-sessions/${this.activeSessionId}`);
      this.activeSessionId = null;
    },
    async skipAllPrompts() {
      await HTTP.post("/admin/tag-prompts/skip-all");
      this.pendingPrompts = [];
      this.promptDialogOpen = false;
    },
    async refresh() {
      // Sync transient tagging state after a (re)connect: which scan (if any)
      // is live, plus any prompts still awaiting an answer.
      await this.discoverSession();
      await this.loadPrompts({ autoOpen: false });
    },
    onPromptNotification() {
      this.loadPrompts();
    },
  },
});
