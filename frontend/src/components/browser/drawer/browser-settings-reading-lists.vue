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
      <template #actions="{ item }">
        <v-btn
          density="compact"
          :icon="mdiOpenInApp"
          size="small"
          title="Open"
          variant="text"
          @click="open(item)"
        />
        <v-btn
          density="compact"
          :icon="mdiFormatListChecks"
          size="small"
          title="Edit entries"
          variant="text"
          @click="edit(item)"
        />
        <v-menu>
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              density="compact"
              :icon="mdiDotsVertical"
              size="small"
              title="More"
              variant="text"
            />
          </template>
          <v-list density="compact">
            <v-list-item title="Duplicate" @click="onDuplicate(item.pk)" />
            <v-list-subheader>Export</v-list-subheader>
            <v-list-item
              v-for="fmt in EXPORT_FORMATS"
              :key="fmt.value"
              :title="fmt.title"
              :href="exportURL(item.pk, fmt.value)"
              download
            />
          </v-list>
        </v-menu>
      </template>
    </NameListEditor>
    <div v-if="creating" class="newList">
      <v-text-field
        v-model="name"
        autofocus
        density="compact"
        hide-details
        label="Reading List Name"
        :maxlength="maxLength"
        variant="outlined"
        @keydown.enter="create"
        @keydown.esc.stop="creating = false"
      />
      <v-btn
        density="compact"
        :disabled="!name.trim()"
        :icon="mdiCheck"
        size="small"
        title="Create"
        variant="text"
        @click="create"
      />
    </div>
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
      Add comics from any shelf menu. Saved in Codex only: no comic file
      changes.
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
import {
  mdiCheck,
  mdiDotsVertical,
  mdiFormatListChecks,
  mdiOpenInApp,
  mdiPlus,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { exportURL } from "@/api/v4/reading-lists";
import ReviewDialog from "@/components/admin/tabs/reading-lists/review-dialog.vue";
import LIMITS from "@/choices/limits.json";
import NameListEditor from "@/components/name-list-editor.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { EXPORT_FORMATS, useReadingListsStore } from "@/stores/reading-lists";

const ARCS = "arcs";

/*
 * The signed-in user's own reading lists: open, edit, rename, duplicate,
 * export, delete, and make new ones. Comics join a list from the shelf
 * menu everywhere it appears.
 */
export default {
  name: "BrowserSettingsReadingLists",
  components: { NameListEditor, ReviewDialog },
  data() {
    return {
      EXPORT_FORMATS,
      maxLength: LIMITS.maxNameLen,
      mdiCheck,
      mdiDotsVertical,
      mdiFormatListChecks,
      mdiOpenInApp,
      mdiPlus,
      creating: false,
      name: "",
      editing: null,
      showEditor: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useReadingListsStore, ["myLists", "myListsLoaded"]),
    personalLists() {
      return this.myLists.filter((list) => list.personal);
    },
  },
  watch: {
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
    exportURL,
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
    async create() {
      const name = this.name.trim();
      if (!name) return;
      const list = await this.createList(name);
      if (list) {
        this.creating = false;
        this.name = "";
        await this.refreshBrowserPage();
      }
    },
  },
};
</script>

<style scoped lang="scss">
@layer codex-components {
  .newList {
    display: flex;
    align-items: center;
    padding: 4px 8px;
  }

  .readingListsHint {
    color: rgb(var(--v-theme-text-secondary));
    font-size: 0.8em;
    padding: 0 12px 8px;
  }
}
</style>
