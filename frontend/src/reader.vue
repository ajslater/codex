<template>
  <div>
    <v-main id="readerWrapper">
      <div v-if="isCodexViewable" id="readerContainer">
        <v-main>
          <div id="pagesContainer">
            <ReaderPage :page-increment="+0" />
            <ReaderPage :page-increment="+1" />
          </div>
          <div id="navOverlay" :v-touch="touchMap" @click="toggleToolbars">
            <ReaderNavOverlay />
          </div>
        </v-main>
        <v-slide-y-transition>
          <ReaderTitleToolbar v-show="showToolbars" />
        </v-slide-y-transition>
        <v-slide-y-reverse-transition>
          <ReaderNavToolbar v-show="showToolbars" />
        </v-slide-y-reverse-transition>
      </div>
      <div v-else id="announcement">
        <h1>
          <router-link :to="{ name: 'home' }">Log in</router-link> to read
          comics
        </h1>
      </div>
    </v-main>
    <ReaderSettingsDrawer />
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import ReaderNavOverlay from "@/components/reader/nav-overlay.vue";
import ReaderNavToolbar from "@/components/reader/nav-toolbar.vue";
import ReaderPage from "@/components/reader/page.vue";
import ReaderSettingsDrawer from "@/components/reader/settings-drawer.vue";
import ReaderTitleToolbar from "@/components/reader/title-toolbar.vue";
import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "MainReader",
  components: {
    ReaderPage,
    ReaderNavOverlay,
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
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    touchMap: () =>
      !this.$vuetify.breakpoint.mobile
        ? {
            left: () => this.routeTo("next"),
            right: () => this.routeTo("prev"),
          }
        : {},
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
