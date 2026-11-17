<template>
  <tr v-if="readingLists.length" class="readingListsRow">
    <td class="key">Reading Lists</td>
    <td class="tags">
      <v-chip
        v-for="item in readingLists"
        :key="item.pk"
        class="listChip clickable"
        variant="tonal"
        :title="item.title"
        @click="open(item)"
      >
        {{ item.label }}
      </v-chip>
    </td>
  </tr>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

const ARCS = "arcs";

/*
 * The reading lists that hold the selection and that the viewer may see,
 * each a chip that opens the list in the browser. A single comic's chip
 * names its place in the list: "Civil War · 12 of 98".
 */
export default {
  name: "MetadataReadingListsRow",
  computed: {
    ...mapState(useMetadataStore, {
      lists: (state) => state.md?.readingLists || [],
    }),
    readingLists() {
      return this.lists.map((list) => {
        const place = list.position
          ? `${list.position} of ${list.count}`
          : `${list.count}`;
        return {
          pk: list.pk,
          label: `${list.name} · ${place}`,
          title: `Open the reading list ${list.name}`,
        };
      });
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["routeWithSettings"]),
    open(item) {
      const route = {
        name: "browser",
        params: { collection: ARCS, pks: String(item.pk), page: 1 },
      };
      this.routeWithSettings({ topCollection: ARCS }, route);
    },
  },
};
</script>

<style scoped lang="scss">
@use "./table";

@layer codex-components {
  .listChip {
    margin: 4px;
  }

  .clickable :deep(.v-chip__content) {
    color: rgb(var(--v-theme-primary));
  }

  .clickable:hover :deep(.v-chip__content) {
    color: rgb(var(--v-theme-link-hover));
  }
}
</style>
