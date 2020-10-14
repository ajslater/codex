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
    <ReaderSettingsDialog />
    <MetadataDialog ref="metadataDialog" group="c" :pk="pk" />
  </v-toolbar>
</template>

<script>
import { mapState } from "vuex";

import { getFullComicName } from "@/components/comic-name";
import MetadataDialog from "@/components/metadata-dialog";
import ReaderSettingsDialog from "@/components/reader-settings-dialog";

const DEFAULT_ROUTE = { group: "r", pk: 0, page: 1 };

export default {
  name: "Reader",
  components: {
    MetadataDialog,
    ReaderSettingsDialog,
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

<!-- eslint-disable-next-line vue-scoped-css/require-scoped -->
<style lang="scss">
/* TOOLBARS */
.readerTopToolbar .v-toolbar__content {
  padding: 0px;
  padding-right: 16px;
}
</style>
