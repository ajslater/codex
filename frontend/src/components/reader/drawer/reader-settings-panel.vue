<template>
  <v-radio-group
    v-model="isGlobalScope"
    class="scopeRadioGroup readerDrawerItem"
    density="compact"
    label="Comic Settings Scope"
    hide-details="auto"
  >
    <v-radio
      v-for="item of scopeItems"
      :key="item.value"
      :label="item.title"
      :value="item.value"
    />
  </v-radio-group>
  <v-expand-transition>
    <div id="readerScopedSettings" class="readerDrawerItem">
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
        @update:model-value="
          settingsDialogChanged({ readingDirection: $event })
        "
      >
        <v-radio
          v-for="item in readingDirectionChoices"
          :key="item.value"
          :label="item.title"
          :value="item.value"
        />
      </v-radio-group>
      <v-btn
        v-if="!isGlobalScope"
        id="clearSettingsButton"
        v-tooltip="{
          openDelay,
          text: 'Use the default settings for all comics for this comic',
        }"
        :disabled="isClearSettingsButtonDisabled"
        @click="clearSettingsLocal"
      >
        Clear Settings
      </v-btn>
    </div>
  </v-expand-transition>
  <v-divider />
  <DrawerItem title="Reader Settings" />
  <v-checkbox
    class="readerDrawerItem"
    :model-value="finishOnLastPage"
    density="compact"
    label="Finish Book On Last Page"
    hide-details="auto"
    :true-value="true"
    @update:model-value="settingsDialogChanged({ finishOnLastPage: $event })"
  />
  <v-checkbox
    :model-value="selectedSettings.readRtlInReverse"
    class="readerDrawerItem"
    density="compact"
    label="Read RTL Comics as LTR"
    hide-details="auto"
    :true-value="true"
    @update:model-value="settingsDialogChanged({ readRtlInReverse: $event })"
  />
  <v-checkbox
    v-tooltip="{
      openDelay,
      text: 'Cache all pages from this book in the browser',
    }"
    :model-value="cacheBook"
    class="readerDrawerItem cacheBook"
    density="compact"
    :disabled="disableCacheBook"
    label="Cache Entire Book"
    hide-details="auto"
    :true-value="true"
    @update:model-value="setSettingsClient({ cacheBook: $event })"
  />
  <!-- eslint-disable sonarjs/no-vue-bypass-sanitization -->
  <DrawerItem
    v-if="pdfInBrowserURL"
    :prepend-icon="mdiEye"
    :append-icon="mdiOpenInNew"
    title="Read in Tab"
    :href="pdfInBrowserURL"
    target="_blank"
  />
</template>

<script>
import { mdiEye, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapGetters, mapState, mapWritableState } from "pinia";

import { getPDFInBrowserURL } from "@/api/v3/reader";
import DrawerItem from "@/components/drawer-item.vue";
import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";
const ATTRS = ["fitTo", "readingDirection", "twoPages"];
Object.freeze(ATTRS);

export default {
  name: "ReaderSettingsPanel",
  components: { DrawerItem },
  data() {
    return {
      isGlobalScope: false,
      mdiOpenInNew,
      mdiEye,
      openDelay: 2000,
      scopeItems: [
        { title: "Only this comic", value: false },
        { title: "Default for all comics", value: true },
      ],
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isAuthDialogOpen"]),
    ...mapGetters(useReaderStore, ["isVertical", "isPDF", "cacheBook"]),
    ...mapState(useReaderStore, {
      choices: (state) => state.choices,
      validBook: (state) => Boolean(state.books?.current),
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
      pdfInBrowserURL(state) {
        if (this.isPDF && state.books?.current) {
          return getPDFInBrowserURL(state.books?.current);
        } else {
          return "";
        }
      },
      finishOnLastPage: (state) => state.readerSettings.finishOnLastPage,
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
.scopeRadioGroup {
  padding-top: 10px;
  padding-bottom: 4px;
}
.scopeRadioGroup :deep(.v-input__control > .v-label) {
  opacity: 1;
}

.readerDrawerItem {
  padding-left: 15px;
  padding-right: env(safe-area-inset-right);
}

.displayTwoPages {
  padding-left: 6px;
  padding-top: 5px;
  padding-bottom: 10px;
}

#clearSettingsButton {
  margin-top: 6px;
  margin-bottom: 4px;
}

#readerScopedSettings {
  background-color: rgba(var(--v-theme-surface));
  margin-left: 10px;
  padding-left: 5px;
  padding-top: 4px;
  margin-right: 8px;
  margin-bottom: 5px;
}
</style>
