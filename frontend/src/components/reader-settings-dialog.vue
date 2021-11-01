<template>
  <v-dialog
    class="readerSettings"
    origin="center top"
    transition="slide-y-transition"
    overlay-opacity="0.5"
    width="fit-content"
  >
    <template #activator="{ on }">
      <v-btn icon v-on="on">
        <v-icon>{{ mdiCog }}</v-icon>
      </v-btn>
    </template>
    <div id="readerSettingsDialog">
      <h2>Reader Settings</h2>
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
        :indeterminate="settingsDialogTwoPages == null"
        ripple
        @change="settingDialogChanged({ twoPages: $event === true })"
      />
      <v-switch
        v-model="isSettingsDialogGlobalMode"
        :label="settingsDialogSwitchLabel"
      />
      <v-btn
        :class="{ invisible: isSettingsDialogGlobalMode }"
        title="Use the global settings for all comics for this comic"
        @click="settingDialogClear()"
        >Clear Settings</v-btn
      >
    </div>
  </v-dialog>
</template>

<script>
import { mdiCog } from "@mdi/js";
import { mapState } from "vuex";

export default {
  data() {
    return {
      mdiCog,
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
      const data = {
        fitTo: null,
        twoPages: null,
      };
      this.$store.dispatch("reader/settingChangedLocal", data);
    },
  },
};
</script>

<style scoped lang="scss">
.invisible {
  visibility: hidden;
}
#readerSettingsDialog {
  padding: 20px;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
.v-dialog {
  /* Seems like I'm fixing a bug here */
  background-color: #121212;
}
</style>
