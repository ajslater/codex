<template>
  <v-main v-if="isCodexViewable" id="readerWrapper">
    <div v-if="!empty">
      <BookChangeDrawer direction="prev" />
      <div id="readerContainer">
        <v-slide-y-transition>
          <ReaderTitleToolbar v-show="showToolbars" />
        </v-slide-y-transition>
        <BooksWindow @click="toggleToolbars" />
        <v-slide-y-reverse-transition>
          <ReaderNavToolbar v-show="showToolbars" />
        </v-slide-y-reverse-transition>
      </div>
      <BookChangeDrawer direction="next" />
    </div>
    <ReaderEmpty v-else />
  </v-main>
  <Unauthorized v-else />
  <SettingsDrawer title="Reader" :panel="ReaderSettingsSuperPanel" temporary />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";
import { markRaw } from "vue";

import BookChangeDrawer from "@/components/reader/book-change-drawer.vue";
import BooksWindow from "@/components/reader/books-window.vue";
import ReaderSettingsSuperPanel from "@/components/reader/drawer/reader-settings-super-panel.vue";
import ReaderEmpty from "@/components/reader/empty.vue";
import ReaderNavToolbar from "@/components/reader/toolbars/reader-nav-toolbar.vue";
import ReaderTitleToolbar from "@/components/reader/toolbars/reader-title-toolbar.vue";
import SettingsDrawer from "@/components/settings/settings-drawer.vue";
import Unauthorized from "@/components/unauthorized.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "MainReader",
  components: {
    BookChangeDrawer,
    BooksWindow,
    ReaderEmpty,
    ReaderNavToolbar,
    ReaderTitleToolbar,
    SettingsDrawer,
    Unauthorized,
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
    ...mapState(useReaderStore, {
      empty: (state) => state.empty,
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
  },
  beforeMount() {
    useReaderStore().$reset;
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
</style>
