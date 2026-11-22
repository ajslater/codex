<template>
  <v-menu v-model="showMenu" offset-y top>
    <template #activator="{ props }">
      <v-btn
        aria-label="action menu"
        class="browserCardMenuIcon cardControlButton"
        :icon="mdiDotsVertical"
        title="Action Menu"
        variant="text"
        v-bind="props"
        @click.prevent
      />
    </template>
    <v-list class="background-soft-highlight">
      <CodexListItem
        v-if="listPk"
        class="listItem continueListItem"
        :prepend-icon="mdiPlay"
        title="Continue Reading"
        @click="continueList"
      />
      <MarkReadButton class="listItem" :button="false" :item="item" />
      <ReadingListMenu
        v-if="targetPk"
        :collection="item.collection"
        :pk="targetPk"
        location="end"
        submenu
      >
        <template #activator="{ props: listMenuProps }">
          <CodexListItem
            v-bind="listMenuProps"
            class="listItem readingListsListItem"
            :prepend-icon="mdiPlaylistPlus"
            :append-icon="mdiChevronRight"
            title="Reading Lists"
          />
        </template>
      </ReadingListMenu>
      <CodexListItem
        v-if="removablePk"
        class="listItem removeFromListItem"
        :prepend-icon="mdiPlaylistRemove"
        title="Remove from List"
        @click="removeFromThisList"
      />
      <CodexListItem
        v-if="copyListPk"
        class="listItem copyListItem"
        :prepend-icon="mdiContentCopy"
        title="Copy to My Lists"
        @click="copyList"
      />
      <ReadingListExportMenu v-if="listPk" :pk="listPk" />
      <DownloadButton class="listItem" :button="false" :item="downloadItem" />
      <ForceUpdateButton class="listItem" :button="false" :item="item" />
      <UploadCoverButton :item="item" @uploaded="closeMenu" />
      <RemoveCoverButton :item="item" @removed="closeMenu" />
    </v-list>
  </v-menu>
</template>

<script>
import {
  mdiChevronRight,
  mdiContentCopy,
  mdiDotsVertical,
  mdiPlay,
  mdiPlaylistPlus,
  mdiPlaylistRemove,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { formattedIssue, formattedVolumeName } from "@/comic-name";
import RemoveCoverButton from "@/components/browser/card/remove-cover-button.vue";
import UploadCoverButton from "@/components/browser/card/upload-cover-button.vue";
import CodexListItem from "@/components/codex-list-item.vue";
import DownloadButton from "@/components/download-button.vue";
import ForceUpdateButton from "@/components/force-update-button.vue";
import MarkReadButton from "@/components/mark-read-button.vue";
import ReadingListExportMenu from "@/components/reading-list-export-menu.vue";
import ReadingListMenu from "@/components/reading-list-menu.vue";
import { routeReadingListPk } from "@/route";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useReadingListsStore } from "@/stores/reading-lists";

const READING_LISTS = "arcs";

export default {
  name: "BrowserContainerMenu",
  components: {
    CodexListItem,
    DownloadButton,
    ForceUpdateButton,
    MarkReadButton,
    ReadingListExportMenu,
    ReadingListMenu,
    RemoveCoverButton,
    UploadCoverButton,
  },
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      mdiChevronRight,
      mdiContentCopy,
      mdiDotsVertical,
      mdiPlay,
      mdiPlaylistPlus,
      mdiPlaylistRemove,
      showMenu: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useBrowserStore, {
      listEditable: (state) => Boolean(state.page.listEditable),
    }),
    openListPk() {
      // The reading list the page shows, if it shows one.
      return routeReadingListPk(this.$route?.params);
    },
    removablePk() {
      // A comic inside a list this user may change.
      if (!this.listEditable || !this.openListPk) return;
      if (this.item?.collection !== "comics") return;
      return this.targetPk;
    },
    listPk() {
      // A reading list's card: everyone who sees it may read or export it.
      if (this.item?.collection !== READING_LISTS) return;
      return this.targetPk;
    },
    copyListPk() {
      /*
       * A signed-in user copies any reading list they can see into a list
       * of their own, to reorder or trim. Anonymous sessions own no lists.
       */
      if (!this.isLoggedIn || this.item?.collection !== READING_LISTS) return;
      return this.targetPk;
    },
    targetPk() {
      /*
       * A list holds single rows. Cards that aggregate several ids
       * (folder rollups, cross-publisher cards) can't go in a list
       * atomically, so they get no Reading Lists entry rather than a
       * guess at which pk to write.
       */
      const ids = this.item?.ids;
      if (!Array.isArray(ids) || ids.length !== 1) return undefined;
      return ids[0];
    },
    _collectionName() {
      const names = [
        this.item?.publisherName,
        this.item?.imprintName,
        this.item?.seriesName,
        formattedVolumeName(this.item?.volumeName),
        formattedIssue(this.item, 3),
        this.item?.name,
      ];
      return names.filter(Boolean).join(" ");
    },
    downloadName() {
      return this.item?.fileName || this._collectionName;
    },
    downloadItem() {
      return { ...this.item, name: this.downloadName };
    },
  },
  methods: {
    ...mapActions(useReadingListsStore, [
      "continueReading",
      "duplicateList",
      "removeFromList",
    ]),
    ...mapActions(useBrowserStore, ["refreshBrowserPage"]),
    closeMenu() {
      this.showMenu = false;
    },
    async removeFromThisList() {
      this.closeMenu();
      if (await this.removeFromList(this.openListPk, [this.removablePk])) {
        await this.refreshBrowserPage();
      }
    },
    async continueList() {
      this.closeMenu();
      await this.continueReading(this.listPk);
    },
    async copyList() {
      this.closeMenu();
      if (await this.duplicateList(this.copyListPk)) {
        // The copy is a card of its own in the reading lists grid.
        await this.refreshBrowserPage();
      }
    },
  },
};
</script>
