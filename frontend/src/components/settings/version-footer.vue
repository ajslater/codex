<template>
  <v-footer id="version-footer" :title="versionTitle">
    <div id="version">codex v{{ versions.installed }}</div>
    <div v-if="outdated" id="latest">
      codex v{{ versions.latest }} is available
    </div>
  </v-footer>
</template>

<script>
import { mdiContentCopy, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
export default {
  name: "VersionFooter",
  data() {
    return {
      mdiOpenInNew,
      mdiContentCopy,
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      versions: (state) => state.versions,
    }),
    ...mapState(useAuthStore, ["isUserAdmin"]),
    outdated: function () {
      return (
        this.isUserAdmin &&
        this.semverGreaterThan(this.versions.latest > this.versions.installed)
      );
    },
    versionTitle: function () {
      return this.outdated
        ? `v${this.versions.latest} is available`
        : "up to date";
    },
  },
  created() {
    this.loadVersions();
  },
  methods: {
    ...mapActions(useCommonStore, ["loadVersions"]),
    semverGreaterThan(a, b) {
      try {
        if (!a || !b) {
          return false;
        }
        const aParts = a.split(".");
        const bParts = b.split(".");

        for (const [i, aPart] of aParts.entries()) {
          if (+aPart > +bParts[i]) {
            return true;
          }
        }
      } catch (error) {
        console.debug("compare codex versions", a, ">", b, error);
      }
      return false;
    },
  },
};
</script>

<style scoped lang="scss">
#version-footer {
  display: block;
  width: 100%;
  color: rgb(var(--v-theme-textDisabled));
}
#latest {
  color: rgb(var(--v-theme-textSecondary));
}
</style>
