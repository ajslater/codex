<template>
  <v-navigation-drawer
    id="readerSettingsDrawer"
    v-model="isSettingsDrawerOpen"
    app
    right
    temporary
    touchless
  >
    <div v-if="isCodexViewable" id="settingsDrawerContainer">
      <div id="topBlock">
        <div id="readerSettings">
          <h3>Reader Settings</h3>
          <v-radio-group v-model="isSettingsDialogGlobalMode" label="Scope">
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
              settingsScope.twoPages === null ||
              settingsScope.twoPages === undefined
            "
            ripple
            @change="settingsDialogChanged({ twoPages: $event === true })"
          />
          <v-btn
            id="clearSettingsButton"
            :class="{ invisible: isSettingsDialogGlobalMode }"
            :disabled="isClearSettingsButtonDisabled"
            title="Use the default settings for all comics for this comic"
            @click="clearSettingsLocal"
          >
            Clear Comic Settings
          </v-btn>
        </div>
        <v-divider />
        <v-list-item ripple @click="downloadPage">
          <v-list-item-content>
            <v-list-item-title>
              <v-icon>{{ mdiFileImage }}</v-icon> Download Page
              {{ $route.params.page }}
            </v-list-item-title>
          </v-list-item-content>
        </v-list-item>
        <v-divider />
        <ReaderKeyboardShortcutsPanel />
        <SettingsCommonPanel />
      </div>
      <SettingsFooter />
    </div>
    <template #append>
      <VersionFooter />
    </template>
  </v-navigation-drawer>
</template>

<script>
import { mdiFileImage } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { getComicPageSource } from "@/api/v3/reader";
import ReaderKeyboardShortcutsPanel from "@/components/reader/keyboard-shortcuts-panel.vue";
import SettingsCommonPanel from "@/components/settings/panel.vue";
import SettingsFooter from "@/components/settings/settings-footer.vue";
import VersionFooter from "@/components/settings/version-footer.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderSettingsPanel",
  components: {
    ReaderKeyboardShortcutsPanel,
    SettingsCommonPanel,
    SettingsFooter,
    VersionFooter,
  },

  data() {
    return {
      isSettingsDialogGlobalMode: false,
      mdiFileImage,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapGetters(useReaderStore, ["title"]),
    ...mapState(useReaderStore, {
      fitToChoices: (state) => state.choices.fitTo,
      settingsScope: function (state) {
        if (this.isSettingsDialogGlobalMode) {
          return state.settings.globl;
        }
        return state.settings.local;
      },
      nullValues: (state) => state.nullValues,
    }),
    isSettingsDrawerOpen: {
      get() {
        return useReaderStore().isSettingsDrawerOpen;
      },
      set(value) {
        useReaderStore().isSettingsDrawerOpen = value;
      },
    },
    isClearSettingsButtonDisabled: function () {
      return (
        this.isSettingsDialogGlobalMode ||
        (this.nullValues.has(this.settingsScope.fitTo) &&
          this.nullValues.has(this.settingsScope.twoPages))
      );
    },
    pageSrc: function () {
      const routeParams = { ...this.$route.params };
      return getComicPageSource(routeParams, this.timestamp);
    },
    pageName: function () {
      const page = this.$route.params.page;
      return `${this.title} - page ${page}.jpg`;
    },
  },
  mounted() {
    window.addEventListener("keyup", this._keyListener);
    this.$emit("panelMounted");
  },
  beforeDestroy: function () {
    window.removeEventListener("keyup", this._keyListener);
  },
  methods: {
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
    ...mapActions(useReaderStore, [
      "clearSettingsLocal",
      "setSettingsGlobal",
      "setSettingsLocal",
    ]),
    settingsDialogChanged: function (data) {
      if (this.isSettingsDialogGlobalMode) {
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

    downloadPage() {
      this.downloadIOSPWAFix(this.pageSrc, this.pageName);
    },
  },
};
</script>

<style scoped lang="scss">
#readerSettingsDrawer {
  z-index: 20;
}
@import "../settings/settings-drawer.scss";
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
