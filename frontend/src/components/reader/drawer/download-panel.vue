<template>
  <div v-if="currentBook" id="downloadPanel">
    <CodexListItem
      :prepend-icon="mdiFileImage"
      :title="downloadPageTitle"
      @click="downloadPage"
    />
    <DownloadButton
      :pks="downloadPks"
      :children="1"
      :names="downloadNames"
      :ts="ts"
    />
  </div>
</template>

<script>
import { mdiDownload, mdiFileImage } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { getDownloadIOSPWAFix } from "@/api/v3/common";
import { getDownloadPageURL } from "@/api/v3/reader";
import CodexListItem from "@/components/codex-list-item.vue";
import DownloadButton from "@/components/download-button.vue";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "DownloadPanel",
  components: {
    CodexListItem,
    DownloadButton,
  },
  data() {
    return {
      mdiDownload,
      mdiFileImage,
    };
  },
  computed: {
    ...mapGetters(useReaderStore, ["activeTitle", "routeParams"]),
    ...mapState(useReaderStore, {
      currentBook: (state) => state.books?.current,
      fileType: (state) => state.books?.current?.fileType,
      ts: (state) => state.books?.current?.mtime,
      pk: (state) => state.books?.current?.pk,
      downloadNames: (state) => [state.books?.current?.filename],
      storePage: (state) => state.page,
    }),
    downloadPks() {
      return [this.pk];
    },
    pageSrc() {
      const pageObj = { pk: this.pk, page: this.storePage, ts: this.ts };
      return getDownloadPageURL(pageObj);
    },
    pageName() {
      const suffix = this.fileType === "PDF" ? "pdf" : "jpg";
      return `${this.activeTitle} - page ${this.storePage}.${suffix}`;
    },
    downloadPageTitle() {
      return `Download Page ${this.storePage}`;
    },
  },
  methods: {
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
    downloadPage() {
      getDownloadIOSPWAFix(this.pageSrc, this.pageName);
    },
  },
};
</script>

<style scoped lang="scss">
#downloadPanel {
  background-color: rgb(var(--v-theme-background));
}
</style>
