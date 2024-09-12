<template>
  <div v-if="currentBook" id="downloadPanel">
    <DrawerItem
      :prepend-icon="mdiFileImage"
      :title="downloadPageTitle"
      @click="downloadPage"
    />
    <DrawerItem
      :prepend-icon="mdiDownload"
      title="Download Book"
      @click="downloadBook"
    />
  </div>
</template>

<script>
import { mdiDownload, mdiFileImage } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { getDownloadIOSPWAFix } from "@/api/v3/common";
import { getDownloadPageURL, getDownloadURL } from "@/api/v3/reader";
import DrawerItem from "@/components/drawer-item.vue";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "DownloadPanel",
  components: {
    DrawerItem,
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
      storePage: (state) => state.page,
    }),
    downloadURL() {
      return getDownloadURL(this.currentBook);
    },
    filename() {
      return this.currentBook?.filename;
    },
    pageSrc() {
      const { pk, mtime } = this.currentBook;
      return getDownloadPageURL({ pk, page: this.storePage, mtime });
    },
    pageName() {
      const suffix = this.currentBook.fileType === "PDF" ? "pdf" : "jpg";
      return `${this.activeTitle} - page ${this.storePage}.${suffix}`;
    },
    downloadPageTitle() {
      return `Download Page ${this.storePage}`;
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
    downloadBook() {
      getDownloadIOSPWAFix(this.downloadURL, this.filename);
    },
  },
};
</script>

<style scoped lang="scss">
#downloadPanel {
  background-color: rgb(var(--v-theme-background));
}
</style>
