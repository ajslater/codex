<template>
  <v-dialog v-model="promptDialogOpen" max-width="900">
    <v-card>
      <!-- Vuetify's .v-card-title is nowrap + overflow:hidden, so as a
         flex container it clips its last child: the buttons cannot
         shrink below their content and the title will not yield.
         ``text-truncate`` makes the title the elastic one (and gives it
         min-width:0), ``flex-shrink-0`` pins the buttons. -->
      <v-card-title class="d-flex justify-space-between align-center">
        <span class="flex-grow-1 text-truncate">{{ title }}</span>
        <div class="flex-shrink-0">
          <v-btn
            variant="text"
            size="small"
            :title="closeHint"
            @click="promptDialogOpen = false"
          >
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
                  <!-- One question is asked per series, so a pick usually
                     writes more than the comic it names. Say how many. -->
                  <v-chip
                    v-if="coveredCount(prompt) > 1"
                    size="x-small"
                    class="ml-1"
                    color="primary"
                  >
                    + {{ coveredCount(prompt) - 1 }} more of this series
                  </v-chip>
                </div>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <CandidateRow
                v-for="(candidate, idx) in prompt.candidates"
                :key="idx"
                :candidate="candidate"
                @pick="pick(prompt, idx)"
              />
              <div v-if="coveredCount(prompt) > 1" class="promptCovers">
                Applies to {{ coveredCount(prompt) }} comics:
                {{ coveredNames(prompt) }}
              </div>
              <div class="promptActions">
                <v-btn variant="text" size="small" @click="skip(prompt)">
                  Skip
                </v-btn>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
        <div v-else class="text-center pa-4">No matches need review.</div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapActions, mapState, mapWritableState } from "pinia";

import CandidateRow from "@/components/online-tag/candidate-row.vue";
import { sourceLabel } from "@/components/online-tag/source-labels";
import { promptComics, useOnlineTagStore } from "@/stores/online-tag";

// How many filenames a prompt lists before it stops naming them.
const NAMED_COMICS = 3;

export default {
  name: "OnlineTagPromptPopup",
  components: {
    CandidateRow,
  },
  data() {
    return {
      // Open the first match panel by default so the admin can act on it
      // immediately without an extra click. Re-opens the new top prompt as
      // each one is resolved.
      openPanel: 0,
      closeHint:
        "Matches stay queued — reopen from the menu or the Tagging tab.",
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
      return this.sessionFinished ? "Dismiss" : "Close";
    },
    title() {
      const count = this.pendingPrompts.length;
      if (!count) return "Online Tagging Match Review";
      return `Online Tagging Match Review — ${count} pending`;
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
    coveredCount(prompt) {
      return promptComics(prompt).length;
    },
    coveredNames(prompt) {
      const names = promptComics(prompt).map((comic) =>
        this.promptFilename(comic.path),
      );
      const shown = names.slice(0, NAMED_COMICS).join(", ");
      const rest = names.length - NAMED_COMICS;
      return rest > 0 ? `${shown} and ${rest} more` : shown;
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

.promptCovers {
  padding-top: 8px;
  color: rgb(var(--v-theme-textSecondary));
  font-size: 0.75rem;
}

.promptActions {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}
</style>
