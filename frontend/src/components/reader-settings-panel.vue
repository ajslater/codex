<template>
  <div>
    <div id="readerSettings">
      <h3>Reader Settings</h3>
      <v-radio-group
        id="fitToSelect"
        :value="settingsDialogFitTo"
        label="Shrink to"
        @change="settingDialogChanged({ fitTo: $event })"
      >
        <v-radio
          v-for="item in fitToChoices"
          :key="item.value"
          :label="item.text"
          :value="item.value"
        />
      </v-radio-group>
      <v-checkbox
        :value="settingsDialogTwoPages"
        label="Display Two pages"
        :indeterminate="
          settingsDialogTwoPages === null ||
          settingsDialogTwoPages === undefined
        "
        ripple
        @change="settingDialogChanged({ twoPages: $event === true })"
      />
      <v-switch
        v-model="isSettingsDialogGlobalMode"
        :label="settingsDialogSwitchLabel"
      />
    </div>
    <v-list-item
      :class="{ invisible: isSettingsDialogGlobalMode }"
      title="Use the global settings for all comics for this comic"
      @click="settingDialogClear"
      >Use Global Settings</v-list-item
    >
    <v-divider />
    <ReaderKeyboardShortcutsPanel />
  </div>
</template>
//
<script>
import { mapState } from "vuex";

import ReaderKeyboardShortcutsPanel from "@/components/reader-keyboard-shortcuts-panel";

export default {
  name: "ReaderSettingsPanel",
  components: {
    ReaderKeyboardShortcutsPanel,
  },

  data() {
    return {
      isSettingsDialogGlobalMode: false,
    };
  },
  computed: {
    ...mapState("reader", {
      fitToChoices: (state) => state.formChoices.fitTo,
      settingsScope: function (state) {
        if (this.isSettingsDialogGlobalMode) {
          return state.settings.globl;
        }
        return state.settings.local;
      },
    }),
    settingsDialogTwoPages: function () {
      return this.settingsScope.twoPages;
    },
    settingsDialogFitTo: function () {
      return this.settingsScope.fitTo;
    },
    settingsDialogSwitchLabel: function () {
      let label = "For ";
      label += this.isSettingsDialogGlobalMode ? "All Comics" : "This Comic";
      return label;
    },
  },
  methods: {
    settingDialogChanged: function (data) {
      if (this.isSettingsDialogGlobalMode) {
        this.$store.dispatch("reader/settingChangedGlobal", data);
      } else {
        this.$store.dispatch("reader/settingChangedLocal", data);
      }
    },
    settingDialogClear: function () {
      this.$store.dispatch("reader/settingDialogClear");
    },
  },
};
</script>

<style scoped lang="scss">
.invisible {
  visibility: hidden;
}
#readerSettings {
  padding-left: 15px;
}
</style>
