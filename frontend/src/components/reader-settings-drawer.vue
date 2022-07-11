<template>
  <v-navigation-drawer
    id="readerSettingsDrawer"
    v-model="isSettingsDrawerOpen"
    app
    right
    temporary
  >
    <div v-if="isOpenToSee">
      <div id="readerSettings">
        <h3>Reader Settings</h3>
        <v-radio-group v-model="isSettingsDialogGlobalMode" label="Scope">
          <v-radio label="Only this comic" :value="false" />
          <v-radio label="Default for all comics" :value="true" />
        </v-radio-group>
        <v-radio-group
          :value="settingsDialogFitTo"
          label="Display"
          @change="settingsDialogChanged({ fitTo: $event })"
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
          label="Show Two pages"
          :indeterminate="
            settingsDialogTwoPages === null ||
            settingsDialogTwoPages === undefined
          "
          ripple
          @change="settingsDialogChanged({ twoPages: $event === true })"
        />
        <v-btn
          :disabled="isSettingsDialogGlobalMode"
          title="Use the default settings for all comics for this comic"
          @click="settingsDialogClear"
        >
          Clear Comic Settings
        </v-btn>
      </div>
      <v-divider />
      <ReaderKeyboardShortcutsPanel />
    </div>
    <SettingsCommonPanel />
  </v-navigation-drawer>
</template>

<script>
import { mapActions, mapGetters, mapMutations, mapState } from "vuex";

import ReaderKeyboardShortcutsPanel from "@/components/reader-keyboard-shortcuts-panel";
import SettingsCommonPanel from "@/components/settings-common-panel";

export default {
  name: "ReaderSettingsPanel",
  components: {
    ReaderKeyboardShortcutsPanel,
    SettingsCommonPanel,
  },

  data() {
    return {
      isSettingsDialogGlobalMode: false,
    };
  },
  computed: {
    ...mapGetters("auth", ["isOpenToSee"]),
    ...mapState("reader", {
      fitToChoices: (state) => state.formChoices.fitTo,
      settingsScope: function (state) {
        if (this.isSettingsDialogGlobalMode) {
          return state.settings.globl;
        }
        return state.settings.local;
      },
    }),
    isSettingsDrawerOpen: {
      get() {
        return this.$store.state.reader.isSettingsDrawerOpen;
      },
      set(value) {
        this.setIsSettingsDrawerOpen(value);
      },
    },
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
  mounted() {
    this.$emit("panelMounted");
  },
  methods: {
    ...mapActions("reader", [
      "settingsChangedGlobal",
      "settingsChangedLocal",
      "settingsDialogClear",
    ]),
    ...mapMutations("reader", ["setIsSettingsDrawerOpen"]),
    settingsDialogChanged: function (data) {
      if (this.isSettingsDialogGlobalMode) {
        this.settingsChangedGlobal(data);
      } else {
        this.settingsChangedLocal(data);
      }
    },
  },
};
</script>

<style scoped lang="scss">
#readerSettingsDrawer {
  background-color: #121212;
  z-index: 20;
}
#readerSettings {
  padding-top: 10px;
  padding-left: 15px;
  padding-right: env(safe-area-inset-right);
}
</style>
