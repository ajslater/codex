<template>
  <div id="downloadPanel">
    <v-list-item @click="downloadPage">
      <v-list-item-title>
        <v-icon>{{ mdiFileImage }}</v-icon
        >Download Page
        {{ $route.params.page }}
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
import { mapActions, mapGetters } from "pinia";

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
    ...mapGetters(useReaderStore, ["activeTitle"]),
    pageSrc: function () {
      return getDownloadPageURL(this.$route.params);
    },
    downloadURL: function () {
      return getDownloadURL(this.$route.params.pk);
    },
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
<style scoped lang="scss">
#downloadPanel {
  background-color: rgb(var(--v-theme-background));
}
</style>
