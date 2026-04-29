<template>
  <v-expansion-panels v-model="openPanels" multiple>
    <v-expansion-panel value="global">
      <v-expansion-panel-title class="scopePanelTitle">
        Default Settings
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <ReaderSettingsControls
          :settings="globalSettings"
          show-clear
          :clear-disabled="isGlobalClearDisabled"
          @update="updateGlobalSettings"
          @clear="clearGlobalSettings"
        />
      </v-expansion-panel-text>
    </v-expansion-panel>
    <v-expansion-panel value="intermediate" :disabled="!hasIntermediate">
      <v-expansion-panel-title class="scopePanelTitle">
        <div class="intermediateTitleWrap">
          <span>{{ intermediateTitle }}</span>
          <span class="intermediateSubtitle">{{ intermediateName }}</span>
        </div>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <ReaderSettingsControls
          :settings="intermediateSettingsData"
          show-clear
          :clear-disabled="isIntermediateClearDisabled"
          @update="updateIntermediateSettings"
          @clear="clearIntermediateSettings"
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

import READER_DEFAULTS from "@/choices/reader-defaults.json";

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

const SCOPE_TYPE_TITLES = Object.freeze({
  s: "Series Settings",
  f: "Folder Settings",
  a: "Story Arc Settings",
});

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
      globalSettings: (state) => state.globalSettings,
      intermediateSettingsData: (state) => state.intermediateSettings || {},
      intermediateInfo: (state) => state.intermediateInfo,
      nullValues: (state) => state.choices.nullValues,
      comicSettings(state) {
        return state.books?.current?.settings || {};
      },
      validBook: (state) => Boolean(state.books?.current),
      isClearDisabled(state) {
        const settings = state.books?.current?.settings;
        if (!settings) {
          return true;
        }
        for (const attr of ATTRS) {
          const val = Reflect.get(settings, attr);
          if (!state.choices.nullValues.has(val)) {
            return false;
          }
        }
        return true;
      },
    }),
    isGlobalClearDisabled() {
      const settings = this.globalSettings;
      if (!settings) {
        return true;
      }
      for (const attr of ATTRS) {
        // eslint-disable-next-line security/detect-object-injection
        if (settings[attr] !== READER_DEFAULTS[attr]) {
          return false;
        }
      }
      return true;
    },
    hasIntermediate() {
      return Boolean(this.intermediateInfo);
    },
    intermediateTitle() {
      if (!this.intermediateInfo) {
        return "Group Settings";
      }
      return (
        SCOPE_TYPE_TITLES[this.intermediateInfo.scopeType] || "Group Settings"
      );
    },
    intermediateName() {
      return this.intermediateInfo?.name || "";
    },
    isIntermediateClearDisabled() {
      if (!this.intermediateInfo) {
        return true;
      }
      const settings = this.intermediateSettingsData;
      if (!settings) {
        return true;
      }
      for (const attr of ATTRS) {
        const val = Reflect.get(settings, attr);
        if (!this.nullValues.has(val)) {
          return false;
        }
      }
      return true;
    },
  },
  created() {
    useEventListener(document, "keyup", this._keyUpListener);
  },
  methods: {
    ...mapActions(useReaderStore, [
      "clearComicSettings",
      "clearGlobalSettings",
      "clearIntermediateSettings",
      "updateGlobalSettings",
      "updateComicSettings",
      "updateIntermediateSettings",
    ]),
    _updateOpenPanelSettings(updates) {
      // Dispatch to the most specific open expansion panel.
      if (this.openPanels.includes("comic")) {
        this.updateComicSettings(updates);
      } else if (this.openPanels.includes("intermediate")) {
        this.updateIntermediateSettings(updates);
      } else if (this.openPanels.includes("global")) {
        this.updateGlobalSettings(updates);
      } else {
        // No panel open — default to comic.
        this.updateComicSettings(updates);
      }
    },
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
        this._updateOpenPanelSettings(updates);
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
@forward "./expansion-panel-overrides";

:deep(.v-expansion-panel) {
  background-color: rgb(var(--v-theme-background));
}

.scopePanelTitle {
  padding-left: 15px;
  padding-right: 10px;
  font-weight: bolder;
  color: rgb(var(--v-theme-textDisabled));
}

.intermediateTitleWrap {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.intermediateSubtitle {
  font-size: 0.75rem;
  font-weight: normal;
  opacity: 0.7;
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
