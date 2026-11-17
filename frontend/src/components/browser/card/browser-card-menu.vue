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
      <MarkReadButton class="listItem" :button="false" :item="item" />
      <ShelfMenu
        v-if="shelfPk"
        :collection="item.collection"
        :pk="shelfPk"
        location="end"
      >
        <template #activator="{ props: shelfMenuProps }">
          <CodexListItem
            v-bind="shelfMenuProps"
            class="listItem shelvesListItem"
            :prepend-icon="mdiLibraryShelves"
            :append-icon="mdiChevronRight"
            title="Shelves & Lists"
          />
        </template>
      </ShelfMenu>
      <DownloadButton class="listItem" :button="false" :item="downloadItem" />
      <ForceUpdateButton class="listItem" :button="false" :item="item" />
      <UploadCoverButton :item="item" @uploaded="closeMenu" />
      <RemoveCoverButton :item="item" @removed="closeMenu" />
    </v-list>
  </v-menu>
</template>

<script>
import { mdiChevronRight, mdiDotsVertical, mdiLibraryShelves } from "@mdi/js";

import { formattedIssue, formattedVolumeName } from "@/comic-name";
import RemoveCoverButton from "@/components/browser/card/remove-cover-button.vue";
import UploadCoverButton from "@/components/browser/card/upload-cover-button.vue";
import CodexListItem from "@/components/codex-list-item.vue";
import DownloadButton from "@/components/download-button.vue";
import ForceUpdateButton from "@/components/force-update-button.vue";
import MarkReadButton from "@/components/mark-read-button.vue";
import ShelfMenu from "@/components/shelf-menu.vue";

export default {
  name: "BrowserContainerMenu",
  components: {
    CodexListItem,
    DownloadButton,
    ForceUpdateButton,
    MarkReadButton,
    RemoveCoverButton,
    ShelfMenu,
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
      mdiDotsVertical,
      mdiLibraryShelves,
      showMenu: false,
    };
  },
  computed: {
    shelfPk() {
      /*
       * A shelf holds single rows. Cards that aggregate several ids
       * (folder rollups, story-arc cross-publisher cards) can't be
       * shelved atomically, so they get no Shelves entry rather than
       * a guess at which pk to write.
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
    closeMenu() {
      this.showMenu = false;
    },
  },
};
</script>
