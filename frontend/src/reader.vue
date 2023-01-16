<template>
  <v-main id="readerWrapper">
    <BookChangeDrawer direction="prev" />
    <div v-if="isCodexViewable" id="readerContainer">
      <v-slide-y-transition>
        <ReaderTitleToolbar v-show="showToolbars" />
      </v-slide-y-transition>
      <BooksWindow @click="toggleToolbars" />
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
  <BookChangeDrawer direction="next" />
  <SettingsDrawer
    title="Reader Settings"
    :panel="ReaderSettingsSuperPanel"
    temporary
  />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";
import { markRaw } from "vue";

import BookChangeDrawer from "@/components/reader/book-change-drawer.vue";
import BooksWindow from "@/components/reader/pages-window.vue";
import ReaderNavToolbar from "@/components/reader/reader-nav-toolbar.vue";
import ReaderSettingsSuperPanel from "@/components/reader/reader-settings-super-panel.vue";
import ReaderTitleToolbar from "@/components/reader/reader-title-toolbar.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "MainReader",
  components: {
    BookChangeDrawer,
    BooksWindow,
    ReaderNavToolbar,
    ReaderTitleToolbar,
    SettingsDrawer,
  },
  data() {
    return {
      showToolbars: false,
      ReaderSettingsSuperPanel: markRaw(ReaderSettingsSuperPanel),
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
  },
  watch: {
    user() {
      this.loadReaderSettings();
    },
    isCodexViewable() {
      this.loadReaderSettings();
    },
  },
  created() {
    useCommonStore().isSettingsDrawerOpen = false;
    this.loadReaderSettings();
  },
  methods: {
    ...mapActions(useReaderStore, ["loadReaderSettings"]),
    toggleToolbars() {
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
