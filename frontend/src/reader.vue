<template>
  <div id="readerWrapper">
    <div v-if="isOpenToSee" id="readerContainer">
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
import { mapActions, mapGetters, mapMutations } from "vuex";

import ReaderComicPage from "@/components/reader-comic-page";
import ReaderNavOverlay from "@/components/reader-nav-overlay";
import ReaderNavToolbar from "@/components/reader-nav-toolbar";
import ReaderSettingsDrawer from "@/components/reader-settings-drawer";
import ReaderTopToolbar from "@/components/reader-top-toolbar";

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
    ...mapGetters("auth", ["isOpenToSee"]),
  },
  watch: {
    $route(to, from) {
      if (!from.params || Number(to.params.pk) !== Number(from.params.pk)) {
        this.bookChanged();
      } else {
        this.routeChanged();
      }
      window.scrollTo(0, 0);
      this.setBrowseTimestamp();
    },
  },
  created() {
    this.bookChanged();
  },
  methods: {
    ...mapActions("reader", ["routeTo", "bookChanged", "routeChanged"]),
    ...mapMutations("browser", ["setBrowseTimestamp"]),
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
