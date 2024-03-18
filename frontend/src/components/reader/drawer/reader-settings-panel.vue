<template>
  <div id="readerSettings">
    <v-radio-group
      v-model="isGlobalScope"
      density="compact"
      label="Scope"
      hide-details="auto"
    >
      <v-radio label="Only this comic" :value="false" />
      <v-radio label="Default for all comics" :value="true" />
    </v-radio-group>
    <v-radio-group
      class="displayRadioGroup"
      density="compact"
      label="Display"
      hide-details="auto"
      :model-value="selectedSettings.fitTo"
      @update:model-value="settingsDialogChanged({ fitTo: $event })"
    >
      <v-radio
        v-for="item in fitToChoices"
        :key="item.value"
        :label="item.title"
        :value="item.value"
      />
    </v-radio-group>
    <v-checkbox
      :disabled="disableTwoPages"
      class="displayTwoPages"
      density="compact"
      label="Two pages"
      hide-details="auto"
      :model-value="selectedSettings.twoPages"
      :true-value="true"
      :indeterminate="
        selectedSettings.twoPages === null ||
        selectedSettings.twoPages === undefined
      "
      @update:model-value="settingsDialogChanged({ twoPages: $event })"
    />
    <v-radio-group
      class="displayRadioGroup"
      density="compact"
      label="Reading Direction"
      hide-details="auto"
      :model-value="selectedSettings.readingDirection"
      @update:model-value="settingsDialogChanged({ readingDirection: $event })"
    >
      <v-radio
        v-for="item in readingDirectionChoices"
        :key="item.value"
        :label="item.title"
        :value="item.value"
      />
    </v-radio-group>
    <v-checkbox
      :model-value="cacheBook"
      class="cacheBook"
      density="compact"
      :disabled="disableCacheBook"
      label="Cache Entire Book"
      hide-details="auto"
      :true-value="true"
      @update:model-value="setSettingsClient({ cacheBook: $event })"
    />
    <a
      v-if="isPDF"
      id="readPDFInBrowser"
      :href="bookInBrowserURL"
      target="_blank"
    >
      <v-icon>{{ mdiOpenInNew }}</v-icon
      >Read PDF in Browser
    </a>
    <v-checkbox
      v-if="isGlobalScope"
      :model-value="selectedSettings.readRtlInReverse"
      class="readRtlInReverse"
      density="compact"
      label="Read RTL Comics as LTR"
      hide-details="auto"
      :true-value="true"
      @update:model-value="settingsDialogChanged({ readRtlInReverse: $event })"
    />
    <v-btn
      v-if="!isGlobalScope"
      id="clearSettingsButton"
      :disabled="isClearSettingsButtonDisabled"
      title="Use the default settings for all comics for this comic"
      @click="clearSettingsLocal"
    >
      Clear Comic Settings
    </v-btn>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapActions, mapGetters, mapState, mapWritableState } from "pinia";

import { getBookInBrowserURL } from "@/api/v3/common";
import { useReaderStore } from "@/stores/reader";

const ATTRS = ["fitTo", "readingDirection", "twoPages"];
Object.freeze(ATTRS);

export default {
  name: "ReaderSettingsPanel",
  data() {
    return {
      isGlobalScope: false,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters(useReaderStore, ["isVertical", "isPDF", "cacheBook"]),
    ...mapState(useReaderStore, {
      choices: (state) => state.choices,
      selectedSettings(state) {
        return this.isGlobalScope || !state.books?.current
          ? state.readerSettings
          : state.books?.current.settings;
      },
      isClearSettingsButtonDisabled(state) {
        if (this.isGlobalScope || !state.books?.current) {
          return true;
        }
        for (const attr of ATTRS) {
          const val = state.books?.current.settings[attr];
          if (!state.choices.nullValues.has(val)) {
            return false;
          }
        }
        return true;
      },
      bookInBrowserURL(state) {
        return getBookInBrowserURL(state.books?.current);
      },
    }),
    ...mapWritableState(useReaderStore, ["readRtlInReverse"]),
    fitToChoices() {
      return this.choicesWithoutNull("fitTo");
    },
    readingDirectionChoices() {
      return this.choicesWithoutNull("readingDirection");
    },
    disableTwoPages() {
      return this.isVertical || (this.isPDF && this.cacheBook);
    },
    disableCacheBook() {
      return this.isVertical && this.isPDF;
    },
  },
  mounted() {
    document.addEventListener("keyup", this._keyUpListener);
  },
  beforeUnmount() {
    document.removeEventListener("keyup", this._keyUpListener);
  },

  methods: {
    ...mapActions(useReaderStore, [
      "clearSettingsLocal",
      "setSettingsGlobal",
      "setSettingsLocal",
      "setSettingsClient",
    ]),
    settingsDialogChanged(data) {
      if (this.isGlobalScope) {
        this.setSettingsGlobal(data);
      } else {
        this.setSettingsLocal(data);
      }
    },
    choicesWithoutNull(attr) {
      const choices = [];
      for (const choice of this.choices[attr]) {
        if (choice.value) {
          choices.push(choice);
        }
      }
      Object.freeze(choices);
      return choices;
    },
    _keyUpListener(event) {
      event.stopPropagation();
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
            twoPages: !this.selectedSettings.twoPages,
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
        this.setSettingsLocal(updates);
      }
      // metadata and close are attached to to title-toolbar
      // No default
    },
  },
};
</script>

<style scoped lang="scss">
#readerSettings {
  padding-top: 10px;
  padding-left: 15px;
  padding-right: env(safe-area-inset-right);
  padding-bottom: 10px;
  background-color: inherit;
}

.displayRadioGroup {
  margin-top: 15px;
}

.displayTwoPages {
  margin-top: 5px;
  margin-bottom: 10px;
}

.readRtlInReverse {
  transition: visibility 0.25s, opacity 0.25s;
}

#clearSettingsButton {
  margin-top: 4px;
  margin-bottom: 4px;
  transition: visibility 0.25s, opacity 0.25s;
}

#readPDFInBrowser {
  display: block;
  padding-left: 2px;
  color: rgba(var(--v-theme-textSecondary));
}
</style>
