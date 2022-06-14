<template>
  <v-toolbar class="readerTopToolbar" dense>
    <v-toolbar-items>
      <v-btn id="closeBook" ref="closeBook" :to="closeBookRoute" large ripple
        ><span v-if="$vuetify.breakpoint.mdAndUp">close book</span
        ><span v-else>x</span></v-btn
      >
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-title id="toolbarTitle">{{ title }}</v-toolbar-title>
    <v-spacer />
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
  computed: {
    ...mapState("reader", {
      title: function (state) {
        return getFullComicName(state.comic);
      },
      timestamp: (state) => state.timestamp,
    }),
    ...mapGetters("reader", ["computedSettings"]),
    ...mapState("reader", {
      readerBrowserRoute: (state) => state.browserRoute,
    }),
    closeBookRoute: function () {
      // Choose the best route
      const route = {
        name: "browser",
      };
      if (this.readerBrowserRoute) {
        route.params = this.readerBrowserRoute;
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
.readerTopToolbar {
  width: 100%;
  position: fixed;
  top: 0px;
}
#toolbarTitle {
  overflow-y: auto;
  text-overflow: clip;
  white-space: normal;
}
#downloadPageButton {
  height: 100%;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #closeBook {
    min-width: 32px;
  }
  #tagButton {
    padding-left: 8px;
    padding-right: 0px;
    min-width: 16px;
  }
  #settingsButton {
    padding-left: 10px;
    padding-right: 0px;
    width: 16px;
  }
  #toolbarTitle {
    font-size: x-small;
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
