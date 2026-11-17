<template>
  <MenuSection title="Reading Lists">
    <v-list class="readingListMenuList" density="compact">
      <v-list-item
        v-for="list of myLists"
        :key="list.pk"
        density="compact"
        :prepend-icon="mdiPlaylistPlus"
        :title="list.name"
        :subtitle="list.personal ? '' : 'Global'"
        @click="add(list)"
      />
      <v-list-item
        v-if="!creating"
        density="compact"
        :prepend-icon="mdiPlus"
        title="New reading list…"
        @click="creating = true"
      />
    </v-list>
    <div v-if="creating" class="newList">
      <v-text-field
        v-model="name"
        autofocus
        density="compact"
        hide-details
        label="Reading List Name"
        variant="outlined"
        @keydown.enter="create"
        @keydown.esc.stop="creating = false"
      />
      <v-btn
        density="compact"
        :disabled="!name.trim()"
        :icon="mdiCheck"
        size="small"
        title="Create the list with these comics"
        variant="text"
        @click="create"
      />
    </div>
    <div class="readingListHint">
      Adds the comics in reading order. Saved in Codex only: no comic file
      changes.
    </div>
  </MenuSection>
</template>

<script>
import { mdiCheck, mdiPlaylistPlus, mdiPlus } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import MenuSection from "@/components/menu-section.vue";
import { useReadingListsStore } from "@/stores/reading-lists";

/*
 * The reading lists half of the shelf menu: add a selection's comics to a
 * list the user may edit, or make a new list of them.
 */
export default {
  name: "ReadingListMenuSection",
  components: { MenuSection },
  props: {
    // ``{collection: [pks]}``, as the shelf menu builds it.
    targets: { type: Object, required: true },
  },
  emits: ["done"],
  data() {
    return { mdiCheck, mdiPlaylistPlus, mdiPlus, creating: false, name: "" };
  },
  computed: {
    ...mapState(useReadingListsStore, ["myLists", "myListsLoaded"]),
  },
  mounted() {
    if (!this.myListsLoaded) this.loadMyLists();
  },
  methods: {
    ...mapActions(useReadingListsStore, [
      "addTargets",
      "createList",
      "loadMyLists",
    ]),
    async add(list) {
      await this.addTargets(list.pk, this.targets);
      this.$emit("done");
    },
    async create() {
      const name = this.name.trim();
      if (!name) return;
      const list = await this.createList(name);
      if (!list) return;
      await this.addTargets(list.pk, this.targets);
      this.creating = false;
      this.name = "";
      this.$emit("done");
    },
  },
};
</script>

<style scoped lang="scss">
@layer codex-components {
  .readingListMenuList {
    max-height: 30vh;
    overflow-y: auto;
    padding-top: 0;
  }

  .newList {
    display: flex;
    align-items: center;
    padding: 4px 8px 10px 12px;
  }

  .readingListHint {
    color: rgb(var(--v-theme-text-secondary));
    font-size: 0.8em;
    padding: 0 12px 8px;
    max-width: 22em;
  }
}
</style>
