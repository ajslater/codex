<template>
  <v-footer id="settingsFooter">
    <OPDSDialog v-if="isCodexViewable" />
    <a
      id="repo"
      href="https://github.com/ajslater/codex"
      title="Codex Source Repository"
      target="_blank"
    >
      <v-icon id="repoIcon" size="x-small">{{ mdiSourceRepository }}</v-icon>
      repository<v-icon
        :color="$vuetify.theme.current.colors.iconsInactive"
        size="x-small"
        >{{ mdiOpenInNew }}</v-icon
      >
    </a>
  </v-footer>
</template>

<script>
import { mdiOpenInNew, mdiSourceRepository } from "@mdi/js";
import { mapGetters } from "pinia";

import OPDSDialog from "@/components/settings/opds-dialog.vue";
import { useAuthStore } from "@/stores/auth";

export default {
  name: "SettingsFooter",
  components: {
    OPDSDialog,
  },
  data() {
    return {
      mdiOpenInNew,
      mdiSourceRepository,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
  },
};
</script>

<style scoped lang="scss">
#settingsFooter {
  width: 100%;
  display: block;
  padding-top: 5px;
  margin-top: auto;
  text-align: center;
  font-size: small;
  color: rgb(var(--v-theme-textDisabled));
}
#repo {
  display: block;
  color: rgb(var(--v-theme-textDisabled));
}
#repo:hover {
  color: rgb(var(--v-theme-textPrimary));
}
#repoIcon {
  margin-right: 0px;
}
:deep(#repo:hover .v-icon) {
  color: rgb(var(--v-theme-textPrimary)) !important;
}
</style>
