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
      <MarkReadButton class="listItem" :item="item" />
      <DownloadButton
        :group="item?.group"
        :pks="item?.ids"
        :children="children"
        :names="downloadNames"
        :ts="item?.mtime"
        class="listItem"
        :button="false"
      />
    </v-list>
  </v-menu>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";

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
    children() {
      return this.item?.childCount || 1;
    },
    groupNames() {
      return [
        this.item?.publisherName,
        this.item?.imprintName,
        this.item?.seriesName,
        this.item?.volumeName,
        this.item?.name,
      ];
    },
    downloadNames() {
      return this.item?.fileName ? [this.item?.fileName] : this.groupNames;
    },
  },
};
</script>
<style scoped lang="scss">
:deep(.v-icon) {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
