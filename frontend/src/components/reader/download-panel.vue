<template>
  <v-list-item @click="downloadPage">
    <v-list-item-title>
      <v-icon>{{ mdiFileImage }}</v-icon> Download Page
      {{ $route.params.page }}
    </v-list-item-title>
  </v-list-item>
  <v-list-item @click="downloadBook">
    <v-list-item-title>
      <v-icon>{{ mdiDownload }}</v-icon> Download Book
    </v-list-item-title>
  </v-list-item>
</template>
<script>
import { mdiDownload, mdiFileImage } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { getComicPageSource, getDownloadURL } from "@/api/v3/reader";
import { useBrowserStore } from "@/stores/browser";
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
    ...mapGetters(useReaderStore, ["activeTitle"]),
    ...mapState(useBrowserStore, {
      timestamp: (state) => state.timestamp,
      pageSrc: function (state) {
        return getComicPageSource(this.$route.params, state.timestamp);
      },
      downloadURL: function (state) {
        return getDownloadURL(this.$route.params.pk, state.timestamp);
      },
    }),
    fileName: function () {
      return this.activeTitle + ".cbz";
    },
    pageName: function () {
      const page = this.$route.params.page;
      return `${this.activeTitle} - page ${page}.jpg`;
    },
  },
  methods: {
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
    downloadPage() {
      this.downloadIOSPWAFix(this.pageSrc, this.pageName);
    },
    downloadBook() {
      this.downloadIOSPWAFix(this.downloadURL, this.fileName);
    },
  },
};
</script>
