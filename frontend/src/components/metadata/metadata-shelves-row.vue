<template>
  <tr v-if="isLoggedIn" class="shelvesRow">
    <td class="key">Shelves</td>
    <td class="tags">
      <div class="shelvesRowCell">
        <ShelfMenu
          v-if="targetPks.length"
          class="shelvesRowMenu"
          :collection="book.collection"
          :pks="targetPks"
        />
        <MetadataTags filter="shelves" :values="shelfItems" />
      </div>
    </td>
  </tr>
</template>

<script>
import { mapState } from "pinia";

import MetadataTags from "@/components/metadata/metadata-tags.vue";
import ShelfMenu from "@/components/shelf-menu.vue";
import { useAuthStore } from "@/stores/auth";
import { useMetadataStore } from "@/stores/metadata";
import { useShelvesStore } from "@/stores/shelves";

/*
 * The selection's shelves as tag chips — each one browses its shelf, like
 * every other tag chip — after the same shelf menu the table's Shelves
 * column has. Shown for any signed-in user, shelves or none, so the menu
 * can put the selection on its first one.
 */
export default {
  name: "MetadataShelvesRow",
  components: { MetadataTags, ShelfMenu },
  props: {
    book: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapState(useAuthStore, {
      // Anonymous sessions own no shelves.
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useMetadataStore, {
      shelfPks: (state) => state.md?.shelves,
    }),
    ...mapState(useShelvesStore, ["shelvesByPks"]),
    targetPks() {
      // What the dialog loaded: the selection's ids, or the lone row's pk.
      const pks = this.book.ids || [this.book.pk];
      return pks.filter((pk) => pk !== null && pk !== undefined).map(Number);
    },
    shelfItems() {
      return this.shelvesByPks(this.shelfPks).map(({ pk, name }) => ({
        pk,
        name,
      }));
    },
  },
};
</script>

<style scoped lang="scss">
@use "./table";

.shelvesRowCell {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.shelvesRowMenu {
  flex: none;
}
</style>
