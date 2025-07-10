<template>
  <h4 class="readerSettingsHeader">Comic Settings Scope</h4>
  <v-radio-group
    v-model="isGlobalScope"
    class="scopeRadioGroup readerCodexListItem"
    density="compact"
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
    <div id="readerScopedSettings" class="readerCodexListItem">
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
        class="scopedCheckbox"
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
      <v-checkbox
        :model-value="selectedSettings.readRtlInReverse"
        class="scopedCheckbox"
        density="compact"
        label="Read RTL Comics LTR"
        hide-details="auto"
        :true-value="true"
        @update:model-value="
          settingsDialogChanged({ readRtlInReverse: $event })
        "
      />

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
  <h4 class="readerSettingsHeader">Reader Settings</h4>
  <v-checkbox
    class="readerCodexListItem"
    :model-value="finishOnLastPage"
    density="compact"
    label="Finish Book On Last Page"
    hide-details="auto"
    :true-value="true"
    @update:model-value="setSettingsGlobal({ finishOnLastPage: $event })"
  />
  <v-checkbox
    v-tooltip="{
      openDelay,
      text: 'Animate page turns when reading horizontally.',
    }"
    :model-value="pageTransition"
    class="readerCodexListItem"
    density="compact"
    :disabled="disablePageTransition"
    label="Animate Page Turns"
    hide-details="auto"
    :true-value="true"
    @update:model-value="setSettingsGlobal({ pageTransition: $event })"
  />
  <v-checkbox
    v-tooltip="{
      openDelay,
      text: 'Cache all pages from this book in the browser',
    }"
    :model-value="cacheBook"
    class="readerCodexListItem"
    density="compact"
    :disabled="disableCacheBook"
    label="Cache Entire Book"
    hide-details="auto"
    :true-value="true"
    @update:model-value="setSettingsClient({ cacheBook: $event })"
  />

  <!-- eslint-disable sonarjs/no-vue-bypass-sanitization -->
  <CodexListItem
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
import { mapActions, mapState, mapWritableState } from "pinia";

import { getPDFInBrowserURL } from "@/api/v3/reader";
import CodexListItem from "@/components/codex-list-item.vue";
import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";
const ATTRS = ["fitTo", "readingDirection", "twoPages"];
Object.freeze(ATTRS);

export default {
  name: "ReaderSettingsPanel",
  components: { CodexListItem },
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
    ...mapState(useAuthStore, ["isAuthDialogOpen"]),
    ...mapState(useReaderStore, ["isVertical", "isPDF", "cacheBook"]),
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
        return this.isPDF && state.books?.current
          ? getPDFInBrowserURL(state.books?.current)
          : "";
      },
      finishOnLastPage: (state) => state.readerSettings.finishOnLastPage,
      pageTransition: (state) => state.readerSettings.pageTransition,
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
    disablePageTransition() {
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
      /*
       * metadata and close are attached to to title-toolbar
       * No default
       */
    },
  },
};
</script>

<style scoped lang="scss">
.readerSettingsHeader {
  padding-top: 10px;
  color: rgb(var(--v-theme-textDisabled));
  padding-left: 15px;
}

.scopeRadioGroup {
  padding-top: 10px;
  padding-bottom: 4px;
}

.scopedCheckbox {
  padding-left: 6px;
  padding-top: 5px;
  padding-bottom: 10px;
}

.readerCodexListItem {
  padding-left: 15px;
  padding-right: env(safe-area-inset-right);
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
