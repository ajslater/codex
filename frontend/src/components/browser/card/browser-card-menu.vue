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
      <DownloadButton class="listItem" :button="false" :item="downloadItem" />
      <ForceUpdateButton class="listItem" :button="false" :item="item" />
      <UploadCoverButton :item="item" @uploaded="closeMenu" />
      <RemoveCoverButton :item="item" @removed="closeMenu" />
    </v-list>
  </v-menu>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";

import { formattedIssue, formattedVolumeName } from "@/comic-name";
import RemoveCoverButton from "@/components/browser/card/remove-cover-button.vue";
import UploadCoverButton from "@/components/browser/card/upload-cover-button.vue";
import DownloadButton from "@/components/download-button.vue";
import ForceUpdateButton from "@/components/force-update-button.vue";
import MarkReadButton from "@/components/mark-read-button.vue";

export default {
  name: "BrowserContainerMenu",
  components: {
    DownloadButton,
    ForceUpdateButton,
    MarkReadButton,
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
      mdiDotsVertical,
      showMenu: false,
    };
  },
  computed: {
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
