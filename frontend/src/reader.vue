<template>
  <div id="readerWrapper">
    <div v-if="isCodexViewable" id="readerContainer">
      <v-main>
        <div id="pagesContainer">
          <ReaderComicPage :page-increment="+0" />
          <ReaderComicPage :page-increment="+1" />
        </div>
        <div id="navOverlay" @click="toggleToolbars">
          <ReaderNavOverlay />
        </div>
      </v-main>
      <v-slide-y-transition>
        <ReaderTopToolbar v-show="showToolbars" />
      </v-slide-y-transition>
      <v-slide-y-reverse-transition>
        <ReaderNavToolbar v-show="showToolbars" />
      </v-slide-y-reverse-transition>
    </div>
    <div v-else id="announcement">
      <h1>
        <router-link :to="{ name: 'home' }">Log in</router-link> to read comics
      </h1>
    </div>
    <ReaderSettingsDrawer />
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import ReaderComicPage from "@/components/reader-comic-page.vue";
import ReaderNavOverlay from "@/components/reader-nav-overlay.vue";
import ReaderNavToolbar from "@/components/reader-nav-toolbar.vue";
import ReaderSettingsDrawer from "@/components/reader-settings-drawer.vue";
import ReaderTopToolbar from "@/components/reader-top-toolbar.vue";
import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";

const MIN_VIEWPORT_WIDTH_SWIPE_ENABLED = 768;

export default {
  name: "MainReader",
  components: {
    ReaderComicPage,
    ReaderNavOverlay,
    ReaderNavToolbar,
    ReaderTopToolbar,
    ReaderSettingsDrawer,
  },
  data() {
    return {
      showToolbars: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
  },
  watch: {
    $route(to, from) {
      if (!from.params || Number(to.params.pk) !== Number(from.params.pk)) {
        this.loadBook();
      } else {
        this.setRoutesAndBookmarkPage();
      }
      window.scrollTo(0, 0);
    },
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
    touchMap: function () {
      const vw = Math.max(
        document.documentElement.clientWidth || 0,
        window.innerWidth || 0
      );
      return vw >= MIN_VIEWPORT_WIDTH_SWIPE_ENABLED
        ? {
            left: () => this.routeTo("next"),
            right: () => this.routeTo("prev"),
          }
        : {};
    },
  },
};
</script>

<style scoped lang="scss">
#navOverlay {
  position: fixed;
  top: 0px;
  width: 100%;
  height: 100vh;
}
#pagesContainer {
  /* because its more difficult to center with v-main */
  display: flex;
  flex-wrap: nowrap;
  justify-content: center;
  touch-action: manipulation;
}
#readerContainer {
  max-width: 100%;
  position: relative;
}
#announcement {
  text-align: center;
}
</style>
