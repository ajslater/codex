<template>
  <v-footer id="version-footer">
    <a
      id="version"
      href="https://github.com/ajslater/codex/"
      target="_blank"
      title="Codex source code"
    >
      <v-icon id="repoIcon" size="x-small">{{ mdiSourceRepository }}</v-icon>
      codex v{{ versions.installed
      }}<v-icon size="x-small">{{ mdiOpenInNew }}</v-icon></a
    >
    <!--
      In a container codex can't install over itself. Send admins to the
      image registry instead of to a job that would only fail.
    -->
    <a
      v-if="outdated && versions.docker"
      id="latest"
      :href="GHCR_URL"
      target="_blank"
      title="Docker image repo"
      >{{ upgradeText }}<v-icon size="x-small">{{ mdiOpenInNew }}</v-icon></a
    >
    <router-link
      v-else-if="outdated"
      id="latest"
      :to="UPDATE_ROUTE"
      title="Upgrade Codex"
    >
      {{ upgradeText }}
    </router-link>
    <div v-if="versions.warning" id="warning">
      {{ versions.warning }}
    </div>
  </v-footer>
</template>

<script>
import { mdiOpenInNew, mdiSourceRepository } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

// The Codex Software job group, where the Update Codex job lives.
const UPDATE_ROUTE = Object.freeze({
  name: "admin-jobs",
  hash: "#codexSoftware",
});
const GHCR_URL = "https://github.com/ajslater/codex/pkgs/container/codex";

export default {
  name: "VersionFooter",
  data() {
    return {
      mdiOpenInNew,
      mdiSourceRepository,
      GHCR_URL,
      UPDATE_ROUTE,
    };
  },
  computed: {
    ...mapState(useCommonStore, ["versions"]),
    ...mapState(useAuthStore, ["isUserAdmin"]),
    outdated: function () {
      /*
       * The server compares versions. It's the only side that can read
       * a PEP 440 version correctly, and only admins can act on the
       * answer anyway.
       */
      return Boolean(this.isUserAdmin && this.versions.outdated);
    },
    upgradeText: function () {
      return `upgrade to codex v${this.versions.latest}`;
    },
  },
  created() {
    this.loadVersions();
  },
  methods: {
    ...mapActions(useCommonStore, ["loadVersions"]),
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
  display: block;
  color: rgb(var(--v-theme-primary));
}

#latest:hover {
  color: rgb(var(--v-theme-linkHover)) !important;
}

#warning {
  color: rgb(var(--v-theme-warning));
}
</style>
