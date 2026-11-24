<template>
  <div v-if="isLoggedIn" class="readingListsSettingsBlock">
    <div class="settingsSubHeader">Reading Lists</div>
    <NameListEditor
      :items="personalLists"
      noun="reading list"
      count-noun="issue"
      empty-text="No reading lists of your own yet"
      delete-hint="No comic file changes."
      :max-length="maxLength"
      @rename="onRename"
      @delete="onDelete"
    >
      <template #menu="{ item }">
        <!-- An empty list has no page to open: off, and says why. -->
        <v-list-item
          title="Open"
          :disabled="!item.count"
          :subtitle="item.count ? '' : emptyOpenHint"
          @click="open(item)"
        />
        <v-list-item title="Edit Issues" @click="edit(item)" />
        <v-list-item title="Duplicate" @click="onDuplicate(item.pk)" />
        <ReadingListExportMenu :pk="item.pk" />
      </template>
    </NameListEditor>
    <ListNameInput
      v-if="creating"
      class="newList"
      :error="createError"
      :existing-names="myListNames"
      @cancel="creating = false"
      @submit="create"
    />
    <v-btn
      v-else
      density="compact"
      :prepend-icon="mdiPlus"
      size="small"
      variant="text"
      @click="creating = true"
    >
      New reading list
    </v-btn>
    <div class="readingListsHint">
      Add comics, series and folders from any Reading Lists menu. Saved in Codex
      only: no comic file changes.
    </div>
    <ReviewDialog
      v-if="editing"
      v-model="showEditor"
      :reading-list="editing"
      :admin="false"
      @changed="loadMyLists"
    />
  </div>
  <v-divider v-if="isLoggedIn" />
</template>

<script>
import { mdiPlus } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ReviewDialog from "@/components/admin/tabs/reading-lists/review-dialog.vue";
import LIMITS from "@/choices/limits.json";
import ListNameInput from "@/components/list-name-input.vue";
import NameListEditor from "@/components/name-list-editor.vue";
import ReadingListExportMenu from "@/components/reading-list-export-menu.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { getErrors } from "@/stores/common";
import { useReadingListsStore } from "@/stores/reading-lists";

const ARCS = "arcs";

/*
 * The signed-in user's own reading lists: open, edit, rename, duplicate,
 * export, delete, and make new ones. Comics join a list from the Reading
 * Lists menu everywhere it appears.
 */
export default {
  name: "BrowserSettingsReadingLists",
  components: {
    ListNameInput,
    NameListEditor,
    ReadingListExportMenu,
    ReviewDialog,
  },
  data() {
    return {
      maxLength: LIMITS.maxNameLen,
      mdiPlus,
      emptyOpenHint: "Empty. Add issues from any Reading Lists menu.",
      createError: "",
      creating: false,
      editing: null,
      showEditor: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useReadingListsStore, [
      "myListNames",
      "myLists",
      "myListsLoaded",
    ]),
    personalLists() {
      return this.myLists.filter((list) => list.personal);
    },
  },
  watch: {
    creating() {
      // Opening or closing the name input drops the last attempt's error.
      this.createError = "";
    },
    isLoggedIn: {
      immediate: true,
      handler(value) {
        if (value && !this.myListsLoaded) this.loadMyLists();
      },
    },
  },
  methods: {
    ...mapActions(useReadingListsStore, [
      "createList",
      "deleteList",
      "duplicateList",
      "loadMyLists",
      "renameList",
    ]),
    ...mapActions(useBrowserStore, ["refreshBrowserPage", "routeWithSettings"]),
    /*
     * The user's lists are cards in the reading lists grid too, so every
     * change refetches the shown page in place.
     */
    async onRename({ pk, name }) {
      await this.renameList(pk, name);
      await this.refreshBrowserPage();
    },
    async onDelete(pk) {
      await this.deleteList(pk);
      await this.refreshBrowserPage();
    },
    async onDuplicate(pk) {
      if (await this.duplicateList(pk)) await this.refreshBrowserPage();
    },
    open(item) {
      // An empty list does not resolve: the browser would bounce it.
      if (!item.count) return;
      const route = {
        name: "browser",
        params: { collection: ARCS, pks: String(item.pk), page: 1 },
      };
      this.routeWithSettings({ topCollection: ARCS }, route);
    },
    edit(item) {
      this.editing = { pk: item.pk, name: item.name };
      this.showEditor = true;
    },
    async create(name) {
      this.createError = "";
      try {
        await this.createList(name);
      } catch (error) {
        this.createError = getErrors(error).join(" ");
        return;
      }
      this.creating = false;
      await this.refreshBrowserPage();
    },
  },
};
</script>

<style scoped lang="scss">
@layer codex-components {
  .newList {
    padding: 4px 8px;
  }

  .readingListsHint {
    color: rgb(var(--v-theme-text-secondary));
    font-size: 0.8em;
    padding: 0 12px 8px;
  }
}
</style>
