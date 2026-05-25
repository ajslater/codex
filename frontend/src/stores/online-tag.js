import { defineStore } from "pinia";

import { HTTP } from "@/api/v3/base";

export const useOnlineTagStore = defineStore("onlineTag", {
  state: () => ({
    activeSessionId: null,
    pendingPrompts: [],
    promptDialogOpen: false,
  }),
  actions: {
    async startSession({
      group,
      pks,
      sources,
      mode,
      promptsMode,
      deleteOriginal,
    }) {
      const response = await HTTP.post("/admin/online-tag/start", {
        group,
        pks: pks.map(String),
        sources,
        mode,
        promptsMode,
        deleteOriginal,
      });
      this.activeSessionId = response.data.sessionId;
      return response.data;
    },
    async discoverSession() {
      const response = await HTTP.get("/admin/online-tag/active");
      const sid = response.data.sessionId;
      if (sid) {
        this.activeSessionId = sid;
      }
      return sid;
    },
    async loadPrompts() {
      if (!this.activeSessionId) {
        await this.discoverSession();
      }
      if (!this.activeSessionId) return;
      const response = await HTTP.get(
        `/admin/online-tag/${this.activeSessionId}/prompts`,
        { params: { ts: Date.now() } },
      );
      this.pendingPrompts = response.data.prompts || [];
      if (this.pendingPrompts.length > 0 && !this.promptDialogOpen) {
        this.promptDialogOpen = true;
      }
    },
    async resolvePrompt(fingerprint, action, payload, chosenVolumeId) {
      if (!this.activeSessionId) return;
      await HTTP.post(
        `/admin/online-tag/${this.activeSessionId}/prompts/${fingerprint}`,
        {
          action,
          payload: String(payload ?? ""),
          chosenVolumeId: String(chosenVolumeId ?? ""),
        },
      );
      this.pendingPrompts = this.pendingPrompts.filter(
        (p) => p.fingerprint !== fingerprint,
      );
      if (this.pendingPrompts.length === 0) {
        this.promptDialogOpen = false;
      }
    },
    async abortSession() {
      if (!this.activeSessionId) return;
      await HTTP.post(`/admin/online-tag/${this.activeSessionId}/abort`);
      this.activeSessionId = null;
      this.pendingPrompts = [];
      this.promptDialogOpen = false;
    },
    async skipAllPrompts() {
      if (!this.activeSessionId) return;
      await HTTP.post(
        `/admin/online-tag/${this.activeSessionId}/skip-all-prompts`,
      );
      this.pendingPrompts = [];
    },
    onPromptNotification() {
      this.loadPrompts();
    },
  },
});
