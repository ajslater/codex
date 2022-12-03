<template>
  <v-toolbar id="readerTopToolbar" class="codexToolbar" density="compact">
    <v-toolbar-items>
      <v-btn id="closeBook" ref="closeBook" :to="closeBookRoute" size="large">
        <span v-if="!$vuetify.display.mobile">close book</span>
        <v-icon v-else title="Close Book">
          {{ mdiClose }}
        </v-icon>
      </v-btn>
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-title id="toolbarTitle" class="codexToolbarTitle">
      {{ activeTitle }}
    </v-toolbar-title>
    <v-spacer />
    <span v-if="seriesPosition" id="seriesPosition" title="Series Position">{{
      seriesPosition
    }}</span>
    <v-toolbar-items>
      <v-btn id="tagButton" @click.stop="openMetadata">
        <MetadataDialog
          ref="metadataDialog"
          group="c"
          :pk="Number($route.params.pk)"
        />
      </v-btn>
      <SettingsDrawerButton
        id="settingsButton"
        @click.stop="isSettingsDrawerOpen = true"
      />
    </v-toolbar-items>
  </v-toolbar>
</template>

<script>
import { mdiClose } from "@mdi/js";
import { mapActions, mapGetters, mapState, mapWritableState } from "pinia";

import CHOICES from "@/choices";
import MetadataDialog from "@/components/metadata/metadata-dialog.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { useBrowserStore } from "@/stores/browser";
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
    };
  },
  head() {
    const page = this.$route.params.page;
    const content = `read ${this.title} page ${page}`;
    return { meta: [{ hid: "description", name: "description", content }] };
  },
  computed: {
    ...mapGetters(useReaderStore, ["activeTitle", "activeBook"]),
    ...mapState(useReaderStore, {
      seriesPosition: function (state) {
        if (this.activeBook && state.seriesCount > 1) {
          return `${this.activeBook.seriesIndex}/${state.seriesCount}`;
        }
        return "";
      },
    }),
    ...mapState(useBrowserStore, {
      lastRoute: (state) => state.page.routes.last,
    }),
    ...mapWritableState(useReaderStore, ["isSettingsDrawerOpen"]),
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
  },
  mounted() {
    document.addEventListener("keyup", this._keyListener);
  },
  unmounted: function () {
    document.removeEventListener("keyup", this._keyListener);
  },
  methods: {
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
            window.innerHeight + window.scrollY + 1 >=
              document.body.scrollHeight
          ) {
            // Spacebar goes next only at the bottom of page
            this.routeToDirection(NEXT);
          } else if (
            // Shift + Spacebar goes back only at the top of page
            !!event.shiftKey &&
            window.scrollY === 0
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
        case "Escape":
          this.$refs.closeBook.$el.click();
          break;
        case "m":
          this.openMetadata();
          break;
        // No default
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
#readerTopToolbar {
  width: 100%;
  top: 0px;
  padding-top: env(safe-area-inset-top);
  padding-left: calc(env(safe-area-inset-left) / 2);
  padding-right: calc(env(safe-area-inset-right) / 2);
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
  color: rgb(var(--v-theme-textSecondary));
  text-align: center;
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #closeBook {
    min-width: 32px;
  }
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
#readerTopToolbar .tagButton {
  min-width: 24px;
  height: 24px;
  width: 24px;
  margin: 0px;
}
</style>
