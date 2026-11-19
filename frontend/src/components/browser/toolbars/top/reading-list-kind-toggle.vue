<template>
  <v-btn-toggle
    v-if="isListsRoot"
    :model-value="kind"
    density="compact"
    mandatory
    variant="text"
    class="readingListKindToggle"
    @update:model-value="setKind"
  >
    <v-btn
      v-for="choice in choices"
      :key="choice.value"
      :value="choice.value"
      size="small"
      :title="choice.hint"
    >
      {{ choice.title }}
    </v-btn>
  </v-btn-toggle>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

const ALL = Object.freeze({
  value: "",
  title: "All",
  hint: "Every reading list",
});
const MINE = Object.freeze({
  value: "mine",
  title: "Mine",
  hint: "The reading lists you made",
});
const CURATED = Object.freeze({
  value: "curated",
  title: "Curated",
  hint: "Every list not made from story arc tags alone: imported, combined or made by hand",
});
const FROM_TAGS = Object.freeze({
  value: "tags",
  title: "From Tags",
  hint: "Lists made from story arc tags alone",
});
const SIGNED_IN_CHOICES = Object.freeze([ALL, MINE, CURATED, FROM_TAGS]);
const ANONYMOUS_CHOICES = Object.freeze([ALL, CURATED, FROM_TAGS]);

/*
 * On the Reading Lists grid, narrow the lists by where they come from.
 * Shown only on the grid of lists itself, not inside one list.
 */
export default {
  name: "ReadingListKindToggle",
  computed: {
    ...mapState(useAuthStore, {
      isLoggedIn: (state) => Boolean(state.user),
    }),
    choices() {
      // Mine only for a signed-in user: a session owns no lists.
      return this.isLoggedIn ? SIGNED_IN_CHOICES : ANONYMOUS_CHOICES;
    },
    ...mapState(useBrowserStore, {
      kind: (state) => state.settings.filters.readingListKind || "",
    }),
    isListsRoot() {
      const params = this.$route?.params || {};
      return params.collection === "arcs" && !params.parentIds;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    setKind(readingListKind) {
      this.setSettings({ filters: { readingListKind: readingListKind || "" } });
    },
  },
};
</script>

<style scoped lang="scss">
@layer codex-components {
  .readingListKindToggle {
    align-self: center;
  }
}
</style>
