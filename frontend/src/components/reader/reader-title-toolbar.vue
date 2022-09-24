<template>
  <v-toolbar id="readerTopToolbar" dense>
    <v-toolbar-items>
      <v-btn id="closeBook" ref="closeBook" :to="closeBookRoute" large ripple>
        <span v-if="!$vuetify.breakpoint.mobile">close book</span>
        <v-icon v-else>
          {{ mdiClose }}
        </v-icon>
      </v-btn>
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-title id="toolbarTitle">
      {{ title }}
    </v-toolbar-title>
    <v-spacer />
    <span v-if="seriesPosition" id="seriesPosition">{{ seriesPosition }}</span>
    <v-toolbar-items>
      <v-btn id="tagButton" @click.stop="openMetadata">
        <MetadataDialog
          ref="metadataDialog"
          group="c"
          :pk="Number($router.currentRoute.params.pk)"
        />
      </v-btn>
      <v-btn id="downloadPageButton" title="Download Page" @click="download">
        <v-icon>{{ mdiFileImage }}</v-icon>
      </v-btn>
      <SettingsDrawerButton
        id="settingsButton"
        @click.stop="isSettingsDrawerOpen = true"
      />
    </v-toolbar-items>
  </v-toolbar>
</template>

<script>
import { mdiClose, mdiFileImage } from "@mdi/js";
import { mapActions, mapGetters, mapState, mapWritableState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import CHOICES from "@/choices";
import { getFullComicName } from "@/comic-name";
import MetadataDialog from "@/components/metadata/metadata-dialog.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

const PREV = "prev";
const NEXT = "next";

export default {
  name: "ReaderTitleToolbar",
  components: {
    MetadataDialog,
    SettingsDrawerButton,
  },
  data() {
    return {
      mdiClose,
      mdiFileImage,
    };
  },
  head() {
    const page = this.$route.params.page;
    const content = `read ${this.title} page ${page}`;
    return { meta: [{ hid: "description", name: "description", content }] };
  },
  computed: {
    ...mapState(useReaderStore, {
      title: function (state) {
        return getFullComicName(state.comic);
      },
      routes: (state) => state.routes,
      timestamp: (state) => state.timestamp,
      seriesPosition: function (state) {
        if (state.routes.seriesCount > 1) {
          return `${state.routes.seriesIndex}/${state.routes.seriesCount}`;
        }
      },
    }),
    ...mapState(useBrowserStore, {
      lastRoute: (state) => state.page.routes.last,
    }),
    ...mapWritableState(useReaderStore, ["isSettingsDrawerOpen"]),
    ...mapGetters(useReaderStore, ["computedSettings"]),
    closeBookRoute: function () {
      // Choose the best route
      const route = {
        name: "browser",
        params: this.lastRoute,
      };
      if (route.params) {
        route.hash = `#card-${this.$route.params.pk}`;
      } else {
        route.params = window.CODEX.LAST_ROUTE || CHOICES.browser.route;
      }
      return route;
    },
    pageSrc: function () {
      const routeParams = { ...this.$router.currentRoute.params };
      return getComicPageSource(routeParams, this.timestamp);
    },
    pageName: function () {
      const page = this.$router.currentRoute.params.page;
      return `${this.title} - page ${page}.jpg`;
    },
  },
  mounted() {
    window.addEventListener("keyup", this._keyListener);
  },
  beforeDestroy: function () {
    window.removeEventListener("keyup", this._keyListener);
  },
  methods: {
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
    ...mapActions(useReaderStore, ["routeToDirection"]),
    openMetadata: function () {
      this.$refs.metadataDialog.dialog = true;
    },
    _keyListener: function (event) {
      event.stopPropagation();
      switch (event.key) {
        case " ":
          if (
            !event.shiftKey &&
            window.innerHeight + window.scrollY >= document.body.scrollHeight &&
            this.routes.next
          ) {
            // Spacebar goes next only at the bottom of page
            this.routeToDirection(NEXT);
          } else if (
            // Shift + Spacebar goes back only at the top of page
            !!event.shiftKey &&
            window.scrollY === 0 &&
            this.routes.prev
          ) {
            this.routeToDirection(PREV);
          }
          break;
        case "j":
        case "ArrowRight":
          this.routeToDirection(NEXT);
          break;

        case "k":
        case "ArrowLeft":
          this.routeToDirection(PREV);
          break;
        case "c":
          this.$refs.closeBook.$el.click();
          break;
        case "m":
          this.openMetadata();
          break;
        // No default
      }
    },
    download() {
      this.downloadIOSPWAFix(this.pageSrc, this.pageName);
    },
  },
};
</script>

<style scoped lang="scss">
#readerTopToolbar {
  width: 100%;
  position: fixed;
  top: 0px;
  padding-top: env(safe-area-inset-top);
  padding-left: calc(env(safe-area-inset-left) / 3);
  padding-right: calc(env(safe-area-inset-right) / 3);
  z-index: 10;
}
#toolbarTitle {
  overflow-y: auto;
  text-overflow: clip;
  white-space: normal;
  font-size: clamp(8pt, 2.5vw, 18pt);
}
#seriesPosition {
  padding-left: 10px;
  padding-right: 10px;
  color: darkgray;
  text-align: center;
}
#downloadPageButton {
  height: 100%;
}
@import "vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #closeBook {
    min-width: 32px;
  }
  #downloadPageButton,
  #tagButton {
    padding-left: 2px;
    padding-right: 2px;
    min-width: 16px;
  }
  #settingsButton {
    padding-left: 2px;
    padding-right: 2px;
  }
  #seriesPosition {
    padding-left: 0px;
    padding-right: 0px;
  }
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#readerTopToolbar .v-toolbar__content {
  padding: 0px;
}
#readerTopToolbar .tagIcon {
  position: relative !important;
  top: 0px !important;
  left: 0px !important;
  height: 24px;
  width: 24px;
  margin: 0px;
}
</style>
