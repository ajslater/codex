<template>
  <v-toolbar id="readerTopToolbar" dense>
    <v-toolbar-items>
      <v-btn id="closeBook" ref="closeBook" :to="closeBookRoute" large ripple>
        <span v-if="$vuetify.breakpoint.mdAndUp">close book</span>
        <span v-else>x</span>
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
      <a :href="pageSrc" title="Download Page" :download="pageName">
        <v-btn id="downloadPageButton">
          <v-icon>{{ mdiDownload }}</v-icon>
        </v-btn>
      </a>
      <SettingsDrawerButton
        id="settingsButton"
        @click.stop="toggleSettingsDrawerOpen"
      />
    </v-toolbar-items>
  </v-toolbar>
</template>

<script>
import { mdiDownload } from "@mdi/js";
import { mapActions, mapGetters, mapMutations, mapState } from "vuex";

import { getComicPageSource } from "@/api/v2/comic";
import CHOICES from "@/choices";
import { getFullComicName } from "@/components/comic-name";
import MetadataDialog from "@/components/metadata-dialog";
import SettingsDrawerButton from "@/components/settings-drawer-button";

export default {
  name: "ReaderTopToolbar",
  components: {
    MetadataDialog,
    SettingsDrawerButton,
  },
  data() {
    return {
      mdiDownload,
    };
  },
  head() {
    const page = this.$route.params.page;
    const content = `read ${this.title} page ${page}`;
    return { meta: [{ hid: "description", name: "description", content }] };
  },
  computed: {
    ...mapState("reader", {
      title: function (state) {
        return getFullComicName(state.comic);
      },
      timestamp: (state) => state.timestamp,
      seriesPosition: function (state) {
        if (state.routes.seriesCount > 1) {
          return `${state.routes.seriesIndex}/${state.routes.seriesCount}`;
        }
      },
    }),
    ...mapState("browser", {
      lastRoute: (state) => state.routes.last,
    }),
    ...mapGetters("reader", ["computedSettings"]),
    closeBookRoute: function () {
      // Choose the best route
      const route = {
        name: "browser",
        params: this.lastRoute,
      };
      if (route.params) {
        route.hash = `#card-${this.$route.params.pk}`;
      } else {
        route.params = window.lastRoute || CHOICES.browser.route;
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
    // Keyboard Shortcuts
    window.addEventListener("keyup", this._keyListener);
  },
  beforeDestroy: function () {
    window.removeEventListener("keyup", this._keyListener);
  },
  methods: {
    ...mapActions("reader", ["settingsChangedLocal"]),
    ...mapMutations("reader", ["toggleSettingsDrawerOpen"]),
    _keyListener: function (event) {
      event.stopPropagation();
      switch (event.key) {
        case "c":
          this.$refs.closeBook.$el.click();
          break;

        case "w":
          this.settingsChangedLocal({ fitTo: "WIDTH" });
          break;

        case "h":
          this.settingsChangedLocal({ fitTo: "HEIGHT" });
          break;
        case "s":
          this.settingsChangedLocal({ fitTo: "SCREEN" });
          break;

        case "o":
          this.settingsChangedLocal({ fitTo: "ORIG" });
          break;

        case "2":
          this.settingsChangedLocal({
            twoPages: !this.computedSettings.twoPages,
          });
          break;

        case "m":
          this.openMetadata();
          break;
        // No default
      }
    },
    openMetadata: function () {
      this.$refs.metadataDialog.dialog = true;
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
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #closeBook {
    min-width: 32px;
  }
  #downloadPageButton,
  #tagButton {
    padding-left: 8px;
    padding-right: 0px;
    min-width: 16px;
  }
  #settingsButton {
    padding-left: 10px;
  }
  #seriesPosition {
    padding-left: 0px;
    padding-right: 0px;
  }
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/* TOOLBARS */
.readerTopToolbar .v-toolbar__content {
  padding: 0px;
  padding-right: 16px;
}
</style>
