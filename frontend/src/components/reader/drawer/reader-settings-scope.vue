<template>
  <v-expansion-panels v-model="openPanels" multiple>
    <v-expansion-panel value="global">
      <v-expansion-panel-title class="scopePanelTitle">
        Default Settings
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <ReaderSettingsControls
          :settings="globalSettings"
          @update="updateGlobalSettings"
        />
      </v-expansion-panel-text>
    </v-expansion-panel>
    <v-expansion-panel value="comic" :disabled="!validBook">
      <v-expansion-panel-title class="scopePanelTitle">
        Comic Settings
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <ReaderSettingsControls
          :settings="comicSettings"
          show-clear
          :clear-disabled="isClearDisabled"
          @update="updateComicSettings"
          @clear="clearComicSettings"
        />
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
  <v-divider />
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";
import { useEventListener } from "@vueuse/core";

import ReaderSettingsControls from "./reader-settings-controls.vue";

const ATTRS = Object.freeze([
  "fitTo",
  "readingDirection",
  "twoPages",
  "readRtlInReverse",
  "finishOnLastPage",
  "pageTransition",
  "cacheBook",
]);

export default {
  name: "ReaderSettingsScope",
  components: { ReaderSettingsControls },
  data() {
    return {
      openPanels: [],
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isAuthDialogOpen"]),
    ...mapState(useReaderStore, {
      globalSettings: (state) => state.readerSettings,
      comicSettings(state) {
        return state.books?.current?.settings || {};
      },
      validBook: (state) => Boolean(state.books?.current),
      isClearDisabled(state) {
        if (!state.books?.current) {
          return true;
        }
        for (const attr of ATTRS) {
          const val = Reflect.get(state.books?.current.settings, attr);
          if (!state.choices.nullValues.has(val)) {
            return false;
          }
        }
        return true;
      },
    }),
  },
  created() {
    useEventListener(document, "keyup", this._keyUpListener);
  },
  methods: {
    ...mapActions(useReaderStore, [
      "clearComicSettings",
      "updateGlobalSettings",
      "updateComicSettings",
    ]),
    _keyUpListener(event) {
      event.stopPropagation();
      if (this.isAuthDialogOpen) {
        return;
      }
      let updates;
      switch (event.key) {
        case "w":
          updates = { fitTo: "W" };
          break;
        case "h":
          updates = { fitTo: "H" };
          break;
        case "s":
          updates = { fitTo: "S" };
          break;
        case "o":
          updates = { fitTo: "O" };
          break;
        case "2":
          updates = {
            twoPages: !this.comicSettings.twoPages,
          };
          break;
        case "l":
          updates = {
            readingDirection: "ltr",
          };
          break;
        case "r":
          updates = {
            readingDirection: "rtl",
          };
          break;
        case "t":
          updates = {
            readingDirection: "ttb",
          };
          break;
        case "b":
          updates = {
            readingDirection: "bbt",
          };
          break;
      }
      if (updates) {
        this.updateComicSettings(updates);
      }
      /*
       * metadata and close are attached to to title-toolbar
       * No default
       */
    },
  },
};
</script>

<style scoped lang="scss">
:deep(.v-expansion-panel) {
  background-color: rgb(var(--v-theme-background));
}

.scopePanelTitle {
  padding-left: 15px;
  padding-right: 10px;
  font-weight: bolder;
  color: rgb(var(--v-theme-textDisabled));
}

:deep(.v-expansion-panel-title--active) {
  min-height: 48px !important;
}

:deep(.v-expansion-panel--active:not(:first-child)) {
  // Fix for default behavior that makes an unsightly margin on active
  margin-top: 0px;
}

:deep(.v-expansion-panel-text__wrapper) {
  padding-left: 10px;
  padding-right: 10px;
}
</style>
