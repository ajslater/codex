<template>
  <v-footer id="version-footer" :title="versionTitle">
    <a id="version" href="https://github.com/ajslater/codex/">
      <v-icon id="repoIcon" size="x-small">{{ mdiSourceRepository }}</v-icon>
      codex v{{ versions.installed
      }}<v-icon size="x-small">{{ mdiOpenInNew }}</v-icon></a
    >
    <div v-if="outdated" id="latest">
      codex v{{ versions.latest }} is available
    </div>
  </v-footer>
</template>

<script>
import { mdiOpenInNew, mdiSourceRepository } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";
export default {
  name: "VersionFooter",
  data() {
    return {
      mdiOpenInNew,
      mdiSourceRepository,
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

#version {
  display: block;
  color: rgb(var(--v-theme-textDisabled));
}

#version:hover {
  color: rgb(var(--v-theme-textPrimary)) !important;
}

#repoIcon {
  margin-right: 0px;
}

#latest {
  color: rgb(var(--v-theme-textSecondary));
}
</style>
