<template>
  <v-slide-y-transition>
    <header v-show="showToolbars" id="readerTopToolbarHeader">
      <AppBanner />
      <v-toolbar
        id="readerToolbarTop"
        density="compact"
        :extension-height="extensionHeight"
      >
        <v-toolbar-items>
          <v-btn
            ref="closeBook"
            class="closeBook"
            :to="closeRoute"
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
            :book="metadataBook"
            :toolbar="true"
          />
        </v-toolbar-items>
        <v-toolbar-items>
          <SettingsDrawerButton />
        </v-toolbar-items>
        <template v-if="title" #extension>
          <!-- eslint-disable-next-line vue/no-v-text-v-html-on-component,vue/no-v-html -->
          <v-toolbar-title class="readerTitle">
            <div id="title">
              {{ title }}
            </div>
            <div v-if="subtitle" id="subtitle">
              {{ subtitle }}
            </div>
          </v-toolbar-title>
        </template>
      </v-toolbar>
    </header>
  </v-slide-y-transition>
</template>

<script>
import { mdiClose } from "@mdi/js";
import deepClone from "deep-clone";
import { mapActions, mapState } from "pinia";

import AppBanner from "@/components/banner.vue";
import MetadataDialog from "@/components/metadata/metadata-dialog.vue";
import ReaderArcSelect from "@/components/reader/toolbars/top/reader-arc-select.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderTitleToolbar",
  components: {
    AppBanner,
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
    const title = `Read / ${this.activeTitle} / page ${this.storePage}`;
    const content = `reader ${title}`;
    return {
      title,
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
    ...mapState(useAuthStore, ["isAuthDialogOpen"]),
    ...mapState(useReaderStore, ["activeTitle", "closeBookRoute"]),
    ...mapState(useReaderStore, {
      showToolbars: (state) => state.showToolbars,
      currentBook: (state) => state.books?.current || {},
      empty: (state) => state.empty,
      subtitle: (state) => state.books?.current?.name || "",
      storePage: (state) => state.page,
    }),
    title() {
      return this.activeTitle;
    },
    extensionHeight() {
      let height = 32;
      if (this.subtitle) {
        height *= 2;
      }
      height += 4;
      return height;
    },
    closeRoute() {
      const route = deepClone(this.closeBookRoute);
      const params = deepClone(route.params);
      delete params["name"];
      route.params = params;
      return route;
    },
    metadataBook() {
      const book = { ...this.currentBook };
      book.group = "c";
      book.childCount = 0;
      return book;
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
@use "sass:map";

#readerTopToolbarHeader {
  position: fixed;
  width: 100%;
  z-index: 20;
}

#readerToolbarTop {
  padding-left: 0px; // given to button;
  padding-right: 0px; // given to button.
}

.closeBook {
  padding-left: max(18px, calc(env(safe-area-inset-left) / 2));
}

.readerTitle {
  padding-left: calc(env(safe-area-inset-left) / 2);
  padding-right: calc(env(safe-area-inset-left) / 2);
  text-align: center;
  white-space: nowrap;
  overflow-y: scroll;
}

.readerTitle {
  padding-bottom: 4px;
}

#title {
  font-size: clamp(18px, 3vw, 20px);
}

#subtitle {
  font-size: clamp(16px, 3vw, 18px);
  color: rgb(var(--v-theme-textSecondary));
  padding-bottom: 10px;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .closeBook {
    font-size: small;
    padding-left: max(10px, calc(env(safe-area-inset-left) / 2));
  }
}
</style>
