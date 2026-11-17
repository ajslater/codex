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
      v-for="choice in CHOICES"
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

import { useBrowserStore } from "@/stores/browser";

const CHOICES = Object.freeze([
  { value: "", title: "All", hint: "Every reading list" },
  {
    value: "curated",
    title: "Curated",
    hint: "Lists from a file, a URL, the catalog, Metron or Comic Vine",
  },
  { value: "tags", title: "From Tags", hint: "Lists from story arc tags only" },
]);

/*
 * On the Reading Lists grid, narrow the lists by where they come from.
 * Shown only on the grid of lists itself, not inside one list.
 */
export default {
  name: "ReadingListKindToggle",
  data() {
    return { CHOICES };
  },
  computed: {
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
