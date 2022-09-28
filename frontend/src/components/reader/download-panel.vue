<template>
  <v-list-item-group>
    <v-list-item ripple @click="downloadPage">
      <v-list-item-content>
        <v-list-item-title>
          <v-icon>{{ mdiFileImage }}</v-icon> Download Page
          {{ $route.params.page }}
        </v-list-item-title>
      </v-list-item-content>
    </v-list-item>
    <v-list-item ripple @click="downloadBook">
      <v-list-item-content>
        <v-list-item-title>
          <v-icon>{{ mdiDownload }}</v-icon> Download Book
        </v-list-item-title>
      </v-list-item-content>
    </v-list-item>
  </v-list-item-group>
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
    ...mapGetters(useReaderStore, ["title"]),
    ...mapState(useBrowserStore, {
      downloadFileName: (state) => state.title + ".cbz",
      timestamp: (state) => state.timestamp,
      pageSrc: function (state) {
        return getComicPageSource(this.$route.params, state.timestamp);
      },
      pageName: function (state) {
        const page = this.$route.params.page;
        return `${state.title} - page ${page}.jpg`;
      },
      downloadURL: function (state) {
        return getDownloadURL(this.$route.params.pk, state.timestamp);
      },
    }),
  },
  methods: {
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
    downloadPage() {
      this.downloadIOSPWAFix(this.pageSrc, this.pageName);
    },
    downloadBook() {
      this.downloadIOSPWAFix(this.downloadURL, this.downloadFileName);
    },
  },
};
</script>
