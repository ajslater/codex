<template>
  <v-toolbar id="topToolbar" class="toolbar" dense>
    <v-btn
      id="closeBook"
      :to="{ name: 'browser', params: browserRoute }"
      large
      ripple
      >close book</v-btn
    >
    <v-spacer />
    <v-toolbar-title id="toolbarTitle">{{ title }}</v-toolbar-title>
    <v-spacer />
    <v-dialog
      class="readerSettings"
      origin="center top"
      transition="slide-y-transition"
      overlay-opacity="0.5"
    >
      <template #activator="{ on }">
        <v-btn icon v-on="on">
          <v-icon>{{ mdiCog }}</v-icon>
        </v-btn>
      </template>
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
    </v-dialog>
    <MetadataDialog ref="metadataDialog" group="c" :pk="pk" />
  </v-toolbar>
</template>

<script>
import { mdiCog } from "@mdi/js";
import { mapState } from "vuex";

import { getFullComicName } from "@/components/comic-name";
import MetadataDialog from "@/components/metadata-dialog";

const DEFAULT_ROUTE = { group: "r", pk: 0, page: 1 };

export default {
  name: "Reader",
  components: {
    MetadataDialog,
  },
  data() {
    return {
      mdiCog,
      isSettingsDialogGlobalMode: false,
    };
  },
  computed: {
    ...mapState("reader", {
      title: function (state) {
        return getFullComicName(
          state.title.seriesName,
          state.title.volumeName,
          state.title.issue,
          state.title.issueCount
        );
      },
      pk: (state) => state.routes.current.pk,
      fitToChoices: (state) => state.formChoices.fitTo,
      settingsScope: function (state) {
        if (this.isSettingsDialogGlobalMode) {
          return state.settings.globl;
        }
        return state.settings.local;
      },
    }),
    ...mapState("browser", {
      browserRoute: (state) => state.routes.current || DEFAULT_ROUTE,
    }),
    settingsDialogTwoPages: function () {
      return this.settingsScope.twoPages;
    },
    settingsDialogFitTo: function () {
      return this.settingsScope.fitTo;
    },
    settingsDialogSwitchLabel: function () {
      let label = "For ";
      if (this.isSettingsDialogGlobalMode) {
        label += "All Comics";
      } else {
        label += "This Comic";
      }
      return label;
    },
  },
  mounted() {
    // Keyboard Shortcuts
    document.addEventListener("keyup", this._keyListener);
  },
  beforeDestroy: function () {
    document.removeEventListener("keyup", this._keyListener);
  },
  methods: {
    _keyListener: function (event) {
      // XXX Hack to get around too many listeners being added.
      event.stopPropagation();

      if (event.key === "Escape") {
        const mdd = this.$refs.metadataDialog;
        if (mdd.isOpen) {
          mdd.isOpen = false;
        } else {
          document.querySelector("#closeBook").click();
        }
      } else if (event.key === "w") {
        this.settingChangedLocal({ fitTo: "WIDTH" });
      } else if (event.key === "h") {
        this.settingChangedLocal({ fitTo: "HEIGHT" });
      } else if (event.key === "o") {
        this.settingChangedLocal({ fitTo: "ORIG" });
      } else if (event.key === "2") {
        this.settingChangedLocal({ twoPages: !this.twoPages });
      }
    },
    settingChangedLocal: function (data) {
      this.$store.dispatch("reader/settingChangedLocal", data);
    },
    settingChangedGlobal: function (data) {
      this.$store.dispatch("reader/settingChangedGlobal", data);
    },
    settingDialogChanged: function (data) {
      if (this.isSettingsDialogGlobalMode) {
        this.settingChangedGlobal(data);
      } else {
        this.settingChangedLocal(data);
      }
    },
    settingDialogClear: function () {
      const data = {
        fitTo: null,
        twoPages: null,
      };
      this.settingChangedLocal(data);
    },
  },
};
</script>

<style scoped lang="scss">
.toolbar {
  width: 100%;
  position: fixed;
}
#topToolbar {
  top: 0px;
}
#toolbarTitle {
  overflow: auto;
  text-overflow: unset;
}
.invisible {
  visibility: hidden;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/require-scoped -->
<style lang="scss">
/* TOOLBARS */
.toolbar .v-toolbar__content {
  padding: 0px;
}
#topToolbar > .v-toolbar__content {
  padding-right: 16px;
}
.v-dialog {
  padding: 20px;
  width: fit-content;
  /* Seems like I'm fixing a bug here */
  background-color: #121212;
}
</style>
<!-- eslint-enable-next-line vue-scoped-css/require-scoped -->
