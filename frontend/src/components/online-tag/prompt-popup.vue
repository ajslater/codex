<template>
  <v-dialog v-model="promptDialogOpen" max-width="700">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span>Online Tagging Match Review</span>
        <div>
          <v-btn variant="text" size="small" @click="promptDialogOpen = false">
            {{ dismissLabel }}
          </v-btn>
          <v-btn
            variant="text"
            size="small"
            :disabled="!pendingPrompts.length"
            @click="skipAll"
          >
            Skip All
          </v-btn>
          <v-btn variant="text" size="small" @click="pause"> Pause </v-btn>
        </div>
      </v-card-title>
      <v-card-text>
        <v-expansion-panels v-if="pendingPrompts.length" v-model="openPanel">
          <v-expansion-panel
            v-for="prompt in pendingPrompts"
            :key="prompt.fingerprint"
          >
            <v-expansion-panel-title>
              <div class="promptTitle">
                <div class="promptPath">{{ promptFilename(prompt.path) }}</div>
                <div class="promptMeta">
                  <v-chip size="x-small">{{
                    sourceLabel(prompt.source)
                  }}</v-chip>
                  <v-chip size="x-small" class="ml-1">
                    {{ prompt.candidates.length }} candidates
                  </v-chip>
                </div>
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
                  <!-- Matching scores alternate series names too, so a comic
                     filed under a localized title matches a series name that
                     looks nothing like its filename. These are the reason. -->
                  <div
                    v-if="candidate.summary.altSeries?.length"
                    class="candidateAka"
                  >
                    a.k.a. {{ candidate.summary.altSeries.join(", ") }}
                  </div>
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

import { sourceLabel } from "@/components/online-tag/source-labels";
import { useOnlineTagStore } from "@/stores/online-tag";

export default {
  name: "OnlineTagPromptPopup",
  data() {
    return {
      // Open the first match panel by default so the admin can act on it
      // immediately without an extra click. Re-opens the new top prompt as
      // each one is resolved.
      openPanel: 0,
    };
  },
  computed: {
    ...mapState(useOnlineTagStore, ["pendingPrompts", "snapshot"]),
    ...mapWritableState(useOnlineTagStore, ["promptDialogOpen"]),
    // The session has finished only when a snapshot exists and reports the scan
    // is neither active nor resumable (paused). Until then, closing the dialog
    // is a "Cancel" out of an in-progress session rather than a "Dismiss".
    sessionFinished() {
      return Boolean(
        this.snapshot && !this.snapshot.active && !this.snapshot.resumable,
      );
    },
    dismissLabel() {
      return this.sessionFinished ? "Dismiss" : "Cancel";
    },
  },
  methods: {
    ...mapActions(useOnlineTagStore, [
      "resolvePrompt",
      "pauseSession",
      "skipAllPrompts",
    ]),
    sourceLabel,
    promptFilename(path) {
      if (!path) return "Unknown";
      const parts = path.split("/");
      return parts[parts.length - 1];
    },
    pick(prompt, candidateIndex) {
      // The candidate's parent container id narrows the re-search replay to
      // that volume. Absent for sources that don't expose one.
      const volumeId = prompt.candidates[candidateIndex]?.volumeId ?? null;
      this.resolvePrompt(
        prompt.fingerprint,
        "choose",
        candidateIndex,
        volumeId,
      );
    },
    skip(prompt) {
      this.resolvePrompt(prompt.fingerprint, "skip", null, null);
    },
    skipAll() {
      this.skipAllPrompts();
    },
    pause() {
      // Stop the in-flight scan, keeping the remainder resumable from the
      // admin Tagging tab; lingering prompts are left intact for review.
      this.pauseSession();
    },
  },
};
</script>

<style scoped lang="scss">
.promptTitle {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  width: 100%;
  min-width: 0;
}

/* Filename gets its own full-width line. The dialog grows with the name up to
 * its max-width, after which the name scrolls horizontally so the full path is
 * always reachable. */
.promptPath {
  font-weight: 500;
  white-space: nowrap;
  overflow-x: auto;
  max-width: 100%;
}

.promptMeta {
  display: flex;
  align-items: center;
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
.candidatePublisher,
.candidateAka {
  color: rgb(var(--v-theme-textSecondary));
}

.candidateAka {
  font-size: 0.8125rem;
}

.promptActions {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}
</style>
