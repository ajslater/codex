<template>
  <div v-if="currentBook" id="downloadPanel">
    <v-list-item @click="downloadPage">
      <v-list-item-title>
        <v-icon>{{ mdiFileImage }}</v-icon
        >Download Page
        {{ storePage }}
      </v-list-item-title>
    </v-list-item>
    <v-list-item @click="downloadBook">
      <v-list-item-title>
        <v-icon>{{ mdiDownload }}</v-icon
        >Download Book
      </v-list-item-title>
    </v-list-item>
  </div>
</template>

<script>
import { mdiDownload, mdiFileImage } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { getDownloadPageURL, getDownloadURL } from "@/api/v3/reader";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "DownloadPanel",
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
      return `${this.activeTitle} - page ${this.storePage}.jpg`;
    },
  },
  methods: {
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
    downloadPage() {
      this.downloadIOSPWAFix(this.pageSrc, this.pageName);
    },
    downloadBook() {
      this.downloadIOSPWAFix(this.downloadURL, this.filename);
    },
  },
};
</script>

<style scoped lang="scss">
#downloadPanel {
  background-color: rgb(var(--v-theme-background));
}
</style>
