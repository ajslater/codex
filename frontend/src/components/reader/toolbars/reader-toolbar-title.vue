<template>
  <v-toolbar id="readerTopToolbar" class="codexToolbar" density="compact">
    <v-toolbar-items>
      <v-btn
        id="closeBook"
        ref="closeBook"
        :to="closeBookRoute"
        size="large"
        density="compact"
        variant="plain"
        @click="onCloseBook"
      >
        <span v-if="!$vuetify.display.smAndDown">close book</span>
        <v-icon v-else title="Close Book">
          {{ mdiClose }}
        </v-icon>
      </v-btn>
    </v-toolbar-items>
    <v-toolbar-title id="toolbarTitle" class="codexToolbarTitle">
      <!-- eslint-disable-next-line vue/no-v-html -->
      <span v-html="title"></span>
    </v-toolbar-title>
    <v-toolbar-items v-if="!empty">
      <ReaderArcSelect />
      <MetadataDialog
        id="tagButton"
        ref="metadataDialog"
        group="c"
        :toolbar="true"
        :book="currentBook"
      />
    </v-toolbar-items>
    <v-toolbar-items>
      <SettingsDrawerButton />
    </v-toolbar-items>
  </v-toolbar>
</template>

<script>
import { mdiClose } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import CHOICES from "@/choices";
import MetadataDialog from "@/components/metadata/metadata-dialog.vue";
import ReaderArcSelect from "@/components/reader/toolbars/reader-arc-select.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderTitleToolbar",
  components: {
    MetadataDialog,
    ReaderArcSelect,
    SettingsDrawerButton,
  },
  data() {
    return {
      mdiClose,
      routeChanged: false,
    };
  },
  head() {
    const content = `reader ${this.activeTitle} page ${this.storePage}`;
    return {
      meta: [
        {
          hid: "description",
          name: "description",
          content,
        },
      ],
    };
  },
  computed: {
    ...mapGetters(useReaderStore, ["activeTitle"]),
    ...mapState(useReaderStore, {
      currentBook: (state) => state.books?.current || {},
      closeRoute: (state) => state.routes.close,
      empty: (state) => state.empty,
    }),
    closeBookRoute() {
      // Choose the best route
      const route = {
        name: "browser",
        params: this.closeRoute,
      };
      if (route.params) {
        route.hash = `#card-${this.currentBook?.pk}`;
      } else {
        route.params =
          window.CODEX.LAST_ROUTE || CHOICES.browser.breadcrumbs[0];
      }
      return route;
    },
    title() {
      return this.activeTitle.replaceAll(" ", " <wrb/>");
    },
  },
  watch: {
    $route(to, from) {
      if (from) {
        this.routeChanged = true;
      }
    },
  },
  mounted() {
    document.addEventListener("keyup", this._keyUpListener);
  },
  beforeUnmount() {
    document.removeEventListener("keyup", this._keyUpListener);
  },
  methods: {
    ...mapActions(useCommonStore, ["setTimestamp"]),
    ...mapActions(useReaderStore, [
      "routeToDirection",
      "routeToDirectionOne",
      "routeToBook",
      "setBookChangeFlag",
    ]),
    openMetadata() {
      this.$refs.metadataDialog.dialog = true;
    },
    onCloseBook() {
      if (this.routeChanged) {
        this.setTimestamp();
      }
    },
    _keyUpListener(event) {
      event.stopPropagation();
      switch (event.key) {
        case "Escape":
          this.$refs.closeBook.$el.click();
          break;
        case "m":
          if (!this.empty) {
            this.openMetadata();
          }
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
  z-index: 20;
}

:deep(.v-toolbar__content) {
  padding: 0px;
}

#toolbarTitle {
  font-size: clamp(8pt, 2.5vw, 18pt);
  line-height: normal;
}

:deep(.v-toolbar-title__placeholder) {
  text-overflow: clip;
  white-space: normal;
}

@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #closeBook {
    min-width: 32px;
  }
}
</style>
