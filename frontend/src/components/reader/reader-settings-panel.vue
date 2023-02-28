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
    <v-label>Reading Direction</v-label>
    <v-checkbox
      class="readInReverse"
      density="compact"
      label="Read in Reverse"
      hide-details="auto"
      :model-value="selectedSettings.readInReverse"
      :true-value="true"
      :indeterminate="
        selectedSettings.readInReverse === null ||
        selectedSettings.readInReverse === undefined
      "
      @update:model-value="settingsDialogChanged({ readInReverse: $event })"
    />
    <v-checkbox
      v-if="isGlobalScope"
      :model-value="selectedSettings.readRtlInReverse"
      class="readRtlInReverse"
      density="compact"
      label="Read RTL comics in Reverse"
      hide-details="auto"
      :true-value="true"
      @update:model-value="settingsDialogChanged({ readRtlInReverse: $event })"
    />
    <v-btn
      v-if="!isGlobalScope"
      id="clearSettingsButton"
      :disabled="isClearSettingsButtonDisabled"
      title="Use the default settings for all comics for this comic"
      @click="clearSettingsLocal($route.params)"
    >
      Clear Comic Settings
    </v-btn>
  </div>
</template>
<script>
import { mapActions, mapState, mapWritableState } from "pinia";

import { useReaderStore } from "@/stores/reader";

const ATTRS = ["fitTo", "twoPages"];

export default {
  name: "ReaderSettingsPanel",
  data() {
    return {
      isGlobalScope: false,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      fitToChoices(state) {
        const displayChoices = [];
        for (const choice of state.choices.fitTo) {
          if (choice.value) {
            displayChoices.push(choice);
          }
        }
        return displayChoices;
      },
      selectedSettings: function (state) {
        return this.isGlobalScope || !state.activeBook
          ? state.readerSettings
          : state.activeBook.settings;
      },
      isClearSettingsButtonDisabled: function (state) {
        if (this.isGlobalScope || !state.activeBook) {
          return true;
        }
        for (const attr of ATTRS) {
          const val = state.activeBook.settings[attr];
          if (!state.choices.nullValues.has(val)) {
            return false;
          }
        }
        return true;
      },
    }),
    ...mapWritableState(useReaderStore, ["readRTLInReverse"]),
  },
  mounted() {
    document.addEventListener("keyup", this._keyListener);
  },
  unmounted: function () {
    document.removeEventListener("keyup", this._keyListener);
  },

  methods: {
    ...mapActions(useReaderStore, [
      "clearSettingsLocal",
      "setSettingsGlobal",
      "setSettingsLocal",
    ]),
    settingsDialogChanged: function (data) {
      if (this.isGlobalScope) {
        this.setSettingsGlobal(this.$route.params, data);
      } else {
        this.setSettingsLocal(this.$route.params, data);
      }
    },
    _keyListener: function (event) {
      event.stopPropagation();
      let updates;
      switch (event.key) {
        case "w":
          updates = { fitTo: "WIDTH" };
          break;

        case "h":
          updates = { fitTo: "HEIGHT" };
          break;

        case "s":
          updates = { fitTo: "SCREEN" };
          break;

        case "o":
          updates = { fitTo: "ORIG" };
          break;

        case "2":
          updates = {
            twoPages: !this.selectedSettings.twoPages,
          };
          break;
        case "r":
          updates = {
            readInReverse: !this.selectedSettings.readInReverse,
          };
          break;
      }
      if (updates) {
        this.setSettingsLocal(this.$route.params, updates);
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
  margin-bottom: 4px;
  transition: visibility 0.25s, opacity 0.25s;
}
</style>
