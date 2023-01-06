<template>
  <v-footer id="version-footer" :title="versionTitle">
    <div id="version" :class="{ outdated: outdated }">
      codex v{{ versions.installed }}
    </div>
    <div v-if="outdated">codex v{{ versions.latest }} is available</div>
  </v-footer>
</template>

<script>
import { mdiContentCopy, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
export default {
  name: "VersionFooter",
  data() {
    return {
      mdiOpenInNew,
      opdsURL: window.origin + window.CODEX.OPDS_PATH,
      mdiContentCopy,
      showTool: false,
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      versions: (state) => state.versions,
    }),
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    outdated: function () {
      return this.isUserAdmin && this.versions.latest > this.versions.installed;
    },
    versionTitle: function () {
      return this.outdated
        ? `v${this.versions.latest} is availble`
        : "up to date";
    },
  },
  created() {
    this.loadVersions();
  },
  methods: {
    ...mapActions(useCommonStore, ["loadVersions"]),
    copyToClipboard() {
      navigator.clipboard
        .writeText(this.opdsURL)
        .then(() => {
          this.showTool = true;
          setTimeout(() => {
            this.showTool = false;
          }, 5000);
          return true;
        })
        .catch(console.warn);
    },
  },
};
</script>

<style scoped lang="scss">
#version-footer {
  width: 100%;
  padding-top: 5px;
  padding-bottom: calc(5px + env(safe-area-inset-bottom) / 2);
  text-align: center;
  font-size: small;
  color: rgb(var(--v-theme-textDisabled));
}
#version-footer * {
  margin: auto;
}
.outdated {
  font-style: italic;
}
</style>
