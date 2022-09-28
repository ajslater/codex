<template>
  <div id="readerSettings">
    <h3>Reader Settings</h3>
    <v-radio-group v-model="isGlobalScope" label="Scope">
      <v-radio label="Only this comic" :value="false" />
      <v-radio label="Default for all comics" :value="true" />
    </v-radio-group>
    <v-radio-group
      class="displayRadioGroup"
      label="Display"
      :value="settingsScope.fitTo"
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
      class="displayTwoPages"
      label="Two pages"
      :input-value="settingsScope.twoPages"
      :indeterminate="
        settingsScope.twoPages === null || settingsScope.twoPages === undefined
      "
      ripple
      @change="settingsDialogChanged({ twoPages: $event === true })"
    />
    <v-btn
      id="clearSettingsButton"
      :class="{ invisible: isGlobalScope }"
      :disabled="isClearSettingsButtonDisabled"
      title="Use the default settings for all comics for this comic"
      @click="clearSettingsLocal"
    >
      Clear Comic Settings
    </v-btn>
  </div>
</template>
<script>
import { mapActions, mapState } from "pinia";

import { useReaderStore } from "@/stores/reader";

const ATTRS = ["fitTo", "twoPages"];

export default {
  name: "ReaderSettingsPanel",
  emits: ["panelMounted"],
  data() {
    return {
      isGlobalScope: false,
    };
  },
  computed: {
    ...mapState(useReaderStore, {
      fitToChoices: (state) => state.choices.fitTo,
      settingsScope: function (state) {
        const scope = this.isGlobalScope ? "globl" : "local";
        return state.settings[scope];
      },
      nullValues: (state) => state.nullValues,
      isClearSettingsButtonDisabled: function (state) {
        if (this.isGlobalScope) {
          return true;
        }
        for (const attr of ATTRS) {
          if (!state.nullValues.has(state.settings.local[attr])) {
            return false;
          }
        }
        return true;
      },
    }),
  },
  mounted() {
    window.addEventListener("keyup", this._keyListener);
    this.$emit("panelMounted");
  },
  beforeDestroy: function () {
    window.removeEventListener("keyup", this._keyListener);
  },

  methods: {
    ...mapActions(useReaderStore, [
      "clearSettingsLocal",
      "setSettingsGlobal",
      "setSettingsLocal",
    ]),
    settingsDialogChanged: function (data) {
      if (this.isGlobalScope) {
        this.setSettingsGlobal(data);
      } else {
        this.setSettingsLocal(data);
      }
    },
    _keyListener: function (event) {
      event.stopPropagation();
      switch (event.key) {
        case "w":
          this.setSettingsLocal({ fitTo: "WIDTH" });
          break;

        case "h":
          this.setSettingsLocal({ fitTo: "HEIGHT" });
          break;
        case "s":
          this.setSettingsLocal({ fitTo: "SCREEN" });
          break;

        case "o":
          this.setSettingsLocal({ fitTo: "ORIG" });
          break;

        case "2":
          this.setSettingsLocal({
            twoPages: !this.settingsScope.twoPages,
          });
          break;

        // metadata and close are attached to to title-toolbar
        // No default
      }
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
}
.displayRadioGroup,
.displayTwoPages {
  margin-top: 0px;
}
.displayTwoPages {
  padding-top: 0px;
}
#clearSettingsButton {
  transition: visibility 0.25s, opacity 0.25s;
}
.invisible {
  visibility: hidden;
  opacity: 0;
}
</style>
