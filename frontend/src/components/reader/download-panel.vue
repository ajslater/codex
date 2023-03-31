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
    ...mapGetters(useReaderStore, ["activeTitle"]),
    ...mapState(useReaderStore, {
      storePage: (state) => state.page,
      pageSrc(state) {
        const params = { pk: state.pk, page: state.page };
        return getDownloadPageURL(params);
      },
      downloadURL(state) {
        return getDownloadURL(state.pk);
      },
    }),
    fileName: function () {
      let suffix = this.activeBook.fileType;
      suffix = suffix.lower() ? suffix : "unknown";
      return this.activeTitle + "." + suffix;
    },
    pageName: function () {
      return `${this.activeTitle} - page ${this.storePage}.jpg`;
    },
  },
  methods: {
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
    ...mapActions(useReaderStore, ["activeBook"]),
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
