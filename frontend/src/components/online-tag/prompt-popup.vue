<template>
  <v-dialog v-model="promptDialogOpen" max-width="700">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span>Online Tagging Prompts</span>
        <div>
          <v-btn
            variant="text"
            size="small"
            @click="promptDialogOpen = false"
          >
            Dismiss
          </v-btn>
          <v-btn variant="text" size="small" color="error" @click="abort">
            Abort Session
          </v-btn>
        </div>
      </v-card-title>
      <v-card-text>
        <v-expansion-panels v-if="pendingPrompts.length">
          <v-expansion-panel
            v-for="prompt in pendingPrompts"
            :key="prompt.fingerprint"
          >
            <v-expansion-panel-title>
              <div class="promptTitle">
                <span class="promptPath">{{
                  promptFilename(prompt.path)
                }}</span>
                <v-chip size="x-small" class="ml-2">{{ prompt.source }}</v-chip>
                <v-chip size="x-small" class="ml-1">
                  {{ prompt.candidates.length }} candidates
                </v-chip>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div
                v-for="(candidate, idx) in prompt.candidates"
                :key="idx"
                class="candidateRow"
              >
                <div class="candidateInfo">
                  <strong>{{ candidate.summary.series }}</strong>
                  <span v-if="candidate.summary.issue">
                    #{{ candidate.summary.issue }}
                  </span>
                  <span v-if="candidate.summary.year" class="candidateYear">
                    ({{ candidate.summary.year }})
                  </span>
                  <span
                    v-if="candidate.summary.publisher"
                    class="candidatePublisher"
                  >
                    &mdash; {{ candidate.summary.publisher }}
                  </span>
                  <v-chip size="x-small" class="ml-2">
                    {{ Math.round(candidate.score * 100) }}%
                  </v-chip>
                </div>
                <v-btn
                  variant="tonal"
                  size="small"
                  color="primary"
                  @click="pick(prompt, idx)"
                >
                  Pick
                </v-btn>
              </div>
              <div class="promptActions">
                <v-btn variant="text" size="small" @click="skip(prompt)">
                  Skip
                </v-btn>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
        <div v-else class="text-center pa-4">
          <v-progress-circular indeterminate size="32" class="mr-2" />
          Waiting for prompts...
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapActions, mapState, mapWritableState } from "pinia";

import { useOnlineTagStore } from "@/stores/online-tag";

export default {
  name: "OnlineTagPromptPopup",
  computed: {
    ...mapState(useOnlineTagStore, ["pendingPrompts"]),
    ...mapWritableState(useOnlineTagStore, ["promptDialogOpen"]),
  },
  methods: {
    ...mapActions(useOnlineTagStore, ["resolvePrompt", "abortSession"]),
    promptFilename(path) {
      if (!path) return "Unknown";
      const parts = path.split("/");
      return parts[parts.length - 1];
    },
    pick(prompt, candidateIndex) {
      this.resolvePrompt(prompt.fingerprint, "choose", candidateIndex, null);
    },
    skip(prompt) {
      this.resolvePrompt(prompt.fingerprint, "skip", null, null);
    },
    abort() {
      this.abortSession();
    },
  },
};
</script>

<style scoped lang="scss">
.promptTitle {
  display: flex;
  align-items: center;
}

.promptPath {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.candidateRow {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.candidateInfo {
  flex: 1;
  min-width: 0;
}

.candidateYear,
.candidatePublisher {
  color: rgb(var(--v-theme-textSecondary));
}

.promptActions {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}
</style>
