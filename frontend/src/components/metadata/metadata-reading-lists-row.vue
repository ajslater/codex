<template>
  <tr v-if="isLoggedIn || readingLists.length" class="readingListsRow">
    <td class="key">Reading Lists</td>
    <td class="tags">
      <div class="readingListsRowCell">
        <ReadingListMenu
          v-if="isLoggedIn && targetPks.length"
          class="readingListsRowMenu"
          :collection="book.collection"
          :pks="targetPks"
        />
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
      </div>
    </td>
  </tr>
</template>

<script>
import { mapActions, mapState } from "pinia";

import ReadingListMenu from "@/components/reading-list-menu.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

const ARCS = "arcs";

/*
 * The reading lists that hold the selection and that the viewer may see,
 * each a chip that opens the list in the browser. A single comic's chip
 * names its place in the list: "Civil War · 12 of 98". A signed-in user
 * gets the list menu first, lists or none, so it can put the selection in
 * one.
 */
export default {
  name: "MetadataReadingListsRow",
  components: { ReadingListMenu },
  props: {
    book: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapState(useAuthStore, {
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useMetadataStore, {
      lists: (state) => state.md?.readingLists || [],
    }),
    targetPks() {
      // What the dialog loaded: the selection's ids, or the lone row's pk.
      const pks = this.book.ids || [this.book.pk];
      return pks.filter((pk) => pk !== null && pk !== undefined).map(Number);
    },
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
  .readingListsRowCell {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
  }

  .readingListsRowMenu {
    flex: none;
  }

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
