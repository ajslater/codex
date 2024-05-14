<template>
  <v-toolbar id="readerToolbarTop" density="compact">
    <v-toolbar-items>
      <v-btn
        ref="closeBook"
        class="closeBook"
        :to="closeBookRoute"
        size="large"
        density="compact"
        variant="plain"
        @click="onCloseBook"
      >
        close book
      </v-btn>
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-items v-if="!empty">
      <ReaderArcSelect />
      <MetadataDialog
        ref="metadataDialog"
        group="c"
        :toolbar="true"
        :book="currentBook"
      />
    </v-toolbar-items>
    <v-toolbar-items>
      <SettingsDrawerButton />
    </v-toolbar-items>
    <template v-if="title" #extension>
      <!-- eslint-disable-next-line vue/no-v-text-v-html-on-component,vue/no-v-html -->
      <v-toolbar-title id="title" v-html="title" />
    </template>
  </v-toolbar>
</template>

<script>
import { mdiClose } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import CHOICES from "@/choices";
import MetadataDialog from "@/components/metadata/metadata-dialog.vue";
import ReaderArcSelect from "@/components/reader/toolbars/top/reader-arc-select.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { useAuthStore } from "@/stores/auth";
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
    ...mapGetters(useAuthStore, ["isAuthDialogOpen"]),
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
      return this.activeTitle;
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
      if (this.isAuthDialogOpen) {
        return;
      }
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

#readerToolbarTop {
  position: fixed;
  top: 0px;
  width: 100%;
  padding-top: env(safe-area-inset-top);
  padding-left: 0px; // given to button;
  padding-right: 0px; // given to button.
  z-index: 20;
}

:deep(.v-toolbar__content) {
  padding: 0px;
}

:deep(.v-toolbar-title__placeholder) {
  text-overflow: clip;
  white-space: normal;
}
.closeBook {
  padding-left: max(20px, calc(env(safe-area-inset-left) / 2));
}
#title {
  font-size: clamp(12px, 2vw, 20px);
  text-align: center;
  white-space: nowrap;
  overflow: scroll;
}
</style>
