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
    </v-list>
  </v-menu>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";

import { formattedIssue, formattedVolumeName } from "@/comic-name";
import DownloadButton from "@/components/download-button.vue";
import MarkReadButton from "@/components/mark-read-button.vue";

export default {
  name: "BrowserContainerMenu",
  components: {
    DownloadButton,
    MarkReadButton,
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
    _groupName() {
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
      return this.item?.fileName || this._groupName;
    },
    downloadItem() {
      return { ...this.item, name: this.downloadName };
    },
  },
};
</script>
<style scoped lang="scss">
:deep(.v-icon) {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
