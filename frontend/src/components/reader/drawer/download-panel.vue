<template>
  <div id="downloadPanel">
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
    <v-list-item v-if="isPDF" @click="openBookInBrowser">
      <v-list-item-title>
        <v-icon>{{ mdiOpenInNew }}</v-icon
        >Read PDF with Browser
      </v-list-item-title>
    </v-list-item>
  </div>
</template>
<script>
import { mdiDownload, mdiFileImage, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { getBookInBrowserURL } from "@/api/v3/common";
import { getDownloadPageURL, getDownloadURL } from "@/api/v3/reader";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "DownloadPanel",
  data() {
    return {
      mdiDownload,
      mdiFileImage,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters(useReaderStore, ["activeTitle", "routeParams"]),
    ...mapState(useReaderStore, {
      storePage: (state) => state.page,
      filename: (state) => state.books?.current?.filename,
      downloadURL(state) {
        return getDownloadURL(state.books?.current?.pk);
      },
      bookInBrowserURL(state) {
        return getBookInBrowserURL(state.books?.current?.pk);
      },
      isPDF(state) {
        return state.books?.current?.fileType == "PDF";
      },
    }),
    pageSrc() {
      return getDownloadPageURL(this.routeParams);
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
    openBookInBrowser() {
      window.open(this.bookInBrowserURL, "_blank");
    },
  },
};
</script>
<style scoped lang="scss">
#downloadPanel {
  background-color: rgb(var(--v-theme-background));
}
</style>
