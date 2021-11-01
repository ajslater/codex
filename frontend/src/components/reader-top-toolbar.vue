<template>
  <v-toolbar class="readerTopToolbar" dense>
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
    <ReaderKeyboardShortcutsDialog v-if="!isMobile()" />
    <ReaderSettingsDialog />
    <MetadataDialog ref="metadataDialog" group="c" :pk="pk" />
  </v-toolbar>
</template>

<script>
import { mapGetters, mapState } from "vuex";

import { getFullComicName } from "@/components/comic-name";
import MetadataDialog from "@/components/metadata-dialog";
import ReaderKeyboardShortcutsDialog from "@/components/reader-keyboard-shortcuts-dialog";
import ReaderSettingsDialog from "@/components/reader-settings-dialog";

const DEFAULT_ROUTE = { group: "r", pk: 0, page: 1 };

export default {
  name: "ReaderTopToolbar",
  components: {
    MetadataDialog,
    ReaderSettingsDialog,
    ReaderKeyboardShortcutsDialog,
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
    }),
    ...mapGetters("reader", ["computedSettings"]),
    ...mapState("browser", {
      browserRoute: (state) => state.routes.current || DEFAULT_ROUTE,
    }),
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

      switch (event.key) {
        case "Escape":
          if (this.$refs.metadataDialog.isOpen) {
            this.$refs.metadataDialog.isOpen = false;
          } else {
            document.querySelector("#closeBook").click();
          }
          break;

        case "w":
          this.settingChangedLocal({ fitTo: "WIDTH" });
          break;

        case "h":
          this.settingChangedLocal({ fitTo: "HEIGHT" });
          break;

        case "o":
          this.settingChangedLocal({ fitTo: "ORIG" });
          break;

        case "2":
          this.settingChangedLocal({
            twoPages: !this.computedSettings.twoPages,
          });
          break;
        // No default
      }
    },
    settingChangedLocal: function (data) {
      this.$store.dispatch("reader/settingChangedLocal", data);
    },
    isMobile: function () {
      // Probably janky mobile detection
      return (
        typeof window.orientation !== "undefined" ||
        navigator.userAgent.includes("IEMobile")
      );
    },
  },
};
</script>

<style scoped lang="scss">
.readerTopToolbar {
  width: 100%;
  position: fixed;
  top: 0px;
}
#toolbarTitle {
  overflow: auto;
  text-overflow: unset;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
/* TOOLBARS */
.readerTopToolbar .v-toolbar__content {
  padding: 0px;
  padding-right: 16px;
}
</style>
