<template>
  <div>
    <v-main id="readerWrapper">
      <div v-if="isCodexViewable" id="readerContainer">
        <ChangeBookDrawer direction="prev" />
        <PagesWindow @click="toggleToolbars" />
        <ChangeBookDrawer direction="next" />
        <v-slide-y-transition>
          <ReaderTitleToolbar v-show="showToolbars" />
        </v-slide-y-transition>
        <v-slide-y-reverse-transition>
          <ReaderNavToolbar v-show="showToolbars" />
        </v-slide-y-reverse-transition>
      </div>
      <div v-else id="announcement">
        <h1>
          <router-link :to="{ name: 'home' }"> Log in </router-link> to read
          comics
        </h1>
      </div>
    </v-main>
    <ReaderSettingsDrawer />
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import ChangeBookDrawer from "@/components/reader/change-book-drawer.vue";
import PagesWindow from "@/components/reader/pages-window.vue";
import ReaderNavToolbar from "@/components/reader/reader-nav-toolbar.vue";
import ReaderSettingsDrawer from "@/components/reader/reader-settings-drawer.vue";
import ReaderTitleToolbar from "@/components/reader/reader-title-toolbar.vue";
import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "MainReader",
  components: {
    ChangeBookDrawer,
    PagesWindow,
    ReaderNavToolbar,
    ReaderTitleToolbar,
    ReaderSettingsDrawer,
  },
  data() {
    return {
      showToolbars: false,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    ...mapState(useReaderStore, {
      isPDF: (state) => state.comic.fileFormat === "pdf",
    }),
  },
  watch: {
    user: function () {
      this.loadReaderSettings();
    },
    isCodexViewable: function () {
      this.loadReaderSettings();
    },
  },
  created() {
    this.loadReaderSettings();
    this.loadBook();
  },
  methods: {
    ...mapActions(useReaderStore, [
      "loadBook",
      "loadReaderSettings",
      "routeTo",
      "setRoutesAndBookmarkPage",
    ]),
    toggleToolbars: function () {
      this.showToolbars = !this.showToolbars;
    },
  },
};
</script>

<style scoped lang="scss">
#readerContainer {
  max-width: 100%;
  position: relative;
}
#announcement {
  text-align: center;
}
</style>
